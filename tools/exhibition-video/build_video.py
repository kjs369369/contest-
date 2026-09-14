#!/usr/bin/env python3
"""캔버스 아트 전시회 사진·영상 → 편집 완성본 영상 자동 생성.

사용법:
    python3 build_video.py                        # config.json 기본값으로 전체 렌더
    python3 build_video.py --limit 12             # 앞 12장만 빠르게 미리보기
    python3 build_video.py --config my.json       # 다른 설정 파일 사용
    python3 build_video.py --preview              # 720p·빠른 프리셋으로 시험 렌더
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib import audio as audio_lib          # noqa: E402
from lib import clips, media, transitions   # noqa: E402
from lib.env import available_korean_font, find_ffmpeg, run  # noqa: E402
from lib.subtitles import AssBuilder        # noqa: E402

DEFAULTS = {
    "project": {"title": "캔버스 아트 전시회", "subtitle": "", "outro": "감사합니다"},
    "video": {"width": 1920, "height": 1080, "fps": 30, "crf": 18, "preset": "medium"},
    "timing": {"still_duration": 3.6, "transition": 0.7, "video_max": 8.0,
               "video_skip_head": 0.0, "intro": 4.5, "outro": 4.0, "section": 2.8},
    "style": {"font": None, "accent": "#FFD24A", "text_color": "#FFFFFF",
              "grade": "gallery", "vignette": True, "grain": 0, "zoom": 1.16,
              "card_color": "#0E0E12", "show_counter": True},
    "audio": {"bgm": "media/audio/bgm.mp3", "narration": "", "keep_clip_audio": False,
              "bgm_gain_db": -17, "sfx_gain_db": -6, "narration_gain_db": 0,
              "sfx": True, "fade_in": 1.5, "fade_out": 2.5, "loudness_lufs": -14},
    "input": {"media_dir": "media", "captions_csv": "captions.csv", "order": "name"},
    "output": {"path": "out/exhibition.mp4"},
    "sections": [],
    "render": {"workers": 0, "chunk_size": 0, "keep_workdir": False},
}


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _sweep_orphan_workdirs(out_dir: Path, max_age_hours: float = 12.0) -> None:
    """중단된 렌더가 남긴 오래된 작업 폴더를 치운다(진행 중인 것은 건드리지 않음)."""
    cutoff = time.time() - max_age_hours * 3600
    for d in out_dir.glob(".work-*"):
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def load_config(path: Path) -> dict:
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg = deep_merge(cfg, json.loads(path.read_text(encoding="utf-8")))
    else:
        log(f"설정 파일이 없어 기본값으로 진행합니다: {path.name}")
    if not cfg["style"].get("font"):
        cfg["style"]["font"] = available_korean_font()
    return cfg


def build(cfg: dict, limit: int | None = None) -> Path:
    ffmpeg = find_ffmpeg()
    log(f"ffmpeg: {ffmpeg}")
    log(f"자막 폰트: {cfg['style']['font']}")

    media_dir = ROOT / cfg["input"]["media_dir"]
    if not media_dir.exists():
        raise SystemExit(f"미디어 폴더가 없습니다: {media_dir}")

    items = media.scan(media_dir, order=cfg["input"].get("order", "name"))
    if limit:
        items = items[:limit]
    if not items:
        raise SystemExit(f"{media_dir} 안에 사진·영상이 없습니다.")
    matched = media.apply_captions(items, ROOT / cfg["input"]["captions_csv"])
    photos = sum(1 for i in items if i.kind == "photo")
    log(f"미디어 {len(items)}개 (사진 {photos} · 영상 {len(items) - photos}), 자막 매칭 {matched}건")

    # 작업 폴더는 실행마다 분리한다.
    # 고정 경로를 쓰면 두 렌더가 동시에 돌 때 한쪽이 다른 쪽의 중간 파일을 지워
    # "Unable to re-open ... No such file or directory" 로 실패한다.
    work = ROOT / "out" / f".work-{os.getpid()}-{int(time.time())}"
    work.mkdir(parents=True, exist_ok=True)
    log(f"작업 폴더: {work.name}")

    # ---------------- 1) 세그먼트 렌더 ----------------
    timing = cfg["timing"]
    section_at = {int(s["at_index"]): s.get("text", "") for s in cfg.get("sections", [])}

    photos_only = [i for i in items if i.kind == "photo"]
    first_bg = (photos_only[0] if photos_only else items[0]).path
    last_bg = (photos_only[-1] if photos_only else items[-1]).path

    plan: list[tuple[str, object]] = []
    if cfg["project"].get("title"):
        plan.append(("intro", first_bg))
    for it in items:
        if it.index in section_at:
            plan.append(("section", section_at[it.index]))
        plan.append(("media", it))
    if cfg["project"].get("outro"):
        plan.append(("outro", last_bg))

    workers = int(cfg["render"].get("workers") or 0) or max((shutil.os.cpu_count() or 2), 2)
    log(f"세그먼트 {len(plan)}개 렌더 시작 (동시 {workers}개)")

    done = [0]

    def render_one(args):
        n, (kind, payload) = args
        out = work / f"seg_{n:05d}.mp4"
        if kind == "media":
            it = payload
            motion = clips.MOTIONS[n % len(clips.MOTIONS)]
            seg = (clips.render_photo(ffmpeg, it, out, cfg, motion) if it.kind == "photo"
                   else clips.render_video(ffmpeg, it, out, cfg))
        elif kind == "intro":
            seg = clips.render_card(ffmpeg, out, cfg, float(timing["intro"]), Path(payload))
        elif kind == "outro":
            seg = clips.render_card(ffmpeg, out, cfg, float(timing["outro"]), Path(payload))
        else:
            seg = clips.render_card(ffmpeg, out, cfg, float(timing["section"]), None)
        done[0] += 1
        if done[0] % 10 == 0 or done[0] == len(plan):
            log(f"  렌더 {done[0]}/{len(plan)}")
        return n, kind, payload, seg

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = sorted(pool.map(render_one, enumerate(plan)), key=lambda r: r[0])

    segments = [r[3] for r in results]
    durations = [s.duration for s in segments]
    trans = float(timing["transition"])
    starts = transitions.timeline_starts(durations, trans)
    total = transitions.total_duration(durations, trans)
    log(f"세그먼트 렌더 완료 · 최종 길이 예상 {total / 60:.1f}분")

    # ---------------- 2) 자막(ASS) 작성 ----------------
    ass = AssBuilder(cfg)
    photo_no = 0
    for (n, kind, payload, seg), start in zip(results, starts):
        end = start + seg.duration
        if kind == "intro":
            ass.title_card(start + 0.3, end - 0.2, cfg["project"]["title"],
                           cfg["project"].get("subtitle") or None)
        elif kind == "outro":
            ass.title_card(start + 0.3, end - 0.2, cfg["project"].get("outro", ""),
                           cfg["project"].get("outro_sub") or None)
        elif kind == "section":
            ass.section_card(start + 0.2, end - 0.2, str(payload))
        else:
            it = payload
            photo_no += 1
            if it.title or it.caption:
                ass.caption(start + 0.45, end - 0.35, it.title, it.caption, it.emphasis)
            if cfg["style"].get("show_counter"):
                ass.badge(start + 0.3, end - 0.3, f"{photo_no:02d} / {len(items)}")
    ass_path = ass.write(work / "captions.ass")
    log(f"자막 이벤트 {len(ass.events)}개 작성")

    # ---------------- 3) 전환효과로 병합 ----------------
    log("전환효과 병합 중…")
    merged = transitions.merge_all(
        ffmpeg, segments, work, cfg,
        chunk_size=int(cfg["render"].get("chunk_size", 0) or 0),
        on_progress=lambda lv, i, n: log(f"  병합 {lv}단계 {i}/{n}"),
    )
    total = merged.duration
    log(f"병합 완료 · {total / 60:.2f}분")

    # ---------------- 4) 오디오 ----------------
    audio_path = None
    acfg = cfg["audio"]
    bgm = ROOT / acfg["bgm"] if acfg.get("bgm") else None
    if bgm and not bgm.exists():
        bgm = work / "bgm_ambient.wav"
        log("BGM 파일이 없어 저작권 안전 기본 앰비언트를 합성합니다")
        audio_lib.synth_bgm(bgm, seconds=72.0)

    sfx_track = None
    if acfg.get("sfx", True):
        whoosh_at, impact_at, shimmer_at = [], [], []
        for (n, kind, payload, seg), start in zip(results, starts):
            if n > 0:
                whoosh_at.append(max(start - trans * 0.5, 0.0))
            if kind in ("intro", "outro", "section"):
                impact_at.append(start + 0.25)
            elif kind == "media" and (payload.title or payload.caption):
                shimmer_at.append(start + 0.45)
        sfx_track = audio_lib.build_sfx_track(
            work / "sfx_track.wav", total, whoosh_at, impact_at, shimmer_at)
        log(f"효과음 배치: 전환 {len(whoosh_at)} · 임팩트 {len(impact_at)} · 반짝임 {len(shimmer_at)}")

    narration = ROOT / acfg["narration"] if acfg.get("narration") else None
    audio_path = audio_lib.mix(ffmpeg, work / "audio_mix.m4a", total, cfg,
                               bgm, sfx_track, narration)

    # ---------------- 5) 자막 굽기 + 오디오 결합 (최종 1패스) ----------------
    out_path = ROOT / cfg["output"]["path"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    v = cfg["video"]
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(merged.path)]
    if audio_path:
        cmd += ["-i", str(audio_path)]
    ass_arg = str(ass_path).replace("\\", "/").replace(":", "\\:")
    cmd += ["-vf", f"ass='{ass_arg}'",
            "-c:v", "libx264", "-preset", str(v.get("preset", "medium")),
            "-crf", str(v.get("crf", 18)), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-r", str(v.get("fps", 30))]
    if audio_path:
        cmd += ["-c:a", "aac", "-b:a", "256k", "-shortest"]
    else:
        cmd += ["-an"]
    cmd += [str(out_path)]
    log("자막·오디오 최종 합성 중…")
    run(cmd)

    if not cfg["render"].get("keep_workdir"):
        shutil.rmtree(work, ignore_errors=True)
        _sweep_orphan_workdirs(ROOT / "out")

    size_mb = out_path.stat().st_size / 1024 / 1024
    log(f"완성: {out_path}  ({total / 60:.2f}분 · {size_mb:.1f}MB)")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="전시회 사진·영상 자동 편집")
    ap.add_argument("--config", default="config.json", help="설정 파일 경로")
    ap.add_argument("--limit", type=int, default=None, help="앞에서 N개만 사용(미리보기)")
    ap.add_argument("--preview", action="store_true", help="720p·빠른 프리셋으로 시험 렌더")
    ap.add_argument("--out", default=None, help="출력 파일 경로 덮어쓰기")
    args = ap.parse_args()

    cfg = load_config(ROOT / args.config)
    if args.preview:
        cfg["video"].update({"width": 1280, "height": 720, "crf": 23, "preset": "veryfast"})
        cfg["output"]["path"] = args.out or "out/preview.mp4"
    if args.out:
        cfg["output"]["path"] = args.out
    build(cfg, limit=args.limit)


if __name__ == "__main__":
    main()
