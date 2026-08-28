"""Light cleanup of streaming ASR text before LLM."""
from __future__ import annotations

import re

_DUP_CHAR = re.compile(r"(.)\1{1,}")
_DUP_GREET = re.compile(r"^(你好[呀啊]?)+")
_PURE_GREET = re.compile(r"^你好[呀啊]?$")
_NAME_FIX = re.compile(r"小懒|小兰|小蓝|小榄|影力")
_GREETING_NAME = re.compile(r"^(?:你好|电好)?小揽[，,、\s]*", re.IGNORECASE)
# Streaming ASR 常见误识：小揽→引力、你都→引力都；句首噪声「因不在」等
_GRAVITY_FIX = re.compile(r"引力都")
_NAME_HOMOPHONE = re.compile(r"^引力(?=[都会]|叫|是)")
_LEADING_JUNK = re.compile(r"^(?:因不在|在小揽|小揽在不在|在不在|那个|那个啥)")
# 句首误识别噪声：保留「请告诉我/请说/帮我…」及之后内容
_INTENT_START = re.compile(r"(请告诉我|请说|请讲|能不能|如何|怎么|帮我|我想)")


def normalize_user_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    text = _DUP_CHAR.sub(r"\1", text)
    text = _DUP_GREET.sub("你好", text)
    if text.startswith("电好"):
        text = "你好" + text[2:]
    text = re.sub(r"(?i)^so好", "你好", text)
    text = re.sub(r"讲讲话", "讲个笑话", text)
    text = re.sub(r"给我讲话", "给我讲个笑话", text)
    text = re.sub(r"讲个故$", "讲个故事", text)
    text = re.sub(r"^党故事", "讲个故事", text)
    text = re.sub(r"来我睡觉", "哄我睡觉", text)
    # 短问候 + ASR 幻听后缀（如「你好…你叫什么名字」）→ 只保留问候
    if _PURE_GREET.match(text) or (
        text.startswith("你好") and len(text) <= 4 and "叫什么" not in text
    ):
        text = "你好"
    text = re.sub(r"^(?:辩了|变了|便了)", "", text)
    text = _GRAVITY_FIX.sub("你都", text)
    text = _NAME_HOMOPHONE.sub("小揽", text)
    text = _NAME_FIX.sub("小揽", text)
    text = _GREETING_NAME.sub("", text)
    text = _LEADING_JUNK.sub("", text)
    text = re.sub(r"因色|音瑟|银色", "音色", text)
    m = _INTENT_START.search(text)
    if m and m.start() > 0 and m.start() <= 8:
        text = text[m.start() :]
    text = re.sub(r"\s+", "", text)
    return text.strip()
