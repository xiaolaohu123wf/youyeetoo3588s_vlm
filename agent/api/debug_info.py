"""Developer debug snapshot for GUI / WebSocket diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path
from typing import Any

from audio.audio_profile import detect_fy_sp701_card


def _run(cmd: list[str], *, timeout: float = 3.0) -> str:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return out.strip() or f"<exit {proc.returncode}>"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"<error: {exc}>"


def _read_tail(path: Path, lines: int = 24) -> list[str]:
    if not path.is_file():
        return [f"(missing {path})"]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"(read failed: {exc})"]
    rows = text.splitlines()
    return rows[-lines:] if len(rows) > lines else rows


def _pgrep(name: str) -> bool:
    return subprocess.run(
        ["pgrep", "-x", name],
        capture_output=True,
        check=False,
    ).returncode == 0


def _pgrep_pattern(pattern: str) -> bool:
    return subprocess.run(
        ["pgrep", "-f", pattern],
        capture_output=True,
        check=False,
    ).returncode == 0


def build_debug_snapshot(agent: Any) -> dict[str, Any]:
    """Build a structured debug payload from a running Orchestrator instance."""
    active = agent.audio_profile.active
    asr_cfg = agent.asr_engine.cfg
    tts_cfg = agent.tts_queue.engine.cfg
    voice = agent.voice_settings.active_profile()
    rt = agent.voice_settings.runtime
    card = detect_fy_sp701_card()
    log_path = agent.agent_root / "logs" / "orchestrator.log"

    mixer: list[str] = []
    if card is not None:
        for ctl in ("PCM", "Mic", "Mic,1"):
            mixer.append(_run(["amixer", "-c", str(card), "get", ctl]))

    llm_sock = Path(agent.socket_path)
    llm_ping = False
    if llm_sock.exists():
        try:
            llm_ping = agent.ping_llm_daemon()
        except Exception:
            llm_ping = False

    speaker_pct = agent._speaker_volume_percent()
    pcm = active.usb_pcm_volume if active.profile_id == "fy_sp701" else None

    return {
        "type": "debug_snapshot",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "agent": {
            "state": agent.state.value,
            "turn_busy": agent._turn_busy,
            "speaking": agent._speaking,
            "tts_abort": agent._tts_abort,
            "api": f"ws://{agent.api_host}:{agent.api_port}/ws",
            "ui": "http://127.0.0.1:8766/",
            "agent_root": str(agent.agent_root),
            "config": str(agent.cfg.get("_config_path", "/userdata/agent/config/agent.yaml")),
        },
        "audio": {
            "profile_id": active.profile_id,
            "label": active.label,
            "capture_device": active.capture_device,
            "capture_channels": active.capture_channels,
            "play_script": active.play_script,
            "mic_arm": active.mic_arm,
            "pasuspender": active.pasuspender,
            "usb_mic_volume": active.usb_mic_volume,
            "usb_pcm_volume": pcm,
            "speaker_volume_percent": speaker_pct,
            "fy_sp701_card": card,
            "vad": {
                "threshold": agent.vad_config.threshold,
                "min_silence_duration": agent.vad_config.min_silence_duration,
                "min_speech_duration": agent.vad_config.min_speech_duration,
                "speech_preroll_ms": agent.vad_config.speech_preroll_ms,
                "speech_tail_pad_ms": agent.vad_config.speech_tail_pad_ms,
                "alsa_device": agent.vad_config.alsa_device,
            },
        },
        "asr": {
            "backend": asr_cfg.backend,
            "model_dir": (
                asr_cfg.streaming_paraformer.model_dir
                if asr_cfg.backend == "streaming_paraformer"
                else asr_cfg.sense_voice.model_dir
            ),
            "sample_rate": asr_cfg.sample_rate,
            "partial_enabled": asr_cfg.partial_enabled,
        },
        "tts": {
            "backend": tts_cfg.backend,
            "voice_id": rt.voice_id,
            "voice_label": voice.label,
            "speed": rt.speed,
            "model_dir": str(voice.model_dir),
            "play_script": tts_cfg.play_script,
        },
        "llm": {
            "socket_path": agent.socket_path,
            "socket_exists": llm_sock.exists(),
            "ping_ok": llm_ping,
            "history_turns": len(agent._chat_turns),
            "max_new_tokens": agent.max_new_tokens,
        },
        "processes": {
            "orchestrator": _pgrep_pattern("orchestrator.main"),
            "arecord": _pgrep("arecord"),
            "llm_daemon": _pgrep_pattern("llm_daemon"),
            "chromium_kiosk": _pgrep_pattern("chromium-kiosk"),
        },
        "system": {
            "uptime": _run(["uptime", "-p"]),
            "load": _run(["cat", "/proc/loadavg"]).split()[0:3] if Path("/proc/loadavg").is_file() else [],
            "memory": _run(["free", "-h"]).splitlines()[1:3],
            "disk_userdata": _run(["df", "-h", "/userdata"]).splitlines()[-1:],
        },
        "hardware": {
            "lsusb_sp701": next(
                (
                    ln
                    for ln in _run(["lsusb"]).splitlines()
                    if "cafe:b20a" in ln.lower() or "timesintelli" in ln.lower()
                ),
                "(not found)",
            ),
            "asound_cards": _run(["cat", "/proc/asound/cards"]),
            "mixer": mixer,
        },
        "log_tail": _read_tail(log_path),
        "debug_audio": agent.debug_audio.status(),
    }


def format_debug_snapshot(data: dict[str, Any]) -> str:
    """Plain-text rendering for GUI <pre> display."""
    lines: list[str] = []
    lines.append(f"=== R1 Agent Debug ===")
    lines.append(f"generated: {data.get('generated_at', '?')}")
    lines.append("")

    def section(title: str, obj: Any) -> None:
        lines.append(f"--- {title} ---")
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{k}:")
                    lines.append(json.dumps(v, ensure_ascii=False, indent=2))
                else:
                    lines.append(f"{k}: {v}")
        elif isinstance(obj, list):
            for row in obj:
                lines.append(str(row))
        else:
            lines.append(str(obj))
        lines.append("")

    section("Agent", data.get("agent"))
    section("Audio / VAD", data.get("audio"))
    section("ASR", data.get("asr"))
    section("TTS", data.get("tts"))
    section("LLM", data.get("llm"))
    section("Processes", data.get("processes"))
    section("System", data.get("system"))
    hw = data.get("hardware") or {}
    section("Hardware", {k: v for k, v in hw.items() if k != "mixer"})
    if hw.get("mixer"):
        lines.append("--- ALSA Mixer ---")
        lines.extend(hw["mixer"])
        lines.append("")
    section("Log tail", data.get("log_tail"))
    section("Debug audio", data.get("debug_audio"))
    return "\n".join(lines).rstrip() + "\n"
