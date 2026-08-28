"""Async TTS queue — pipelined synth/play, one sentence per chunk."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from tts.sentence_split import is_speakable, sanitize_tts_text
from tts.tts_engine import TtsEngine

LOG = logging.getLogger(__name__)
TTS_RUN_DIR = Path("/userdata/agent/run")


class TtsQueue:
    def __init__(
        self,
        engine: TtsEngine,
        *,
        merge_max_chars: int = 80,
    ) -> None:
        self.engine = engine
        self.merge_max_chars = merge_max_chars  # kept for config compat
        self._text_q: asyncio.Queue[str | None] = asyncio.Queue()
        self._wav_q: asyncio.Queue[tuple[Path, str] | None] = asyncio.Queue(maxsize=3)
        self._synth_task: asyncio.Task | None = None
        self._play_task: asyncio.Task | None = None
        self._first_play_at: float | None = None
        self._utterance_started_at: float | None = None
        self._slot = 0
        self._interrupted = asyncio.Event()
        self._utterance_chunks = 0
        self._played_chunks = 0
        self._utterance_gain: float | None = None

    @property
    def is_playing(self) -> bool:
        return self._play_task is not None and not self._interrupted.is_set() and (
            self._wav_q.qsize() > 0 or self._text_q.qsize() > 0
        )

    def set_max_sentences(self, n: int) -> None:
        _ = n

    async def discard_pending(self) -> None:
        while True:
            try:
                self._text_q.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._text_q.task_done()
        await self._drain_wav_queue()

    async def _drain_wav_queue(self) -> None:
        while True:
            try:
                self._wav_q.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._wav_q.task_done()

    async def interrupt(self) -> None:
        self._interrupted.set()
        await self.discard_pending()
        await self._drain_wav_queue()
        await asyncio.to_thread(self.engine.stop_playback)
        LOG.info("[tts] interrupted")

    async def start(self) -> None:
        if self._synth_task is None:
            self._synth_task = asyncio.create_task(self._synth_worker())
            self._play_task = asyncio.create_task(self._play_worker())

    def mark_utterance_start(self) -> None:
        self._utterance_started_at = time.monotonic()
        self._first_play_at = None
        self._utterance_chunks = 0
        self._played_chunks = 0
        self._utterance_gain = None
        self._interrupted.clear()

    @property
    def first_play_latency_s(self) -> float | None:
        if self._utterance_started_at is None or self._first_play_at is None:
            return None
        return self._first_play_at - self._utterance_started_at

    async def enqueue(self, text: str) -> None:
        if self._interrupted.is_set():
            return
        text = sanitize_tts_text(text)
        if not is_speakable(text):
            return
        self._utterance_chunks += 1
        await self._text_q.put(text)

    async def flush(self) -> None:
        return

    async def wait_done(self) -> None:
        if self._interrupted.is_set() or self._utterance_chunks <= 0:
            return
        await self._text_q.join()
        if self._interrupted.is_set():
            return
        await self._wav_q.join()

    async def reconfigure(self, cfg) -> None:
        from tts.tts_engine import TtsConfig

        assert isinstance(cfg, TtsConfig)
        await asyncio.to_thread(self.engine.reconfigure, cfg)
        LOG.info(
            "[tts] reconfigured backend=%s sid=%d speed=%.2f",
            cfg.backend,
            cfg.sid,
            cfg.speed,
        )

    async def _synth_worker(self) -> None:
        while True:
            text = await self._text_q.get()
            try:
                if text is None:
                    await self._wav_q.put(None)
                    return
                if self._interrupted.is_set():
                    continue
                TTS_RUN_DIR.mkdir(parents=True, exist_ok=True)
                path = TTS_RUN_DIR / f"tts_{self._slot}.wav"
                self._slot += 1
                t0 = time.monotonic()
                wav = await asyncio.to_thread(self.engine.synthesize, text, str(path))
                if self._interrupted.is_set():
                    continue
                LOG.info("[tts] synth %.2fs (%d chars)", time.monotonic() - t0, len(text))
                await self._wav_q.put((wav, text))
            except Exception as exc:
                LOG.error("[tts] synth failed: %s", exc)
            finally:
                self._text_q.task_done()

    async def _play_worker(self) -> None:
        while True:
            item = await self._wav_q.get()
            try:
                if item is None:
                    return
                if self._interrupted.is_set():
                    continue
                wav, text = item
                if self._first_play_at is None:
                    self._first_play_at = time.monotonic()
                    lat = self.first_play_latency_s
                    if lat is not None:
                        LOG.info("[tts] first_play latency=%.2fs", lat)
                self._played_chunks += 1
                continuation = self._played_chunks > 1
                last = self._played_chunks >= self._utterance_chunks
                LOG.info("[tts] speak (%d/%d): %s", self._played_chunks, self._utterance_chunks, text[:80])
                t0 = time.monotonic()
                gain = await asyncio.to_thread(
                    self.engine.play,
                    wav,
                    continuation=continuation,
                    last_in_utterance=last,
                    utterance_gain=self._utterance_gain,
                )
                if self._utterance_gain is None and gain is not None:
                    self._utterance_gain = gain
                if self._interrupted.is_set():
                    LOG.info("[tts] play aborted (barge-in)")
                else:
                    tag = " cont" if continuation else ""
                    if last:
                        tag += " last"
                    LOG.info("[tts] play %.2fs%s", time.monotonic() - t0, tag)
            except Exception as exc:
                LOG.error("[tts] play failed: %s", exc)
            finally:
                self._wav_q.task_done()
