"""Runtime TTS voice catalog + conversational settings control."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

LOG = logging.getLogger(__name__)

_LLM_TAG = re.compile(
    r"^【设(?:音色(?P<voice>[^】\s]+))?(?:语速(?P<speed>[\d\.]+))?】"
)
_SPEED_NUM = re.compile(r"(\d+(?:\.\d+)?)")
_LIST_VOICES = re.compile(
    r"哪些音色|什么音色|什么声音|能换什么|可以换什么|有哪些声音|音色列表|列出音色|"
    r"有什么音色|音色有哪些|几种音色|几个音色|音色介绍|介绍.*音色|换什么音色|换哪些音色"
)
_CURRENT = re.compile(r"当前音色|现在什么声音|什么设置|语速多少|现在语速")
_RESET = re.compile(r"恢复默认|默认音色|重置语音")
_SLOW = re.compile(r"慢一点|说慢|慢一些|语速慢|放慢")
_FAST = re.compile(r"快一点|说快|快一些|语速快|加快")
_SPEED_SET = re.compile(r"语速\s*(?:调到|设为|改成|改为|用)?\s*([\d\.]+|[零一二三四五六七八九十两点半]+)")
_VOICE_QUERY = re.compile(r"音色|声音|语速|男声|女声")


def is_voice_settings_query(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if not _VOICE_QUERY.search(t):
        return False
    return bool(
        re.search(
            r"哪些|什么|列出|介绍|几种|几个|能换|可以换|怎么换|如何换|当前|现在|多少",
            t,
        )
    )


_VOICE_PICK = re.compile(
    r"(?:换|改|切|用|要)(?:成|为|到|一下)?(?:音色)?(?:为|成|到)?(.{2,12}?)(?:声|音色|说话)?$"
)


def _speed_cn(speed: float) -> str:
    raw = f"{speed:.2f}".rstrip("0").rstrip(".")
    cn = "零一二三四五六七八九"
    out: list[str] = []
    for ch in raw:
        if ch == ".":
            out.append("点")
        elif ch.isdigit():
            out.append(cn[int(ch)])
        else:
            out.append(ch)
    return "".join(out)


@dataclass
class VoiceProfile:
    voice_id: str
    label: str
    backend: str
    model_dir: str
    sid: int = 0
    vocoder: str = ""
    model_file: str = "model.onnx"
    rule_fsts: list[str] = field(default_factory=list)
    noise_scale: float | None = None
    default_speed: float = 1.0

    def model_path(self) -> Path:
        return Path(self.model_dir) / self.model_file

    def available(self) -> bool:
        p = Path(self.model_dir)
        if self.backend == "matcha":
            return (p / "model-steps-3.onnx").is_file()
        return self.model_path().is_file()


@dataclass
class VoiceRuntime:
    voice_id: str
    speed: float = 1.0


@dataclass
class VoiceSettingsManager:
    profiles: dict[str, VoiceProfile] = field(default_factory=dict)
    default_voice_id: str = "baker"
    speed_min: float = 0.7
    speed_max: float = 1.4
    default_vocoder: str = "/userdata/voice/vocos-22khz-univ.onnx"
    runtime: VoiceRuntime = field(default_factory=lambda: VoiceRuntime("baker", 1.0))

    @classmethod
    def from_config(cls, tts_cfg: dict) -> VoiceSettingsManager:
        voices_raw = tts_cfg.get("voices") or {}
        default_id = str(tts_cfg.get("default_voice") or "baker")
        default_vocoder = str(tts_cfg.get("vocoder") or "/userdata/voice/vocos-22khz-univ.onnx")
        profiles: dict[str, VoiceProfile] = {}

        if voices_raw:
            for vid, spec in voices_raw.items():
                if not isinstance(spec, dict):
                    continue
                profiles[str(vid)] = VoiceProfile(
                    voice_id=str(vid),
                    label=str(spec.get("label") or vid),
                    backend=str(spec.get("backend") or "matcha"),
                    model_dir=str(spec.get("model_dir") or tts_cfg.get("model_dir", "")),
                    sid=int(spec.get("sid", 0)),
                    vocoder=str(spec.get("vocoder") or default_vocoder),
                    model_file=str(spec.get("model_file") or "model.onnx"),
                    rule_fsts=[str(x) for x in (spec.get("rule_fsts") or [])],
                    noise_scale=(
                        float(spec["noise_scale"])
                        if spec.get("noise_scale") is not None
                        else None
                    ),
                    default_speed=float(spec.get("default_speed", tts_cfg.get("speed", 1.0))),
                )
        else:
            profiles[default_id] = VoiceProfile(
                voice_id=default_id,
                label="清亮女声",
                backend=str(tts_cfg.get("backend", "matcha")),
                model_dir=str(tts_cfg.get("model_dir", "/userdata/voice/matcha-icefall-zh-baker")),
                sid=int(tts_cfg.get("sid", 0)),
                vocoder=default_vocoder,
                default_speed=float(tts_cfg.get("speed", 1.0)),
            )

        if default_id not in profiles and profiles:
            default_id = next(iter(profiles))
        rt = VoiceRuntime(default_id, float(tts_cfg.get("speed", 1.0)))
        mgr = cls(
            profiles=profiles,
            default_voice_id=default_id,
            speed_min=float(tts_cfg.get("speed_min", 0.7)),
            speed_max=float(tts_cfg.get("speed_max", 1.4)),
            default_vocoder=default_vocoder,
            runtime=rt,
        )
        if mgr.runtime.voice_id not in mgr.profiles:
            mgr.runtime.voice_id = default_id
        return mgr

    def available_profiles(self) -> list[VoiceProfile]:
        return [p for p in self.profiles.values() if p.available()]

    def active_profile(self) -> VoiceProfile:
        p = self.profiles.get(self.runtime.voice_id)
        if p and p.available():
            return p
        for cand in self.available_profiles():
            self.runtime.voice_id = cand.voice_id
            return cand
        return self.profiles[self.default_voice_id]

    def clamp_speed(self, speed: float) -> float:
        return max(self.speed_min, min(self.speed_max, round(speed, 2)))

    def describe_for_prompt(self) -> str:
        names = "、".join(f"{p.label}({p.voice_id})" for p in self.available_profiles())
        return (
            "语音设置：可用音色有"
            + names
            + f"。语速可调范围{_speed_cn(self.speed_min)}到{_speed_cn(self.speed_max)}倍，当前音色"
            + self.active_profile().label
            + f"语速{_speed_cn(self.runtime.speed)}。"
            + "用户询问音色或语速时直接口头说明。"
            + "用户要求改音色或语速时在回答最开头写【设音色voice_id语速数值】再正常回答，例如【设音色baker语速1.1】。"
            + "无设置变更时不要写该标签。"
            + "对话温度由模型固定暂不可调，若被问到请说明暂不支持。"
        )

    def describe_for_user(self) -> str:
        avail = self.available_profiles()
        parts = [f"当前是{self.active_profile().label}，语速{_speed_cn(self.runtime.speed)}倍。"]
        if avail:
            names = "、".join(p.label for p in avail)
            parts.append(f"现在能用的音色有{names}。")
        else:
            parts.append("当前没有检测到可用音色模型。")
        pending = [p for p in self.profiles.values() if not p.available()]
        if pending:
            names = "、".join(p.label for p in pending)
            parts.append(f"配置里还有{names}，安装对应模型后可切换。")
        parts.append(
            f"语速可在{_speed_cn(self.speed_min)}到{_speed_cn(self.speed_max)}倍之间调节，你可以说慢一点或语速一点二。"
        )
        return "".join(parts)

    def describe_current(self) -> str:
        p = self.active_profile()
        return f"现在是{p.label}，语速{_speed_cn(self.runtime.speed)}倍。"

    def _resolve_voice_id(self, token: str) -> str | None:
        token = token.strip()
        if not token:
            return None
        if token in self.profiles and self.profiles[token].available():
            return token
        for p in self.available_profiles():
            if token in p.label or p.label in token:
                return p.voice_id
            if p.voice_id in token:
                return p.voice_id
        aliases = {
            "女": "baker",
            "女声": "baker",
            "清亮": "baker",
            "默认": self.default_voice_id,
            "温柔": "melo",
            "男": "wnj_male",
            "男声": "wnj_male",
            "沉稳": "wnj_male",
        }
        for key, vid in aliases.items():
            if key in token and vid in self.profiles and self.profiles[vid].available():
                return vid
        return None

    def apply(self, *, voice_id: str | None = None, speed: float | None = None) -> str:
        changed: list[str] = []
        if voice_id is not None:
            resolved = self._resolve_voice_id(voice_id) if voice_id not in self.profiles else voice_id
            if resolved and self.profiles.get(resolved) and self.profiles[resolved].available():
                self.runtime.voice_id = resolved
                changed.append(self.profiles[resolved].label)
            else:
                return f"没有找到音色{voice_id}，可用音色请说有哪些音色。"
        if speed is not None:
            self.runtime.speed = self.clamp_speed(speed)
            changed.append(f"语速{self.runtime.speed}")
        if not changed:
            return self.describe_current()
        LOG.info("[voice] applied voice=%s speed=%.2f", self.runtime.voice_id, self.runtime.speed)
        p = self.active_profile()
        return f"好的，已切换为{p.label}，语速{_speed_cn(self.runtime.speed)}倍。"

    def try_rule_command(self, text: str) -> str | None:
        t = text.strip()
        if not t:
            return None
        if _LIST_VOICES.search(t):
            msg = self.describe_for_user()
            LOG.info(
                "[voice] list command matched (%d installed / %d configured): %s",
                len(self.available_profiles()),
                len(self.profiles),
                msg[:96],
            )
            return msg
        if _CURRENT.search(t):
            return self.describe_current()
        if _RESET.search(t):
            self.runtime.voice_id = self.default_voice_id
            self.runtime.speed = self.active_profile().default_speed
            return self.apply()

        m = _SPEED_SET.search(t)
        if m:
            raw = m.group(1)
            speed = _parse_speed_token(raw)
            if speed is not None:
                return self.apply(speed=speed)

        if _SLOW.search(t):
            return self.apply(speed=self.runtime.speed - 0.15)
        if _FAST.search(t):
            return self.apply(speed=self.runtime.speed + 0.15)

        if re.search(r"换|切|改|用.*声", t):
            m2 = _VOICE_PICK.search(t)
            if m2:
                picked = self.apply(voice_id=m2.group(1).strip())
                return picked
            for p in self.available_profiles():
                if p.label in t or p.voice_id in t:
                    return self.apply(voice_id=p.voice_id)

        return None

    def parse_and_strip_llm_tag(self, reply: str) -> tuple[str, str | None]:
        """Return (spoken_text, apply_result_message_or_none)."""
        m = _LLM_TAG.match(reply.strip())
        if not m:
            return reply, None
        voice_tok = (m.group("voice") or "").strip()
        speed_tok = (m.group("speed") or "").strip()
        speed = float(speed_tok) if speed_tok else None
        msg = self.apply(voice_id=voice_tok or None, speed=speed)
        rest = reply[m.end() :].lstrip()
        return rest, msg


def _parse_speed_token(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    cn_map = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if raw in ("半",):
        return 0.5
    if "点" in raw or "．" in raw:
        parts = re.split(r"[点．]", raw, maxsplit=1)
        if len(parts) == 2 and parts[0] in cn_map:
            dec = parts[1]
            if dec.isdigit():
                return float(f"{cn_map[parts[0]]}.{dec}")
            if len(dec) == 1 and dec in cn_map:
                return float(f"{cn_map[parts[0]]}.{cn_map[dec]}")
    m = _SPEED_NUM.search(raw)
    if m:
        return float(m.group(1))
    if raw in cn_map and cn_map[raw] <= 2:
        return float(cn_map[raw])
    return None
