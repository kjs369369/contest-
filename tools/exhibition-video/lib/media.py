"""미디어 스캔·정렬·자막 매핑."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mts"}

_NUM_RE = re.compile(r"(\d+)")


@dataclass
class MediaItem:
    path: Path
    kind: str                 # "photo" | "video"
    index: int = 0
    shot_at: str | None = None      # EXIF 촬영일시 (있을 때만)
    caption: str | None = None      # 하단 자막 본문
    title: str | None = None        # 작품명 등 굵게 표시할 줄
    emphasis: list[str] = field(default_factory=list)  # 강조(컬러+볼드)할 단어
    duration: float | None = None   # 영상일 때 원본 길이


def _natural_key(p: Path):
    """파일명 자연 정렬 (IMG_2 < IMG_10)."""
    parts = _NUM_RE.split(p.name.lower())
    return [int(x) if x.isdigit() else x for x in parts]


def _exif_datetime(path: Path) -> str | None:
    try:
        from PIL import Image, ExifTags

        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return None
            tagmap = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            for key in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                if tagmap.get(key):
                    return str(tagmap[key])
    except Exception:
        return None
    return None


def scan(root: Path, order: str = "name") -> list[MediaItem]:
    """media 폴더(하위 폴더 포함)를 훑어 사진·영상 목록을 만든다.

    order: "name"(파일명 자연정렬) | "shot"(EXIF 촬영순, 없으면 파일명) | "mtime"
    """
    items: list[MediaItem] = []
    for p in sorted(root.rglob("*"), key=_natural_key):
        if not p.is_file() or p.name.startswith("."):
            continue
        ext = p.suffix.lower()
        if ext in PHOTO_EXT:
            items.append(MediaItem(path=p, kind="photo", shot_at=_exif_datetime(p)))
        elif ext in VIDEO_EXT:
            items.append(MediaItem(path=p, kind="video"))

    if order == "shot":
        items.sort(key=lambda i: (i.shot_at or "9999", _natural_key(i.path)))
    elif order == "mtime":
        items.sort(key=lambda i: i.path.stat().st_mtime)

    for n, it in enumerate(items):
        it.index = n
    return items


def apply_captions(items: list[MediaItem], csv_path: Path) -> int:
    """captions.csv를 읽어 자막을 붙인다.

    형식(헤더 필수): filename,title,caption,emphasis
      - filename : 파일명(확장자 포함) 또는 파일명 일부
      - title    : 큰 줄 (작품명 등). 비워도 됨
      - caption  : 작은 줄 (설명). 비워도 됨
      - emphasis : 강조할 단어들, `|`로 구분. 비워도 됨
    원문을 그대로 반영하며 임의 요약·변형하지 않는다.
    """
    if not csv_path.exists():
        return 0
    by_name = {it.path.name: it for it in items}
    matched = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row.get("filename") or "").strip()
            if not key:
                continue
            target = by_name.get(key)
            if target is None:
                cands = [it for it in items if key in it.path.name]
                target = cands[0] if len(cands) == 1 else None
            if target is None:
                continue
            target.title = (row.get("title") or "").strip() or None
            target.caption = (row.get("caption") or "").strip() or None
            emph = (row.get("emphasis") or "").strip()
            target.emphasis = [w.strip() for w in emph.split("|") if w.strip()]
            matched += 1
    return matched
