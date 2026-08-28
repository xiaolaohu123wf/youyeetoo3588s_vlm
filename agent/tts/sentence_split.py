"""Split LLM stream into speakable sentence chunks."""
from __future__ import annotations

import re

from tts.pronunciation_fix import fix_tts_pronunciation

_PRIMARY = re.compile(r"([^。！？!?]+[。！？!?])")
_CJK = re.compile(r"[\u4e00-\u9fff]")

_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_LIST = re.compile(r"^\s*\d+\.\s*", re.MULTILINE)
_MD_HEAD = re.compile(r"^#+\s*", re.MULTILINE)
_ASCII = re.compile(r"[A-Za-z]+")
_DIGITS = re.compile(r"\d+")
# TTS 只保留汉字和句末标点；冒号/分号/括号等会被念出来且很难听
_NON_SPOKEN = re.compile(r"[^\u4e00-\u9fff。！？，]")
_WS = re.compile(r"\s+")

_MIN_CJK_CHARS = 4


def sanitize_tts_text(text: str) -> str:
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_LIST.sub("", text)
    text = _MD_HEAD.sub("", text)
    text = text.replace("*", "").replace("`", "").replace("#", "")
    # LLM 常复读 prompt 里的「小揽：」前缀
    text = re.sub(r"^小揽[：:]\s*", "", text)
    text = re.sub(r"三[Dd]?打印", "三维打印", text, flags=re.IGNORECASE)
    text = _ASCII.sub("", text)
    text = _DIGITS.sub("", text)
    text = re.sub(r"[：:；;、·\-—–\.．\(\)（）【】\[\]「」\"\"'\"]+", "", text)
    text = _NON_SPOKEN.sub("", text)
    text = _WS.sub("", text)
    text = re.sub(r"[，]{2,}", "，", text)
    text = re.sub(r"^[，。！？]+", "", text)
    text = re.sub(r"[，]+$", "", text)
    return text.strip()


def is_speakable(text: str) -> bool:
    return len(_CJK.findall(text)) >= _MIN_CJK_CHARS


def count_cjk(text: str) -> int:
    return len(_CJK.findall(text))


def cap_speak_text(text: str, max_cjk: int) -> str:
    """Hard cap on spoken Chinese characters; prefer ending at 。！？."""
    if max_cjk <= 0:
        return ""
    text = sanitize_tts_text(text)
    if not text:
        return ""
    if count_cjk(text) <= max_cjk:
        return text
    buf: list[str] = []
    cjk = 0
    for ch in text:
        buf.append(ch)
        if _CJK.match(ch):
            cjk += 1
        if cjk >= max_cjk:
            break
    chunk = "".join(buf)
    last_end = 0
    for m in _PRIMARY.finditer(chunk):
        last_end = m.end()
    if last_end:
        chunk = chunk[:last_end]
    else:
        chunk = chunk.rstrip("，") + "。"
    chunk = sanitize_tts_text(chunk)
    return chunk if is_speakable(chunk) else ""


def drain_complete_sentences(buffer: str, *, min_flush_chars: int = 22) -> tuple[list[str], str]:
    """Only emit on 。！？ — never flush mid-sentence fragments."""
    out: list[str] = []
    rest = buffer
    while True:
        m = _PRIMARY.match(rest)
        if m:
            sent = sanitize_tts_text(m.group(1))
            if is_speakable(sent):
                out.append(sent)
            rest = rest[m.end() :]
            continue
        break
    return out, rest


