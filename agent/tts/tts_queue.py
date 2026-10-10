"""Async TTS queue — pipelined synth/play, one sentence per chunk."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from tts.pronunciation_fix import fix_tts_pronunciation
from tts.sentence_split import is_speakable, sanitize_tts_text
from tts.tts_engine import TtsEngine

LOG = logging.getLogger(__name__)
TTS_RUN_DIR = Path("/userdata/agent/run/tts")


@dataclass(frozen=True)
class _TextItem:
    generation: int
    text: str


@dataclass(frozen=True)
class _WavItem:
    generation: int
    wav: Path
    text: str


class TtsQueue:
    def __init__(
        self,
        engine: TtsEngine,
        *,
        merge_max_chars: int = 80,
    ) -> None:
        self.engine = engine
        self.merge_max_chars = merge_max_chars  # kept for config compat
        self._text_q: asyncio.Queue[_TextItem | None] = asyncio.Queue()
        self._wav_q: asyncio.Queue[_WavItem | None] = asyncio.Queue(maxsize=3)
        self._synth_task: asyncio.Task | None = None
        self._play_task: asyncio.Task | None = None
        self._first_play_at: float | None = None
        self._utterance_started_at: float | None = None
        self._slot = 0
        self._interrupted = asyncio.Event()
        self._utterance_chunks = 0
        self._played_chunks = 0
        self._utterance_gain: float | None = None
        self._current_speaking_chunk: str | None = None
        self._current_speaking_generation: int | None = None
        self._active_generation = 0

    @property
    def is_playing(self) -> bool:
        return self._play_task is not None and not self._interrupted.is_set() and (
            self._wav_q.qsize() > 0 or self._text_q.qsize() > 0 or self._current_speaking_chunk is not None
        )

    def set_max_sentences(self, n: int) -> None:
        _ = n

    async def discard_pending(self, *, include_current: bool = False) -> list[str]:
        texts: list[str] = []
        if include_current and self._current_speaking_chunk:
            texts.append(self._current_speaking_chunk)
        while True:
            try:
                item = self._wav_q.get_nowait()
                if item and item.text:
                    texts.append(item.text)
            except asyncio.QueueEmpty:
                break
            else:
                self._wav_q.task_done()
        while True:
            try:
                t = self._text_q.get_nowait()
                if t:
                    texts.append(t.text)
            except asyncio.QueueEmpty:
                break
            else:
                self._text_q.task_done()
        return texts

    async def interrupt(self) -> list[str]:
        self._interrupted.set()
        pending = await self.discard_pending()
        await asyncio.to_thread(self.engine.stop_playback)
        LOG.info("[tts] interrupted, saved %d clauses for relay", len(pending))
        return pending

    def abort(self) -> None:
        """Synchronously request abort and discard pending queues."""
        self._interrupted.set()
        while not self._wav_q.empty():
            try:
                self._wav_q.get_nowait()
                self._wav_q.task_done()
            except Exception:
                break
        while not self._text_q.empty():
            try:
                self._text_q.get_nowait()
                self._text_q.task_done()
            except Exception:
                break
        try:
            self.engine.stop_playback()
        except Exception:
            pass

    async def start(self) -> None:
        if self._synth_task is None:
            self._synth_task = asyncio.create_task(self._synth_worker())
            self._play_task = asyncio.create_task(self._play_worker())

    def mark_utterance_start(self, generation: int = 0) -> None:
        self._active_generation = generation
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

    @property
    def first_play_at(self) -> float | None:
        return self._first_play_at

    async def enqueue(self, text: str, *, generation: int | None = None) -> None:
        generation = self._active_generation if generation is None else generation
        if self._interrupted.is_set() or generation != self._active_generation:
            return
        text = sanitize_tts_text(text)
        text = fix_tts_pronunciation(text)
        if not is_speakable(text):
            return
        self._utterance_chunks += 1
        await self._text_q.put(_TextItem(generation, text))

    async def flush(self) -> None:
        return

    async def wait_done(self, generation: int | None = None) -> None:
        generation = self._active_generation if generation is None else generation
        if (
            self._interrupted.is_set()
            or generation != self._active_generation
            or self._utterance_chunks <= 0
        ):
            return
        await self._text_q.join()
        if self._interrupted.is_set() or generation != self._active_generation:
            return
        await self._wav_q.join()

    async def stop(self) -> None:
        """Cancel queue workers during orchestrator shutdown; safe to call repeatedly."""
        tasks = [task for task in (self._synth_task, self._play_task) if task is not None]
        if not tasks:
            return
        self._interrupted.set()
        await self.discard_pending()
        await asyncio.to_thread(self.engine.stop_playback)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._synth_task = None
        self._play_task = None
        self._current_speaking_chunk = None
        self._current_speaking_generation = None

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
            item = await self._text_q.get()
            try:
                if item is None:
                    await self._wav_q.put(None)
                    return
                if self._interrupted.is_set() or item.generation != self._active_generation:
                    continue
                TTS_RUN_DIR.mkdir(parents=True, exist_ok=True)
                path = TTS_RUN_DIR / f"agent_tts_{self._slot}.wav"
                self._slot += 1
                if path.is_file():
                    try:
                        path.unlink(missing_ok=True)
                    except Exception:
                        path = TTS_RUN_DIR / f"agent_tts_{time.monotonic_ns()}_{self._slot}.wav"
                t0 = time.monotonic()
                wav = await asyncio.to_thread(self.engine.synthesize, item.text, str(path))
                if self._interrupted.is_set() or item.generation != self._active_generation:
                    continue
                LOG.info("[tts] synth %.2fs (%d chars)", time.monotonic() - t0, len(item.text))
                await self._wav_q.put(_WavItem(item.generation, wav, item.text))
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
                if self._interrupted.is_set() or item.generation != self._active_generation:
                    continue
                if self._first_play_at is None:
                    self._first_play_at = time.monotonic()
                    lat = self.first_play_latency_s
                    if lat is not None:
                        LOG.info("[tts] first_play latency=%.2fs", lat)
                self._played_chunks += 1
                continuation = self._played_chunks > 1
                last = self._played_chunks >= self._utterance_chunks
                LOG.info("[tts] speak (%d/%d): %s", self._played_chunks, self._utterance_chunks, item.text[:80])
                t0 = time.monotonic()
                self._current_speaking_chunk = item.text
                self._current_speaking_generation = item.generation
                try:
                    gain = await asyncio.to_thread(
                        self.engine.play,
                        item.wav,
                        continuation=continuation,
                        last_in_utterance=last,
                        utterance_gain=self._utterance_gain,
                    )
                finally:
                    if self._current_speaking_generation == item.generation:
                        self._current_speaking_chunk = None
                        self._current_speaking_generation = None
                    try:
                        if item.wav and item.wav.is_file() and str(item.wav).startswith(str(TTS_RUN_DIR)):
                            item.wav.unlink(missing_ok=True)
                    except Exception:
                        pass
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
