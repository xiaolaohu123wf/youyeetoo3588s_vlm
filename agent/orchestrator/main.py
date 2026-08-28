"""Asyncio orchestrator — Phase E: voice pipeline + WebSocket event API."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

_AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

from api.event_bus import EventBus
from api.ws_server import run_ws_server
from audio.audio_profile import AudioProfileManager
from asr.asr_engine import AsrEngine, AsrEngineConfig
from asr.normalize import normalize_user_text
from asr.sense_voice import SenseVoiceConfig
from asr.sherpa_streaming_asr import StreamingParaformerConfig
from asr.vad_stream import VadConfig, VadStream
from llm.client import llm_chat_stream, llm_clear_history, llm_ping
from orchestrator.config_loader import load_yaml
from orchestrator.events import AgentState
from settings.store import UserSettingsStore
from tts.sentence_split import (
    canned_reply_for,
    clean_llm_reply,
    extract_speak_sentences,
    is_off_topic_reply,
    is_robotic_reply,
    is_spurious_name_reply,
    is_speakable,
    persona_reply_for,
    sanitize_tts_text,
    should_skip_llm,
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
    def __init__(self, cfg: dict[str, Any], agent_root: Path) -> None:
        self.cfg = cfg
        self.agent_root = agent_root
        self.state = AgentState.IDLE
        self.vad_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._turn_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._asr_session = None
        self._listen_cooldown_until = 0.0
        self._turn_busy = False
        self._speaking = False
        self._tts_abort = False
        self._vad_restart = asyncio.Event()

        vad_cfg = cfg.get("vad") or {}
        asr_cfg = cfg.get("asr") or {}
        tts_cfg = cfg.get("tts") or {}
        api_cfg = cfg.get("api") or {}
        paths = cfg.get("paths") or {}
        barge_cfg = cfg.get("barge_in") or {}

        self.event_bus = EventBus()
        self.api_enabled = str(api_cfg.get("enabled", "true")).lower() not in ("0", "false", "no")
        self.api_host = str(api_cfg.get("host", "127.0.0.1"))
        self.api_port = int(api_cfg.get("port", 8765))
        self.barge_in_enabled = str(barge_cfg.get("enabled", "true")).lower() not in ("0", "false", "no")
        self.barge_in_min_sec = float(barge_cfg.get("min_speech_sec", 0.35))

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
            asyncio.create_task(self.emit({"type": "state", "value": new.value}))

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
        async def on_partial(text: str) -> None:
            LOG.info("[event] asr_partial: %s", text)
            await self.emit({"type": "asr_partial", "text": text})

        async def on_final(text: str, meta: dict) -> None:
            LOG.info("[event] asr_final: %s", text or meta.get("status"))
            await self.emit({"type": "asr_final", "text": text, "meta": meta})

        self._asr_session = self.asr_engine.create_session(on_partial, on_final)
        return self._asr_session

    async def _interrupt_tts(self) -> None:
        if not self._speaking:
            return
        LOG.info("[barge-in] interrupt TTS playback")
        self._tts_abort = True
        self._listen_cooldown_until = 0.0
        await self.tts_queue.interrupt()
        await self.emit({"type": "barge_in", "phase": "tts"})

    async def handle_ws_message(self, text: str) -> None:
        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            return
        mtype = msg.get("type")
        if mtype == "settings_get":
            await self.emit(await self._build_settings_snapshot())
        elif mtype == "settings_set":
            await self._apply_settings_patch(msg.get("patch") or {})

    def _can_hot_swap_audio(self) -> bool:
        return (
            not self._turn_busy
            and not self._speaking
            and self.state in (AgentState.IDLE, AgentState.LISTEN)
        )

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
                break
        finally:
            await self.vad_queue.put({"type": "shutdown"})

    async def _turn_worker(self) -> None:
        while True:
            event = await self._turn_queue.get()
            try:
                await self._process_turn(event)
            finally:
                self._turn_queue.task_done()

    async def handle_events(self) -> None:
        self.set_state(AgentState.LISTEN)
        while True:
            event = await self.vad_queue.get()
            etype = event.get("type")
            if etype == "shutdown":
                LOG.info("[event] shutdown")
                break
            if etype == "error":
                LOG.error("[event] %s", event)
                continue
            if etype == "speech_start":
                LOG.info("[event] speech_start")
                if self.barge_in_enabled and self._speaking:
                    await self._interrupt_tts()
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
                if self._turn_busy and not self._speaking:
                    LOG.info("[vad] busy ASR/LLM, drop %.2fs segment", duration)
                    continue
                if (
                    not self._speaking
                    and time.monotonic() < self._listen_cooldown_until
                    and duration < self.listen_cooldown_skip_max_sec
                ):
                    LOG.info("[vad] post-tts cooldown, skip short %.2fs segment", duration)
                    continue
                if self.barge_in_enabled and self._speaking:
                    if duration < self.barge_in_min_sec:
                        LOG.info("[barge-in] segment too short (%.2fs), skip", duration)
                        continue
                    await self._interrupt_tts()
                await self._turn_queue.put(event)

    async def _process_turn(self, event: dict[str, Any]) -> None:
        self._turn_busy = True
        self._tts_abort = False
        self.tts_queue.mark_utterance_start()
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
                await self._run_llm(text)
            else:
                LOG.info("[asr] no text recognized")
        finally:
            if self._asr_session is session:
                self._asr_session = None
            self._speaking = False
            self._turn_busy = False
            self.set_state(AgentState.LISTEN)

    async def _enqueue_speak(self, text: str, tts_state: dict[str, int | bool]) -> bool:
        if self._tts_abort:
            return False
        speak = sanitize_tts_text(text)
        if not is_speakable(speak):
            return False
        tts_state["n"] = int(tts_state["n"]) + 1
        LOG.info("[event] tts_sentence: %s", speak[:60])
        await self.emit({"type": "tts_sentence", "text": speak})
        await self.tts_queue.enqueue(speak)
        return True

    async def _speak_extracted(self, full: str, *, canned: bool = False) -> None:
        """Enqueue every complete sentence in full — no char/sentence cap."""
        tts_state: dict[str, int | bool] = {"n": 0, "canned": canned}
        sents = extract_speak_sentences(full, max_cjk=99999)
        if not sents:
            return
        LOG.info("[tts] speak plan: %d sentence(s)", len(sents))
        for sent in sents:
            if not await self._enqueue_speak(sent, tts_state):
                break
        if int(tts_state["n"]) <= 0 or self._tts_abort:
            return
        self.set_state(AgentState.TTS)
        self._speaking = True
        try:
            await self.tts_queue.wait_done()
        finally:
            self._speaking = False
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
                self._chat_turns.clear()
        await asyncio.to_thread(llm_clear_history, self.socket_path)

    def _build_llm_prompt(self, user_text: str) -> str:
        parts: list[str] = []
        system = self.system_prompt
        voice_block = self.voice_settings.describe_for_prompt()
        if system and voice_block:
            parts.append(f"{system}\n\n{voice_block}")
        elif system:
            parts.append(system)
        elif voice_block:
            parts.append(voice_block)
        for user, assistant in self._chat_turns[-self.history_max_turns :]:
            parts.append(f"用户：{user}\n小揽：{assistant}")
        parts.append(f"用户：{user_text}\n小揽：")
        return "\n\n".join(parts)

    def _record_chat_turn(self, user: str, assistant: str) -> None:
        text = clean_llm_reply(user, (assistant or "").strip())
        if not text:
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

    async def _speak_turn(self, text: str) -> None:
        await self._emit_reply_final(text)
        await self._speak_extracted(text, canned=True)

    async def _run_llm(self, prompt: str) -> None:
        user_prompt = prompt
        self.set_state(AgentState.LLM)

        voice_reply = self.voice_settings.try_rule_command(user_prompt)
        if voice_reply is None and is_voice_settings_query(user_prompt):
            LOG.info("[voice] fuzzy voice query (rule miss): %s", user_prompt[:48])
            voice_reply = self.voice_settings.describe_for_user()
        if voice_reply:
            LOG.info("[voice] rule command: %s", voice_reply[:48])
            await self._sync_tts_from_voice_settings()
            await self._emit_reply_final(voice_reply)
            await self._speak_extracted(voice_reply, canned=True)
            self._record_chat_turn(user_prompt, voice_reply)
            return

        if should_skip_llm(user_prompt):
            speak = canned_reply_for(user_prompt) or persona_reply_for(user_prompt)
            LOG.info("[llm] fast-path (skip LLM): %s", speak[:48])
            await self._emit_reply_final(speak)
            await self._speak_extracted(speak, canned=True)
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
        buffer = {"text": ""}
        turn_tainted = {"v": False}
        loop = asyncio.get_running_loop()

        def on_token(piece: str) -> None:
            if self._tts_abort:
                return
            buffer["text"] += piece
            if is_robotic_reply(buffer["text"], user_prompt):
                turn_tainted["v"] = True
            asyncio.run_coroutine_threadsafe(
                self.emit({"type": "llm_token", "text": piece}),
                loop,
            )

        try:
            reply = await asyncio.to_thread(
                llm_chat_stream,
                prompt,
                on_token,
                sock_path=self.socket_path,
                max_new_tokens=self.max_new_tokens,
            )
            raw = reply["text"]
            full = clean_llm_reply(user_prompt, raw)
            if len(full) + 20 < len(raw.strip()):
                LOG.info("[llm] stripped transcript echo (%d -> %d chars)", len(raw.strip()), len(full))
            spoken, _settings_applied = self.voice_settings.parse_and_strip_llm_tag(full)
            if _settings_applied:
                LOG.info("[voice] llm tag applied")
                await self._sync_tts_from_voice_settings()
            need_fallback = (
                not spoken.strip()
                or turn_tainted["v"]
                or is_robotic_reply(spoken, user_prompt)
                or is_spurious_name_reply(user_prompt, spoken)
                or is_off_topic_reply(user_prompt, spoken)
            )
            spoken_out = ""
            if not self._tts_abort and need_fallback:
                await self.tts_queue.discard_pending()
                speak = persona_reply_for(user_prompt)
                spoken_out = speak
                LOG.info("[llm] persona fallback: %s", speak[:48])
                await self._emit_reply_final(spoken_out)
                await self._speak_extracted(speak, canned=True)
            elif not self._tts_abort:
                spoken_out = spoken
                await self._emit_reply_final(spoken_out)
                await self._speak_extracted(spoken, canned=False)
            if not self._tts_abort and spoken_out.strip():
                self._record_chat_turn(user_prompt, spoken_out)
            LOG.info(
                "[llm] reply (%d chars, ttft=%.3fs): %s",
                len(spoken),
                reply.get("ttft_s") or 0,
                spoken[:120],
            )
            if self._tts_abort:
                LOG.info("[barge-in] skipped post-abort cooldown")
        except OSError as exc:
            LOG.error("[llm] request failed: %s", exc)

    async def run(self, inject_wav: str | None = None) -> None:
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
        if self.api_enabled:
            try:
                await run_ws_server(
                    self.event_bus,
                    self.api_host,
                    self.api_port,
                    on_message=self.handle_ws_message,
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
        )


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
        async def _noop_enqueue(text: str) -> None:
            LOG.info("[tts] skipped: %s", text[:60])

        async def _noop_wait() -> None:
            return None

        orch.tts_queue.enqueue = _noop_enqueue  # type: ignore[method-assign]
        orch.tts_queue.wait_done = _noop_wait  # type: ignore[method-assign]
    try:
        asyncio.run(orch.run(inject_wav=args.inject_wav))
    except KeyboardInterrupt:
        LOG.info("stopped")


if __name__ == "__main__":
    main()
