"""배경음(BGM)·효과음(SFX) 합성과 최종 오디오 믹싱.

· 사용자가 음원을 넣으면 그것을 쓰고, 없으면 저작권 걱정 없는 기본 사운드를
  numpy로 직접 합성한다(앰비언트 패드 / 휘익 whoosh / 임팩트 / 반짝임).
· 효과음은 ffmpeg 입력으로 수백 개를 넣지 않고, numpy에서 한 개의 긴 트랙으로
  미리 배치해 만든다 → 전환이 수백 번이어도 믹싱이 가볍고 타이밍이 정확하다.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from .env import run

SR = 48000


# ---------------------------------------------------------------- 기본 유틸
def _write_wav(path: Path, stereo: np.ndarray, sr: int = SR) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = float(np.max(np.abs(stereo))) or 1.0
    if peak > 0.99:
        stereo = stereo / peak * 0.99
    pcm = (np.clip(stereo, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return path


def _lowpass(x: np.ndarray, cutoff_hz: float, sr: int = SR) -> np.ndarray:
    """1차 IIR 로우패스 (부드러운 음색용)."""
    a = math.exp(-2.0 * math.pi * cutoff_hz / sr)
    out = np.empty_like(x)
    prev = 0.0
    for i in range(x.shape[0]):          # 길이가 길어도 초 단위라 부담 적음
        prev = (1 - a) * x[i] + a * prev
        out[i] = prev
    return out


def _adsr(n: int, attack: float, release: float, sr: int = SR) -> np.ndarray:
    env = np.ones(n)
    a = min(int(attack * sr), n // 2)
    r = min(int(release * sr), n // 2)
    if a > 0:
        env[:a] = np.linspace(0, 1, a) ** 2
    if r > 0:
        env[-r:] = np.linspace(1, 0, r) ** 2
    return env


# ---------------------------------------------------------------- BGM 합성
_CHORDS = {  # 주파수(Hz) — Am7 · Fmaj7 · Cmaj7 · G6  (잔잔한 전시장 분위기)
    "Am7":  [220.00, 261.63, 329.63, 392.00],
    "Fmaj7": [174.61, 220.00, 261.63, 329.63],
    "Cmaj7": [130.81, 196.00, 261.63, 329.63],
    "G6":   [196.00, 246.94, 293.66, 392.00],
}
_PROGRESSION = ["Am7", "Fmaj7", "Cmaj7", "G6"]


def synth_bgm(path: Path, seconds: float = 64.0, bar: float = 8.0) -> Path:
    """저작권 안전한 앰비언트 패드 BGM 생성 (루프해서 쓰기 좋게)."""
    total = int(seconds * SR)
    left = np.zeros(total)
    right = np.zeros(total)
    bar_n = int(bar * SR)
    t_bar = np.arange(bar_n) / SR

    for b in range(int(math.ceil(seconds / bar))):
        chord = _CHORDS[_PROGRESSION[b % len(_PROGRESSION)]]
        seg_l = np.zeros(bar_n)
        seg_r = np.zeros(bar_n)
        for k, f in enumerate(chord):
            amp = 0.26 / (k + 1.35)
            vib = 1.0 + 0.0016 * np.sin(2 * np.pi * (0.17 + 0.03 * k) * t_bar)
            seg_l += amp * np.sin(2 * np.pi * f * vib * t_bar)
            seg_r += amp * np.sin(2 * np.pi * f * 1.0018 * vib * t_bar + 0.6)
            seg_l += amp * 0.18 * np.sin(2 * np.pi * f * 2 * t_bar)
            seg_r += amp * 0.18 * np.sin(2 * np.pi * f * 2 * 1.0018 * t_bar + 0.4)
        env = _adsr(bar_n, attack=1.6, release=2.2)
        seg_l *= env
        seg_r *= env
        s = b * bar_n
        e = min(s + bar_n, total)
        left[s:e] += seg_l[:e - s]
        right[s:e] += seg_r[:e - s]

    # 공기감용 아주 약한 노이즈 워시
    rng = np.random.default_rng(7)
    wash = _lowpass(rng.normal(0, 1, total), 900.0) * 0.012
    left += wash
    right += np.roll(wash, 137)

    fade = _adsr(total, attack=2.5, release=3.0)
    return _write_wav(path, np.stack([left * fade, right * fade], axis=-1))


# ---------------------------------------------------------------- SFX 합성
def _whoosh(dur: float = 0.55, seed: int = 0) -> np.ndarray:
    n = int(dur * SR)
    rng = np.random.default_rng(1000 + seed)
    noise = rng.normal(0, 1, n)
    sweep = _lowpass(noise, 1200.0) * np.linspace(0.2, 1.0, n)
    sweep += (noise - _lowpass(noise, 2500.0)) * np.linspace(1.0, 0.15, n) * 0.5
    env = np.sin(np.linspace(0, np.pi, n)) ** 1.6
    mono = sweep * env * 0.45
    return np.stack([mono, np.roll(mono, 220)], axis=-1)


def _impact(dur: float = 1.1) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = 62 * np.exp(-2.6 * t) + 38
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-3.2 * t)
    rng = np.random.default_rng(31)
    click = _lowpass(rng.normal(0, 1, n), 3000.0) * np.exp(-26 * t) * 0.35
    mono = (body * 0.85 + click) * 0.8
    return np.stack([mono, mono], axis=-1)


def _shimmer(dur: float = 1.4) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    mono = np.zeros(n)
    for f, a in ((1567.98, 0.5), (2349.32, 0.3), (3135.96, 0.18), (4186.01, 0.1)):
        mono += a * np.sin(2 * np.pi * f * t) * np.exp(-3.0 * t)
    mono *= 0.35
    return np.stack([mono, np.roll(mono, 400)], axis=-1)


def build_sfx_track(path: Path, total_seconds: float,
                    whoosh_at: list[float], impact_at: list[float],
                    shimmer_at: list[float], gain: float = 1.0) -> Path:
    """전환·타이틀 시점에 효과음을 배치한 하나의 긴 트랙을 만든다."""
    total = int(total_seconds * SR) + SR
    track = np.zeros((total, 2))

    def place(sample: np.ndarray, at: float, vol: float):
        s = int(max(at, 0.0) * SR)
        e = min(s + sample.shape[0], total)
        if e > s:
            track[s:e] += sample[:e - s] * vol

    cache = [_whoosh(seed=i) for i in range(6)]
    for i, at in enumerate(whoosh_at):
        place(cache[i % len(cache)], at, 0.55 * gain)
    imp = _impact()
    for at in impact_at:
        place(imp, at, 0.7 * gain)
    shm = _shimmer()
    for at in shimmer_at:
        place(shm, at, 0.5 * gain)
    return _write_wav(path, track)


# ---------------------------------------------------------------- 최종 믹싱
def mix(ffmpeg: str, out: Path, total_seconds: float, cfg: dict,
        bgm: Path | None, sfx_track: Path | None, narration: Path | None = None) -> Path | None:
    """BGM + 효과음 + (선택)내레이션을 섞어 하나의 오디오 파일로."""
    acfg = cfg.get("audio", {})
    inputs: list[str] = []
    parts: list[str] = []
    labels: list[str] = []

    fade_in = float(acfg.get("fade_in", 1.5))
    fade_out = float(acfg.get("fade_out", 2.5))

    if bgm and Path(bgm).exists():
        idx = len(inputs) // 2
        inputs += ["-stream_loop", "-1", "-i", str(bgm)]
        gain = float(acfg.get("bgm_gain_db", -17))
        parts.append(
            f"[{idx}:a]atrim=0:{total_seconds:.3f},asetpts=N/SR/TB,"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"volume={gain}dB,"
            f"afade=t=in:st=0:d={fade_in:.2f},"
            f"afade=t=out:st={max(total_seconds - fade_out, 0):.2f}:d={fade_out:.2f}[bgm]"
        )
        labels.append("[bgm]")

    if sfx_track and Path(sfx_track).exists():
        idx = len([x for x in inputs if x == "-i"])
        inputs += ["-i", str(sfx_track)]
        gain = float(acfg.get("sfx_gain_db", -6))
        parts.append(
            f"[{idx}:a]atrim=0:{total_seconds:.3f},asetpts=N/SR/TB,"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"volume={gain}dB[sfx]"
        )
        labels.append("[sfx]")

    narr_label = None
    if narration and Path(narration).exists():
        idx = len([x for x in inputs if x == "-i"])
        inputs += ["-i", str(narration)]
        gain = float(acfg.get("narration_gain_db", 0))
        parts.append(
            f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"volume={gain}dB[narr]"
        )
        narr_label = "[narr]"

    if not labels and not narr_label:
        return None

    # 내레이션이 있으면 BGM을 사이드체인으로 눌러 준다(더킹)
    if narr_label and "[bgm]" in labels:
        parts.append(f"[narr]asplit=2[narr_mix][narr_key]")
        parts.append(
            f"[bgm][narr_key]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[bgmduck]"
        )
        labels = ["[bgmduck]" if l == "[bgm]" else l for l in labels]
        labels.append("[narr_mix]")
    elif narr_label:
        labels.append(narr_label)

    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0[mixed]")
    parts.append(f"[mixed]loudnorm=I={acfg.get('loudness_lufs', -14)}:TP=-1.5:LRA=11[aout]")

    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join(parts), "-map", "[aout]",
         "-t", f"{total_seconds:.3f}",
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", str(out)])
    return out