_BAD_REPLY = re.compile(
    r"以下是|我可以帮助|有什么需要|帮忙的吗|没有名字|小AI"
    r"|爱因斯坦|广义相对论|以下方法|如果您能提供|乐意帮助"
    r"|乐意为你讲述|感兴趣的主题|请告诉我你.*需求|创作一个简短"
    r"|作为一个人工智能|作为一个AI|我是语言模型"
)
_TOPIC_ASK = re.compile(
    r"人工智能|机器学习|深度学习|神经网络|什么是|解释一下|解释|区别|原理|算法|怎么理解"
)
_CAPABILITY = re.compile(r"做什么|会什么|能干|帮我什么|都会做")
_STORY = re.compile(r"故事|哄我|睡前|讲个笑话|讲个故事|讲讲话|讲个话|笑话")
_NAME = re.compile(r"叫什么|名字|你是谁|哪位")
_RECITE = re.compile(r"背诵|元素周期|周期表|乘法表|九九表")
_GREET = re.compile(r"^你好[呀啊]?$|早上好|晚上好")
_STOP = re.compile(r"^(不再|停|停止|别说了|不要说了|闭嘴|算了)[了]?$")
_INTRO_PREFIX = re.compile(r"^(?:我叫小揽|我是小揽)[，,。\s]*")
_NAME_ONLY = re.compile(r"^(?:我叫小揽|我是小揽)[。！？]?$")
_SCIENCE_LECTURE = re.compile(r"引力是|基本力|时空弯曲|训练数据|超参数")
_TRANSCRIPT_ECHO = re.compile(r"(?:\r?\n\s*){1,2}用户[：:]")
_INLINE_TRANSCRIPT = re.compile(r"用户[：:][^。！？!?]*小揽[：:]")
_STORY_FALLBACKS = (
    "好呀，小狐狸在夜里找星星，走累了靠着月亮睡了。风轻轻吹，它梦见彩虹。晚安，好梦。",
    "从前有只小兔子，每天傍晚都在窗台等晚霞。有一天晚霞落在它耳朵上，变成了一朵温暖的花。",
    "夜里，小猫抱着月亮的倒影睡着了，梦里它在一整片星星上跳来跳去。",
)


def _story_fallback(user_text: str) -> str:
    idx = sum(ord(c) for c in user_text) % len(_STORY_FALLBACKS)
    return _STORY_FALLBACKS[idx]


def user_asked_name(user_text: str) -> bool:
    return bool(_NAME.search(user_text))


def strip_transcript_echo(text: str) -> str:
    """Drop history replay when the model copies prompt transcript into its reply."""
    text = (text or "").strip()
    if not text:
        return text
    m = _TRANSCRIPT_ECHO.search(text)
    if m:
        text = text[: m.start()].strip()
    m2 = _INLINE_TRANSCRIPT.search(text)
    if m2:
        text = text[: m2.start()].strip()
    return text.strip()


def clean_llm_reply(user_text: str, reply: str) -> str:
    """Strip transcript echo and spurious self-intro when user did not ask for name."""
    text = strip_transcript_echo((reply or "").strip())
    text = re.sub(r"^小揽[：:]\s*", "", text)
    if not user_asked_name(user_text):
        text = _INTRO_PREFIX.sub("", text).strip()
    if not user_asked_name(user_text) and _NAME_ONLY.match(sanitize_tts_text(text)):
        return ""
    return text.strip()


def is_spurious_name_reply(user_text: str, reply: str) -> bool:
    if user_asked_name(user_text):
        return False
    clean = sanitize_tts_text(clean_llm_reply(user_text, reply))
    if not clean:
        return True
    return len(_CJK.findall(clean)) <= 8 and bool(re.search(r"叫小揽|是小揽", clean))


def is_robotic_reply(text: str, user_text: str = "") -> bool:
    if _TOPIC_ASK.search(user_text or ""):
        return False
    return bool(_BAD_REPLY.search(text))


def is_off_topic_reply(user_text: str, reply: str) -> bool:
    """User asked persona/capability/story but LLM lectured or deflected."""
    if is_spurious_name_reply(user_text, reply):
        return True
    if _STORY.search(user_text) and _BAD_REPLY.search(reply):
        return True
    if _RECITE.search(user_text) and _NAME_ONLY.match(sanitize_tts_text(clean_llm_reply(user_text, reply))):
        return True
    if not (_CAPABILITY.search(user_text) or _NAME.search(user_text) or _GREET.search(user_text.strip())):
        return False
    return bool(_SCIENCE_LECTURE.search(reply) or is_robotic_reply(reply, user_text))


