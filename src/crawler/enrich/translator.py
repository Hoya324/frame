"""Translation backends (LLM via Gemini, offline Argos fallback) plus
source-language detection by script."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from typing import Protocol

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt

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

    def translate_batch(self, jobs: list[tuple[str, str, str]]) -> list[str]:
        """Translate many (text, from_code, to_code) jobs, returning results
        aligned by index. Backends that can't truly batch loop translate()."""
        ...


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

    def translate_batch(self, jobs: list[tuple[str, str, str]]) -> list[str]:
        # Argos is local/offline; there's no request to batch, so just loop.
        return [self.translate(text, src, tgt) for text, src, tgt in jobs]


_LANG_NAMES: dict[str, str] = {"ko": "Korean", "en": "English", "ja": "Japanese"}

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# Gemini 2.0 Flash is deprecated (2026-06-01); 2.5 Flash is the current free-tier
# default. Override with GEMINI_MODEL when a newer Flash model is preferred.
_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# Free-tier Flash allows ~15 requests/minute. Space calls ~4.5s apart (~13 RPM)
# so the backfill stays under the cap instead of tripping 429 on every burst and
# wasting the run on retry backoff. Override with GEMINI_MIN_INTERVAL_SEC.
_DEFAULT_GEMINI_MIN_INTERVAL = 4.5

# Longest a 429 RetryInfo delay we'll actually wait out before giving up. A
# per-minute block clears in well under this; a per-day block reports a delay far
# beyond it (or is flagged daily), so we fail fast and let the next run resume.
_MAX_RETRY_WAIT = 90.0


def _gemini_retry_delay(exc: BaseException) -> float | None:
    """Seconds from a 429's RetryInfo, or None if not a parseable 429 delay."""
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code != 429:
        return None
    try:
        details = exc.response.json().get("error", {}).get("details", [])
    except Exception:
        return None
    for d in details:
        if isinstance(d, dict) and str(d.get("@type", "")).endswith("RetryInfo"):
            m = re.match(r"^([0-9.]+)s$", str(d.get("retryDelay", "")))
            if m:
                return float(m.group(1))
    return None


def _gemini_is_daily_429(exc: BaseException) -> bool:
    """True when a 429 is a per-day quota block (vs a transient per-minute one)."""
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code != 429:
        return False
    try:
        details = exc.response.json().get("error", {}).get("details", [])
    except Exception:
        return False
    for d in details:
        if not isinstance(d, dict):
            continue
        for v in d.get("violations", []) or []:
            blob = f"{v.get('quotaId', '')} {v.get('quotaMetric', '')}".lower()
            if "perday" in blob.replace("_", "").replace(" ", "") or "daily" in blob:
                return True
    return False


def _is_retryable_gemini(exc: BaseException) -> bool:
    """Retry transient transport errors and 5xx. For 429: retry a short
    (per-minute) block — honoring its RetryInfo delay — but give up immediately on
    a per-day block or one whose delay exceeds _MAX_RETRY_WAIT, so the run fails
    fast and resumes next time instead of hanging for hours."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (500, 502, 503, 504):
            return True
        if code == 429:
            if _gemini_is_daily_429(exc):
                return False
            delay = _gemini_retry_delay(exc)
            return delay is None or delay <= _MAX_RETRY_WAIT
    return False


def _gemini_wait(retry_state) -> float:
    """Wait the 429's RetryInfo delay (capped) when present, else back off
    exponentially for transport/5xx errors."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    delay = _gemini_retry_delay(exc) if exc is not None else None
    if delay is not None:
        return min(delay + 1.0, _MAX_RETRY_WAIT)
    return min(2.0 ** (retry_state.attempt_number - 1), 30.0)


