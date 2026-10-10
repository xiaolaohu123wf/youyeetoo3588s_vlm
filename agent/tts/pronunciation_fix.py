"""TTS-only text fixes for common Matcha/VITS mis-segmentation."""
from __future__ import annotations

import re

# Matcha+jieba often reads 水果 as 水 + 果 (water + fruit). Rewrite food-context
# compounds to 鲜果, which is spoken naturally and avoids the bad break.
_FRUIT_WORD = re.compile(
    r"水果(?!店|园|味|汁|机|篮|摊|批|商|农|种植|产业|市场|行业|节|糖|酒|茶|干|冻|箱|刀|皮|核|肉|树|木|飞|捞)"
)

# Longest phrases first — applied before the generic 水果 rule.
_PHRASE_FIXES: tuple[tuple[str, str], ...] = (
    ("水果沙拉", "鲜果沙拉"),
    ("水果拼盘", "鲜果拼盘"),
    ("水果捞", "鲜果捞"),
)


def fix_tts_pronunciation(text: str) -> str:
    """Rewrite known bad G2P spans; display/LLM text should stay unchanged."""
    if not text:
        return text
    for src, dst in _PHRASE_FIXES:
        text = text.replace(src, dst)
    return _FRUIT_WORD.sub("鲜果", text)
