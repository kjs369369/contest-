"""xfade 전환을 '계층 병합'으로 처리 — 사진 수백 장에서도 안 터지게.

한 번의 filter_complex에 클립 수백 개를 넣으면 ffmpeg가 메모리/필터그래프 한계로
실패한다. 그래서 K개씩 묶어 중간 파일로 합치고(1단계), 그 결과들을 다시 합치는
방식(2·3단계)으로 처리한다. 전체 길이와 각 클립의 타임라인 시작 시각은
순차 합성과 수학적으로 동일하다:  start_i = Σd(0..i-1) − i × T
"""
from __future__ import annotations

import math
from pathlib import Path

from .env import run
from .clips import Segment

# 전시 영상에 어울리는 전환 — 과하지 않게 화려한 순서로 배치
TRANSITION_CYCLE = [
    "fade", "smoothleft", "circleopen", "wipeup", "dissolve",
    "slideright", "zoomin", "radial", "smoothup", "diagtr",
    "hlslice", "fadeblack", "squeezev", "coverleft", "pixelize",
    "revealright", "vertopen", "hblur", "wipebl", "fadefast",
]


def timeline_starts(durations: list[float], transition: float) -> list[float]:
    """각 세그먼트가 최종 영상에서 시작하는 시각(초)."""
    starts, acc = [], 0.0
    for i, d in enumerate(durations):
        starts.append(acc - i * transition)
        acc += d
    return starts


def total_duration(durations: list[float], transition: float) -> float:
    if not durations:
        return 0.0
    return sum(durations) - (len(durations) - 1) * transition


def _merge_chunk(ffmpeg: str, segs: list[Segment], out: Path, transition: float,
                 cfg: dict, trans_start_index: int) -> Segment:
    if len(segs) == 1:
        return segs[0]
    v = cfg.get("video", {})
    fps = int(v.get("fps", 30))
    crf = max(int(v.get("crf", 18)) - 3, 12)   # 중간 파일은 더 좋은 화질로 (세대 손실 방지)

    inputs: list[str] = []
    for s in segs:
        inputs += ["-i", str(s.path)]

    parts, acc, label = [], segs[0].duration, "0:v"
    for i in range(1, len(segs)):
        t = min(transition, segs[i].duration * 0.9, acc * 0.9)
        offset = max(acc - t, 0.0)
        name = TRANSITION_CYCLE[(trans_start_index + i - 1) % len(TRANSITION_CYCLE)]
        nxt = f"x{i}"
        parts.append(
            f"[{label}][{i}:v]xfade=transition={name}:duration={t:.3f}:offset={offset:.3f}[{nxt}]"
        )
        label = nxt
        acc = acc + segs[i].duration - t

    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join(parts), "-map", f"[{label}]",
         "-r", str(fps), "-an",
         "-c:v", "libx264", "-preset", str(v.get("preset", "medium")), "-crf", str(crf),
         "-pix_fmt", "yuv420p", str(out)])
    return Segment(path=out, duration=acc, source=segs[0].source)


def auto_chunk_size(n: int) -> int:
    """병합 단계 수를 2단계 이하로 유지하는 청크 크기.

    √n 으로 잡으면 n개 → √n개 → 1개, 즉 재인코딩 세대가 2회로 끝난다.
    (8개 고정이면 n=400일 때 3단계가 되어 화질 손실이 한 세대 더 쌓인다.)
    """
    return max(8, min(24, int(math.ceil(math.sqrt(max(n, 1))))))


def merge_all(ffmpeg: str, segments: list[Segment], workdir: Path, cfg: dict,
              chunk_size: int = 0, on_progress=None) -> Segment:
    """전 세그먼트를 전환효과로 이어 붙인 하나의 무음 영상으로 만든다."""
    if not segments:
        raise ValueError("합칠 세그먼트가 없습니다.")
    if not chunk_size:
        chunk_size = auto_chunk_size(len(segments))
    transition = float(cfg.get("timing", {}).get("transition", 0.7))
    level, current = 0, list(segments)
    global_idx = 0

    while len(current) > 1:
        level += 1
        merged: list[Segment] = []
        for c, start in enumerate(range(0, len(current), chunk_size)):
            chunk = current[start:start + chunk_size]
            out = workdir / f"merge_L{level}_{c:04d}.mp4"
            merged.append(_merge_chunk(ffmpeg, chunk, out, transition, cfg, global_idx))
            global_idx += max(len(chunk) - 1, 0)
            if on_progress:
                on_progress(level, c + 1, (len(current) + chunk_size - 1) // chunk_size)
        current = merged
    return current[0]
