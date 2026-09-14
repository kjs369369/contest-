"""개별 사진·영상 → 규격이 통일된 세그먼트 클립으로 렌더링.

사진: Ken Burns(줌·팬) + 컬러 그레이딩 + 비네트 + (옵션)필름 그레인
영상: 스케일·크롭·fps 통일 + 동일한 그레이딩
모든 세그먼트는 같은 해상도/fps/픽셀포맷/타임베이스를 가지므로
이후 xfade 전환과 concat이 안전하게 동작한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .env import probe_duration, run
from .media import MediaItem

# Ken Burns 모션 프리셋 — 순서대로 돌려 쓰며 단조로움을 피한다.
STILL_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"}

MOTIONS = ["zoom_in", "pan_right", "zoom_out", "pan_up", "pan_left", "zoom_in_tl", "pan_down", "zoom_out_br"]

GRADES = {
    "neutral": "eq=contrast=1.03:saturation=1.05:brightness=0.005",
    "warm":    "eq=contrast=1.07:saturation=1.14:brightness=0.012,colorbalance=rs=.04:gs=.01:bs=-.04",
    "cool":    "eq=contrast=1.07:saturation=1.10:brightness=0.008,colorbalance=rs=-.04:gs=.00:bs=.05",
    "gallery": "eq=contrast=1.10:saturation=1.18:brightness=0.010,unsharp=5:5:0.6:5:5:0.0",
    "cinema":  "eq=contrast=1.14:saturation=0.96:brightness=-0.005,curves=preset=medium_contrast,colorbalance=rs=-.03:bs=.05",
}


@dataclass
class Segment:
    path: Path
    duration: float
    source: MediaItem
    start_on_timeline: float = 0.0
    has_audio: bool = False


def _kenburns(motion: str, frames: int, zoom: float, out_w: int, out_h: int, fps: int) -> str:
    """zoompan 필터 문자열 생성. 입력은 출력의 2배 크기로 미리 확대해 둔다."""
    n = max(frames - 1, 1)
    p = f"on/{n}"                      # 0 → 1 진행도
    cx, cy = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    z_static = f"{zoom:.4f}"
    if motion == "zoom_in":
        z, x, y = f"1+{zoom - 1:.4f}*{p}", cx, cy
    elif motion == "zoom_out":
        z, x, y = f"{zoom:.4f}-{zoom - 1:.4f}*{p}", cx, cy
    elif motion == "zoom_in_tl":
        z, x, y = f"1+{zoom - 1:.4f}*{p}", f"(iw-iw/zoom)*{p}*0.6", f"(ih-ih/zoom)*{p}*0.6"
    elif motion == "zoom_out_br":
        z = f"{zoom:.4f}-{zoom - 1:.4f}*{p}"
        x, y = f"(iw-iw/zoom)*(1-{p}*0.6)", f"(ih-ih/zoom)*(1-{p}*0.6)"
    elif motion == "pan_right":
        z, x, y = z_static, f"(iw-iw/zoom)*{p}", cy
    elif motion == "pan_left":
        z, x, y = z_static, f"(iw-iw/zoom)*(1-{p})", cy
    elif motion == "pan_down":
        z, x, y = z_static, cx, f"(ih-ih/zoom)*{p}"
    elif motion == "pan_up":
        z, x, y = z_static, cx, f"(ih-ih/zoom)*(1-{p})"
    else:
        z, x, y = "1", cx, cy
    return (f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={out_w}x{out_h}:fps={fps}")


def _fx_suffix(cfg: dict) -> str:
    style = cfg.get("style", {})
    chain = [GRADES.get(style.get("grade", "gallery"), GRADES["gallery"])]
    if style.get("vignette", True):
        chain.append("vignette=PI/5")
    grain = float(style.get("grain", 0) or 0)
    if grain > 0:
        chain.append(f"noise=alls={int(grain)}:allf=t+u")
    chain.append("setsar=1")
    chain.append("format=yuv420p")
    return ",".join(chain)


def _encode_args(cfg: dict) -> list[str]:
    v = cfg.get("video", {})
    return [
        "-c:v", "libx264",
        "-preset", str(v.get("preset", "medium")),
        "-crf", str(v.get("crf", 18)),
        "-pix_fmt", "yuv420p",
        "-x264-params", "keyint=30:min-keyint=15:scenecut=0",
        "-movflags", "+faststart",
    ]


def render_photo(ffmpeg: str, item: MediaItem, out: Path, cfg: dict, motion: str) -> Segment:
    v = cfg.get("video", {})
    w, h, fps = int(v.get("width", 1920)), int(v.get("height", 1080)), int(v.get("fps", 30))
    dur = float(cfg.get("timing", {}).get("still_duration", 3.6))
    zoom = float(cfg.get("style", {}).get("zoom", 1.16))
    frames = max(int(round(dur * fps)), 2)

    vf = ",".join([
        f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={w * 2}:{h * 2}",
        _kenburns(motion, frames, zoom, w, h, fps),
        _fx_suffix(cfg),
    ])
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-i", str(item.path),
         "-vf", vf, "-frames:v", str(frames), "-r", str(fps),
         "-an", *_encode_args(cfg), str(out)])
    return Segment(path=out, duration=frames / fps, source=item)


def render_video(ffmpeg: str, item: MediaItem, out: Path, cfg: dict) -> Segment:
    v = cfg.get("video", {})
    w, h, fps = int(v.get("width", 1920)), int(v.get("height", 1080)), int(v.get("fps", 30))
    timing = cfg.get("timing", {})
    keep_audio = bool(cfg.get("audio", {}).get("keep_clip_audio", False))

    src_dur = item.duration or probe_duration(ffmpeg, item.path)
    item.duration = src_dur
    take = min(src_dur, float(timing.get("video_max", 8.0)))
    skip = float(timing.get("video_skip_head", 0.0))
    if skip and src_dur - skip >= take:
        start = skip
    else:
        start = 0.0
    take = max(min(take, src_dur - start), 0.5)

    vf = ",".join([
        f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={w}:{h}",
        f"fps={fps}",
        _fx_suffix(cfg),
    ])
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-t", f"{take:.3f}", "-i", str(item.path),
           "-vf", vf, "-r", str(fps)]
    has_audio = False
    if keep_audio:
        probe = run([ffmpeg, "-hide_banner", "-i", str(item.path)], check=False)
        has_audio = "Audio:" in probe.stderr
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    else:
        cmd += ["-an"]
    cmd += [*_encode_args(cfg), str(out)]
    run(cmd)
    return Segment(path=out, duration=take, source=item, has_audio=has_audio)


def render_card(ffmpeg: str, out: Path, cfg: dict, duration: float,
                background: Path | None = None, blur: int = 28) -> Segment:
    """타이틀/섹션/아웃트로 카드의 '배경'만 만든다. 글자는 ASS 자막으로 얹는다."""
    v = cfg.get("video", {})
    w, h, fps = int(v.get("width", 1920)), int(v.get("height", 1080)), int(v.get("fps", 30))
    frames = max(int(round(duration * fps)), 2)
    bg_color = cfg.get("style", {}).get("card_color", "#0E0E12")

    bg = Path(background) if background else None
    if bg and bg.exists():
        is_still = bg.suffix.lower() in STILL_EXT
        chain = [
            f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase:flags=lanczos",
            f"crop={w * 2}:{h * 2}",
        ]
        if is_still:
            # 스틸 배경은 느린 줌으로 살짝 움직여 준다
            chain.append(_kenburns("zoom_in", frames, 1.10, w, h, fps))
        else:
            chain.append(f"scale={w}:{h}:flags=lanczos")
            chain.append(f"fps={fps}")
        chain += [
            f"gblur=sigma={blur}",
            "eq=brightness=-0.18:saturation=0.85",
            "vignette=PI/4", "setsar=1", "format=yuv420p",
        ]
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        if is_still:
            cmd += ["-loop", "1", "-i", str(bg)]
        else:
            # 영상 배경은 필요한 길이만큼 잘라 쓰고, 모자라면 마지막 프레임을 늘린다
            cmd += ["-stream_loop", "-1", "-t", f"{duration:.3f}", "-i", str(bg)]
        cmd += ["-vf", ",".join(chain), "-frames:v", str(frames), "-r", str(fps),
                "-an", *_encode_args(cfg), str(out)]
        run(cmd)
    else:
        run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", f"color=c={bg_color}:s={w}x{h}:r={fps}:d={duration:.3f}",
             "-vf", "format=yuv420p", "-frames:v", str(frames),
             "-an", *_encode_args(cfg), str(out)])
    item = MediaItem(path=out, kind="photo")
    return Segment(path=out, duration=frames / fps, source=item)
