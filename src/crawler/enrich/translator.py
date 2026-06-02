"""Translation backends (LLM via Gemini, offline Argos fallback) plus
source-language detection by script."""

from __future__ import annotations

import logging
import os
import re
from typing import Protocol

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

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
    first use. Argos ships no direct KO<->JA package and does not auto-pivot,
    so non-English pairs are routed through English (from->en->to)."""

    def __init__(self) -> None:
        self._ensured: set[tuple[str, str]] = set()

    @staticmethod
    def _legs(from_code: str, to_code: str) -> list[tuple[str, str]]:
        """Legs to walk for a translation. English-touching pairs go direct;
        any other pair pivots through English: from->en then en->to."""
        if from_code == "en" or to_code == "en":
            return [(from_code, to_code)]
        return [(from_code, "en"), ("en", to_code)]

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

        out = text
        for frm, to in self._legs(from_code, to_code):
            self._ensure_pair(frm, to)
            out = tr.translate(out, frm, to)
        return out


_LANG_NAMES: dict[str, str] = {"ko": "Korean", "en": "English", "ja": "Japanese"}

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# Gemini 2.0 Flash is deprecated (2026-06-01); 2.5 Flash is the current free-tier
# default. Override with GEMINI_MODEL when a newer Flash model is preferred.
_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def _is_retryable_gemini(exc: BaseException) -> bool:
    """Retry transient transport errors and 429/5xx; never retry 4xx like a bad
    request or an unknown model — those won't fix themselves."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


class GeminiTranslator:
    """Google Gemini LLM translator. Unlike Argos it needs no language-pair
    packages and no English pivot — a single prompt handles any pair, and the
    prompt instructs the model to preserve proper nouns (artist/venue/work
    names) instead of mistranslating them into unrelated words."""

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_GEMINI_MODEL,
        timeout: float = 30.0,
    ) -> None:
        self._key = api_key
        self._model = model
        self._client = httpx.Client(timeout=timeout)

    @classmethod
    def from_env(cls) -> GeminiTranslator:
        return cls(
            api_key=os.environ["GEMINI_API_KEY"],
            model=os.environ.get("GEMINI_MODEL", _DEFAULT_GEMINI_MODEL),
        )

    @staticmethod
    def _prompt(text: str, from_code: str, to_code: str) -> str:
        src = _LANG_NAMES.get(from_code, from_code)
        tgt = _LANG_NAMES.get(to_code, to_code)
        return (
            f"Translate the following photography-exhibition text from {src} "
            f"to {tgt}.\n"
            "Rules:\n"
            "- Preserve proper nouns (artist names, gallery/venue names, "
            "artwork titles): transliterate them naturally instead of "
            "translating their literal meaning; keep names already written in "
            "the target script or the Latin alphabet as they are.\n"
            "- Translate the meaning faithfully and naturally. Do not add, "
            "repeat, omit, or explain anything.\n"
            "- Output ONLY the translation, with no quotes, labels, or "
            "surrounding text.\n\n"
            f"Text:\n{text}"
        )

    @retry(
        retry=retry_if_exception(_is_retryable_gemini),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _generate(self, prompt: str) -> dict:
        r = self._client.post(
            _GEMINI_URL.format(model=self._model),
            params={"key": self._key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0},
            },
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _extract(data: dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)

    def translate(self, text: str, from_code: str, to_code: str) -> str:
        if not text or not text.strip():
            return text
        data = self._generate(self._prompt(text, from_code, to_code))
        out = self._extract(data).strip()
        # Empty / safety-blocked response: keep the original rather than wiping
        # the field to "" (which the UI would render as a blank translation).
        return out or text

    def close(self) -> None:
        self._client.close()
