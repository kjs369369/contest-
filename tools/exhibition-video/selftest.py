#!/usr/bin/env python3
"""ffmpeg 없이 돌아가는 논리 검증 테스트.

  python3 selftest.py
모든 항목이 OK면 타임라인 계산·자막 생성·설정 병합이 깨지지 않은 것입니다.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib.subtitles import AssBuilder, emphasize, esc, hex_to_ass, ts  # noqa: E402
from lib.transitions import auto_chunk_size, timeline_starts, total_duration  # noqa: E402

FAILED: list[str] = []


def check(name: str, got, want) -> None:
    if got == want:
        print(f"  OK   {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL {name}\n       got  = {got!r}\n       want = {want!r}")


def approx(name: str, got: float, want: float, tol: float = 1e-6) -> None:
    check(name, abs(got - want) < tol, True) if abs(got - want) >= tol else print(f"  OK   {name}")


print("1) 타임라인 계산")
d = [3.6] * 5
T = 0.7
approx("총 길이 = Σd − (n−1)T", total_duration(d, T), sum(d) - 4 * T)
check("시작 시각", [round(x, 2) for x in timeline_starts(d, T)], [0.0, 2.9, 5.8, 8.7, 11.6])
approx("마지막 클립 끝 == 총 길이", timeline_starts(d, T)[-1] + d[-1], total_duration(d, T))

# 길이가 제각각이어도 성립해야 한다
d2 = [4.0, 2.5, 6.0, 3.1]
approx("가변 길이 총합", total_duration(d2, T), sum(d2) - 3 * T)
approx("가변 길이 끝점", timeline_starts(d2, T)[-1] + d2[-1], total_duration(d2, T))
check("클립 1개일 때", total_duration([5.0], T), 5.0)
check("빈 목록", total_duration([], T), 0.0)

print("2) 계층 병합 청크 크기 (병합 단계 2회 이하 유지)")
for n in (14, 50, 120, 204, 400, 576):
    k = auto_chunk_size(n)
    levels, cur = 0, n
    while cur > 1:
        levels += 1
        cur = (cur + k - 1) // k
    check(f"n={n} chunk={k} → {levels}단계", levels <= 2, True)

print("3) 자막(ASS) 생성")
check("색상 변환 #FFD24A → BGR", hex_to_ass("#FFD24A"), "&H004AD2FF&")
check("색상 3자리 축약", hex_to_ass("#FA0"), "&H0000AAFF&")
check("타임코드", ts(3725.5), "1:02:05.50")
check("타임코드 음수 보정", ts(-3), "0:00:00.00")
check("중괄호 이스케이프", esc("a{b}c"), "a\\{b\\}c")
check("줄바꿈 변환", esc("1줄\n2줄"), "1줄\\N2줄")
check("강조 태그", emphasize("빛의 결 No.1", ["빛의 결"], "#FFD24A"),
      "{\\b1\\c&H004AD2FF&}빛의 결{\\r} No.1")
check("강조 단어 없으면 원문 유지", emphasize("작품명", [], "#FFD24A"), "작품명")

cfg = {"video": {"width": 1920, "height": 1080},
       "style": {"font": "NanumSquare", "accent": "#FFD24A"}}
b = AssBuilder(cfg)
b.title_card(0, 4, "제목", "부제")
b.caption(4, 8, "작품 01", "설명", ["작품"])
b.badge(4, 8, "01 / 12")
with tempfile.TemporaryDirectory() as tmp:
    out = b.write(Path(tmp) / "t.ass")
    text = out.read_text(encoding="utf-8")
check("PlayRes가 영상 크기와 일치", "PlayResX: 1920" in text and "PlayResY: 1080" in text, True)
check("스타일 6종 정의", text.count("\nStyle: "), 6)
check("이벤트 5줄", text.count("\nDialogue: "), 5)
check("이벤트가 시간순 정렬", text.index("0:00:00.00") < text.index("0:00:04.15"), True)

print("4) 세로형(숏폼) 해상도에서도 좌표가 따라가는지")
b2 = AssBuilder({"video": {"width": 1080, "height": 1920},
                 "style": {"font": "NanumSquare", "accent": "#FFD24A"}})
with tempfile.TemporaryDirectory() as tmp:
    text2 = b2.write(Path(tmp) / "v.ass").read_text(encoding="utf-8")
check("세로 PlayRes", "PlayResX: 1080" in text2 and "PlayResY: 1920" in text2, True)
check("폰트 크기 스케일링", b2._sz(52) > b._sz(52), True)

print("5) 설정 병합")
sys.path.insert(0, str(ROOT))
from build_video import DEFAULTS, deep_merge  # noqa: E402

merged = deep_merge(DEFAULTS, {"video": {"crf": 22}, "project": {"title": "새 제목"}})
check("중첩 키만 덮어씀", merged["video"]["crf"], 22)
check("같은 묶음의 다른 키는 유지", merged["video"]["width"], DEFAULTS["video"]["width"])
check("원본 DEFAULTS 불변", DEFAULTS["video"]["crf"], 18)
check("다른 묶음 유지", merged["timing"], DEFAULTS["timing"])

print()
if FAILED:
    print(f"실패 {len(FAILED)}건: {', '.join(FAILED)}")
    sys.exit(1)
print("모든 검증 통과")
