#!/bin/bash
# Short beep on FY-SP701 speaker before recording.
set -euo pipefail
BEEP=/tmp/fy_sp701_beep.wav
python3 - <<'PY'
import struct, math, wave
rate = 16000
dur = 0.25
freq = 880.0
n = int(rate * dur)
with wave.open("/tmp/fy_sp701_beep.wav", "w") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    for i in range(n):
        v = int(20000 * math.sin(2 * math.pi * freq * i / rate))
        w.writeframes(struct.pack("<h", v))
PY
bash /userdata/voice/scripts/fy_sp701_play.sh "${BEEP}"
sleep 0.12
