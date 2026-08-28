"""WAV helpers — stdlib only (no numpy)."""
from __future__ import annotations

import array
import struct
import wave
from pathlib import Path


def int16_bytes_to_float32(raw: bytes) -> list[float]:
    n = len(raw) // 2
    samples = array.array("h")
    samples.frombytes(raw)
    return [s / 32768.0 for s in samples]


def float32_to_int16_bytes(samples: list[float]) -> bytes:
    out = array.array("h")
    for s in samples:
        v = int(max(-32768, min(32767, round(s * 32768.0))))
        out.append(v)
    return out.tobytes()


def write_wav_int16(path: str | Path, pcm: bytes, sample_rate: int = 16000, channels: int = 1) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


def read_wav_float32(path: str | Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM, got {wf.getsampwidth()} bytes/sample")
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    return int16_bytes_to_float32(raw), rate


def float32_peak_int16(samples: list[float]) -> int:
    if not samples:
        return 0
    return max(abs(int(round(s * 32768.0))) for s in samples)


def clipped_sample_ratio(samples: list[float], *, threshold: int = 30000) -> float:
    if not samples:
        return 0.0
    hit = sum(1 for s in samples if abs(int(round(s * 32768.0))) >= threshold)
    return hit / len(samples)


def limit_peak_float32(
    samples: list[float],
    *,
    ceiling: float = 0.85,
) -> tuple[list[float], float, int]:
    """Scale down if float PCM exceeds ceiling (post-int16 clip cannot be restored)."""
    peak_i16 = float32_peak_int16(samples)
    peak_f = peak_i16 / 32768.0
    if peak_f <= ceiling:
        return samples, 1.0, peak_i16
    gain = ceiling / peak_f
    limited = [max(-1.0, min(1.0, s * gain)) for s in samples]
    return limited, gain, peak_i16


def merge_preroll_segment(
    preroll: list[float],
    segment: list[float],
    *,
    sample_rate: int = 16000,
    max_overlap_ms: int = 500,
    match_threshold: float = 0.08,
) -> tuple[list[float], int]:
    """Legacy overlap trim — prefer collect_stream_prefix() for VAD segments."""
    if not preroll:
        return list(segment), 0
    if not segment:
        return list(preroll), 0

    max_overlap = min(len(preroll), len(segment), int(sample_rate * max_overlap_ms / 1000))
    best = 0
    for n in range(max_overlap, 0, -1):
        tail = preroll[-n:]
        head = segment[:n]
        err = sum((a - b) ** 2 for a, b in zip(tail, head)) / n
        ref = sum(b * b for b in head) / n + 1e-12
        if err / ref < match_threshold:
            best = n
            break

    if best > 0:
        return preroll + segment[best:], best
    return list(segment), 0


def collect_stream_prefix(
    chunks: list[tuple[int, list[float]]],
    end_index: int,
    *,
    max_samples: int,
) -> list[float]:
    """Return up to max_samples of PCM strictly before end_index in the stream."""
    if end_index <= 0 or max_samples <= 0:
        return []
    begin = max(0, end_index - max_samples)
    out: list[float] = []
    for start, samples in chunks:
        chunk_end = start + len(samples)
        if chunk_end <= begin:
            continue
        if start >= end_index:
            break
        s = max(0, begin - start)
        e = min(len(samples), end_index - start)
        out.extend(samples[s:e])
    return out


def collect_stream_suffix(
    chunks: list[tuple[int, list[float]]],
    begin_index: int,
    *,
    max_samples: int,
) -> list[float]:
    """Return up to max_samples of PCM from begin_index onward in the stream."""
    if max_samples <= 0:
        return []
    end_index = begin_index + max_samples
    out: list[float] = []
    for start, samples in chunks:
        chunk_end = start + len(samples)
        if chunk_end <= begin_index:
            continue
        if start >= end_index:
            break
        s = max(0, begin_index - start)
        e = min(len(samples), end_index - start)
        out.extend(samples[s:e])
    return out
