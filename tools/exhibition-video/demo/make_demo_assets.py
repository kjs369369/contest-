#!/usr/bin/env python3
"""데모용 샘플 소재 생성 — 실제 전시 사진 대신 추상 캔버스 이미지를 합성한다.

실제 사용 시에는 이 스크립트를 돌릴 필요 없이 media/photos 에 사진을,
media/videos 에 영상을 넣으면 된다.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib.env import find_ffmpeg, run  # noqa: E402

PALETTES = [
    [(28, 42, 74), (74, 132, 180), (232, 214, 178), (196, 92, 60)],
    [(18, 18, 24), (196, 168, 92), (238, 238, 232), (120, 96, 72)],
    [(42, 66, 54), (146, 186, 138), (240, 236, 220), (206, 132, 78)],
    [(58, 26, 46), (188, 84, 112), (244, 226, 214), (96, 122, 168)],
    [(20, 52, 68), (66, 150, 152), (236, 226, 200), (222, 148, 84)],
]


def canvas_texture(w: int, h: int, rng: random.Random) -> Image.Image:
    arr = np.random.default_rng(rng.randrange(1 << 30)).normal(0, 7, (h, w, 3))
    weave = (np.sin(np.arange(w) * 1.6)[None, :, None] +
             np.sin(np.arange(h) * 1.6)[:, None, None]) * 3.0
    return Image.fromarray(np.clip(128 + arr + weave, 0, 255).astype("uint8"))


def make_painting(path: Path, seed: int, w: int = 2400, h: int = 1800) -> Path:
    rng = random.Random(seed)
    palette = PALETTES[seed % len(PALETTES)]
    img = Image.new("RGB", (w, h), palette[2])
    draw = ImageDraw.Draw(img, "RGBA")

    # 배경 그라데이션
    top, bottom = palette[0], palette[2]
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)],
                  fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))

    # 붓터치 레이어
    for _ in range(rng.randint(26, 46)):
        c = palette[rng.randrange(len(palette))]
        a = rng.randint(60, 170)
        cx, cy = rng.randrange(w), rng.randrange(h)
        rw, rh = rng.randrange(w // 14, w // 3), rng.randrange(h // 20, h // 4)
        shape = rng.choice(["ellipse", "rect", "arc"])
        box = [cx - rw // 2, cy - rh // 2, cx + rw // 2, cy + rh // 2]
        if shape == "ellipse":
            draw.ellipse(box, fill=(*c, a))
        elif shape == "rect":
            draw.rectangle(box, fill=(*c, a))
        else:
            draw.arc(box, rng.randrange(360), rng.randrange(360), fill=(*c, 255),
                     width=rng.randint(6, 28))

    # 가는 선 드로잉
    for _ in range(rng.randint(8, 18)):
        c = palette[rng.randrange(len(palette))]
        pts = [(rng.randrange(w), rng.randrange(h)) for _ in range(rng.randint(3, 6))]
        draw.line(pts, fill=(*c, 200), width=rng.randint(3, 12), joint="curve")

    img = img.filter(ImageFilter.GaussianBlur(radius=rng.choice([0.8, 1.4, 2.2])))

    # 캔버스 결 + 액자 여백
    tex = canvas_texture(w, h, rng)
    img = Image.blend(img, tex, 0.10)
    framed = Image.new("RGB", (w + 160, h + 160), (16, 16, 20))
    framed.paste(img, (80, 80))
    framed.save(path, quality=92)
    return path


def make_clip(ffmpeg: str, path: Path, seed: int, seconds: float = 6.0) -> Path:
    """전시장에서 찍은 '영상'을 대신할 샘플 클립 (움직이는 색면 + 노이즈)."""
    hue = (seed * 47) % 360
    vf = (f"geq=r='128+80*sin(2*PI*(X/W+T/6))':"
          f"g='110+70*sin(2*PI*(Y/H+T/8)+1)':"
          f"b='140+70*sin(2*PI*((X+Y)/(W+H)+T/5)+2)',"
          f"hue=h={hue},gblur=sigma=6,noise=alls=8:allf=t,format=yuv420p")
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=gray:s=1280x720:r=30:d={seconds}",
         "-vf", vf, "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(path)])
    return path


def main() -> None:
    n_photos = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    n_videos = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    photos = ROOT / "media" / "photos"
    videos = ROOT / "media" / "videos"
    photos.mkdir(parents=True, exist_ok=True)
    videos.mkdir(parents=True, exist_ok=True)

    for i in range(1, n_photos + 1):
        p = photos / f"art_{i:03d}.jpg"
        make_painting(p, seed=i)
        print("photo:", p.name)

    ffmpeg = find_ffmpeg()
    for i in range(1, n_videos + 1):
        v = videos / f"clip_{i:03d}.mp4"
        make_clip(ffmpeg, v, seed=i * 13)
        print("video:", v.name)


if __name__ == "__main__":
    main()