def persona_reply_for(user_text: str) -> str:
    """Deterministic voice reply when LLM ignores system prompt."""
    if _STOP.search(user_text.strip()):
        return "好的。"
    if _NAME.search(user_text):
        return "我叫小揽，是你这边的语音助手。"
    if _CAPABILITY.search(user_text):
        return "我能跟你聊天，还能帮你看情况。"
    if _STORY.search(user_text):
        return _story_fallback(user_text)
    if _RECITE.search(user_text):
        return "元素周期表太长了，我没法完整背完。前几个是氢、氦、锂、铍、硼、碳、氮、氧、氟、氖。"
    if _GREET.search(user_text.strip()):
        return "你好呀，我是小揽。"
    return "我是小揽，你的语音助手。"


def canned_reply_for(user_text: str) -> str | None:
    if _STOP.search(user_text.strip()):
        return "好的。"
    if _NAME.search(user_text):
        return "我叫小揽，是你这边的语音助手。"
    if _CAPABILITY.search(user_text):
        return "我能跟你聊天，还能帮你看情况。"
    if _GREET.search(user_text.strip()):
        return "你好呀，我是小揽。"
    return None


def should_skip_llm(user_text: str) -> bool:
    """Known intents: skip LLM and speak canned reply (saves latency + avoids garbage)."""
    return canned_reply_for(user_text) is not None


def pick_first_sentence(text: str) -> str:
    sents = extract_speak_sentences(text, max_cjk=9999)
    return sents[0] if sents else ""


def extract_speak_sentences(text: str, max_cjk: int = 99999) -> list[str]:
    """Split on 。！？; include trailing fragment. max_cjk>=9999 means no budget cap."""
    if max_cjk <= 0:
        return []
    uncapped = max_cjk >= 9999
    out: list[str] = []
    used = 0
    consumed = 0
    for m in _PRIMARY.finditer(text):
        sent = sanitize_tts_text(m.group(1))
        consumed = m.end()
        if not is_speakable(sent):
            continue
        n = count_cjk(sent)
        if not uncapped and used + n > max_cjk:
            tail = cap_speak_text(sent, max_cjk - used)
            if tail:
                out.append(tail)
            return out
        out.append(sent)
        used += n
    rest = sanitize_tts_text(text[consumed:])
    # Drop LLM-truncated tail without 。！？ — avoids mid-sentence fragments.
    if is_speakable(rest) and re.search(r"[。！？!?]$", rest):
        if uncapped:
            out.append(rest)
        elif used + count_cjk(rest) <= max_cjk:
            out.append(cap_speak_text(rest, max_cjk - used))
    if not out and text.strip():
        one = cap_speak_text(text, max_cjk if not uncapped else 99999)
        if one:
            out.append(one)
    deduped: list[str] = []
    seen: set[str] = set()
    for sent in out:
        if sent in seen:
            continue
        seen.add(sent)
        deduped.append(sent)
    return deduped


def split_tts_clauses(sentence: str) -> list[str]:
    """Split one sentence into comma clauses for smoother TTS prosody."""
    sentence = sanitize_tts_text(sentence)
    if not sentence:
        return []
    if "，" not in sentence or count_cjk(sentence) < 16:
        fixed = fix_tts_pronunciation(sentence)
        return [fixed] if is_speakable(fixed) else []

    out: list[str] = []
    for chunk in re.split(r"(?<=[，])", sentence):
        chunk = chunk.strip()
        if not chunk:
            continue
        fixed = fix_tts_pronunciation(chunk)
        if is_speakable(fixed):
            out.append(fixed)
        elif out:
            out[-1] += fixed
    if out:
        return out
    fixed = fix_tts_pronunciation(sentence)
    return [fixed] if is_speakable(fixed) else []


def flush_remainder(buffer: str) -> list[str]:
    text = sanitize_tts_text(buffer)
    return [text] if is_speakable(text) else []
