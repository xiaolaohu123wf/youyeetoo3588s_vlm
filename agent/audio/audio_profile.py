"""Capture/playback profiles for R1 agent — board ES8388 vs FY-SP701 USB."""
from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)
VOICE_SCRIPTS = Path("/userdata/voice/scripts")


@dataclass
class AudioProfile:
    profile_id: str
    label: str
    capture_device: str
    capture_channels: int = 1
    play_script: str = "play_wav.sh"
    hw_script: str = "voice_hw_board.sh"
    mic_arm: bool = True
    route_guard: bool = True
    pasuspender: bool = False
    mic_capture_gain: int = 6
    playback_env: dict[str, str] = field(default_factory=dict)
    vad_overrides: dict[str, Any] = field(default_factory=dict)
    usb_mic_volume: int | None = None

    def play_script_path(self) -> Path:
        return VOICE_SCRIPTS / self.play_script

    def hw_script_path(self) -> Path | None:
        p = VOICE_SCRIPTS / self.hw_script
        return p if p.is_file() else None

    def load_hw_env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(base or {})
        path = self.hw_script_path()
        if not path:
            return env
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith("export ") or "=" not in line:
                continue
            key, _, val = line[len("export ") :].partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                env[key] = val
        env.update(self.playback_env)
        return env


