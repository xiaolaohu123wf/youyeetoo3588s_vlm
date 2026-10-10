"""Split LLM stream into speakable sentence chunks."""
from __future__ import annotations

import re

from tts.pronunciation_fix import fix_tts_pronunciation

_PRIMARY = re.compile(r"([^。！？!?\n]+[。！？!?\n])")
_CJK = re.compile(r"[\u4e00-\u9fff]")

_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_LIST = re.compile(r"^\s*[-*•]\s*", re.MULTILINE)
_MD_NUM_LIST = re.compile(r"^\s*\d+[\.、]\s*", re.MULTILINE)
_MD_HEAD = re.compile(r"^#+\s*", re.MULTILINE)

LETTER_MAP = {
    "A": "诶", "B": "必", "C": "西", "D": "弟", "E": "伊", "F": "艾弗",
    "G": "吉", "H": "艾尺", "I": "爱", "J": "借", "K": "开", "L": "艾勒",
    "M": "艾姆", "N": "恩", "O": "欧", "P": "批", "Q": "丘", "R": "阿尔",
    "S": "艾斯", "T": "踢", "U": "优", "V": "微", "W": "达布溜", "X": "艾克斯",
    "Y": "歪", "Z": "贼",
}

COMMON_EN = [
    (r"(?<![A-Za-z])(hello|hi)(?![A-Za-z])", "哈喽"),
    (r"(?<![A-Za-z])ok(ay)?(?![A-Za-z])", "好的"),
    (r"(?<![A-Za-z])(bye|goodbye)(?![A-Za-z])", "再见"),
    (r"(?<![A-Za-z])(yes|yeah)(?![A-Za-z])", "是的"),
    (r"(?<![A-Za-z])no(?![A-Za-z])", "不"),
    (r"(?<![A-Za-z])good(?![A-Za-z])", "好"),
    (r"(?<![A-Za-z])ai(?![A-Za-z])", "人工智能"),
    (r"(?<![A-Za-z])app(?![A-Za-z])", "应用"),
    (r"(?<![A-Za-z])api(?![A-Za-z])", "接口"),
    (r"(?<![A-Za-z])intern-?s1(?![A-Za-z])", "小揽"),
    (r"(?<![A-Za-z])intern(?![A-Za-z])", "小揽"),
    (r"(?<![A-Za-z])r1(?![A-Za-z])", "阿尔一"),
    (r"(?<![A-Za-z])cpu(?![A-Za-z])", "处理器"),
    (r"(?<![A-Za-z])gpu(?![A-Za-z])", "显卡"),
    (r"(?<![A-Za-z])tpu(?![A-Za-z])", "张量处理器"),
    (r"(?<![A-Za-z])npu(?![A-Za-z])", "神经网络处理器"),
    (r"(?<![A-Za-z])usb(?![A-Za-z])", "优盘"),
    (r"(?<![A-Za-z])wifi(?![A-Za-z])", "无线网"),
]

KNOWN_ACRONYMS = {
    "AI", "CPU", "GPU", "NPU", "TPU", "RAM", "ROM", "USB", "WIFI", "LED",
    "API", "APP", "SDK", "OS", "PC", "VAD", "ASR", "TTS", "LLM", "VLM",
    "OK", "ID", "IP", "DNS", "URL", "HTTP", "HTTPS", "TCP", "UDP", "HTML",
    "PDF", "MP3", "MP4", "WAV", "GPS", "SOS", "VIP", "SIM", "DIY", "KFC",
    "BMW", "BYD", "DJI", "QQ", "R1", "S1", "3D", "4G", "5G"
}

_DIGIT_MAP = str.maketrans("0123456789", "零一二三四五六七八九")
_MIN_SPOKEN_CHARS = 2


def transliterate_en(text: str) -> str:
    """Map common English words and letters to Chinese phonetics for pure-Chinese TTS."""
    for pattern, rep in COMMON_EN:
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)

    def repl_acronym(m: re.Match[str]) -> str:
        word = m.group(0).upper()
        if word in KNOWN_ACRONYMS:
            return "".join(LETTER_MAP.get(c, c) for c in word)
        return ""  # Drop unknown multi-letter English words like 'think', 'null'

    text = re.sub(r"(?<![A-Za-z])[A-Za-z]{2,}(?![A-Za-z])", repl_acronym, text)

    def repl_letter(m: re.Match[str]) -> str:
        ch = m.group(0).upper()
        return LETTER_MAP.get(ch, "")

    return re.sub(r"[A-Za-z]", repl_letter, text)


