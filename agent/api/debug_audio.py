"""Debug-panel manual record / playback / mic passthrough (no ASR/TTS)."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)
VOICE_SCRIPTS = Path("/userdata/voice/scripts")
SAMPLE_RATE = 16000


class DebugAudioController:
    """Exclusive ALSA access for developer audio tests."""

    def __init__(self, agent: Any) -> None:
        self._agent = agent
        self._passthrough_arecord: asyncio.subprocess.Process | None = None
        self._passthrough_aplay: asyncio.subprocess.Process | None = None
        self._recording = False

    @property
    def wav_path(self) -> Path:
        return self._agent.agent_root / "run" / "debug_manual.wav"

    @property
    def passthrough_active(self) -> bool:
        return self._passthrough_arecord is not None

    async def _wait_arecord_idle(self, timeout: float = 3.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if subprocess.run(["pgrep", "-x", "arecord"], capture_output=True).returncode != 0:
                return
            await asyncio.sleep(0.1)

    async def acquire(self) -> None:
        agent = self._agent
        if agent._speaking:
            await agent.tts_queue.interrupt()
        agent._debug_vad_paused = True
        agent.vad_stream.stop()
        agent._vad_restart.set()
        await asyncio.sleep(0.5)
        await self._wait_arecord_idle()

    async def release(self) -> None:
        if self.passthrough_active:
            return
        agent = self._agent
        agent._debug_vad_paused = False
        agent._vad_restart.set()
        LOG.info("[debug-audio] released mic — VAD will resume")
        await asyncio.sleep(0.5)
        agent._vad_restart.set()

    async def _analyze_wav(self, path: Path) -> dict[str, Any]:
        script = VOICE_SCRIPTS / "analyze_wav.py"
        if not script.is_file() or not path.is_file():
            return {"path": str(path), "exists": path.is_file()}
        proc = await asyncio.create_subprocess_exec(
            "python3",
            str(script),
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        text = (stdout or b"").decode(errors="replace").strip()
        lines = text.splitlines()
        analysis: dict[str, Any] = {"path": str(path), "lines": lines}
        for line in lines:
            if line.startswith("samples="):
                analysis["summary"] = line
            if line.startswith("VERDICT:"):
                analysis["verdict"] = line.replace("VERDICT:", "").strip()
        if proc.returncode != 0 and stderr:
            analysis["error"] = stderr.decode(errors="replace").strip()
        return analysis

    def _capture_cmd(self, *, wav_out: Path | None = None, duration_sec: float | None = None) -> list[str]:
        cfg = self._agent.vad_config
        active = self._agent.audio_profile.active
        cmd = [
            "arecord",
            "-q",
            "-D",
            cfg.alsa_device,
            "-f",
            "S16_LE",
            "-r",
            str(SAMPLE_RATE),
            "-c",
            str(active.capture_channels),
        ]
        if duration_sec is not None:
            cmd.extend(["-d", f"{duration_sec:.2f}"])
        if wav_out is not None:
            cmd.append(str(wav_out))
        else:
            cmd.extend(["-t", "raw"])
        if active.pasuspender:
            return ["pasuspender", "--", *cmd]
        return cmd

    def _playback_cmd(self, *, raw_stdin: bool = False) -> list[str]:
        device = self._agent.vad_config.alsa_device
        cmd = [
            "aplay",
            "-q",
            "-D",
            device,
            "-f",
            "S16_LE",
            "-r",
            str(SAMPLE_RATE),
            "-c",
            str(self._agent.audio_profile.active.capture_channels),
        ]
        if raw_stdin:
            cmd.extend(["-t", "raw"])
        return cmd

    async def record(self, seconds: float = 5.0) -> dict[str, Any]:
        if self._recording:
            return {"ok": False, "error": "busy", "message": "正在录音，请稍候"}
        if self.passthrough_active:
            await self.stop_passthrough()

        seconds = max(1.0, min(30.0, float(seconds)))
        self.wav_path.parent.mkdir(parents=True, exist_ok=True)
        self._recording = True
        try:
            await self.acquire()
            self._agent.audio_profile.apply_usb_mixer()
            cmd = self._capture_cmd(wav_out=self.wav_path, duration_sec=seconds)
            LOG.info("[debug-audio] record %.1fs -> %s", seconds, self.wav_path)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                return {"ok": False, "error": "record_failed", "message": err or f"exit {proc.returncode}"}
            analysis = await self._analyze_wav(self.wav_path)
            return {
                "ok": True,
                "action": "record",
                "seconds": seconds,
                "wav": str(self.wav_path),
                "analysis": analysis,
                "message": analysis.get("verdict") or analysis.get("summary") or "录音完成",
            }
        finally:
            self._recording = False
            await self.release()

    async def play(self) -> dict[str, Any]:
        if not self.wav_path.is_file():
            return {"ok": False, "error": "no_recording", "message": "尚无录音，请先录音"}
        if self.passthrough_active:
            await self.stop_passthrough()

        await self.acquire()
        try:
            self._agent.audio_profile.apply_usb_mixer()
            play_script = self._agent.audio_profile.play_script()
            env = os.environ.copy()
            env.update(self._agent.audio_profile.playback_env())
            env["PLAYBACK_AGENT_TTS"] = "1"
            LOG.info("[debug-audio] play %s", self.wav_path)
            proc = await asyncio.create_subprocess_exec(
                "bash",
                str(play_script),
                str(self.wav_path),
                "monitor",
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                return {"ok": False, "error": "play_failed", "message": err or f"exit {proc.returncode}"}
            analysis = await self._analyze_wav(self.wav_path)
            return {
                "ok": True,
                "action": "play",
                "wav": str(self.wav_path),
                "analysis": analysis,
                "message": "回放完成",
            }
        finally:
            await self.release()

    async def start_passthrough(self) -> dict[str, Any]:
        if self.passthrough_active:
            return {
                "ok": True,
                "action": "passthrough_start",
                "passthrough": True,
                "message": "直通对话进行中（麦克风 → 喇叭，无 ASR/TTS）",
            }
        if self._recording:
            return {"ok": False, "error": "busy", "message": "正在录音，无法开启直通"}

        await self.acquire()
        self._agent.audio_profile.apply_usb_mixer()
        try:
            arecord_cmd = self._capture_cmd()
            aplay_cmd = self._playback_cmd(raw_stdin=True)
            LOG.info("[debug-audio] passthrough start %s", self._agent.vad_config.alsa_device)
            self._passthrough_arecord = await asyncio.create_subprocess_exec(
                *arecord_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert self._passthrough_arecord.stdout is not None
            self._passthrough_aplay = await asyncio.create_subprocess_exec(
                *aplay_cmd,
                stdin=self._passthrough_arecord.stdout,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._passthrough_arecord.stdout.close()
            await asyncio.sleep(0.3)
            if self._passthrough_arecord.returncode is not None:
                err = await self._passthrough_arecord.stderr.read() if self._passthrough_arecord.stderr else b""
                await self._cleanup_passthrough()
                await self.release()
                return {
                    "ok": False,
                    "error": "passthrough_failed",
                    "message": err.decode(errors="replace").strip() or "arecord 退出",
                }
            return {
                "ok": True,
                "action": "passthrough_start",
                "passthrough": True,
                "message": "直通对话已开启：对着麦克风说话即可从喇叭听到（无 ASR/TTS/LLM）",
            }
        except OSError as exc:
            await self._cleanup_passthrough()
            await self.release()
            return {"ok": False, "error": "passthrough_failed", "message": str(exc)}

    async def _cleanup_passthrough(self) -> None:
        for proc in (self._passthrough_arecord, self._passthrough_aplay):
            if proc is None:
                continue
            if proc.returncode is None:
                proc.terminate()
                with contextlib.suppress(asyncio.TimeoutError, ProcessLookupError):
                    await asyncio.wait_for(proc.wait(), timeout=1.0)
        self._passthrough_arecord = None
        self._passthrough_aplay = None

    async def stop_passthrough(self) -> dict[str, Any]:
        if not self.passthrough_active:
            return {
                "ok": True,
                "action": "passthrough_stop",
                "passthrough": False,
                "message": "直通未开启",
            }
        LOG.info("[debug-audio] passthrough stop")
        await self._cleanup_passthrough()
        await self.release()
        return {
            "ok": True,
            "action": "passthrough_stop",
            "passthrough": False,
            "message": "直通对话已停止，语音助手将恢复聆听",
        }

    def status(self) -> dict[str, Any]:
        return {
            "recording": self._recording,
            "passthrough": self.passthrough_active,
            "wav_exists": self.wav_path.is_file(),
            "wav_path": str(self.wav_path),
        }


async def handle_debug_audio(agent: Any, msg: dict[str, Any]) -> dict[str, Any]:
    ctrl: DebugAudioController = agent.debug_audio
    action = str(msg.get("action") or "").strip()
    if action == "record":
        return await ctrl.record(float(msg.get("seconds", 5)))
    if action == "play":
        return await ctrl.play()
    if action == "passthrough_start":
        return await ctrl.start_passthrough()
    if action == "passthrough_stop":
        return await ctrl.stop_passthrough()
    if action == "status":
        return {"ok": True, "action": "status", **ctrl.status()}
    return {"ok": False, "error": "unknown_action", "message": f"未知 action: {action}"}