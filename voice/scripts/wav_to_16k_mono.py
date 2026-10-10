#!/usr/bin/env python3
"""Convert any wav to mono S16 for ES8388 playback (rate via PLAYBACK_RATE)."""
import os
import struct
import sys
import wave


def read_wav(path):
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if sw != 2:
        raise SystemExit(f"unsupported sample width: {sw}")
    samples = struct.unpack("<%dh" % (len(frames) // 2), frames)
    if nch == 2:
        samples = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)]
    elif nch != 1:
        raise SystemExit(f"unsupported channels: {nch}")
    return rate, list(samples)


def resample(rate, samples, out_rate=16000):
    if rate == out_rate:
        return samples
    out_len = int(len(samples) * out_rate / rate)
    if out_len <= 1:
        return samples[:1]
    out = []
    for i in range(out_len):
        src = i * (len(samples) - 1) / (out_len - 1)
        j = int(src)
        k = min(j + 1, len(samples) - 1)
        frac = src - j
        out.append(int(samples[j] * (1 - frac) + samples[k] * frac))
    return out


def apply_gain(samples, gain):
    if gain <= 1.0:
        return samples
    out = []
    for s in samples:
        v = int(s * gain)
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        out.append(v)
    return out


def trim_leading_silence(samples, threshold=80, max_ms=80, rate=16000):
    """Drop only a short leading silence tail from TTS, not speech onset."""
    max_n = int(rate * max_ms / 1000)
    cut = 0
    for s in samples[:max_n]:
        if abs(s) >= threshold:
            break
        cut += 1
    return samples[cut:] if cut else samples


def prepend_lead(samples, rate=16000, lead_ms=120, fade_ms=10):
    """Leading silence + short fade-in so ES8388/amp settle before speech."""
    lead_n = int(rate * lead_ms / 1000)
    fade_n = min(int(rate * fade_ms / 1000), len(samples))
    if lead_n <= 0 and fade_n <= 0:
        return samples
    out = [0] * lead_n
    if fade_n > 0:
        for i in range(fade_n):
            factor = (i + 1) / fade_n
            out.append(int(samples[i] * factor))
        out.extend(samples[fade_n:])
    else:
        out.extend(samples)
    return out


def append_fade_out(samples, rate=16000, fade_ms=15):
    """Short fade-out so chunk boundaries do not click/pop."""
    fade_n = min(int(rate * fade_ms / 1000), len(samples))
    if fade_n <= 1:
        return samples
    out = list(samples[:-fade_n])
    start = len(samples) - fade_n
    for i in range(fade_n):
        factor = 1.0 - (i + 1) / fade_n
        out.append(int(samples[start + i] * factor))
    return out


def write_wav(path, samples, rate=16000, channels=1):
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))


def to_stereo(mono):
    out = []
    for s in mono:
        out.extend([s, s])
    return out


def auto_gain(samples, target_peak=26000, max_gain=6.0):
    peak = max((abs(s) for s in samples), default=0)
    if peak <= 0:
        return samples, 1.0
    gain = min(max_gain, target_peak / peak)
    if gain < 1.0:
        gain = 1.0
    return apply_gain(samples, gain), gain


def main():
    src, dst = sys.argv[1], sys.argv[2]
    monitor = os.environ.get("PLAYBACK_MODE") == "monitor"
    continuation = os.environ.get("PLAYBACK_CONTINUATION") == "1"
    fixed_gain = float(os.environ.get("PLAYBACK_GAIN", "4.5"))
    utterance_gain = os.environ.get("PLAYBACK_FIXED_GAIN")
    target_peak = int(os.environ.get("PLAYBACK_TARGET_PEAK", "26000"))
    max_gain = float(os.environ.get("PLAYBACK_MAX_GAIN", "8.0"))
    lead_ms = int(os.environ.get("PLAYBACK_LEAD_MS", "120"))
    fade_ms = int(os.environ.get("PLAYBACK_FADE_MS", "10"))
    fade_out_ms = int(os.environ.get("PLAYBACK_FADE_OUT_MS", "15"))
    trim_ms = int(os.environ.get("PLAYBACK_TRIM_MS", "60"))
    channels = int(os.environ.get("PLAYBACK_CHANNELS", "1"))
    out_rate = int(os.environ.get("PLAYBACK_RATE", "16000"))
    if continuation:
        lead_ms = int(os.environ.get("PLAYBACK_LEAD_MS", "18"))
        fade_ms = int(os.environ.get("PLAYBACK_FADE_MS", "8"))
        trim_ms = int(os.environ.get("PLAYBACK_TRIM_MS", "0"))
    rate, samples = read_wav(src)
    samples = resample(rate, samples, out_rate)
    if not monitor and trim_ms > 0:
        samples = trim_leading_silence(samples, rate=out_rate, max_ms=trim_ms)
    if monitor:
        src_peak = max((abs(s) for s in samples), default=0)
        if src_peak >= 28000:
            gain = 1.0
            print(
                f"[play] clipped source peak={src_peak}; monitor gain=1.0 (no boost)",
                file=sys.stderr,
            )
        else:
            samples, gain = auto_gain(
                samples,
                target_peak=target_peak,
                max_gain=float(os.environ.get("REPLAY_MONITOR_GAIN", "8.0")),
            )
    elif utterance_gain:
        gain = float(utterance_gain)
        samples = apply_gain(samples, gain)
    elif os.environ.get("PLAYBACK_NORMALIZE", "1") == "1":
        samples, gain = auto_gain(
            samples,
            target_peak=target_peak,
            max_gain=max_gain,
        )
    else:
        samples = apply_gain(samples, fixed_gain)
        gain = fixed_gain
    samples = append_fade_out(samples, rate=out_rate, fade_ms=fade_out_ms)
    if lead_ms > 0 or fade_ms > 0:
        samples = prepend_lead(samples, rate=out_rate, lead_ms=lead_ms, fade_ms=fade_ms)
    if channels >= 2:
        samples = to_stereo(samples)
        channels = 2
    write_wav(dst, samples, out_rate, channels=channels)
    peak = max((abs(s) for s in samples), default=0)
    print(
        f"[play] mode={'monitor' if monitor else 'normal'} ch={channels} rate={out_rate} "
        f"gain={gain:.2f} lead={lead_ms}ms fade={fade_ms}ms peak={peak}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
