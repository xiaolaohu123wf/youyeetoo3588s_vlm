"""Always-on mic + Silero VAD event stream."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

from asr.audio_util import collect_stream_prefix, int16_bytes_to_float32, read_wav_float32
from asr.mic_capture import arm_mic, mic_route_guard, open_arecord
from asr.sherpa_vad import SherpaVad, SherpaVadError

LOG = logging.getLogger(__name__)


@dataclass
class _StreamChunk:
    start: int
    samples: list[float]


@dataclass
class VadConfig:
    model_path: str
    sherpa_lib: str
    sample_rate: int = 16000
    chunk_ms: int = 100
    threshold: float = 0.5
    min_silence_duration: float = 0.4
    min_speech_duration: float = 0.25
    max_speech_duration: float = 30.0
    alsa_device: str = "plughw:0,0"
    capture_channels: int = 1
    min_segment_sec: float = 0.5
    speech_preroll_ms: int = 400
    arecord_period_size: int = 320
    arecord_buffer_size: int = 2560
    mic_capture_gain: int = 6
    mic_arm: bool = True
    route_guard: bool = True
    pasuspender: bool = False

    @property
    def chunk_samples(self) -> int:
        return int(self.sample_rate * self.chunk_ms / 1000)

    @property
    def preroll_samples(self) -> int:
        return int(self.sample_rate * self.speech_preroll_ms / 1000)


class VadStream:
    """Feed mic PCM into sherpa Silero VAD; push events to asyncio.Queue."""

    def __init__(self, cfg: VadConfig, queue: asyncio.Queue[Any]) -> None:
        self.cfg = cfg
        self.queue = queue
        self._stop = asyncio.Event()
        self._history: deque[_StreamChunk] = deque()
        self._stream_total = 0
        keep_sec = max(30.0, cfg.max_speech_duration + 5.0)
        self._history_keep = cfg.preroll_samples + int(cfg.sample_rate * keep_sec)

    def _append_stream(self, samples: list[float]) -> None:
        if not samples:
            return
        self._history.append(_StreamChunk(self._stream_total, samples))
        self._stream_total += len(samples)
        min_start = max(0, self._stream_total - self._history_keep)
        while len(self._history) > 1:
            first = self._history[0]
            if first.start + len(first.samples) <= min_start:
                self._history.popleft()
            else:
                break

    def _prefix_before(self, end_index: int) -> list[float]:
        chunks = [(c.start, c.samples) for c in self._history]
        return collect_stream_prefix(
            chunks,
            end_index,
            max_samples=self.cfg.preroll_samples,
        )

    def stop(self) -> None:
        self._stop.set()

    async def run_live(self) -> None:
        guard_task: asyncio.Task[None] | None = None
        guard_stop = asyncio.Event()
        if self.cfg.mic_arm:
            arm_mic(mic_gain=self.cfg.mic_capture_gain)
        if self.cfg.route_guard:
            guard_task = asyncio.create_task(
                mic_route_guard(guard_stop, mic_gain=self.cfg.mic_capture_gain)
            )
        proc = await open_arecord(
            device=self.cfg.alsa_device,
            sample_rate=self.cfg.sample_rate,
            channels=self.cfg.capture_channels,
            period_size=self.cfg.arecord_period_size,
            buffer_size=self.cfg.arecord_buffer_size,
            pasuspender=self.cfg.pasuspender,
        )
        try:
            await self._consume_arecord(proc)
        finally:
            guard_stop.set()
            if guard_task is not None:
                await guard_task
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()

    async def run_wav_file(self, wav_path: str) -> None:
        samples, rate = read_wav_float32(wav_path)
        if rate != self.cfg.sample_rate:
            raise ValueError(f"expected {self.cfg.sample_rate} Hz wav, got {rate}")
        chunk = self.cfg.chunk_samples
        with SherpaVad(
            self.cfg.model_path,
            self.cfg.sherpa_lib,
            sample_rate=self.cfg.sample_rate,
            threshold=self.cfg.threshold,
            min_silence_duration=self.cfg.min_silence_duration,
            min_speech_duration=self.cfg.min_speech_duration,
            max_speech_duration=self.cfg.max_speech_duration,
        ) as vad:
            for i in range(0, len(samples), chunk):
                if self._stop.is_set():
                    break
                part = samples[i : i + chunk]
                self._append_stream(part)
                vad.accept_pcm_float32(part)
                if vad.is_speech_detected:
                    await self.queue.put({"type": "audio_chunk", "samples": part})
                await self._emit(vad.poll_segments())
                await asyncio.sleep(self.cfg.chunk_ms / 1000.0)
            vad.flush()
            await self._emit(vad.poll_segments())

    async def _consume_arecord(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        chunk_bytes = self.cfg.chunk_samples * 2
        try:
            with SherpaVad(
                self.cfg.model_path,
                self.cfg.sherpa_lib,
                sample_rate=self.cfg.sample_rate,
                threshold=self.cfg.threshold,
                min_silence_duration=self.cfg.min_silence_duration,
                min_speech_duration=self.cfg.min_speech_duration,
                max_speech_duration=self.cfg.max_speech_duration,
            ) as vad:
                LOG.info("[vad] listening on %s", self.cfg.alsa_device)
                while not self._stop.is_set():
                    raw = await proc.stdout.read(chunk_bytes)
                    if not raw:
                        err = await proc.stderr.read() if proc.stderr else b""
                        if err:
                            LOG.error("[vad] arecord ended: %s", err.decode(errors="replace"))
                        break
                    floats = int16_bytes_to_float32(raw)
                    self._append_stream(floats)
                    vad.accept_pcm_float32(floats)
                    if vad.is_speech_detected:
                        await self.queue.put({"type": "audio_chunk", "samples": floats})
                    await self._emit(vad.poll_segments())
        except SherpaVadError as exc:
            LOG.error("[vad] init failed: %s", exc)
            await self.queue.put({"type": "error", "source": "vad", "message": str(exc)})

    async def _emit(self, events: list[tuple[str, Any]]) -> None:
        for kind, payload in events:
            if kind == "speech_start":
                await self.queue.put({"type": "speech_start"})
            elif kind == "speech_end":
                await self.queue.put({"type": "speech_end"})
            elif kind == "segment" and payload is not None:
                prefix = self._prefix_before(payload.start)
                segment = prefix + list(payload.samples)
                duration_sec = len(segment) / self.cfg.sample_rate
                if duration_sec < self.cfg.min_segment_sec:
                    LOG.debug("[vad] drop short segment %.2fs", duration_sec)
                    continue
                if prefix:
                    LOG.info(
                        "[vad] prefix +%.0fms (start=%d) · utterance %.2fs",
                        1000 * len(prefix) / self.cfg.sample_rate,
                        payload.start,
                        duration_sec,
                    )
                await self.queue.put(
                    {
                        "type": "audio_segment",
                        "samples": segment,
                        "duration_sec": duration_sec,
                        "start": payload.start,
                    }
                )
