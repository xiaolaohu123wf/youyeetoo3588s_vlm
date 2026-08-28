"""Offline TTS — persistent sherpa C API (Matcha/VITS) with CLI fallback."""
from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

LOG = logging.getLogger(__name__)
VOICE_SCRIPTS = Path("/userdata/voice/scripts")


@dataclass
class TtsConfig:
    backend: str = "matcha"
    model_dir: str = "/userdata/voice/matcha-icefall-zh-baker"
    model_file: str = "model.onnx"
    vocoder: str = "/userdata/voice/vocos-22khz-univ.onnx"
    rule_fsts: list[str] = field(default_factory=list)
    sherpa_bin: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline-tts"
    sherpa_lib: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib"
    num_threads: int = 2
    sid: int = 0
    speed: float = 1.0
    noise_scale: float = 0.667
    max_chars: int = 80
    out_wav: str = "/userdata/agent/run/agent_tts_out.wav"


class TtsEngine:
    def __init__(self, cfg: TtsConfig | None = None) -> None:
        self.cfg = cfg or TtsConfig()
        self.model_dir = Path(self.cfg.model_dir)
        self._native: object | None = None
        self._play_proc: subprocess.Popen[bytes] | None = None
        self._play_lock = threading.Lock()
        self._play_stopped = False
        self._init_native()

    def _init_native(self) -> None:
        try:
            from tts.sherpa_tts import SherpaOfflineTts, SherpaTtsConfig

            self._native = SherpaOfflineTts(
                SherpaTtsConfig(
                    backend=self.cfg.backend,
                    model_dir=str(self.model_dir),
                    model_file=self.cfg.model_file,
                    vocoder=self.cfg.vocoder,
                    rule_fsts=list(self.cfg.rule_fsts),
                    sherpa_lib=self.cfg.sherpa_lib,
                    num_threads=self.cfg.num_threads,
                    sid=self.cfg.sid,
                    speed=self.cfg.speed,
                    noise_scale=self.cfg.noise_scale,
                )
            )
            LOG.info("[tts] loaded %s model (persistent C API)", self.cfg.backend)
        except Exception as exc:
            self._native = None
            LOG.warning("[tts] persistent engine unavailable (%s), using CLI", exc)

    def reconfigure(self, cfg: TtsConfig) -> None:
        prev = self.cfg
        self.cfg = cfg
        self.model_dir = Path(cfg.model_dir)
        reload = (
            prev.backend != cfg.backend
            or prev.model_dir != cfg.model_dir
            or prev.model_file != cfg.model_file
            or prev.sid != cfg.sid
            or prev.vocoder != cfg.vocoder
            or list(prev.rule_fsts) != list(cfg.rule_fsts)
        )
        if self._native is not None:
            if reload:
                self._native.close()  # type: ignore[union-attr]
                self._native = None
                self._init_native()
            else:
                self._native.cfg.speed = cfg.speed  # type: ignore[union-attr]
                self._native.cfg.noise_scale = cfg.noise_scale  # type: ignore[union-attr]
        elif reload:
            self._init_native()

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        lib = self.cfg.sherpa_lib
        env["LD_LIBRARY_PATH"] = lib + (f":{env['LD_LIBRARY_PATH']}" if env.get("LD_LIBRARY_PATH") else "")
        return env

    def _rule_fsts_str(self) -> str:
        return ",".join(self.cfg.rule_fsts)

    def synthesize(self, text: str, out_path: str | None = None) -> Path:
        text = text.strip()
        if not text:
            raise ValueError("empty TTS text")
        if len(text) > self.cfg.max_chars:
            text = text[: self.cfg.max_chars]
            LOG.info("[tts] truncated to %d chars", self.cfg.max_chars)

        out = Path(out_path or self.cfg.out_wav)
        if self._native is not None:
            return self._native.synthesize_to_wav(text, out)  # type: ignore[union-attr]

        cmd: list[str] = [self.cfg.sherpa_bin]
        if self.cfg.backend == "matcha":
            cmd.extend(
                [
                    f"--matcha-acoustic-model={self.model_dir / 'model-steps-3.onnx'}",
                    f"--matcha-vocoder={self.cfg.vocoder}",
                    f"--matcha-lexicon={self.model_dir / 'lexicon.txt'}",
                    f"--matcha-tokens={self.model_dir / 'tokens.txt'}",
                    f"--matcha-dict-dir={self.model_dir / 'dict'}",
                    f"--matcha-length-scale={1.0 / max(self.cfg.speed, 0.1)}",
                ]
            )
            if self.cfg.rule_fsts:
                cmd.append(f"--tts-rule-fsts={self._rule_fsts_str()}")
        else:
            cmd.extend(
                [
                    f"--vits-model={self.model_dir / self.cfg.model_file}",
                    f"--vits-tokens={self.model_dir / 'tokens.txt'}",
                    f"--vits-lexicon={self.model_dir / 'lexicon.txt'}",
                ]
            )
            dict_dir = self.model_dir / "dict"
            if dict_dir.is_dir():
                cmd.append(f"--vits-dict-dir={dict_dir}")
            if self.cfg.rule_fsts:
                cmd.append(f"--tts-rule-fsts={self._rule_fsts_str()}")
        cmd.extend(
            [
                f"--sid={self.cfg.sid}",
                f"--num-threads={self.cfg.num_threads}",
                f"--output-filename={out}",
                text,
            ]
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self._env())
        if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"TTS synth failed: {proc.stderr[-400:]}")
        return out

    def play(
        self,
        wav_path: Path,
        *,
        continuation: bool = False,
        last_in_utterance: bool = True,
        utterance_gain: float | None = None,
    ) -> float | None:
        play_script = VOICE_SCRIPTS / "play_wav.sh"
        env = os.environ.copy()
        env["PLAYBACK_AGENT_TTS"] = "1"
        env.setdefault("PLAYBACK_BUFFER_US", "160000")
        if continuation:
            env["PLAYBACK_CONTINUATION"] = "1"
            env["PLAYBACK_WARMUP_SEC"] = "0"
            env["PLAYBACK_LEAD_MS"] = "0"
            env["PLAYBACK_FADE_MS"] = "0"
            env["PLAYBACK_TRIM_MS"] = "0"
            env["PLAYBACK_FADE_OUT_MS"] = "0"
        else:
            env["PLAYBACK_WARMUP_SEC"] = env.get("PLAYBACK_WARMUP_SEC", "0.08")
            env["PLAYBACK_LEAD_MS"] = env.get("PLAYBACK_LEAD_MS", "80")
            env["PLAYBACK_FADE_MS"] = env.get("PLAYBACK_FADE_MS", "12")
            env["PLAYBACK_FADE_OUT_MS"] = env.get("PLAYBACK_FADE_OUT_MS", "20")
        if not last_in_utterance:
            env["VOICE_RESTORE_MIC"] = "0"
        if utterance_gain is not None:
            env["PLAYBACK_FIXED_GAIN"] = f"{utterance_gain:.4f}"
        with self._play_lock:
            self._play_stopped = False
            self._play_proc = subprocess.Popen(
                ["bash", str(play_script), str(wav_path)],
                env=env,
                start_new_session=True,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc = self._play_proc
        assert proc is not None
        _, stderr = proc.communicate()
        rc = proc.returncode
        with self._play_lock:
            self._play_proc = None
            stopped = self._play_stopped
        if stopped:
            LOG.info("[tts] playback stopped (barge-in)")
            return None
        if rc != 0:
            raise RuntimeError(f"play_wav exited {rc}: {stderr[-400:]}")
        m = re.search(r"gain=([\d.]+)", stderr)
        return float(m.group(1)) if m else None

    def stop_playback(self) -> None:
        with self._play_lock:
            self._play_stopped = True
            proc = self._play_proc
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=1.0)

    def speak(self, text: str) -> None:
        LOG.info("[tts] speak: %s", text[:80])
        wav = self.synthesize(text)
        self.play(wav, last_in_utterance=True)
