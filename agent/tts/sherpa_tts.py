"""Persistent offline TTS via sherpa-onnx C API (VITS or Matcha)."""
from __future__ import annotations

import ctypes
import os
import wave
from dataclasses import dataclass, field
from pathlib import Path


class SherpaTtsError(RuntimeError):
    pass


class _VitsModelConfig(ctypes.Structure):
    _fields_ = [
        ("model", ctypes.c_char_p),
        ("lexicon", ctypes.c_char_p),
        ("tokens", ctypes.c_char_p),
        ("data_dir", ctypes.c_char_p),
        ("noise_scale", ctypes.c_float),
        ("noise_scale_w", ctypes.c_float),
        ("length_scale", ctypes.c_float),
        ("dict_dir", ctypes.c_char_p),
    ]


class _MatchaModelConfig(ctypes.Structure):
    _fields_ = [
        ("acoustic_model", ctypes.c_char_p),
        ("vocoder", ctypes.c_char_p),
        ("lexicon", ctypes.c_char_p),
        ("tokens", ctypes.c_char_p),
        ("data_dir", ctypes.c_char_p),
        ("noise_scale", ctypes.c_float),
        ("length_scale", ctypes.c_float),
        ("dict_dir", ctypes.c_char_p),
    ]


class _KokoroModelConfig(ctypes.Structure):
    _fields_ = [
        ("model", ctypes.c_char_p),
        ("voices", ctypes.c_char_p),
        ("tokens", ctypes.c_char_p),
        ("data_dir", ctypes.c_char_p),
        ("length_scale", ctypes.c_float),
        ("dict_dir", ctypes.c_char_p),
        ("lexicon", ctypes.c_char_p),
        ("lang", ctypes.c_char_p),
    ]


class _KittenModelConfig(ctypes.Structure):
    _fields_ = [
        ("model", ctypes.c_char_p),
        ("voices", ctypes.c_char_p),
        ("tokens", ctypes.c_char_p),
        ("data_dir", ctypes.c_char_p),
        ("length_scale", ctypes.c_float),
    ]


class _OfflineTtsModelConfig(ctypes.Structure):
    _fields_ = [
        ("vits", _VitsModelConfig),
        ("num_threads", ctypes.c_int32),
        ("debug", ctypes.c_int32),
        ("provider", ctypes.c_char_p),
        ("matcha", _MatchaModelConfig),
        ("kokoro", _KokoroModelConfig),
        ("kitten", _KittenModelConfig),
    ]


class _OfflineTtsConfig(ctypes.Structure):
    _fields_ = [
        ("model", _OfflineTtsModelConfig),
        ("rule_fsts", ctypes.c_char_p),
        ("max_num_sentences", ctypes.c_int32),
        ("rule_fars", ctypes.c_char_p),
        ("silence_scale", ctypes.c_float),
    ]


class _GeneratedAudio(ctypes.Structure):
    _fields_ = [
        ("samples", ctypes.POINTER(ctypes.c_float)),
        ("n", ctypes.c_int32),
        ("sample_rate", ctypes.c_int32),
    ]


def _load_library(lib_dir: str) -> ctypes.CDLL:
    lib_dir = str(Path(lib_dir).resolve())
    os.environ["LD_LIBRARY_PATH"] = lib_dir + (
        f":{os.environ['LD_LIBRARY_PATH']}" if os.environ.get("LD_LIBRARY_PATH") else ""
    )
    path = Path(lib_dir) / "libsherpa-onnx-c-api.so"
    if not path.is_file():
        raise SherpaTtsError(f"missing {path}")
    return ctypes.CDLL(str(path))


@dataclass
class SherpaTtsConfig:
    backend: str = "matcha"  # matcha | vits
    model_dir: str = "/userdata/voice/matcha-icefall-zh-baker"
    model_file: str = "model.onnx"
    vocoder: str = "/userdata/voice/vocos-22khz-univ.onnx"
    rule_fsts: list[str] = field(default_factory=list)
    sherpa_lib: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib"
    num_threads: int = 2
    sid: int = 0
    noise_scale: float = 0.667
    speed: float = 1.0


