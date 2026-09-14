"""실행 환경 탐색: ffmpeg 바이너리, 한글 폰트, 명령 실행 헬퍼."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 한글 자막에 쓸 폰트 우선순위 (fontconfig family 이름)
KOREAN_FONT_CANDIDATES = [
    "NanumSquare",
    "NanumSquareRound",
    "NanumBarunGothic",
    "NanumGothic",
    "Noto Sans CJK KR",
    "Noto Sans KR",
    "Malgun Gothic",
    "AppleSDGothicNeo",
]


def find_ffmpeg() -> str:
    """시스템 ffmpeg → imageio-ffmpeg 정적 바이너리 순으로 탐색."""
    env = os.environ.get("FFMPEG_BIN")
    if env and Path(env).exists():
        return env
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - 환경 의존
        raise RuntimeError(
            "ffmpeg를 찾지 못했습니다. `pip install imageio-ffmpeg` 또는 "
            "시스템에 ffmpeg를 설치하세요."
        ) from exc


def find_ffprobe() -> str | None:
    """ffprobe는 없을 수 있음. 없으면 ffmpeg 출력 파싱으로 대체한다."""
    env = os.environ.get("FFPROBE_BIN")
    if env and Path(env).exists():
        return env
    return shutil.which("ffprobe")


def available_korean_font() -> str:
    """fc-list로 설치된 한글 폰트 family를 고른다. 없으면 sans-serif."""
    try:
        out = subprocess.run(
            ["fc-list", ":lang=ko", "family"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        out = ""
    installed = out.replace("\n", ",")
    for family in KOREAN_FONT_CANDIDATES:
        if family.lower() in installed.lower():
            return family
    return "sans-serif"


def run(cmd: list[str], *, quiet: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """ffmpeg 실행 헬퍼. 실패하면 stderr 끝부분을 보여 준다."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise RuntimeError(f"명령 실패 (exit {proc.returncode})\n$ {' '.join(cmd[:6])} ...\n{tail}")
    if not quiet:
        sys.stderr.write(proc.stderr)
    return proc


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")


def probe_duration(ffmpeg: str, path: str | Path) -> float:
    """ffprobe가 없어도 동작하도록 ffmpeg 출력에서 Duration을 파싱한다."""
    ffprobe = find_ffprobe()
    if ffprobe:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True,
        )
        try:
            return float(proc.stdout.strip())
        except ValueError:
            pass
    proc = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                          capture_output=True, text=True)
    m = _DURATION_RE.search(proc.stderr)
    if not m:
        raise RuntimeError(f"재생 길이를 읽지 못했습니다: {path}")
    h, mnt, sec = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(sec)
