"""Microphone capture helpers — reuse frozen R1 voice hardware scripts."""
from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path

VOICE_SCRIPTS = Path(os.environ.get("VOICE_SCRIPTS", "/userdata/voice/scripts"))


def arm_mic(*, retries: int = 2, mic_gain: int | None = None) -> None:
    """Lock ES8388 mic route; retry once like voice/scripts/asr.sh."""
    script = VOICE_SCRIPTS / "mic_arm.sh"
    hw = VOICE_SCRIPTS / "voice_hw_board.sh"
    if not script.is_file():
        raise FileNotFoundError(script)
    env = os.environ.copy()
    if hw.is_file():
        # Ensure MIC_ROUTE / MIC_ARM_* match frozen board profile when orchestrator
        # is started without sourcing voice_hw_board.sh in the parent shell.
        for line in hw.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                key, _, val = line[len("export ") :].partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in env:
                    env[key] = val
    if mic_gain is not None:
        env["MIC_CAPTURE_GAIN"] = str(mic_gain)
    route = env.get("MIC_ROUTE") or env.get("ROUTE") or "main_board"
    env["MIC_ROUTE"] = route
    env["ROUTE"] = route
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            env=env,
        )
        if proc.returncode == 0:
            if proc.stderr:
                print(proc.stderr.rstrip(), flush=True)
            return
        last_err = subprocess.CalledProcessError(proc.returncode, proc.args, proc.stderr)
        if attempt < retries:
            time.sleep(0.2)
    assert last_err is not None
    raise last_err


def setup_mic(mic_gain: int | None = None) -> None:
    script = VOICE_SCRIPTS / "mic_setup.sh"
    if script.is_file():
        env = os.environ.copy()
        if mic_gain is not None:
            env["MIC_CAPTURE_GAIN"] = str(mic_gain)
        subprocess.run(["bash", str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)


async def mic_route_guard(
    stop: asyncio.Event,
    interval: float = 0.08,
    mic_gain: int | None = None,
) -> None:
    """Keep ES8388 mic route locked while recording (same idea as mic_record.sh)."""
    while not stop.is_set():
        setup_mic(mic_gain)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def open_arecord(
    *,
    device: str = "plughw:0,0",
    sample_rate: int = 16000,
    channels: int = 1,
    period_size: int = 320,
    buffer_size: int = 2560,
    pasuspender: bool = False,
) -> asyncio.subprocess.Process:
    # Larger ALSA buffer reduces underrun gaps when the asyncio loop stalls briefly.
    arecord_cmd = [
        "arecord",
        "-q",
        "-D",
        device,
        "-f",
        "S16_LE",
        "-r",
        str(sample_rate),
        "-c",
        str(channels),
        "--period-size",
        str(period_size),
        "--buffer-size",
        str(buffer_size),
        "-t",
        "raw",
    ]
    cmd = ["pasuspender", "--", *arecord_cmd] if pasuspender else arecord_cmd
    return await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
