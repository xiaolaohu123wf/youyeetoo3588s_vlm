"""Persist GUI / user preferences for the R1 agent."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


@dataclass
class UserSettings:
    audio_profile: str | None = None
    voice_id: str | None = None
    speed: float | None = None
    usb_mic_volume: int | None = None
    vad: dict[str, Any] = field(default_factory=dict)


class UserSettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> UserSettings:
        if not self.path.is_file():
            return UserSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return UserSettings()
        if not isinstance(raw, dict):
            return UserSettings()
        vad = raw.get("vad")
        return UserSettings(
            audio_profile=str(raw["audio_profile"]) if raw.get("audio_profile") else None,
            voice_id=str(raw["voice_id"]) if raw.get("voice_id") else None,
            speed=float(raw["speed"]) if raw.get("speed") is not None else None,
            usb_mic_volume=int(raw["usb_mic_volume"]) if raw.get("usb_mic_volume") is not None else None,
            vad=dict(vad) if isinstance(vad, dict) else {},
        )

    def save(self, settings: UserSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if self.path.is_file():
            try:
                existing = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    data = existing
            except (OSError, json.JSONDecodeError):
                pass
        if settings.audio_profile is not None:
            data["audio_profile"] = settings.audio_profile
        if settings.voice_id is not None:
            data["voice_id"] = settings.voice_id
        if settings.speed is not None:
            data["speed"] = settings.speed
        if settings.usb_mic_volume is not None:
            data["usb_mic_volume"] = settings.usb_mic_volume
        if settings.vad:
            prev_vad = data.get("vad") if isinstance(data.get("vad"), dict) else {}
            merged_vad = dict(prev_vad)
            merged_vad.update(settings.vad)
            data["vad"] = merged_vad
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        LOG.info("[settings] saved %s", self.path)

    def patch(self, updates: dict[str, Any]) -> UserSettings:
        current = self.load()
        if "audio_profile" in updates:
            val = updates["audio_profile"]
            current.audio_profile = str(val).strip() if val else None
        if "voice_id" in updates:
            val = updates["voice_id"]
            current.voice_id = str(val).strip() if val else None
        if "speed" in updates and updates["speed"] is not None:
            current.speed = float(updates["speed"])
        if "usb_mic_volume" in updates and updates["usb_mic_volume"] is not None:
            current.usb_mic_volume = int(updates["usb_mic_volume"])
        if "vad" in updates and isinstance(updates["vad"], dict):
            merged = dict(current.vad)
            merged.update(updates["vad"])
            current.vad = merged
        self.save(current)
        return current
