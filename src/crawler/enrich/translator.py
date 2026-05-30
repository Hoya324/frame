"""Offline translation (Argos) plus source-language detection by script."""

from __future__ import annotations

import logging
import re
from typing import Protocol

logger = logging.getLogger(__name__)

TARGET_LOCALES: tuple[str, ...] = ("ko", "en", "ja")

_HANGUL = re.compile(r"[가-힣]")
_KANA = re.compile(r"[぀-ヿ]")
_HAN = re.compile(r"[一-鿿]")


def detect_lang(text: str) -> str:
    """Best-effort source language for our two CJK + latin world.

    Hangul -> ko. Kana or bare Han -> ja (Korean uses hangul, not bare hanja,
    so Han-only strings like '世田谷' are treated as Japanese). Else -> en.
    """
    if _HANGUL.search(text):
        return "ko"
    if _KANA.search(text) or _HAN.search(text):
        return "ja"
    return "en"


def targets_for(source_lang: str) -> list[str]:
    """Locales we translate INTO — every supported locale except the source."""
    return [loc for loc in TARGET_LOCALES if loc != source_lang]


class Translator(Protocol):
    def translate(self, text: str, from_code: str, to_code: str) -> str: ...