def detect_fy_sp701_card() -> int | None:
    """Return ALSA card index for FY-SP701 / Timesintelli USB audio, or None."""
    try:
        lsusb = subprocess.run(
            ["lsusb"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if lsusb.returncode == 0 and not re.search(
            r"cafe:b20a|Timesintelli", lsusb.stdout, re.I
        ):
            return None
    except (OSError, subprocess.TimeoutExpired):
        pass

    cards = Path("/proc/asound/cards")
    if not cards.is_file():
        return None
    for line in cards.read_text(encoding="utf-8", errors="replace").splitlines():
        if "USB" not in line:
            continue
        m = re.match(r"\s*(\d+)\s+\[", line)
        if not m:
            continue
        idx = int(m.group(1))
        if idx != 0:
            return idx
    return None


def _merge_profile_defaults(profile_id: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(BOARD_DEFAULTS if profile_id == "board" else FY_SP701_DEFAULTS)
    if raw:
        merged = dict(base)
        merged.update(raw)
        if "vad" in raw and isinstance(raw["vad"], dict):
            merged["vad"] = {**(base.get("vad") or {}), **raw["vad"]}
        if "playback_env" in raw and isinstance(raw["playback_env"], dict):
            merged["playback_env"] = {**(base.get("playback_env") or {}), **raw["playback_env"]}
        return merged
    return base


def _profile_from_dict(profile_id: str, raw: dict[str, Any]) -> AudioProfile:
    card = detect_fy_sp701_card()
    device = str(raw.get("capture_device", "plughw:0,0"))
    if profile_id == "fy_sp701" and card is not None:
        device = f"plughw:{card},0"
    playback_env = raw.get("playback_env") or {}
    vad_overrides = raw.get("vad") or raw.get("vad_overrides") or {}
    usb_vol = raw.get("usb_mic_volume")
    return AudioProfile(
        profile_id=profile_id,
        label=str(raw.get("label", profile_id)),
        capture_device=device,
        capture_channels=int(raw.get("capture_channels", 1)),
        play_script=str(raw.get("play_script", "play_wav.sh")),
        hw_script=str(raw.get("hw_script", "voice_hw_board.sh")),
        mic_arm=str(raw.get("mic_arm", "true")).lower() not in ("0", "false", "no"),
        route_guard=str(raw.get("route_guard", "true")).lower() not in ("0", "false", "no"),
        pasuspender=str(raw.get("pasuspender", "false")).lower() in ("1", "true", "yes"),
        mic_capture_gain=int(raw.get("mic_capture_gain", 6)),
        playback_env={str(k): str(v) for k, v in playback_env.items()},
        vad_overrides={str(k): v for k, v in vad_overrides.items()},
        usb_mic_volume=int(usb_vol) if usb_vol is not None else None,
    )


BOARD_DEFAULTS: dict[str, Any] = {
    "label": "板载 ES8388",
    "capture_device": "plughw:0,0",
    "capture_channels": 1,
    "play_script": "play_wav.sh",
    "hw_script": "voice_hw_board.sh",
    "mic_arm": True,
    "route_guard": True,
    "pasuspender": False,
    "mic_capture_gain": 6,
}

FY_SP701_DEFAULTS: dict[str, Any] = {
    "label": "FY-SP701 USB",
    "capture_device": "plughw:1,0",
    "capture_channels": 1,
    "play_script": "fy_sp701_play.sh",
    "hw_script": "fy_sp701_hw.sh",
    "mic_arm": False,
    "route_guard": False,
    "pasuspender": True,
    "mic_capture_gain": 0,
    "playback_env": {
        "VOICE_RESTORE_MIC": "0",
        "PLAYBACK_AGENT_TTS": "1",
    },
    "usb_mic_volume": 20000,
    "vad": {
        "threshold": 0.58,
        "min_silence_duration": 0.68,
        "min_speech_duration": 0.22,
        "speech_preroll_ms": 400,
        "speech_tail_pad_ms": 350,
    },
}


class AudioProfileManager:
    PROFILE_CHOICES = (
        ("auto", "自动检测"),
        ("board", "板载 ES8388"),
        ("fy_sp701", "FY-SP701 USB"),
    )

    def __init__(
        self,
        active: AudioProfile,
        settings_path: Path,
        profiles_raw: dict[str, dict[str, Any]],
    ) -> None:
        self.active = active
        self.settings_path = settings_path
        self.profiles_raw = profiles_raw

    def apply_user_overrides(self, *, usb_mic_volume: int | None = None, vad: dict[str, Any] | None = None) -> None:
        if usb_mic_volume is not None:
            self.active.usb_mic_volume = max(0, min(24660, int(usb_mic_volume)))
        if vad:
            merged = dict(self.active.vad_overrides)
            merged.update(vad)
            self.active.vad_overrides = merged

    def switch_active(self, profile_id: str) -> None:
        if profile_id == "auto":
            profile_id = "fy_sp701" if detect_fy_sp701_card() is not None else "board"
        if profile_id not in self.profiles_raw:
            profile_id = "board"
        self.active = _profile_from_dict(profile_id, self.profiles_raw[profile_id])
        LOG.info(
            "[audio] switched profile=%s (%s) capture=%s play=%s",
            self.active.profile_id,
            self.active.label,
            self.active.capture_device,
            self.active.play_script,
        )

    @classmethod
    def from_config(
        cls,
        cfg: dict[str, Any],
        agent_root: Path,
        *,
        cli_override: str | None = None,
    ) -> AudioProfileManager:
        audio_cfg = cfg.get("audio") or {}
        profiles_raw = dict(audio_cfg.get("profiles") or {})
        profiles_raw["board"] = _merge_profile_defaults("board", profiles_raw.get("board"))
        profiles_raw["fy_sp701"] = _merge_profile_defaults("fy_sp701", profiles_raw.get("fy_sp701"))

        settings_path = Path(
            audio_cfg.get("settings_path", str(agent_root / "run" / "user_settings.json"))
        )
        saved_profile = cls._read_saved_profile(settings_path)
        default = str(
            cli_override
            or saved_profile
            or audio_cfg.get("default_profile", "auto")
        ).strip()

        if default == "auto":
            profile_id = "fy_sp701" if detect_fy_sp701_card() is not None else "board"
        else:
            profile_id = default if default in profiles_raw else "board"

        active = _profile_from_dict(profile_id, profiles_raw[profile_id])
        LOG.info(
            "[audio] profile=%s (%s) capture=%s play=%s",
            active.profile_id,
            active.label,
            active.capture_device,
            active.play_script,
        )
        mgr = cls(active, settings_path, profiles_raw)
        return mgr

    @staticmethod
    def _read_saved_profile(path: Path) -> str | None:
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            pid = data.get("audio_profile")
            return str(pid) if pid else None
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def save_profile(self, profile_id: str) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if self.settings_path.is_file():
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        data["audio_profile"] = profile_id
        self.settings_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def save_fields(self, fields: dict[str, Any]) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if self.settings_path.is_file():
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        data.update(fields)
        self.settings_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def apply_to_vad(self, vad_cfg: Any) -> None:
        vad_cfg.alsa_device = self.active.capture_device
        vad_cfg.capture_channels = self.active.capture_channels
        vad_cfg.mic_capture_gain = self.active.mic_capture_gain
        vad_cfg.mic_arm = self.active.mic_arm
        vad_cfg.route_guard = self.active.route_guard
        vad_cfg.pasuspender = self.active.pasuspender
        for key, val in self.active.vad_overrides.items():
            if hasattr(vad_cfg, key):
                if key.endswith("_ms") or key in ("mic_capture_gain", "arecord_period_size", "arecord_buffer_size"):
                    setattr(vad_cfg, key, int(val))
                elif key in ("threshold", "min_silence_duration", "min_speech_duration", "max_speech_duration", "min_segment_sec"):
                    setattr(vad_cfg, key, float(val))
                else:
                    setattr(vad_cfg, key, val)

    def apply_usb_mixer(self) -> None:
        vol = self.active.usb_mic_volume
        card = detect_fy_sp701_card()
        if vol is None or card is None:
            return
        vol = max(0, min(24660, int(vol)))
        subprocess.run(
            ["amixer", "-c", str(card), "cset", "numid=7", f"{vol},{vol}"],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["amixer", "-c", str(card), "cset", "numid=8", str(vol)],
            capture_output=True,
            check=False,
        )
        LOG.info("[audio] USB mic digital volume -> %d (card %d, was max 24660)", vol, card)

    def playback_env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        return self.active.load_hw_env(base)

    def play_script(self) -> Path:
        return self.active.play_script_path()