def sanitize_tts_text(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?think>", "", text)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"<\|.*?\|>", "", text)
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_LIST.sub("，", text)
    text = _MD_NUM_LIST.sub("，", text)
    text = _MD_HEAD.sub("", text)
    text = text.replace("*", "").replace("`", "").replace("#", "")
    # LLM 常复读 prompt 里的「小揽：」前缀或标记
    text = re.sub(r"^小揽[：:]\s*", "", text)
    text = re.sub(r"<\|im_end\|>.*", "", text)
    text = re.sub(r"三[Dd]?打印", "三维打印", text, flags=re.IGNORECASE)
    # 冒号、分号转逗号停顿，换行转句号
    text = re.sub(r"[：:；;]+", "，", text)
    text = re.sub(r"[\r\n]+", "。", text)
    # 数字转汉字
    text = text.translate(_DIGIT_MAP)
    # 英文音译转汉字发音
    text = transliterate_en(text)
    # 过滤无法发音的符号
    text = re.sub(r"[-—–\.．\(\)（）【】\[\]「」\"\"\'\'·=]+", "", text)
    text = re.sub(r"[^\u4e00-\u9fff。！？，]", "", text)
    text = re.sub(r"[，。！？]+([。！？])", r"\1", text)
    text = re.sub(r"^[，。！？]+", "", text)
    text = re.sub(r"[，]{2,}", "，", text)
    return text.strip()


def is_speakable(text: str) -> bool:
    return len(re.findall(r"[\u4e00-\u9fff0-9]", text)) >= _MIN_SPOKEN_CHARS


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
STOP_PATTERN = re.compile(r"(停|暂停|别说了|不要说了|闭嘴|算了|打住|停止|停下|别讲了|安静|不要讲|停一下|等等|等一下|别出声|闭上嘴)")
_STOP = STOP_PATTERN
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


_THINKING_PREFIX = re.compile(
    r"^(?:"
    r"(?:【?思考(?:过程)?】?|Thought(?:s)?)[：:\s]+.*?(?:\n|$)|"
    r"好的[，,。]*(?:我[来帮]?看[看一下]+|让我[来]?看[看一下]+|让我[来]?查[一下]+|我正在[想看查]|让我[来]?想想|我来帮你看看|我[来]?告诉你|请稍等|请稍候)[，,。]*|"
    r"我[来帮]?看[看一下]+[，,。]*|"
    r"让我[来]?看[看一下]+[，,。]*|"
    r"我正在[想看查][，,。]*|"
    r"正在为你(?:查询|搜索|生成|分析|思考)[，,。]*|"
    r"让我[来]?想想[看]?[，,。]*|"
    r"我思考了一下[，,。]*|"
    r"请稍[等候][，,。]*|"
    r"请把你的手伸过来[，,。]*|"
    r"让我看看你面前的桌面[，,。]*"
    r")"
)


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
    """Strip transcript echo, spurious self-intro, thinking tags, and preamble filler."""
    text = strip_transcript_echo((reply or "").strip())
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?think>", "", text)
    text = re.sub(r"<\|.*?\|>", "", text)
    text = re.sub(r"^小揽[：:]\s*", "", text)
    if not user_asked_name(user_text):
        text = _INTRO_PREFIX.sub("", text).strip()
    text = _THINKING_PREFIX.sub("", text).strip("，,。！？ ")
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
    return bool(_SCIENCE_LECTURE.search(reply) or is_robotic_reply(reply, user_text))


def is_self_echo(spoken_text: str, detected_text: str) -> bool:
    """Detect if mic picked up acoustic feedback of robot's own speaker audio."""
    s = re.sub(r"[^\u4e00-\u9fa50-9A-Za-z]", "", spoken_text or "")
    d = re.sub(r"[^\u4e00-\u9fa50-9A-Za-z]", "", detected_text or "")
    if not s or not d:
        return False
    if d in s:
        return True
    overlap = sum(1 for c in d if c in s)
    if len(d) >= 2 and (overlap / len(d)) >= 0.70:
        return True
    return False


def is_echo_reply(user_text: str, reply: str) -> bool:
    """Detect if LLM is parroting the user's question instead of answering."""
    u = re.sub(r"[^\u4e00-\u9fa50-9]", "", user_text or "")
    r = re.sub(r"[^\u4e00-\u9fa50-9]", "", reply or "")
    if not u or not r:
        return False
    if u == r:
        return True
    if u.replace("我", "你") == r or u.replace("你", "我") == r:
        return True
    u_core = re.sub(r"^[那对嗯啊好请问]+", "", u)
    r_core = re.sub(r"^[那对嗯啊好请问]+", "", r)
    if u_core and u_core == r_core and len(u_core) >= 2:
        return True
    if (reply.endswith("？") or reply.endswith("?")) and len(r) <= len(u) + 3:
        overlap = sum(1 for c in r if c in u)
        if len(r) >= 2 and (overlap / len(r)) >= 0.60:
            return True
    return False


_PRESENCE = re.compile(r"^(?:你?在[吗嘛]|人呢|你在[哪哪儿]|在不在|(?:你好|电好|男好|嘿|嗨|喂)?小揽)[呀啊吧呢]?$")


_JARVIS_CANNED_REPLIES = (
    "随时待命，主人。",
    "我在，主人请吩咐。",
    "系统运转正常，随时听候调遣，主人。",
    "小揽一直在，主人请讲。",
)
_canned_idx = 0


def persona_reply_for(user_text: str) -> str:
    """仅在 LLM 完全无输出或崩溃时的真正兜底。"""
    u = user_text.strip()
    if _STOP.search(u):
        return "好的，主人。"
    if "首都" in u:
        return "中国的首都是北京。"
    if _PRESENCE.search(u):
        return "随时待命，主人，请吩咐。"
    return "随时待命，主人请随时吩咐。"


def canned_reply_for(user_text: str) -> str | None:
    global _canned_idx
    u = user_text.strip()
    if _STOP.search(u):
        return "好的，主人。"
    if _PRESENCE.search(u):
        reply = _JARVIS_CANNED_REPLIES[_canned_idx % len(_JARVIS_CANNED_REPLIES)]
        _canned_idx += 1
        return reply
    return None


def should_skip_llm(user_text: str) -> bool:
    return canned_reply_for(user_text) is not None


def pick_first_sentence(text: str) -> str:
    sents = extract_speak_sentences(text, max_cjk=9999)
    return sents[0] if sents else ""


def extract_speak_sentences(text: str, max_cjk: int = 99999, *, max_chunk_len: int = 24) -> list[str]:
    """Split into natural, conversational speakable chunks with proper comma pauses."""
    if max_cjk <= 0:
        return []
    uncapped = max_cjk >= 9999

    # 1. Split on sentence-ending punctuation or newlines
    raw_parts = re.split(r"([。！？!?\n]+)", text)
    sentences: list[str] = []
    for i in range(0, len(raw_parts) - 1, 2):
        s = raw_parts[i].strip()
        p = raw_parts[i + 1].strip()
        if s:
            sentences.append(s + (p if p in "。！？!?" else "。"))
    if len(raw_parts) % 2 == 1 and raw_parts[-1].strip():
        sentences.append(raw_parts[-1].strip() + "。")

    # 2. Refine each sentence with natural comma chunking
    out: list[str] = []
    used = 0
    for raw_s in sentences:
        s_clean = sanitize_tts_text(raw_s)
        if not is_speakable(s_clean):
            continue
        # If sentence is long and has commas, break at clause boundaries
        chunks_to_add: list[str] = []
        if len(s_clean) > max_chunk_len and "，" in s_clean:
            clauses = s_clean.split("，")
            buf = ""
            for c in clauses:
                c = c.strip("，。！？")
                if not c:
                    continue
                if not buf:
                    buf = c
                elif len(buf) + len(c) + 1 <= max_chunk_len:
                    buf += "，" + c
                else:
                    chunks_to_add.append(buf + "。")
                    buf = c
            if buf:
                chunks_to_add.append(buf + "。")
        else:
            chunks_to_add.append(s_clean if s_clean.endswith(("。", "！", "？")) else s_clean + "。")

        for chunk in chunks_to_add:
            n = count_cjk(chunk)
            if not uncapped and used + n > max_cjk:
                tail = cap_speak_text(chunk, max_cjk - used)
                if tail:
                    out.append(tail)
                return out
            out.append(chunk)
            used += n

    return out


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


class StreamingSentenceSplitter:
    """Consumes LLM tokens in real-time, emitting speakable clauses/sentences naturally without word chopping."""

    def __init__(self, min_clause_chars: int = 7, max_clause_chars: int = 26):
        self.min_clause_chars = min_clause_chars
        self.max_clause_chars = max_clause_chars
        self._buf = ""
        self._think_active = False
        self._first_chunk_emitted = False

    def feed(self, piece: str) -> list[str]:
        self._buf += piece
        if "<think>" in self._buf:
            self._think_active = True
        if self._think_active:
            if "</think>" in self._buf:
                self._buf = self._buf.split("</think>", 1)[1]
                self._think_active = False
            else:
                return []

        # Strip prefixes and special tokens
        self._buf = re.sub(r"^小揽[：:]\s*", "", self._buf)
        self._buf = re.sub(r"<\|.*?\|>", "", self._buf)
        self._buf = re.sub(r"</?think>", "", self._buf)

        chunks: list[str] = []
        curr_min = 6 if not self._first_chunk_emitted else self.min_clause_chars
        curr_max = self.max_clause_chars

        while True:
            # 1. Check for full sentence-ending punctuation (。！？!?\n)
            m_full = re.search(r"[。！？!?\n]+", self._buf)
            cut_pos = -1
            cut_end = -1
            is_clause = False

            if m_full:
                full_pos = m_full.start()
                if full_pos <= curr_max:
                    cut_pos = full_pos
                    cut_end = m_full.end()
                    is_clause = False
                else:
                    # Sentence is long, search for a comma before curr_max that is >= curr_min
                    best_comma = None
                    for m in re.finditer(r"[，,；;、：:]+", self._buf[:full_pos]):
                        if m.start() >= curr_min and m.start() <= curr_max:
                            best_comma = m
                    if best_comma:
                        cut_pos = best_comma.start()
                        cut_end = best_comma.end()
                        is_clause = True
                    else:
                        for m in re.finditer(r"[，,；;、：:]+", self._buf[:full_pos]):
                            if m.start() >= 5:
                                best_comma = m
                        if best_comma:
                            cut_pos = best_comma.start()
                            cut_end = best_comma.end()
                            is_clause = True
                        else:
                            cut_pos = full_pos
                            cut_end = m_full.end()
                            is_clause = False
            else:
                # No full stop yet. Only split on comma if buffer is getting long enough
                best_comma = None
                for m in re.finditer(r"[，,；;、：:]+", self._buf):
                    if m.start() >= curr_min:
                        best_comma = m
                        if (not self._first_chunk_emitted and m.start() >= curr_min) or m.start() >= 10 or len(self._buf) >= curr_max:
                            break

                if best_comma:
                    if (not self._first_chunk_emitted and best_comma.start() >= curr_min) or best_comma.start() >= 10 or len(self._buf) >= curr_max:
                        cut_pos = best_comma.start()
                        cut_end = best_comma.end()
                        is_clause = True

            if cut_pos >= 0:
                raw_chunk = self._buf[:cut_end].strip()
                self._buf = self._buf[cut_end:]
                clean = sanitize_tts_text(raw_chunk)
                if not self._first_chunk_emitted:
                    clean = _THINKING_PREFIX.sub("", clean).strip("，,。！？ ")
                if is_speakable(clean):
                    if is_clause:
                        if not clean.endswith(("。", "！", "？", "，")):
                            clean += "，"
                    else:
                        if not clean.endswith(("。", "！", "？")):
                            clean += "。"
                    chunks.append(clean)
                    self._first_chunk_emitted = True
                    curr_min = self.min_clause_chars
                continue

            # Fallback only when buffer exceeds 36 chars without ANY punctuation
            if len(self._buf) >= 36:
                m_con = re.search(r"(以及|并且|而且|但是|不过|然而|同时|因此|所以|包括|使得|导致)", self._buf[12:32])
                if m_con:
                    split_idx = 12 + m_con.start()
                    raw_chunk = self._buf[:split_idx].strip()
                    self._buf = self._buf[split_idx:]
                else:
                    raw_chunk = self._buf[:26].strip()
                    self._buf = self._buf[26:]
                clean = sanitize_tts_text(raw_chunk)
                if is_speakable(clean):
                    clean += "，"
                    chunks.append(clean)
                    self._first_chunk_emitted = True
                continue

            break

        return chunks

    def finish(self) -> list[str]:
        if self._think_active:
            self._buf = ""
            return []
        raw = self._buf.strip()
        self._buf = ""
        raw = re.sub(r"</?think>", "", raw)
        raw = re.sub(r"<.*?>", "", raw)
        clean = sanitize_tts_text(raw)
        if not self._first_chunk_emitted:
            clean = _THINKING_PREFIX.sub("", clean).strip("，,。！？ ")
        if is_speakable(clean):
            if not clean.endswith(("。", "！", "？")):
                clean += "。"
            return [clean]
        return []

