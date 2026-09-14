"""ASS(Advanced SubStation Alpha) 자막 생성.

ffmpeg의 drawtext 대신 libass를 쓰는 이유:
  · 한글 줄바꿈·자간이 정확하고, 볼드/외곽선/그림자/반투명 박스를 제대로 지원
  · \fad(페이드), \move(슬라이드 인), \t(스케일 팝) 같은 동적 애니메이션 가능
  · 단어 단위 색상 강조(하이라이트)를 태그 한 줄로 처리
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def hex_to_ass(color: str, alpha: int = 0) -> str:
    """#RRGGBB → &HAABBGGRR&  (ASS는 BGR 순서, 알파는 00이 불투명)"""
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper() + "&"


def ts(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def esc(text: str) -> str:
    """ASS 특수문자 이스케이프 + 줄바꿈 변환. 원문 내용은 바꾸지 않는다."""
    return (text.replace("\\", "∖").replace("{", "\\{").replace("}", "\\}")
                .replace("\n", "\\N"))


def emphasize(text: str, words: list[str], accent: str) -> str:
    """지정 단어만 볼드 + 강조색. 원문 문구는 그대로 두고 태그만 감싼다."""
    out = esc(text)
    color = hex_to_ass(accent)
    for w in sorted([w for w in words if w], key=len, reverse=True):
        tok = esc(w)
        if tok and tok in out:
            out = out.replace(tok, f"{{\\b1\\c{color}}}{tok}{{\\r}}")
    return out


@dataclass
class Event:
    start: float
    end: float
    style: str
    text: str
    override: str = ""

    def line(self) -> str:
        return f"Dialogue: 0,{ts(self.start)},{ts(self.end)},{self.style},,0,0,0,,{self.override}{self.text}"


class AssBuilder:
    def __init__(self, cfg: dict):
        v = cfg.get("video", {})
        st = cfg.get("style", {})
        self.w = int(v.get("width", 1920))
        self.h = int(v.get("height", 1080))
        self.font = st.get("font") or "NanumSquare"
        self.accent = st.get("accent", "#FFD24A")
        self.text_color = st.get("text_color", "#FFFFFF")
        self.scale = self.h / 1080.0
        self.events: list[Event] = []

    def _sz(self, base: int) -> int:
        return max(int(round(base * self.scale)), 10)

    # ---------- 스타일 정의 ----------
    def _styles(self) -> list[str]:
        white = hex_to_ass(self.text_color)
        accent = hex_to_ass(self.accent)
        black = hex_to_ass("#000000")
        shadow = hex_to_ass("#000000", alpha=0x60)
        box = hex_to_ass("#0B0B10", alpha=0x50)
        f = self.font

        def row(name, size, primary, outline, back, bold, border_style, outline_w, shadow_w, align, ml, mr, mv):
            return (f"Style: {name},{f},{size},{primary},{accent},{outline},{back},"
                    f"{bold},0,0,0,100,100,0,0,{border_style},{outline_w},{shadow_w},{align},{ml},{mr},{mv},1")

        m = int(90 * self.scale)
        return [
            # 대형 타이틀 (인트로/아웃트로)
            row("Title", self._sz(96), white, black, shadow, -1, 1, 4, 3, 5, m, m, 0),
            row("TitleSub", self._sz(40), accent, black, shadow, 0, 1, 3, 2, 5, m, m, 0),
            # 하단 자막 (작품명 + 설명)
            row("Caption", self._sz(52), white, black, box, -1, 1, 4, 3, 2, m, m, int(150 * self.scale)),
            row("CaptionSub", self._sz(34), white, black, box, 0, 1, 3, 2, 2, m, m, int(100 * self.scale)),
            # 섹션 구분 타이틀
            row("Section", self._sz(72), accent, black, shadow, -1, 1, 4, 3, 5, m, m, 0),
            # 좌상단 카운터 뱃지
            row("Badge", self._sz(28), accent, black, shadow, -1, 1, 3, 2, 7, int(60 * self.scale), m, int(50 * self.scale)),
        ]

    # ---------- 이벤트 추가 ----------
    def title_card(self, start: float, end: float, title: str, subtitle: str | None = None):
        """중앙 대형 타이틀: 확대 팝 + 페이드 인/아웃."""
        pad = 0.35
        self.events.append(Event(
            start, end, "Title", esc(title),
            override=(f"{{\\an5\\pos({self.w // 2},{int(self.h * 0.44)})"
                      f"\\fad(600,500)\\fscx84\\fscy84\\t(0,650,\\fscx100\\fscy100)"
                      f"\\blur0.6}}"),
        ))
        if subtitle:
            self.events.append(Event(
                start + pad, end, "TitleSub", esc(subtitle),
                override=(f"{{\\an5\\pos({self.w // 2},{int(self.h * 0.56)})\\fad(500,400)"
                          f"\\move({self.w // 2},{int(self.h * 0.59)},{self.w // 2},{int(self.h * 0.56)},0,600)}}"),
            ))

    def section_card(self, start: float, end: float, text: str):
        self.events.append(Event(
            start, end, "Section", esc(text),
            override=(f"{{\\an5\\pos({self.w // 2},{self.h // 2})\\fad(450,450)"
                      f"\\fscx88\\fscy88\\t(0,550,\\fscx100\\fscy100)}}"),
        ))

    def caption(self, start: float, end: float, title: str | None,
                sub: str | None, emphasis: list[str] | None = None):
        """하단 자막: 아래에서 위로 슬라이드 인 + 페이드, 키워드 강조."""
        emphasis = emphasis or []
        y_title = int(self.h * 0.845)
        y_sub = int(self.h * 0.915)
        if title:
            self.events.append(Event(
                start, end, "Caption", emphasize(title, emphasis, self.accent),
                override=(f"{{\\an2\\fad(350,350)"
                          f"\\move({self.w // 2},{y_title + int(46 * self.scale)},{self.w // 2},{y_title},0,420)}}"),
            ))
        if sub:
            self.events.append(Event(
                start + 0.15, end, "CaptionSub", emphasize(sub, emphasis, self.accent),
                override=(f"{{\\an2\\fad(320,320)"
                          f"\\move({self.w // 2},{y_sub + int(34 * self.scale)},{self.w // 2},{y_sub},0,420)}}"),
            ))

    def badge(self, start: float, end: float, text: str):
        self.events.append(Event(start, end, "Badge", esc(text),
                                 override="{\\an7\\fad(250,250)\\alpha&H30&}"))

    # ---------- 출력 ----------
    def write(self, path: Path) -> Path:
        header = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: TV.709",
            f"PlayResX: {self.w}",
            f"PlayResY: {self.h}",
            "",
            "[V4+ Styles]",
            ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
             "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
             "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"),
            *self._styles(),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        body = [e.line() for e in sorted(self.events, key=lambda e: e.start)]
        path.write_text("\n".join(header + body) + "\n", encoding="utf-8")
        return path
