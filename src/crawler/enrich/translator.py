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


class ArgosTranslator:
    """Argos Translate wrapper. Installs missing language-pair packages on
    first use, then delegates to argostranslate's auto-pivoting translate()."""

    def __init__(self) -> None:
        self._ensured: set[tuple[str, str]] = set()

    def _ensure_pair(self, from_code: str, to_code: str) -> None:
        if (from_code, to_code) in self._ensured:
            return
        import argostranslate.package as pkg

        installed = {
            (p.from_code, p.to_code) for p in pkg.get_installed_packages()
        }
        if (from_code, to_code) not in installed:
            try:
                pkg.update_package_index()
                available = pkg.get_available_packages()
                match = next(
                    (
                        p
                        for p in available
                        if p.from_code == from_code and p.to_code == to_code
                    ),
                    None,
                )
                if match is not None:
                    match.install()
            except Exception:
                logger.exception(
                    "argos: failed to install %s->%s package", from_code, to_code
                )
        self._ensured.add((from_code, to_code))

    def translate(self, text: str, from_code: str, to_code: str) -> str:
        if not text or not text.strip():
            return text
        import argostranslate.translate as tr

        self._ensure_pair(from_code, to_code)
        return tr.translate(text, from_code, to_code)
