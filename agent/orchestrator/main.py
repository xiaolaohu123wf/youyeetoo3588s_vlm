"""Asyncio orchestrator — Phase E: voice pipeline + WebSocket event API."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

_AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

from api.debug_audio import DebugAudioController, handle_debug_audio
from api.debug_info import build_debug_snapshot, format_debug_snapshot
from api.event_bus import EventBus
from orchestrator.mediamtx_camera import (
    MediamtxCameraConfig,
    copy_mediamtx_cache_file,
    grab_mediamtx_vlm_pair,
    mediamtx_cache_age_sec,
    mediamtx_cache_available,
    mediamtx_cache_fresh,
    preview_jpeg_bytes_valid,
    uses_mediamtx,
)
from api.ws_server import run_ws_server
from audio.audio_profile import (
    AudioProfileManager,
    speaker_gain_to_percent,
    speaker_pcm_to_percent,
)
from asr.asr_engine import AsrEngine, AsrEngineConfig
from asr.normalize import normalize_user_text
from asr.sense_voice import SenseVoiceConfig
from asr.sherpa_streaming_asr import StreamingParaformerConfig
from asr.vad_stream import VadConfig, VadStream
from llm.client import llm_chat_stream, llm_clear_history, llm_ping
from orchestrator.config_loader import load_yaml
from orchestrator.dialogue_policy import (
    can_barge_in,
    is_resume_command,
    is_stop_command,
    is_vision_query,
    normalize_spoken_text,
)
from orchestrator.events import AgentState
from settings.store import UserSettingsStore
from tts.sentence_split import (
    StreamingSentenceSplitter,
    canned_reply_for,
    clean_llm_reply,
    extract_speak_sentences,
    is_echo_reply,
    is_self_echo,
    is_speakable,
    persona_reply_for,
    sanitize_tts_text,
    should_skip_llm,
    split_tts_clauses,
)
from tts.tts_engine import TtsConfig, TtsEngine
from tts.tts_queue import TtsQueue
from tts.voice_settings import VoiceSettingsManager, is_voice_settings_query

LOG = logging.getLogger("orchestrator")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


class Orchestrator:
    camera_enabled: bool = False
    camera_url: str = "http://10.0.0.159:8080/shot.jpg"
    camera_timeout: float = 2.5
    camera_size: int = 448
    camera_prompt: str = "用一句话简短描述画面中的核心物品和场景。"
    camera_vlm_cmd: str = "/userdata/p4/scripts/vlm_see.sh"
    camera_api_url: str = ""
    camera_api_key: str = ""
    camera_model: str = "qwen-vl-plus"

    def __init__(self, cfg: dict[str, Any], agent_root: Path) -> None:
        self.cfg = cfg
        self.agent_root = agent_root
        self.state = AgentState.IDLE
        self.vad_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._turn_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=2)
        self._asr_session = None
        self._listen_cooldown_until = 0.0
        self._turn_busy = False
        self._speaking = False
        self._tts_abort = False
        self._active_tts_text = ""
        self._last_spoken_turn = ""
        self._last_tts_end_at = 0.0
        self._paused_relay_text: str | None = None
        self._current_splitter: Any = None
        self._next_turn_id = 0
        self._active_turn_id = 0
        self._ws_server: asyncio.Server | None = None
        self._vad_restart = asyncio.Event()
        self._debug_vad_paused = False

        vad_cfg = cfg.get("vad") or {}
        asr_cfg = cfg.get("asr") or {}
        tts_cfg = cfg.get("tts") or {}
        api_cfg = cfg.get("api") or {}
        paths = cfg.get("paths") or {}
        barge_cfg = cfg.get("barge_in") or {}
        cam_cfg = cfg.get("camera") or {}

        self.event_bus = EventBus()
        self.api_enabled = str(api_cfg.get("enabled", "true")).lower() not in ("0", "false", "no")
        self.api_host = str(api_cfg.get("host", "0.0.0.0"))
        self.api_port = int(api_cfg.get("port", 8765))
        self.barge_in_enabled = str(barge_cfg.get("enabled", "true")).lower() not in ("0", "false", "no")
        self.barge_in_min_sec = float(barge_cfg.get("min_speech_sec", 0.35))

        self.camera_enabled = str(cam_cfg.get("enabled", "true")).lower() not in ("0", "false", "no")
        self.camera_url = str(cam_cfg.get("url", "http://10.0.0.159:8080/shot.jpg"))
        rtsp_env = Path("/userdata/p4/config/rtsp.env")
        if rtsp_env.is_file():
            for line in rtsp_env.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("RTSP_URL="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        self.camera_url = val
                    break
        self.camera_rtsp_transport = str(cam_cfg.get("rtsp_transport", "tcp")).strip()
        self.camera_timeout = float(cam_cfg.get("timeout", 2.5))
        self.camera_size = int(cam_cfg.get("size", 448))
        self.camera_prompt = str(cam_cfg.get("prompt", "用一句话简短描述画面中的核心物品和场景。"))
        self.camera_see_max_new_tokens = int(cam_cfg.get("see_max_new_tokens", 96))
        self.camera_vlm_cmd = str(cam_cfg.get("vlm_cmd", "/userdata/p4/scripts/vlm_see.sh"))
        self.camera_api_url = str(cam_cfg.get("api_url", "")).strip()
        self.camera_api_key = str(cam_cfg.get("api_key", "")).strip()
        self.camera_model = str(cam_cfg.get("model", "qwen-vl-plus")).strip()
        self.proactive_enabled = str(cam_cfg.get("proactive_enabled", "true")).lower() not in ("0", "false", "no")
        self.proactive_interval_sec = float(cam_cfg.get("proactive_interval_sec", 2.5))
        self.proactive_motion_threshold = float(cam_cfg.get("proactive_motion_threshold", 4.0))
        self.proactive_cooldown_sec = float(cam_cfg.get("proactive_cooldown_sec", 35.0))
        mtx = cam_cfg.get("mediamtx") or {}
        self.camera_grab_backend = str(cam_cfg.get("grab_backend", "rtsp")).strip().lower()
        mtx_path = str(mtx.get("path", cam_cfg.get("mediamtx_path", "cam"))).strip() or "cam"
        self.mediamtx_cfg = MediamtxCameraConfig(
            path=mtx_path,
            rtsp_url=str(mtx.get("rtsp_url", f"rtsp://127.0.0.1:8554/{mtx_path}")),
            whep_url=str(mtx.get("whep_url", f"http://127.0.0.1:8889/{mtx_path}/whep")),
            latest_frame=str(mtx.get("latest_frame", str(agent_root / "run" / "mediamtx_latest.jpg"))),
            cache_max_age_sec=float(mtx.get("cache_max_age_sec", 0.8)),
            grab_backend=self.camera_grab_backend,
        )
        if self.camera_grab_backend.startswith("mediamtx") or self.camera_grab_backend == "whep":
            self.camera_url = self.mediamtx_cfg.rtsp_url
            LOG.info(
                "[camera] mediamtx grab_backend=%s whep=%s rtsp=%s",
                self.camera_grab_backend,
                self.mediamtx_cfg.whep_url,
                self.mediamtx_cfg.rtsp_url,
            )
        self._last_proactive_speak_at = 0.0
        self._latest_camera_bytes: bytes | None = None
        self._latest_camera_time: float = 0.0
        self._scene_memory_file = self.agent_root / "run" / "scene_memory.json"
        self._scene_memory: dict[str, Any] = self._load_scene_memory()

        self.vad_config = VadConfig(
            model_path=vad_cfg.get("model", "/userdata/voice/silero_vad.onnx"),
            sherpa_lib=vad_cfg.get(
                "sherpa_lib",
                "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
            ),
            sample_rate=int(vad_cfg.get("sample_rate", 16000)),
            chunk_ms=int(vad_cfg.get("chunk_ms", 100)),
            threshold=float(vad_cfg.get("threshold", 0.5)),
            min_silence_duration=float(vad_cfg.get("min_silence_duration", 0.4)),
            min_speech_duration=float(vad_cfg.get("min_speech_duration", 0.25)),
            max_speech_duration=float(vad_cfg.get("max_speech_duration", 30.0)),
            alsa_device=str(vad_cfg.get("alsa_device", "plughw:0,0")),
            min_segment_sec=float(vad_cfg.get("min_segment_sec", 0.5)),
            speech_preroll_ms=int(vad_cfg.get("speech_preroll_ms", 400)),
            speech_tail_pad_ms=int(vad_cfg.get("speech_tail_pad_ms", 0)),
            arecord_period_size=int(vad_cfg.get("arecord_period_size", 320)),
            arecord_buffer_size=int(vad_cfg.get("arecord_buffer_size", 2560)),
            mic_capture_gain=int(vad_cfg.get("mic_capture_gain", 6)),
        )
        self.listen_cooldown_sec = float(vad_cfg.get("listen_cooldown_sec", 0.5))
        self.listen_cooldown_skip_max_sec = float(vad_cfg.get("listen_cooldown_skip_max_sec", 0.45))
        self.mute_mic_during_tts = str(vad_cfg.get("mute_mic_during_tts", "false")).lower() not in ("0", "false", "no")

        audio_override = (cfg.get("_cli_audio_profile") or "").strip() or None
        audio_cfg = cfg.get("audio") or {}
        settings_path = Path(
            audio_cfg.get("settings_path", str(agent_root / "run" / "user_settings.json"))
        )
        self.user_settings = UserSettingsStore(settings_path)
        saved_user = self.user_settings.load()
        self.audio_profile = AudioProfileManager.from_config(
            cfg, agent_root, cli_override=audio_override
        )
        self.audio_profile.apply_user_overrides(
            usb_mic_volume=saved_user.usb_mic_volume,
            speaker_volume=saved_user.speaker_volume,
            vad=saved_user.vad or None,
        )
        self.audio_profile.apply_to_vad(self.vad_config)

        utterance = paths.get("utterance_wav", str(agent_root / "run" / "last_utterance.wav"))
        asr_backend = str(asr_cfg.get("backend", "sense_voice")).strip().lower()
        self.asr_engine = AsrEngine(
            AsrEngineConfig(
                backend=asr_backend,
                sense_voice=SenseVoiceConfig(
                    model_dir=asr_cfg.get(
                        "model_dir",
                        "/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17",
                    ),
                    sherpa_bin=asr_cfg.get(
                        "sherpa_bin",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline",
                    ),
                    sherpa_lib=asr_cfg.get(
                        "sherpa_lib",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
                    ),
                    language=str(asr_cfg.get("language", "zh")),
                    num_threads=int(asr_cfg.get("num_threads", 2)),
                ),
                streaming_paraformer=StreamingParaformerConfig(
                    model_dir=asr_cfg.get(
                        "model_dir",
                        "/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en",
                    ),
                    sherpa_lib=asr_cfg.get(
                        "sherpa_lib",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
                    ),
                    encoder=str(asr_cfg.get("encoder", "encoder.int8.onnx")),
                    decoder=str(asr_cfg.get("decoder", "decoder.int8.onnx")),
                    tokens=str(asr_cfg.get("tokens", "tokens.txt")),
                    num_threads=int(asr_cfg.get("num_threads", 2)),
                    sample_rate=int(vad_cfg.get("sample_rate", 16000)),
                ),
                sample_rate=self.vad_config.sample_rate,
                partial_interval_sec=float(asr_cfg.get("partial_interval_sec", 1.2)),
                partial_min_sec=float(asr_cfg.get("partial_min_sec", 1.0)),
                partial_enabled=str(asr_cfg.get("partial_enabled", "true")).lower() not in ("0", "false", "no"),
                max_partials_per_utterance=int(asr_cfg.get("max_partials_per_utterance", 3)),
                min_duration_sec=self.vad_config.min_segment_sec,
                utterance_wav=utterance,
                clip_peak_threshold=int(asr_cfg.get("clip_peak_threshold", 30000)),
                clip_limit_ceiling=float(asr_cfg.get("clip_limit_ceiling", 0.85)),
            )
        )

        self.socket_path = cfg.get("socket_path", "/tmp/r1-llm.sock")
        from xiaolan_cli.brain import XiaolanBrain

        infer_cfg = cfg.get("inference") or {}
        backend = str(infer_cfg.get("backend", "llm_daemon"))
        self.brain = XiaolanBrain(
            self.agent_root,
            socket_path=self.socket_path,
            max_new_tokens=int(cfg.get("max_new_tokens", 128)),
            backend=backend,
        )
        self.inference_backend = backend
        self.max_new_tokens = int(cfg.get("max_new_tokens", 64))
        self.history_max_turns = int(cfg.get("history_max_turns", 4))
        self.history_idle_clear_sec = float(cfg.get("history_idle_clear_sec", 600))
        self.system_prompt = (cfg.get("system_prompt") or "").strip()
        self._chat_turns: list[tuple[str, str]] = []
        self._llm_last_turn_at = 0.0
        self.voice_settings = VoiceSettingsManager.from_config(tts_cfg)
        if saved_user.voice_id:
            self.voice_settings.apply(voice_id=saved_user.voice_id)
        if saved_user.speed is not None:
            self.voice_settings.apply(speed=saved_user.speed)
        tts_engine = TtsEngine(self._tts_config_from_voice())
        tts_engine.set_playback_env(self.audio_profile.playback_env())
        self.tts_queue = TtsQueue(
            tts_engine,
            merge_max_chars=int(tts_cfg.get("merge_max_chars", 40)),
        )
        self.vad_stream = VadStream(self.vad_config, self.vad_queue)
        self.debug_audio = DebugAudioController(self)
        self._loop: asyncio.AbstractEventLoop | None = None

    def _tts_config_from_voice(self) -> TtsConfig:
        tts_cfg = self.cfg.get("tts") or {}
        profile = self.voice_settings.active_profile()
        rt = self.voice_settings.runtime
        return TtsConfig(
            backend=profile.backend,
            model_dir=profile.model_dir,
            model_file=profile.model_file,
            vocoder=profile.vocoder or self.voice_settings.default_vocoder,
            rule_fsts=list(profile.rule_fsts or tts_cfg.get("rule_fsts") or []),
            play_script=self.audio_profile.active.play_script,
            sherpa_bin=tts_cfg.get(
                "sherpa_bin",
                "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline-tts",
            ),
            sherpa_lib=tts_cfg.get(
                "sherpa_lib",
                "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
            ),
            num_threads=int(tts_cfg.get("num_threads", 2)),
            sid=profile.sid,
            speed=rt.speed,
            noise_scale=float(
                profile.noise_scale
                if profile.noise_scale is not None
                else tts_cfg.get("noise_scale", 0.667)
            ),
            max_chars=int(tts_cfg.get("max_chars", 80)),
        )

    async def _sync_tts_from_voice_settings(self) -> None:
        await self.tts_queue.reconfigure(self._tts_config_from_voice())
        self.tts_queue.engine.set_playback_env(self.audio_profile.playback_env())
        p = self.voice_settings.active_profile()
        rt = self.voice_settings.runtime
        LOG.info(
            "[voice] synced tts voice=%s backend=%s sid=%d model=%s",
            rt.voice_id,
            p.backend,
            p.sid,
            p.model_path(),
        )
        await self.emit(
            {
                "type": "voice_settings",
                "voice_id": rt.voice_id,
                "label": p.label,
                "speed": rt.speed,
            }
        )

    async def emit(self, event: dict[str, Any]) -> None:
        await self.event_bus.publish(event)

    def set_state(self, new: AgentState) -> None:
        if new != self.state:
            LOG.info("[state] %s -> %s", self.state.value, new.value)
            self.state = new
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.emit({"type": "state", "value": new.value}))
            except RuntimeError:
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.emit({"type": "state", "value": new.value}), self._loop
                    )

    def ping_llm_daemon(self) -> bool:
        if not Path(self.socket_path).exists():
            LOG.warning("[llm] socket missing: %s", self.socket_path)
            return False
        try:
            ok = llm_ping(self.socket_path)
            LOG.info("[llm] ping %s", "ok" if ok else "fail")
            return ok
        except OSError as exc:
            LOG.warning("[llm] ping failed: %s", exc)
            return False

    def _new_asr_session(self):
        session: Any = None
        last_partial = ""

        async def on_partial(text: str) -> None:
            nonlocal last_partial
            LOG.info("[event] asr_partial: %s", text)
            await self.emit({"type": "asr_partial", "text": text})
            if self.barge_in_enabled and self._speaking and text.strip():
                clean_p = normalize_spoken_text(text)
                if not clean_p:
                    return
                cur_speak = (
                    (self._active_tts_text or "")
                    + " "
                    + (getattr(self.tts_queue, "_current_speaking_chunk", "") or "")
                    + " "
                    + (self._last_spoken_turn or "")
                ).strip()
                if cur_speak and is_self_echo(cur_speak, clean_p):
                    LOG.info("[barge-in] self-acoustic feedback detected: %s", clean_p[:15])
                    return
                if is_stop_command(clean_p):
                    LOG.info("[barge-in] stop command matched: %s", clean_p)
                    await self._interrupt_tts()
                    return
                speech_sec = session.buffer_sec if session is not None else 0.0
                if not can_barge_in(clean_p, speech_sec, self.barge_in_min_sec):
                    return
                if clean_p.startswith(last_partial) and len(clean_p) > len(last_partial):
                    delta = clean_p[len(last_partial) :]
                else:
                    delta = clean_p[-4:]
                last_partial = clean_p
                if delta and cur_speak and is_self_echo(cur_speak, delta):
                    LOG.info("[barge-in] self-acoustic feedback delta ignored: %s", delta)
                    return
                LOG.info("[barge-in] user speech after %.2fs, interrupting TTS: %s", speech_sec, text)
                await self._interrupt_tts()

        async def on_final(text: str, meta: dict) -> None:
            LOG.info("[event] asr_final: %s", text or meta.get("status"))
            await self.emit({"type": "asr_final", "text": text, "meta": meta})
            if self.barge_in_enabled and self._speaking and text.strip():
                clean_f = normalize_spoken_text(text)
                cur_speak = (
                    (self._active_tts_text or "")
                    + " "
                    + (getattr(self.tts_queue, "_current_speaking_chunk", "") or "")
                    + " "
                    + (self._last_spoken_turn or "")
                ).strip()
                if is_stop_command(clean_f) and not (cur_speak and is_self_echo(cur_speak, clean_f)):
                    LOG.info("[barge-in] final stop command matched: %s", clean_f)
                    await self._interrupt_tts()

        session = self.asr_engine.create_session(on_partial, on_final)
        self._asr_session = session
        return session

    async def _interrupt_tts(self) -> None:
        if not self._speaking:
            return
        LOG.info("[barge-in] interrupt TTS playback immediately")
        self._tts_abort = True
        self._speaking = False
        self._last_tts_end_at = time.monotonic()
        self._listen_cooldown_until = 0.0
        pending = await self.tts_queue.interrupt()
        relay_parts = list(pending)
        if getattr(self, "_current_splitter", None):
            rem = self._current_splitter.finish()
            for r in rem:
                if r not in relay_parts:
                    relay_parts.append(r)
        if relay_parts:
            self._paused_relay_text = "".join(relay_parts).strip()
            LOG.info("[relay] saved %d pending clauses (%d chars) for resume: %s", len(relay_parts), len(self._paused_relay_text), self._paused_relay_text[:40])
        await self.emit({"type": "barge_in", "phase": "tts"})

    async def handle_ws_message(self, text: str) -> None:
        await self._handle_ws_message(text)

    def _can_hot_swap_audio(self) -> bool:
        return (
            not self._turn_busy
            and not self._speaking
            and self.state in (AgentState.IDLE, AgentState.LISTEN)
        )

    def _speaker_volume_percent(self) -> int:
        active = self.audio_profile.active
        if active.profile_id == "fy_sp701":
            return speaker_pcm_to_percent(active.usb_pcm_volume)
        gain = float(active.playback_env.get("PLAYBACK_GAIN", "2.0"))
        return speaker_gain_to_percent(gain)

    async def _build_settings_snapshot(self) -> dict[str, Any]:
        saved = self.user_settings.load()
        rt = self.voice_settings.runtime
        voice = self.voice_settings.active_profile()
        audio_choice = saved.audio_profile or str(
            (self.cfg.get("audio") or {}).get("default_profile", "auto")
        )
        return {
            "type": "settings_snapshot",
            "state": self.state.value,
            "audio_profiles": [
                {"id": pid, "label": label} for pid, label in AudioProfileManager.PROFILE_CHOICES
            ],
            "audio_profile": audio_choice,
            "active_audio_profile": self.audio_profile.active.profile_id,
            "active_audio_label": self.audio_profile.active.label,
            "voices": [
                {
                    "id": p.voice_id,
                    "label": p.label,
                    "available": p.available(),
                }
                for p in self.voice_settings.profiles.values()
            ],
            "voice_id": rt.voice_id,
            "voice_label": voice.label,
            "speed": rt.speed,
            "speed_min": self.voice_settings.speed_min,
            "speed_max": self.voice_settings.speed_max,
            "usb_mic_volume": self.audio_profile.active.usb_mic_volume or 20000,
            "usb_mic_volume_max": 24660,
            "usb_mic_supported": self.audio_profile.active.profile_id == "fy_sp701",
            "speaker_volume": self._speaker_volume_percent(),
            "speaker_volume_min": 0,
            "speaker_volume_max": 100,
            "vad": {
                "threshold": self.vad_config.threshold,
                "min_silence_duration": self.vad_config.min_silence_duration,
                "speech_tail_pad_ms": self.vad_config.speech_tail_pad_ms,
            },
            "can_change_audio": self._can_hot_swap_audio(),
        }

    async def _apply_settings_patch(self, patch: dict[str, Any]) -> None:
        errors: list[str] = []
        restart_vad = False
        store_patch: dict[str, Any] = {}

        if "voice_id" in patch and patch["voice_id"]:
            self.voice_settings.apply(voice_id=str(patch["voice_id"]))
            store_patch["voice_id"] = self.voice_settings.runtime.voice_id
            await self._sync_tts_from_voice_settings()

        if "speed" in patch and patch["speed"] is not None:
            self.voice_settings.apply(speed=float(patch["speed"]))
            store_patch["speed"] = self.voice_settings.runtime.speed
            await self._sync_tts_from_voice_settings()

        if "audio_profile" in patch and patch["audio_profile"] is not None:
            choice = str(patch["audio_profile"]).strip()
            if choice not in ("auto", "board", "fy_sp701"):
                errors.append("invalid_audio_profile")
            elif not self._can_hot_swap_audio():
                errors.append("busy")
            else:
                store_patch["audio_profile"] = choice
                self.audio_profile.switch_active(choice)
                saved = self.user_settings.load()
                self.audio_profile.apply_user_overrides(
                    usb_mic_volume=saved.usb_mic_volume,
                    speaker_volume=saved.speaker_volume,
                    vad=saved.vad or None,
                )
                self.audio_profile.apply_to_vad(self.vad_config)
                self.audio_profile.apply_usb_mixer()
                await self._sync_tts_from_voice_settings()
                restart_vad = True
                await self.emit(
                    {
                        "type": "audio_profile",
                        "profile_id": self.audio_profile.active.profile_id,
                        "label": self.audio_profile.active.label,
                        "capture_device": self.audio_profile.active.capture_device,
                        "play_script": self.audio_profile.active.play_script,
                    }
                )

        if "usb_mic_volume" in patch and patch["usb_mic_volume"] is not None:
            vol = max(0, min(24660, int(patch["usb_mic_volume"])))
            store_patch["usb_mic_volume"] = vol
            self.audio_profile.apply_user_overrides(usb_mic_volume=vol)
            self.audio_profile.apply_usb_mixer()

        if "speaker_volume" in patch and patch["speaker_volume"] is not None:
            pct = max(0, min(100, int(patch["speaker_volume"])))
            store_patch["speaker_volume"] = pct
            self.audio_profile.apply_user_overrides(speaker_volume=pct)
            self.audio_profile.apply_usb_mixer()
            self.tts_queue.engine.set_playback_env(self.audio_profile.playback_env())

        if "vad" in patch and isinstance(patch["vad"], dict):
            store_patch["vad"] = patch["vad"]
            self.audio_profile.apply_user_overrides(vad=patch["vad"])
            self.audio_profile.apply_to_vad(self.vad_config)
            if self._can_hot_swap_audio():
                restart_vad = True

        if store_patch:
            self.user_settings.patch(store_patch)

        if restart_vad:
            self._vad_restart.set()

        snap = await self._build_settings_snapshot()
        await self.emit(
            {
                "type": "settings_applied",
                "ok": not errors,
                "errors": errors,
                "restart_vad": restart_vad,
                **{k: v for k, v in snap.items() if k != "type"},
            }
        )

    async def run_vad_loop(self, inject_wav: str | None = None) -> None:
        try:
            while True:
                while self._debug_vad_paused:
                    await asyncio.sleep(0.25)
                if inject_wav:
                    await self.vad_stream.run_wav_file(inject_wav)
                    break
                self.vad_stream = VadStream(self.vad_config, self.vad_queue)
                live_task = asyncio.create_task(self.vad_stream.run_live())
                restart_task = asyncio.create_task(self._vad_restart.wait())
                done, pending = await asyncio.wait(
                    [live_task, restart_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                if self._vad_restart.is_set():
                    self._vad_restart.clear()
                    self.vad_stream.stop()
                    with contextlib.suppress(Exception):
                        await live_task
                    LOG.info("[settings] VAD restarted after audio settings change")
                    continue
                if live_task.done():
                    with contextlib.suppress(Exception):
                        await live_task
                    LOG.warning("[vad] capture stopped — retry in 3s")
                    await asyncio.sleep(3)
                    continue
                LOG.error("[vad] unexpected loop exit — retry in 3s")
                await asyncio.sleep(3)
        finally:
            if not self._debug_vad_paused:
                await self.vad_queue.put({"type": "shutdown"})

    async def _turn_worker(self) -> None:
        while True:
            event = await self._turn_queue.get()
            try:
                if event is None:
                    LOG.info("[turn] worker shutdown")
                    return
                await self._process_turn(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("[turn] processing failed")
                self._speaking = False
                self._tts_abort = False
                self.set_state(AgentState.LISTEN)
                await self.emit({"type": "error", "code": "turn_failed"})
            finally:
                self._turn_queue.task_done()

    async def _enqueue_turn(self, event: dict[str, Any]) -> None:
        """Keep the newest speech turns instead of answering an obsolete backlog."""
        event.setdefault("_vad_end_at", time.monotonic())
        dropped = 0
        while self._turn_queue.full():
            stale = self._turn_queue.get_nowait()
            self._turn_queue.task_done()
            if stale is None:
                await self._turn_queue.put(None)
                return
            dropped += 1
        if dropped:
            LOG.info("[turn] dropped %d stale queued segment(s)", dropped)
        await self._turn_queue.put(event)

    async def handle_events(self) -> None:
        self.set_state(AgentState.LISTEN)
        while True:
            event = await self.vad_queue.get()
            etype = event.get("type")
            if etype == "shutdown":
                LOG.warning("[event] shutdown signal — restarting event loop")
                self.set_state(AgentState.LISTEN)
                return
            if etype == "error":
                LOG.error("[event] %s", event)
                continue
            if self.mute_mic_during_tts and self._speaking:
                # Completely block all mic events while TTS is playing —
                # cancels in-flight ASR and drops audio_chunk so NPU does not
                # waste cycles transcribing the speaker's own echo.
                if etype in ("speech_start", "audio_chunk"):
                    if self._asr_session:
                        await self._asr_session.cancel()
                        self._asr_session = None
                    LOG.debug("[vad] mute_mic: blocked %s during TTS playback", etype)
                    continue
                if etype == "speech_end":
                    LOG.debug("[vad] mute_mic: blocked speech_end during TTS playback")
                    continue
                # audio_segment is handled below (echo-time-window check)
            if etype == "speech_start":
                if self._turn_busy and not self._speaking:
                    LOG.debug("[vad] ignore speech start while ASR/LLM owns recognizer")
                    continue
                LOG.info("[event] speech_start")
                self._new_asr_session()
                await self._asr_session.start()
                continue
            if etype == "speech_end":
                LOG.info("[event] speech_end")
                continue
            if etype == "audio_chunk" and self._asr_session and (not self._turn_busy or self._speaking):
                await self._asr_session.feed(event["samples"])
                continue
            if etype == "audio_segment":
                duration = float(event.get("duration_sec", 0.0))
                if self.mute_mic_during_tts:
                    end_at = float(event.get("end_at") or time.monotonic())
                    start_at = end_at - duration
                    if start_at < (getattr(self, "_last_tts_end_at", 0.0) or 0.0):
                        LOG.info("[vad] mute_mic_during_tts: dropped playback echo segment (%.2fs)", duration)
                        continue
                if self._speaking:
                    if duration >= self.barge_in_min_sec:
                        LOG.info("[vad] speaking turn, queuing potential user speech (%.2fs)", duration)
                        await self._enqueue_turn(event)
                    continue
                if self._turn_busy and not self._speaking and not self._tts_abort:
                    if duration >= 0.8:
                        LOG.info("[vad] busy turn, but segment is valid user speech (%.2fs), queuing", duration)
                        await self._enqueue_turn(event)
                        continue
                    LOG.info("[vad] busy ASR/LLM, drop %.2fs segment", duration)
                    continue
                if (
                    not self._speaking
                    and time.monotonic() < self._listen_cooldown_until
                    and duration < self.listen_cooldown_skip_max_sec
                ):
                    LOG.info("[vad] post-tts cooldown, skip short %.2fs segment", duration)
                    continue
                await self._enqueue_turn(event)
        await self._turn_queue.put(None)

    async def _process_turn(self, event: dict[str, Any]) -> None:
        self._next_turn_id += 1
        generation = self._next_turn_id
        self._active_turn_id = generation
        self._turn_busy = True
        self._tts_abort = False
        self.tts_queue.mark_utterance_start(generation)
        duration = event.get("duration_sec", 0.0)
        LOG.info("[event] audio_segment %.2fs", duration)
        self.set_state(AgentState.ASR)
        session = self._asr_session
        try:
            if not session:
                session = self._new_asr_session()
                await session.start()
            result = await session.finalize_samples(event["samples"])
            text = normalize_user_text((result.get("text") or "").strip())
            if text:
                LOG.info("[asr] normalized: %s", text)
                recent_tts = self._speaking or (time.monotonic() - getattr(self, "_last_tts_end_at", 0.0) < 2.0)
                cur_speak = (
                    (getattr(self, "_active_tts_text", "") or "")
                    + " "
                    + (getattr(self, "_last_spoken_turn", "") or "")
                ).strip()
                if recent_tts and cur_speak and is_self_echo(cur_speak, text):
                    LOG.warning(
                        "[asr] detected acoustic echo of assistant speech ('%s' in '%s'), dropping loop",
                        text,
                        cur_speak[:30],
                    )
                    return
                await self._run_llm(
                    text,
                    generation=generation,
                    vad_end_at=float(event.get("_vad_end_at", time.monotonic())),
                )
            else:
                LOG.info("[asr] no text recognized")
        finally:
            if self._asr_session is session:
                self._asr_session = None
            self._speaking = False
            self._turn_busy = False
            self.set_state(AgentState.LISTEN)

    async def _enqueue_speak(
        self,
        text: str,
        tts_state: dict[str, Any],
        *,
        generation: int,
    ) -> bool | None:
        if self._tts_abort or generation != self._active_turn_id:
            return False
        speak = sanitize_tts_text(text)
        if not is_speakable(speak):
            return False
        spoken_key = normalize_spoken_text(speak)
        spoken_keys: set[str] = tts_state.setdefault("spoken_keys", set())
        if spoken_key and spoken_key in spoken_keys:
            LOG.warning("[llm] suppressed repeated streamed clause: %s", speak[:60])
            return None
        if spoken_key:
            spoken_keys.add(spoken_key)
        tts_state["n"] = int(tts_state["n"]) + 1
        spoken_texts: list[str] = tts_state.setdefault("spoken_texts", [])
        spoken_texts.append(speak)
        if self.state != AgentState.TTS:
            self.set_state(AgentState.TTS)
        self._speaking = True
        LOG.info("[event] tts_sentence: %s", speak[:60])
        await self.emit({"type": "tts_sentence", "text": speak})
        await self.tts_queue.enqueue(speak, generation=generation)
        return True

    async def _speak_extracted(self, full: str, *, canned: bool = False, generation: int) -> None:
        """Enqueue every complete sentence in full — no char/sentence cap."""
        tts_state: dict[str, Any] = {"n": 0, "canned": canned, "spoken_keys": set(), "spoken_texts": []}
        sents = extract_speak_sentences(full, max_cjk=99999)
        if not sents:
            return
        LOG.info("[tts] speak plan: %d sentence(s)", len(sents))
        self._active_tts_text = full
        self._last_spoken_turn = full
        for sent in sents:
            for clause in split_tts_clauses(sent):
                if (await self._enqueue_speak(clause, tts_state, generation=generation)) is False:
                    break
        if int(tts_state["n"]) <= 0 or self._tts_abort:
            return
        self.set_state(AgentState.TTS)
        self._speaking = True
        try:
            await self.tts_queue.wait_done(generation=generation)
        finally:
            self._speaking = False
            self._last_tts_end_at = time.monotonic()
        if not self._tts_abort:
            self._listen_cooldown_until = time.monotonic() + self.listen_cooldown_sec
        lat = self.tts_queue.first_play_latency_s
        if lat is not None:
            LOG.info("[tts] utterance first_play=%.2fs (target <4s)", lat)

    async def _prepare_llm_call(self) -> None:
        now = time.monotonic()
        if self._chat_turns and self.history_idle_clear_sec > 0:
            idle = now - self._llm_last_turn_at
            if idle >= self.history_idle_clear_sec:
                LOG.info(
                    "[llm] idle %.0fs >= %.0fs, clearing transcript",
                    idle,
                    self.history_idle_clear_sec,
                )
        try:
            await asyncio.to_thread(llm_clear_history, self.socket_path)
        except Exception as exc:
            LOG.debug("[llm] clear history skipped: %s", exc)

    @staticmethod
    def _datetime_context() -> str:
        """Return a compact Chinese datetime context string for the system prompt."""
        import datetime
        _WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        now = datetime.datetime.now()
        weekday = _WEEKDAYS[now.weekday()]
        hour = now.hour
        if hour < 6:
            period = "凌晨"
        elif hour < 12:
            period = "上午"
        elif hour == 12:
            period = "中午"
        elif hour < 18:
            period = "下午"
        else:
            period = "晚上"
        h12 = hour % 12 or 12
        return (
            f"当前时间：{now.year}年{now.month}月{now.day}日，{weekday}，"
            f"{period}{h12}点{now.minute:02d}分。"
        )

    def _build_llm_prompt(self, user_text: str) -> str:
        prompt = ""
        sys_body = (self.system_prompt or "").strip()
        voice_block = self.voice_settings.describe_for_prompt() if hasattr(self, "voice_settings") and self.voice_settings else ""
        if voice_block:
            sys_body = f"{sys_body}\n\n{voice_block}".strip()
        if sys_body:
            # Prepend live datetime so model can answer time/date questions correctly
            datetime_line = self._datetime_context()
            prompt += f"<|im_start|>system\n{datetime_line}\n{sys_body}<|im_end|>\n"
        if self.history_max_turns > 0:
            for user, assistant in self._chat_turns[-self.history_max_turns :]:
                prompt += f"<|im_start|>user\n{user.strip()}<|im_end|>\n<|im_start|>assistant\n{assistant.strip()}<|im_end|>\n"
        prompt += f"<|im_start|>user\n{user_text.strip()}<|im_end|>\n<|im_start|>assistant\n"
        return prompt

    def _reply_hit_segment_limit(self, reply: dict) -> bool:
        return reply.get("finish_reason") == "length"

    def _record_chat_turn(self, user: str, assistant: str) -> None:
        if self.history_max_turns <= 0:
            self._chat_turns.clear()
            return
        text = clean_llm_reply(user, (assistant or "").strip())
        if not text:
            return
        if self._chat_turns and self._chat_turns[-1][1].strip() == text:
            LOG.warning("[llm] repetition detected in record_turn, wiping history")
            self._chat_turns.clear()
            return
        self._chat_turns.append((user, text))
        if len(self._chat_turns) > self.history_max_turns:
            self._chat_turns = self._chat_turns[-self.history_max_turns :]
        self._llm_last_turn_at = time.monotonic()
        LOG.info("[llm] transcript stored (%d/%d turns)", len(self._chat_turns), self.history_max_turns)

    async def _emit_reply_final(self, text: str) -> None:
        text = (text or "").strip()
        if text:
            await self.emit({"type": "reply_final", "text": text})

    async def _speak_turn(self, text: str, *, generation: int = 0) -> None:
        await self._emit_reply_final(text)
        await self._speak_extracted(text, canned=True, generation=generation)

    def _grab_rtsp_frame(self, url: str, save_path: Path, timeout: float = 3.0) -> bool:
        from orchestrator.rtsp_frame import grab_rtsp_frame

        transport = getattr(self, "camera_rtsp_transport", "tcp") or "tcp"
        size = int(getattr(self, "camera_size", 448))
        return grab_rtsp_frame(
            url,
            save_path,
            timeout=max(float(timeout), 12.0),
            transport=transport,
            size=size,
        )

    def _uses_mediamtx_grab(self) -> bool:
        return uses_mediamtx(getattr(self, "mediamtx_cfg", MediamtxCameraConfig()))

    def _mediamtx_cache_fresh(self) -> bool:
        cfg = getattr(self, "mediamtx_cfg", None)
        return bool(cfg) and mediamtx_cache_fresh(cfg)

    def _sync_preview_from_mediamtx_cache(self) -> bool:
        """WebUI preview: latest mediamtx_latest.jpg → ui/latest_frame.jpg."""
        if not self._uses_mediamtx_grab():
            return False
        ui_path = self.agent_root / "ui" / "latest_frame.jpg"
        if not copy_mediamtx_cache_file(self.mediamtx_cfg, ui_path):
            return False
        try:
            data = ui_path.read_bytes()
            self._latest_camera_bytes = data
            self._latest_camera_time = time.monotonic()
        except OSError:
            return False
        return True

    def _grab_and_prepare_vlm_frame(
        self,
        raw_path: Path,
        vlm_path: Path,
        *,
        timeout: float | None = None,
        force_live: bool = False,
        cache_only: bool = False,
    ) -> tuple[bool, str]:
        """Grab + 448 prep for InternVL see. Returns (ok, source tag)."""
        t_out = float(timeout if timeout is not None else self.camera_timeout)
        size = int(getattr(self, "camera_size", 448))
        if self._uses_mediamtx_grab():
            cfg = self.mediamtx_cfg
            ok, src = grab_mediamtx_vlm_pair(
                cfg,
                raw_path,
                vlm_path,
                timeout=t_out,
                size=size,
                force_live=force_live,
                cache_only=cache_only,
            )
            if ok and vlm_path.is_file():
                data = vlm_path.read_bytes()
                self._latest_camera_bytes = data
                self._latest_camera_time = time.monotonic()
                self._sync_ui_preview_frame(data)
            return ok, src
        ok = self._grab_camera_frame(self.camera_url, raw_path, timeout=t_out, max_cache_age_sec=0.0)
        if not ok:
            return False, "miss"
        prep = self._prepare_vlm_frame(raw_path, vlm_path, size=size)
        return prep, "rtsp_direct" if prep else "miss"

    def _vision_prefers_scene_memory_only(self, user_prompt: str) -> bool:
        """Activity-style questions can answer from memory; desk/object queries need see."""
        if any(k in user_prompt for k in ("重新", "重看", "再看", "刷新", "拍张照", "拍个照")):
            return False
        if any(k in user_prompt for k in ("干什么", "干嘛", "做什么", "在干", "在做")):
            return True
        if self._uses_mediamtx_grab():
            return False
        return bool(str(getattr(self, "_scene_memory", {}).get("caption", "")).strip())

    def _sync_ui_preview_frame(self, data: bytes) -> None:
        try:
            if not preview_jpeg_bytes_valid(data):
                return
            ui_frame_path = self.agent_root / "ui" / "latest_frame.jpg"
            ui_frame_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = ui_frame_path.with_suffix(".part.jpg")
            tmp.write_bytes(data)
            tmp.replace(ui_frame_path)
        except Exception:
            pass

    def _grab_camera_frame(
        self,
        url: str,
        save_path: Path,
        timeout: float = 2.0,
        max_cache_age_sec: float = 3.0,
    ) -> bool:
        try:
            now = time.monotonic()
            grab_backend = getattr(self, "camera_grab_backend", "rtsp")
            if grab_backend.startswith("mediamtx") or grab_backend == "whep":
                mtx = getattr(self, "mediamtx_cfg", None)
                if mtx and mediamtx_cache_fresh(mtx):
                    latest = Path(mtx.latest_frame)
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    data = latest.read_bytes()
                    save_path.write_bytes(data)
                    self._latest_camera_bytes = data
                    self._latest_camera_time = now
                    self._sync_ui_preview_frame(data)
                    LOG.info(
                        "[camera] mediamtx latest_frame hit (age=%.2fs, %d bytes)",
                        mediamtx_cache_age_sec(mtx) or 0,
                        len(data),
                    )
                    return True
            # 1. Zero-wait in-memory cache hit
            if (
                self._latest_camera_bytes
                and (now - self._latest_camera_time) <= max_cache_age_sec
            ):
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(self._latest_camera_bytes)
                LOG.info(
                    "[camera] zero-wait: used in-memory frame (age=%.2fs, size=%d bytes)",
                    now - self._latest_camera_time,
                    len(self._latest_camera_bytes),
                )
                self._sync_ui_preview_frame(self._latest_camera_bytes)
                return True

            data: bytes | None = None
            if grab_backend.startswith("mediamtx") or grab_backend == "whep":
                from orchestrator.mediamtx_camera import grab_mediamtx_frame

                size = int(getattr(self, "camera_size", 448))
                mtx = getattr(self, "mediamtx_cfg", None)
                if mtx and grab_mediamtx_frame(mtx, save_path, timeout=timeout, size=size):
                    data = save_path.read_bytes()
                    LOG.info("[camera] mediamtx grab ok (%d bytes) backend=%s", len(data), grab_backend)
            elif url.startswith("rtsp://"):
                ok = False
                try:
                    self.brain.grab_frame(save_path, rtsp_url=url)
                    if save_path.is_file() and save_path.stat().st_size > 1000:
                        ok = True
                        data = save_path.read_bytes()
                        LOG.info("[camera] grab_camera_frame ok (%d bytes)", len(data))
                except Exception as exc:
                    LOG.warning("[camera] grab_camera_frame failed: %s", exc)
                if not ok:
                    ok = self._grab_rtsp_frame(url, save_path, timeout=timeout)
                    if ok and save_path.is_file():
                        data = save_path.read_bytes()
            elif os.path.exists(url):
                import shutil
                save_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(url, save_path)
                data = save_path.read_bytes()
            else:
                target_url = url.rstrip("/")
                if not target_url.startswith("file://"):
                    if not target_url.endswith(".jpg") and not target_url.endswith(".jpeg"):
                        target_url += "/shot.jpg"
                req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "XiaoLan-CameraClient/1.0"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                if data:
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(data)

            if not data:
                return False

            self._latest_camera_bytes = data
            self._latest_camera_time = now
            self._sync_ui_preview_frame(data)
            return True
        except Exception as exc:
            LOG.warning("[camera] grab frame from %s failed: %s", url, exc)
            return False

    def _prepare_vlm_frame(self, src_path: Path, dst_path: Path, size: int = 448) -> bool:
        try:
            from PIL import Image
            im = Image.open(src_path).convert("RGB")
            w, h = im.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            cropped = im.crop((left, top, left + side, top + side))
            resized = cropped.resize((size, size), Image.BILINEAR)
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            resized.save(dst_path, format="JPEG", quality=92)
            return True
        except Exception as exc:
            LOG.warning("[camera] prepare frame failed: %s", exc)
            return False

    @staticmethod
    def _compute_frame_motion(img_a: Any, img_b: Any) -> float:
        try:
            thumb_a = img_a.resize((64, 64)).convert("L")
            thumb_b = img_b.resize((64, 64)).convert("L")
            bytes_a = thumb_a.tobytes()
            bytes_b = thumb_b.tobytes()
            diff = sum(abs(a - b) for a, b in zip(bytes_a, bytes_b)) / len(bytes_a)
            return float(diff)
        except Exception:
            return 0.0

    async def _proactive_companion_loop(self) -> None:
        """Jarvis proactive companion: observe motion & provide emotional companionship."""
        if not self.camera_enabled or not getattr(self, "proactive_enabled", True):
            LOG.info("[companion] proactive companion loop disabled")
            return

        LOG.info("[companion] proactive companion loop started (interval=%.1fs, threshold=%.1f, cooldown=%.1fs)",
                 self.proactive_interval_sec, self.proactive_motion_threshold, self.proactive_cooldown_sec)

        from PIL import Image
        temp_dir = self.agent_root / "run"
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            temp_dir = Path("/tmp")
        raw_shot_path = temp_dir / "camera_proactive_raw.jpg"

        last_img: Any = None

        while True:
            try:
                await asyncio.sleep(self.proactive_interval_sec)

                # Skip if agent is currently speaking, busy, or listening to user speech
                if self._speaking or self._turn_busy or self.state not in (AgentState.IDLE, AgentState.LISTEN):
                    continue

                # Run camera grab in thread
                grab_ok = await asyncio.to_thread(
                    self._grab_camera_frame, self.camera_url, raw_shot_path, self.camera_timeout
                )
                if not grab_ok or not raw_shot_path.exists():
                    continue

                def _load_and_diff(p: Path, prev: Any) -> tuple[Any, float]:
                    cur = Image.open(p).convert("RGB")
                    m = Orchestrator._compute_frame_motion(prev, cur) if prev is not None else 0.0
                    return cur, m

                cur_img, motion = await asyncio.to_thread(_load_and_diff, raw_shot_path, last_img)
                last_img = cur_img
                await self.emit({"type": "camera_frame", "motion": round(motion, 2), "timestamp": time.time()})

                now = time.monotonic()
                if motion > 1.5:
                    LOG.debug("[companion] motion index: %.2f (thresh=%.1f, cooldown_rem=%.0fs)",
                              motion, self.proactive_motion_threshold,
                              max(0.0, self.proactive_cooldown_sec - (now - self._last_proactive_speak_at)))

                if (
                    motion >= self.proactive_motion_threshold
                    and (now - self._last_proactive_speak_at >= self.proactive_cooldown_sec)
                    and not self._speaking
                    and not self._turn_busy
                ):
                    self._last_proactive_speak_at = now
                    LOG.info("[companion] motion detected (%.2f >= %.2f), triggering proactive interaction",
                             motion, self.proactive_motion_threshold)

                    # Dynamic Jarvis prompt based on time of day
                    import datetime
                    hr = datetime.datetime.now().hour
                    if hr < 6:
                        time_cue = "深夜仍未休息"
                        style_cue = "以顶级私人管家的沉稳从容口吻，适度调侃睡眠与维护的重要性，并极具温度地劝主人保重身体早点休息。"
                    elif hr < 12:
                        time_cue = "上午专注投入"
                        style_cue = "以顶级私人管家的沉稳优雅口吻，肯定主人的专注力，并贴心提醒活动肩颈或准备一杯热饮。"
                    elif hr < 18:
                        time_cue = "下午高强度工作"
                        style_cue = "以顶级私人管家温和从容又带点风趣的口吻，提醒适时补充水分并赞许主人的工作节奏。"
                    else:
                        time_cue = "晚上持续奋战"
                        style_cue = "以顶级私人管家温和忠诚的语气，给予主人坚定的陪伴感与情绪支持，提醒注意劳逸结合。"

                    proactive_prompt = (
                        f"主人正在面前操作设备或打字敲键盘，当前处于{time_cue}状态。"
                        f"请{style_cue}用一句极简自然、充满忠诚陪伴感的纯中文口语直接向主人表达关心。严禁出现任何角色名、电影名或英文，不超过二十五个汉字。"
                    )

                    self._next_turn_id += 1
                    generation = self._next_turn_id
                    self._active_turn_id = generation
                    self._turn_busy = True
                    self._tts_abort = False
                    self.tts_queue.mark_utterance_start(generation)
                    try:
                        await self._run_llm(proactive_prompt, generation=generation, vad_end_at=now, is_companion=True)
                    finally:
                        self._turn_busy = False

            except asyncio.CancelledError:
                LOG.info("[companion] proactive companion loop cancelled")
                break
            except Exception as exc:
                LOG.warning("[companion] exception in proactive loop: %s", exc)
                await asyncio.sleep(self.proactive_interval_sec)

    async def _handle_ws_message(self, raw_msg: str) -> None:
        try:
            data = json.loads(raw_msg)
        except Exception:
            return
        mtype = str(data.get("type", "")).strip().lower()
        if mtype == "settings_get":
            await self.emit(await self._build_settings_snapshot())
        elif mtype == "settings_set":
            await self._apply_settings_patch(data.get("patch") or {})
        elif mtype == "debug_get":
            snap = await asyncio.to_thread(build_debug_snapshot, self)
            snap["text"] = format_debug_snapshot(snap)
            await self.emit(snap)
        elif mtype == "debug_audio":
            result = await handle_debug_audio(self, data)
            result["type"] = "debug_audio_result"
            result.update(self.debug_audio.status())
            await self.emit(result)
        elif mtype in ("chat", "user_message"):
            text = str(data.get("text", "")).strip()
            if text:
                asyncio.create_task(self._handle_direct_chat(text))
        elif mtype in ("snap", "capture"):
            prompt = str(data.get("prompt", "桌面上有什么？")).strip()
            asyncio.create_task(self._handle_manual_snap(user_prompt=prompt))
        elif mtype in ("set_camera_url", "update_camera"):
            url = str(data.get("url", "")).strip()
            if url:
                if "transport" in data:
                    self.camera_rtsp_transport = str(data.get("transport", "tcp")).strip()
                asyncio.create_task(self._apply_camera_url_change(url))
        elif mtype in ("get_status", "status", "ping"):
            await self._broadcast_status()
        elif mtype in ("stop", "abort", "tts_abort"):
            await self._abort_tts_playback()
            self.set_state(AgentState.LISTEN)

    async def _abort_tts_playback(self) -> None:
        self._tts_abort = True
        if hasattr(self, "tts_queue") and self.tts_queue is not None:
            if hasattr(self.tts_queue, "abort"):
                try:
                    res = self.tts_queue.abort()
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
            elif hasattr(self.tts_queue, "interrupt"):
                try:
                    await self.tts_queue.interrupt()
                except Exception:
                    pass

    async def _handle_direct_chat(self, text: str) -> None:
        self._next_turn_id += 1
        generation = self._next_turn_id
        self._active_turn_id = generation
        self._turn_busy = True
        await self._abort_tts_playback()
        self._tts_abort = False
        if hasattr(self.tts_queue, "mark_utterance_start"):
            self.tts_queue.mark_utterance_start(generation)
        try:
            clean_text = normalize_user_text(text)
            if clean_text:
                await self.emit({"type": "asr_final", "text": clean_text, "generation": generation, "source": "web"})
                if self.camera_enabled and self.brain.wants_vision(clean_text):
                    LOG.info("[web] vision intent: %s", clean_text[:48])
                    await self._handle_vision_turn(clean_text, generation=generation)
                else:
                    await self._run_llm(clean_text, generation=generation, vad_end_at=time.monotonic())
        finally:
            self._turn_busy = False
            self.set_state(AgentState.LISTEN)

    async def _handle_manual_snap(self, user_prompt: str = "桌面上有什么？") -> None:
        run_dir = self.agent_root / "run"
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            run_dir = Path("/tmp")
        raw_shot_path = run_dir / "camera_shot.jpg"
        vlm_frame_path = run_dir / "latest_vlm.jpg"

        await self.emit({"type": "vision_start", "query": user_prompt, "generation": 0})
        success, caption = False, ""
        ok, _src = await asyncio.to_thread(
            self._grab_and_prepare_vlm_frame,
            raw_shot_path,
            vlm_frame_path,
            cache_only=self._uses_mediamtx_grab(),
        )
        if ok:
            await self.emit(
                {"type": "camera_frame", "motion": 0, "timestamp": time.time(), "grab_source": _src}
            )
            caption = await self._board_vlm_with_web_tokens(
                vlm_frame_path, user_prompt, generation=0
            )
            success = True
        if success and caption:
            self._save_scene_memory(caption)
            await self.emit({"type": "vision_caption", "caption": caption, "generation": 0, "url": "/latest_frame.jpg"})
        else:
            await self.emit({"type": "vision_error", "error": "camera_unreachable", "generation": 0})

    def _update_mediamtx_rtsp_upstream(self, rtsp_url: str) -> None:
        """Point mediamtx pull at a new camera RTSP URL (WebUI stream switch)."""
        p4 = Path("/userdata/p4")
        env_path = p4 / "config" / "rtsp.env"
        if not env_path.is_file():
            LOG.warning("[camera] no %s — cannot switch mediamtx upstream", env_path)
            return
        lines: list[str] = []
        replaced = False
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("RTSP_URL="):
                lines.append(f"RTSP_URL={rtsp_url}")
                replaced = True
            else:
                lines.append(line)
        if not replaced:
            lines.append(f"RTSP_URL={rtsp_url}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        gen = p4 / "scripts" / "mediamtx_gen_config.sh"
        if gen.is_file():
            subprocess.run(["bash", str(gen)], check=False, timeout=30)
        subprocess.run(["pkill", "-x", "mediamtx"], check=False)
        time.sleep(1)
        mtx_bin = p4 / "bin" / "mediamtx"
        mtx_cfg = p4 / "config" / "mediamtx.yml"
        if mtx_bin.is_file() and mtx_cfg.is_file():
            subprocess.Popen(
                [str(mtx_bin), str(mtx_cfg)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        cache = Path(getattr(self.mediamtx_cfg, "latest_frame", "/userdata/agent/run/mediamtx_latest.jpg"))
        try:
            cache.unlink(missing_ok=True)
        except OSError:
            pass
        LOG.info("[camera] mediamtx upstream -> %s (cache cleared)", rtsp_url)

    async def _apply_camera_url_change(self, url: str) -> None:
        self.camera_url = url
        LOG.info("[ws] camera URL updated to %s (transport=%s)", self.camera_url, self.camera_rtsp_transport)
        local_mediamtx = "127.0.0.1" in url or ":8554/" in url
        if self._uses_mediamtx_grab() and url.startswith("rtsp://") and not local_mediamtx:
            await asyncio.to_thread(self._update_mediamtx_rtsp_upstream, url)
        ok = await asyncio.to_thread(
            self._grab_camera_frame,
            self.camera_url if not self._uses_mediamtx_grab() else self.mediamtx_cfg.rtsp_url,
            self.agent_root / "run" / "camera_test.jpg",
            self.camera_timeout,
            0.0,
        )
        if ok:
            await self.emit({"type": "camera_frame", "motion": 0, "timestamp": time.time()})
        await self.emit(
            {
                "type": "camera_status",
                "url": self.camera_url,
                "transport": self.camera_rtsp_transport,
                "connected": ok,
            }
        )

    async def _test_camera_connection(self) -> None:
        run_dir = self.agent_root / "run"
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            run_dir = Path("/tmp")
        raw_shot_path = run_dir / "camera_test.jpg"
        ok = await asyncio.to_thread(
            self._grab_camera_frame, self.camera_url, raw_shot_path, self.camera_timeout, 0.0
        )
        await self.emit({
            "type": "camera_status",
            "url": self.camera_url,
            "transport": self.camera_rtsp_transport,
            "connected": ok,
        })

    async def _broadcast_status(self) -> None:
        preview_exists = (self.agent_root / "ui" / "latest_frame.jpg").is_file()
        vlm_ready = await asyncio.to_thread(self.ping_llm_daemon)
        asr_backend = "sense_voice"
        cfg = getattr(getattr(self, "asr_engine", None), "config", None)
        if cfg is not None:
            asr_backend = getattr(cfg, "backend", asr_backend)
        await self.emit({
            "type": "status_response",
            "state": self.state.value if hasattr(self.state, "value") else str(self.state),
            "camera_url": self.camera_url,
            "camera_transport": self.camera_rtsp_transport,
            "scene_memory": getattr(self, "_scene_memory", {}),
            "preview_exists": preview_exists,
            "asr_backend": asr_backend,
            "inference_backend": self.inference_backend,
            "llm_socket": self.socket_path,
            "vlm_daemon_ready": vlm_ready,
            "llm_backend": self.inference_backend,
            "camera_grab_backend": getattr(self, "camera_grab_backend", "rtsp"),
            "mediamtx_cache_age_sec": mediamtx_cache_age_sec(self.mediamtx_cfg)
            if self._uses_mediamtx_grab()
            else None,
        })

    async def _board_vlm_with_web_tokens(
        self,
        frame_path: Path,
        prompt: str,
        *,
        generation: int,
    ) -> str:
        """Run board VLM; stream see tokens to WebUI when using P5b vlm_daemon."""
        loop = asyncio.get_running_loop()
        token_queue: asyncio.Queue[str] = asyncio.Queue()
        stream_tokens = self.inference_backend == "vlm_daemon"

        def on_token(piece: str) -> None:
            loop.call_soon_threadsafe(token_queue.put_nowait, piece)

        infer_task = asyncio.create_task(
            asyncio.to_thread(
                self._infer_vlm,
                frame_path,
                prompt,
                on_token if stream_tokens else None,
            )
        )
        if stream_tokens:
            while not infer_task.done() or not token_queue.empty():
                try:
                    piece = await asyncio.wait_for(token_queue.get(), timeout=0.04)
                except asyncio.TimeoutError:
                    continue
                if generation and generation != self._active_turn_id:
                    continue
                await self.emit({"type": "llm_token", "text": piece, "generation": generation})
        return await infer_task

    def _infer_vlm(
        self,
        frame_path: Path,
        user_prompt: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        prompt = user_prompt.strip() or self.camera_prompt

        # 1. Cloud VLM API if configured
        if self.camera_api_url and self.camera_api_key:
            try:
                import base64
                with open(frame_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("ascii")
                endpoint = self.camera_api_url.rstrip("/")
                if not endpoint.endswith("/chat/completions"):
                    endpoint += "/chat/completions"
                payload = {
                    "model": self.camera_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"},
                                },
                            ],
                        }
                    ],
                    "max_tokens": 128,
                    "temperature": 0.2,
                }
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.camera_api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                cap = str(res["choices"][0]["message"]["content"]).strip()
                if cap:
                    return cap
            except Exception as exc:
                LOG.warning("[vision] cloud VLM call failed: %s", exc)

        # 2. Board RKNN VLM (P5b socket or legacy run_board_vlm.sh)
        try:
            LOG.info("[vision] board VLM via xiaolan_cli.brain backend=%s", self.inference_backend)
            if self.brain.unified_vlm:
                cap = self.brain.see_via_socket(
                    frame_path,
                    prompt,
                    on_token=on_token,
                    max_new_tokens=self.camera_see_max_new_tokens,
                )
            else:
                cap = self.brain.board_vlm(frame_path, prompt)
            if cap:
                return cap
        except Exception as exc:
            LOG.warning("[vision] board VLM failed: %s", exc)

        # 3. Fallback: simple natural confirmation
        return "好的，已经拍下当前画面了。"

    def _load_scene_memory(self) -> dict[str, Any]:
        try:
            if hasattr(self, "_scene_memory_file") and self._scene_memory_file.is_file():
                data = json.loads(self._scene_memory_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("caption"):
                    LOG.info("[vision] loaded visual scene memory: %s", data.get("caption"))
                    return data
        except Exception as exc:
            LOG.warning("[vision] failed to load visual scene memory: %s", exc)
        return {}

    def _save_scene_memory(self, caption: str, activity: str = "") -> None:
        try:
            tags: list[str] = []
            for kw in ("电脑", "笔记本", "显示器", "屏幕", "键盘", "鼠标", "水杯", "手机", "书籍", "耳机", "咖啡", "平板"):
                if kw in caption and kw not in tags:
                    tags.append(kw)
            import datetime
            self._scene_memory = {
                "caption": caption,
                "activity": activity or ("正在电脑前专注工作" if any(k in caption for k in ("电脑", "屏幕", "键盘")) else "室内活动"),
                "tags": tags or ["桌面物品"],
                "updated_at": time.monotonic(),
                "time_str": datetime.datetime.now().strftime("%H:%M:%S"),
            }
            if hasattr(self, "_scene_memory_file"):
                self._scene_memory_file.parent.mkdir(parents=True, exist_ok=True)
                self._scene_memory_file.write_text(
                    json.dumps(self._scene_memory, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                LOG.info("[vision] saved visual scene memory: %s", caption)
            if hasattr(self, "event_bus") and hasattr(self, "_loop") and self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.emit({"type": "scene_memory", "memory": self._scene_memory}),
                    self._loop,
                )
        except Exception as exc:
            LOG.warning("[vision] failed to save visual scene memory: %s", exc)

    async def _handle_vision_turn(self, user_prompt: str, *, generation: int) -> None:
        self.set_state(AgentState.LLM)
        await self.emit({"type": "vision_start", "query": user_prompt, "generation": generation})

        is_refresh_query = any(k in user_prompt for k in ("重新", "重看", "再看", "刷新", "拍张照", "拍个照"))
        cached_caption = str(getattr(self, "_scene_memory", {}).get("caption", "")).strip()

        # 1. Scene memory fast path (activity-only when using mediamtx — object queries always see)
        if cached_caption and self._vision_prefers_scene_memory_only(user_prompt):
            LOG.info(
                "[vision] zero-wait: using visual scene memory (%.2fs old): %s",
                time.monotonic() - float(getattr(self, "_scene_memory", {}).get("updated_at", 0.0)),
                cached_caption,
            )
            is_activity_query = any(k in user_prompt for k in ("干什么", "干嘛", "做什么", "在干", "在做", "看我"))
            if is_activity_query:
                activity = getattr(self, "_scene_memory", {}).get("activity")
                if activity:
                    reply = f"主人，我看到您{activity}，面前放有键盘、鼠标和水杯。"
                else:
                    reply = "主人，我看到您正在电脑前编写和调试代码，面前放有键盘、鼠标和水杯。"
            else:
                reply = cached_caption
                if reply.startswith("画面中有一台"):
                    reply = "主人，桌上有一台" + reply[6:]
                elif reply.startswith("画面中有"):
                    reply = "主人，桌上有" + reply[4:]
                elif not reply.startswith("主人") and not reply.startswith("桌上"):
                    reply = f"主人，桌上识别到{reply}"
            await self.emit({"type": "vision_caption", "caption": reply, "generation": generation})
            self._record_chat_turn(user_prompt, reply)
            await self._speak_turn(reply, generation=generation)
            if not self._tts_abort:
                self._listen_cooldown_until = time.monotonic() + self.listen_cooldown_sec
            return

        # No filler TTS before see: WebUI already gets vision_start; board see runs immediately.
        if self._uses_mediamtx_grab():
            age = mediamtx_cache_age_sec(self.mediamtx_cfg)
            if mediamtx_cache_available(self.mediamtx_cfg):
                LOG.info(
                    "[vision] mediamtx cache ready (age=%s) — no wait TTS",
                    f"{age:.2f}s" if age is not None else "?",
                )
            else:
                LOG.info("[vision] mediamtx cache missing — still skip wait TTS, grab then see")

        use_mtx_cache = is_refresh_query and self._uses_mediamtx_grab()
        if use_mtx_cache:
            synced = await asyncio.to_thread(self._sync_preview_from_mediamtx_cache)
            if synced:
                await self.emit(
                    {
                        "type": "camera_frame",
                        "motion": 0,
                        "timestamp": time.time(),
                        "grab_source": "cache",
                    }
                )

        run_dir = self.agent_root / "run"
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            run_dir = Path("/tmp")
        raw_shot_path = run_dir / "camera_shot.jpg"
        vlm_frame_path = run_dir / "latest_vlm.jpg"

        t0 = time.monotonic()
        grab_source = "miss"
        try:
            ok, grab_source = await asyncio.to_thread(
                self._grab_and_prepare_vlm_frame,
                raw_shot_path,
                vlm_frame_path,
                force_live=False,
                cache_only=use_mtx_cache,
            )
            if use_mtx_cache and not ok:
                ok, grab_source = await asyncio.to_thread(
                    self._grab_and_prepare_vlm_frame,
                    raw_shot_path,
                    vlm_frame_path,
                    force_live=False,
                    cache_only=False,
                )
            success, caption = False, ""
            if ok:
                LOG.info("[vision] grab source=%s prep=vlm_frame", grab_source)
                await self.emit(
                    {
                        "type": "camera_frame",
                        "motion": 0,
                        "timestamp": time.time(),
                        "grab_source": grab_source,
                    }
                )
                caption = await self._board_vlm_with_web_tokens(
                    vlm_frame_path, user_prompt, generation=generation
                )
                success = True
        except Exception as exc:
            LOG.error("[vision] exception during vision turn: %s", exc)
            success, caption = False, ""

        if self._tts_abort or generation != self._active_turn_id:
            LOG.info("[vision] turn aborted or superseded")
            return

        if not success:
            LOG.warning("[vision] camera frame grab failed")
            await self.emit({"type": "vision_error", "error": "camera_unreachable", "generation": generation})
            await self._speak_turn("摄像头暂时连接不上，请确认摄像头已打开。", generation=generation)
            return

        if not caption or caption == "好的，已经拍下当前画面了。":
            caption = "画面中未识别到具体物品。"
        else:
            self._save_scene_memory(caption)

        LOG.info(
            "[vision] caption ready in %.2fs (grab=%s): %s",
            time.monotonic() - t0,
            grab_source,
            caption,
        )
        await self.emit({"type": "vision_caption", "caption": caption, "generation": generation})

        if not self._tts_abort and generation == self._active_turn_id:
            self._record_chat_turn(user_prompt, caption)
            await self._speak_turn(caption, generation=generation)
            if not self._tts_abort:
                self._listen_cooldown_until = time.monotonic() + self.listen_cooldown_sec

    async def _run_llm(
        self,
        prompt: str,
        *,
        generation: int,
        vad_end_at: float,
        is_companion: bool = False,
    ) -> None:
        user_prompt = prompt
        self.set_state(AgentState.LLM)

        u_clean = user_prompt.strip()
        normalized = normalize_spoken_text(u_clean)

        if not is_companion:
            if is_resume_command(normalized):
                if getattr(self, "_paused_relay_text", None):
                    relay = self._paused_relay_text
                    self._paused_relay_text = None
                    LOG.info("[relay] resuming playback from paused sentences (%d chars): %s", len(relay), relay[:60])
                    await self._speak_turn(relay, generation=generation)
                    return
                elif not self._chat_turns:
                    await self._speak_turn("随时待命，主人请吩咐。", generation=generation)
                    return

            if is_stop_command(normalized):
                self._paused_relay_text = None
                LOG.info("[llm] user requested stop: %s", u_clean)
                await self._speak_turn("好的，主人。", generation=generation)
                return

            self._paused_relay_text = None

            if len(normalized) <= 1 or (normalized and set(normalized) <= set("啊嗯呃哦呀吧呵哈嘿")):
                LOG.info("[llm] ignored single char or filler noise: %s", u_clean)
                self.set_state(AgentState.LISTEN)
                return

            if self.camera_enabled and is_vision_query(normalized):
                LOG.info("[vision] visual query recognized: %s", u_clean)
                await self._handle_vision_turn(user_prompt, generation=generation)
                return

            voice_reply = self.voice_settings.try_rule_command(user_prompt) if hasattr(self, "voice_settings") and self.voice_settings else None
            if voice_reply is None and is_voice_settings_query(user_prompt):
                LOG.info("[voice] fuzzy voice query (rule miss): %s", user_prompt[:48])
                voice_reply = self.voice_settings.describe_for_user() if hasattr(self, "voice_settings") and self.voice_settings else None
            if voice_reply:
                LOG.info("[voice] rule command: %s", voice_reply[:48])
                await self._sync_tts_from_voice_settings()
                await self._speak_turn(voice_reply, generation=generation)
                self._record_chat_turn(user_prompt, voice_reply)
                return

            if should_skip_llm(user_prompt):
                speak = canned_reply_for(user_prompt) or persona_reply_for(user_prompt)
                LOG.info("[llm] fast-path (skip LLM): %s", speak[:48])
                await self._speak_turn(speak, generation=generation)
                return

        await self._prepare_llm_call()
        prompt = self._build_llm_prompt(user_prompt)
        LOG.info(
            "[llm] hist=%d/%d prompt %d chars · user=%s",
            len(self._chat_turns),
            self.history_max_turns,
            len(prompt),
            user_prompt[:48],
        )
        self._active_tts_text = ""
        loop = asyncio.get_running_loop()
        token_queue: asyncio.Queue[str] = asyncio.Queue()
        splitter = StreamingSentenceSplitter(min_clause_chars=7, max_clause_chars=26)
        self._current_splitter = splitter
        tts_state: dict[str, Any] = {"n": 0, "canned": False, "spoken_keys": set(), "spoken_texts": []}
        first_token_at: float | None = None

        def on_token(piece: str) -> None:
            loop.call_soon_threadsafe(token_queue.put_nowait, piece)

        try:
            reply_parts: list[str] = []
            llm_task = asyncio.create_task(
                asyncio.to_thread(
                    llm_chat_stream,
                    prompt,
                    on_token,
                    sock_path=self.socket_path,
                    max_new_tokens=self.max_new_tokens,
                )
            )
            while not llm_task.done() or not token_queue.empty():
                try:
                    piece = await asyncio.wait_for(token_queue.get(), timeout=0.04)
                except asyncio.TimeoutError:
                    continue
                if self._tts_abort or generation != self._active_turn_id:
                    continue
                if first_token_at is None:
                    first_token_at = time.monotonic()
                self._active_tts_text += piece
                for chunk in splitter.feed(piece):
                    if is_echo_reply(user_prompt, chunk):
                        LOG.warning("[llm] suppressed echo chunk: %s", chunk)
                        continue
                    queued = await self._enqueue_speak(chunk, tts_state, generation=generation)
                    if queued:
                        await self.emit({"type": "llm_token", "text": chunk})

            reply = await llm_task
            reply_parts.append(str(reply.get("text") or ""))
            hit_limit = self._reply_hit_segment_limit(reply)
            if hit_limit:
                LOG.warning(
                    "[llm] RKNN reached the %d-token generation window; not re-prompting because that restarts the answer",
                    self.max_new_tokens,
                )

            if not self._tts_abort and generation == self._active_turn_id:
                for chunk in splitter.finish():
                    if is_echo_reply(user_prompt, chunk):
                        LOG.warning("[llm] suppressed echo chunk: %s", chunk)
                        continue
                    queued = await self._enqueue_speak(chunk, tts_state, generation=generation)
                    if queued:
                        await self.emit({"type": "llm_token", "text": chunk})

            # If we hit the token limit AND the last spoken text was a fragment (no ending
            # punctuation), speak a natural trailing cue so the listener knows more was cut off.
            if (
                hit_limit
                and not self._tts_abort
                and generation == self._active_turn_id
            ):
                spoken: list[str] = tts_state.get("spoken_texts") or []
                last_spoken = spoken[-1] if spoken else ""
                last_spoken_clean = last_spoken.rstrip()
                if last_spoken_clean and not last_spoken_clean.endswith(("。", "！", "？", "…")):
                    LOG.info("[llm] token-limit truncation detected, appending trail cue")
                    trail_cue = "以上是我目前能说的部分，如需了解更多请继续询问。"
                    await self._enqueue_speak(trail_cue, tts_state, generation=generation)

            full = clean_llm_reply(user_prompt, "".join(reply_parts))

            if hasattr(self, "voice_settings") and self.voice_settings:
                full, _settings_applied = self.voice_settings.parse_and_strip_llm_tag(full)
                if _settings_applied:
                    LOG.info("[voice] llm tag applied")
                    await self._sync_tts_from_voice_settings()

            if is_echo_reply(user_prompt, full):
                LOG.warning("[llm] detected echo reply ('%s' -> '%s'), wiping history", user_prompt, full)
                self._chat_turns.clear()
                full = "我没有听清楚，请再说一遍。"
                if int(tts_state["n"]) == 0 and not self._tts_abort:
                    await self._speak_extracted(full, canned=True, generation=generation)

            spoken_texts: list[str] = tts_state["spoken_texts"]
            if spoken_texts:
                full = "".join(spoken_texts)
                self._active_tts_text = full

            self._last_spoken_turn = full

            if not self._tts_abort:
                await self._emit_reply_final(full)

            if int(tts_state["n"]) == 0 and not self._tts_abort:
                speak = persona_reply_for(user_prompt)
                LOG.info("[llm] persona fallback: %s", speak[:48])
                await self._speak_extracted(speak, canned=True, generation=generation)
                full = speak
                self._last_spoken_turn = full
                if not self._tts_abort:
                    await self._emit_reply_final(full)
            elif not self._tts_abort:
                try:
                    await self.tts_queue.wait_done(generation=generation)
                finally:
                    self._speaking = False
                    self._last_tts_end_at = time.monotonic()

            if not self._tts_abort:
                self._listen_cooldown_until = time.monotonic() + self.listen_cooldown_sec
                if full.strip():
                    self._record_chat_turn(user_prompt, full)

            first_play_at = self.tts_queue.first_play_at
            if first_play_at is not None:
                latency = {
                    "type": "latency",
                    "generation": generation,
                    "vad_to_first_token_ms": round(
                        1000 * ((first_token_at or first_play_at) - vad_end_at), 1
                    ),
                    "vad_to_first_play_ms": round(1000 * (first_play_at - vad_end_at), 1),
                }
                await self.emit(latency)
                LOG.info("[latency] turn=%d first_token=%sms first_play=%sms", generation, latency["vad_to_first_token_ms"], latency["vad_to_first_play_ms"])

            LOG.info(
                "[llm] reply (%d chars, ttft=%.3fs): %s",
                len(full),
                reply.get("ttft_s") or 0.0,
                full[:60],
            )
            if self._tts_abort:
                LOG.info("[barge-in] skipped post-abort cooldown")
        except Exception as exc:
            LOG.exception("[llm] request failed (%s): %r", type(exc).__name__, exc)
            await self.emit({"type": "error", "code": "llm_failed"})
            if not self._tts_abort and generation == self._active_turn_id:
                try:
                    await self._speak_turn("音频信号略有微弱，主人请再说一遍。", generation=generation)
                except Exception:
                    LOG.exception("[tts] recovery prompt failed")
        finally:
            self._current_splitter = None

    async def run(self, inject_wav: str | None = None) -> None:
        self._loop = asyncio.get_running_loop()
        (self.agent_root / "run").mkdir(parents=True, exist_ok=True)
        (self.agent_root / "logs").mkdir(parents=True, exist_ok=True)
        self.set_state(AgentState.IDLE)
        self.ping_llm_daemon()
        self.audio_profile.apply_usb_mixer()
        await self.emit(
            {
                "type": "audio_profile",
                "profile_id": self.audio_profile.active.profile_id,
                "label": self.audio_profile.active.label,
                "capture_device": self.audio_profile.active.capture_device,
                "play_script": self.audio_profile.active.play_script,
            }
        )
        await self.tts_queue.start()
        try:
            if self.api_enabled:
                try:
                    self._ws_server = await run_ws_server(
                        self.event_bus,
                        self.api_host,
                        self.api_port,
                        on_message=self._handle_ws_message,
                    )
                except OSError as exc:
                    LOG.warning(
                        "[api] WebSocket bind failed (%s) — voice pipeline continues without WS",
                        exc,
                    )
            await asyncio.gather(
                self.run_vad_loop(inject_wav),
                self.handle_events(),
                self._turn_worker(),
                self._proactive_companion_loop(),
            )
        finally:
            if self._ws_server is not None:
                self._ws_server.close()
                await self._ws_server.wait_closed()
                self._ws_server = None
            await self.tts_queue.stop()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="R1 agent orchestrator (Phase E)")
    parser.add_argument("--config", default="/userdata/agent/config/agent.yaml")
    parser.add_argument("--agent-root", default="/userdata/agent")
    parser.add_argument("--inject-wav", help="offline test: feed wav instead of mic")
    parser.add_argument("--audio-profile", choices=("auto", "board", "fy_sp701"), help="audio I/O profile")
    parser.add_argument("--no-partial", action="store_true", help="disable partial ASR (faster offline test)")
    parser.add_argument("--no-tts", action="store_true", help="skip TTS playback")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    agent_root = Path(args.agent_root)
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))

    cfg = load_yaml(args.config)
    if args.audio_profile:
        cfg["_cli_audio_profile"] = args.audio_profile
    setup_logging(args.log_level)
    LOG.info("=== R1 orchestrator Phase E ===")
    orch = Orchestrator(cfg, agent_root)
    if args.no_partial or args.inject_wav:
        orch.asr_engine.cfg.partial_enabled = False
    if args.no_tts:
        async def _noop_enqueue(text: str, *, generation: int | None = None) -> None:
            LOG.info("[tts] skipped: %s", text[:60])

        async def _noop_wait(generation: int | None = None) -> None:
            return None

        orch.tts_queue.enqueue = _noop_enqueue  # type: ignore[method-assign]
        orch.tts_queue.wait_done = _noop_wait  # type: ignore[method-assign]
    try:
        asyncio.run(orch.run(inject_wav=args.inject_wav))
    except KeyboardInterrupt:
        LOG.info("stopped")


if __name__ == "__main__":
    main()