class SherpaOfflineTts:
    """Keep TTS model resident; each generate() is inference only."""

    def __init__(self, cfg: SherpaTtsConfig) -> None:
        self.cfg = cfg
        self.model_dir = Path(cfg.model_dir)
        self._lib = _load_library(cfg.sherpa_lib)
        self._lib.SherpaOnnxCreateOfflineTts.argtypes = [ctypes.POINTER(_OfflineTtsConfig)]
        self._lib.SherpaOnnxCreateOfflineTts.restype = ctypes.c_void_p
        self._lib.SherpaOnnxDestroyOfflineTts.argtypes = [ctypes.c_void_p]
        self._lib.SherpaOnnxDestroyOfflineTts.restype = None
        self._lib.SherpaOnnxOfflineTtsGenerate.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int32,
            ctypes.c_float,
        ]
        self._lib.SherpaOnnxOfflineTtsGenerate.restype = ctypes.POINTER(_GeneratedAudio)
        self._lib.SherpaOnnxDestroyOfflineTtsGeneratedAudio.argtypes = [ctypes.POINTER(_GeneratedAudio)]
        self._lib.SherpaOnnxDestroyOfflineTtsGeneratedAudio.restype = None

        config = _OfflineTtsConfig()
        backend = cfg.backend.lower()
        if backend == "matcha":
            config.model.matcha.acoustic_model = str(self.model_dir / "model-steps-3.onnx").encode()
            config.model.matcha.vocoder = str(Path(cfg.vocoder)).encode()
            config.model.matcha.lexicon = str(self.model_dir / "lexicon.txt").encode()
            config.model.matcha.tokens = str(self.model_dir / "tokens.txt").encode()
            dict_dir = self.model_dir / "dict"
            if dict_dir.is_dir():
                config.model.matcha.dict_dir = str(dict_dir).encode()
            config.model.matcha.length_scale = 1.0 / max(cfg.speed, 0.1)
            config.model.matcha.noise_scale = float(cfg.noise_scale)
            if cfg.rule_fsts:
                config.rule_fsts = ",".join(cfg.rule_fsts).encode()
        elif backend == "vits":
            model_path = self.model_dir / cfg.model_file
            config.model.vits.model = str(model_path).encode()
            config.model.vits.lexicon = str(self.model_dir / "lexicon.txt").encode()
            config.model.vits.tokens = str(self.model_dir / "tokens.txt").encode()
            dict_dir = self.model_dir / "dict"
            if dict_dir.is_dir():
                config.model.vits.dict_dir = str(dict_dir).encode()
            config.model.vits.length_scale = 1.0 / max(cfg.speed, 0.1)
            config.model.vits.noise_scale = float(cfg.noise_scale)
            if cfg.rule_fsts:
                config.rule_fsts = ",".join(cfg.rule_fsts).encode()
        else:
            raise SherpaTtsError(f"unsupported TTS backend: {backend}")

        config.model.num_threads = cfg.num_threads
        config.model.provider = b"cpu"
        config.max_num_sentences = -1
        self._backend = backend

        self._handle = self._lib.SherpaOnnxCreateOfflineTts(ctypes.byref(config))
        if not self._handle:
            raise SherpaTtsError("SherpaOnnxCreateOfflineTts failed")

    def synthesize_to_wav(self, text: str, out_path: str | Path) -> Path:
        text = text.strip()
        if not text:
            raise ValueError("empty TTS text")
        out = Path(out_path)
        audio_ptr = self._lib.SherpaOnnxOfflineTtsGenerate(
            self._handle,
            text.encode("utf-8"),
            self.cfg.sid,
            ctypes.c_float(self.cfg.speed),
        )
        if not audio_ptr:
            raise SherpaTtsError("TTS generate returned NULL")
        try:
            audio = audio_ptr.contents
            if audio.n <= 0 or not audio.samples:
                raise SherpaTtsError("TTS generated empty audio")
            samples = [audio.samples[i] for i in range(audio.n)]
            self._write_wav(out, samples, audio.sample_rate)
            return out
        finally:
            self._lib.SherpaOnnxDestroyOfflineTtsGeneratedAudio(audio_ptr)

    @staticmethod
    def _write_wav(path: Path, samples: list[float], sample_rate: int) -> None:
        pcm = b"".join(
            int(max(-1.0, min(1.0, s)) * 32767).to_bytes(2, "little", signed=True) for s in samples
        )
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)

    def close(self) -> None:
        if self._handle:
            self._lib.SherpaOnnxDestroyOfflineTts(self._handle)
            self._handle = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
