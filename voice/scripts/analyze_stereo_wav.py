#!/usr/bin/env python3
"""Per-channel peak/RMS for stereo FY-SP701 2-mic captures."""
import math
import struct
import sys
import wave


def analyze(path: str) -> None:
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    if ch < 2:
        print(f"channels={ch} (mono — use analyze_wav.py)")
        return
    samples = struct.unpack(f"<{len(frames)//2}h", frames)
    left = samples[0::2]
    right = samples[1::2]
    for name, data in ("L", left), ("R", right):
        peak = max(abs(s) for s in data) if data else 0
        rms = math.sqrt(sum(s * s for s in data) / len(data)) if data else 0.0
        active = sum(1 for s in data if abs(s) > 500)
        pct = 100.0 * active / len(data) if data else 0.0
        print(f"{name}: peak={peak} rms={rms:.1f} active500={pct:.2f}%")
    lp = max(abs(s) for s in left) if left else 0
    rp = max(abs(s) for s in right) if right else 0
    if lp < 100 and rp < 100:
        print("VERDICT: SILENCE — check USB cable / mic array")
    elif lp < 100 or rp < 100:
        print("VERDICT: ONE_CHANNEL_DEAD — 2MIC 阵列可能只通一路")
    elif abs(lp - rp) / max(lp, rp, 1) > 0.85:
        print("VERDICT: IMBALANCED — 两路电平差异大，检查安装/密封")
    else:
        print("VERDICT: STEREO_OK — 双麦均有信号")


if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1 else "/tmp/fy_sp701_mic_diag.wav")