class GeminiTranslator:
    """Google Gemini LLM translator. Unlike Argos it needs no language-pair
    packages and no English pivot — a single prompt handles any pair, and the
    prompt instructs the model to preserve proper nouns (artist/venue/work
    names) instead of mistranslating them into unrelated words."""

    def __init__(
        self,
        api_key: str | list[str],
        model: str = _DEFAULT_GEMINI_MODEL,
        # Generous read timeout: a batched request asks the model to generate a
        # whole JSON array, which (with 2.5-flash thinking) can take well over the
        # old 30s and was timing the requests out. Override with GEMINI_TIMEOUT_SEC.
        timeout: float = 120.0,
        min_interval: float = _DEFAULT_GEMINI_MIN_INTERVAL,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._keys = [api_key] if isinstance(api_key, str) else list(api_key)
        if not self._keys:
            raise ValueError("GeminiTranslator needs at least one API key")
        self._model = model
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._min_interval = min_interval
        self._sleep = sleep
        self._monotonic = monotonic
        # Each key (typically a separate free-tier project) has its own quota, so
        # round-robin spreads load and the per-key cooldown lets the aggregate
        # rate scale ~linearly with the number of keys.
        self._next_at = [0.0] * len(self._keys)
        self._key_idx = 0

    @classmethod
    def from_env(cls) -> GeminiTranslator:
        # GEMINI_API_KEY may hold several comma-separated keys (each ideally in a
        # separate project) to combine their free-tier quotas.
        raw = os.environ["GEMINI_API_KEY"]
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        return cls(
            api_key=keys,
            model=os.environ.get("GEMINI_MODEL", _DEFAULT_GEMINI_MODEL),
            timeout=float(os.environ.get("GEMINI_TIMEOUT_SEC", "120")),
            min_interval=float(
                os.environ.get(
                    "GEMINI_MIN_INTERVAL_SEC", str(_DEFAULT_GEMINI_MIN_INTERVAL)
                )
            ),
        )

    def _acquire_key(self) -> str:
        """Pick the next key round-robin, blocking only until that key's own
        min_interval has elapsed (so N keys give ~N× the request rate)."""
        i = self._key_idx
        self._key_idx = (self._key_idx + 1) % len(self._keys)
        if self._min_interval > 0:
            wait = self._next_at[i] - self._monotonic()
            if wait > 0:
                self._sleep(wait)
            self._next_at[i] = self._monotonic() + self._min_interval
        return self._keys[i]

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

    @staticmethod
    def _batch_prompt(jobs: list[tuple[str, str, str]]) -> str:
        # Items are passed as a JSON array so multi-line text survives intact;
        # the model returns a JSON array of translations aligned by index.
        items = [
            {
                "from": _LANG_NAMES.get(src, src),
                "to": _LANG_NAMES.get(tgt, tgt),
                "text": text,
            }
            for text, src, tgt in jobs
        ]
        return (
            "Translate each photography-exhibition item below from its `from` "
            "language to its `to` language.\n"
            "Rules:\n"
            "- Preserve proper nouns (artist names, gallery/venue names, "
            "artwork titles): transliterate them naturally instead of "
            "translating their literal meaning; keep names already written in "
            "the target script or the Latin alphabet as they are.\n"
            "- Translate the meaning faithfully and naturally. Do not add, "
            "repeat, omit, or explain anything.\n"
            "- Return ONLY a JSON array of strings with exactly one element per "
            "item, in the same order: element i is the translation of item i.\n\n"
            "Items (JSON):\n" + json.dumps(items, ensure_ascii=False)
        )

    @retry(
        retry=retry_if_exception(_is_retryable_gemini),
        wait=_gemini_wait,
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _post(self, payload: dict, key: str) -> dict:
        r = self._client.post(
            _GEMINI_URL.format(model=self._model),
            params={"key": key},
            json=payload,
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

    def translate_batch(self, jobs: list[tuple[str, str, str]]) -> list[str]:
        """Translate many (text, source, target) jobs in a single request and
        return translations aligned by index. The free tier limits requests, not
        tokens, so batching many jobs per call is the throughput lever."""
        if not jobs:
            return []
        key = self._acquire_key()
        data = self._post({
            "contents": [{"parts": [{"text": self._batch_prompt(jobs)}]}],
            # No maxOutputTokens: let the model default (large) apply so a big
            # batch's JSON array isn't truncated, which would fail parsing.
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }, key)
        raw = self._extract(data).strip()
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError as e:
            raise ValueError(f"gemini batch: invalid JSON response: {raw[:120]}") from e
        if isinstance(parsed, dict):  # tolerate {"translations": [...]} shapes
            parsed = next((v for v in parsed.values() if isinstance(v, list)), None)
        if not isinstance(parsed, list) or len(parsed) != len(jobs):
            raise ValueError(
                f"gemini batch: expected {len(jobs)} items, got "
                f"{len(parsed) if isinstance(parsed, list) else type(parsed).__name__}"
            )
        out: list[str] = []
        for (text, _src, _tgt), got in zip(jobs, parsed, strict=True):
            s = got.strip() if isinstance(got, str) else ""
            out.append(s or text)  # blank/blocked item keeps the original
        return out

    def translate(self, text: str, from_code: str, to_code: str) -> str:
        if not text or not text.strip():
            return text
        key = self._acquire_key()
        data = self._post({
            "contents": [{"parts": [{"text": self._prompt(text, from_code, to_code)}]}],
            "generationConfig": {"temperature": 0},
        }, key)
        out = self._extract(data).strip()
        # Empty / safety-blocked response: keep the original rather than wiping
        # the field to "" (which the UI would render as a blank translation).
        return out or text

    def generate(self, prompt: str, *, temperature: float = 0.4) -> str:
        """Generate free-form text from a prompt (not a translation). Reuses the
        same key rotation + retry/quota handling as translate(). Returns the
        model text, or "" when the response is empty/blocked."""
        if not prompt or not prompt.strip():
            return ""
        key = self._acquire_key()
        data = self._post({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }, key)
        return self._extract(data).strip()

    def close(self) -> None:
        self._client.close()
