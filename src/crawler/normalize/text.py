"""Text cleanup and matching-key normalization. Pure functions."""

from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = re.compile(r"[​-‍﻿]")
_WS = re.compile(r"\s+")
_POSTAL_PREFIX = re.compile(r"^\(\s*\d{3,5}\s*\)\s*")
_SPECIAL_CITY = re.compile(r"(특별시|광역시|특별자치시|특별자치도)")
_PUNCT = re.compile(r"[^\w\s가-힣]", re.UNICODE)

# Scraped descriptions leak page chrome: an inline image-resize <script> (often
# wrapped in an HTML comment) and a third party's contact email. Strip those —
# but NOT generic "<...>", because artwork titles legitimately use angle brackets
# (e.g. "<패 : FAIT>") and would otherwise be destroyed.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_EMAIL_ADDR = r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"
# Consume a leading "이메일/메일/email" label with the address so no dangling
# label is left behind; a bare address (no label) is stripped by the second pass.
_EMAIL_LABELED = re.compile(r"\s*(?:이메일|메일|e-?mail)\s*[:：]?\s*" + _EMAIL_ADDR, re.I)
_EMAIL = re.compile(_EMAIL_ADDR)


def clean_whitespace(s: str) -> str:
    s = _ZERO_WIDTH.sub("", s)
    return _WS.sub(" ", s).strip()


_HORIZ_WS = re.compile(r"[^\S\n]+")  # whitespace except newlines
_AROUND_NL = re.compile(r"[^\S\n]*\n[^\S\n]*")
_BLANK_RUN = re.compile(r"\n{3,}")


def sanitize_description(s: str | None) -> str:
    """Strip scraped page chrome (leaked <script>/HTML comments) and third-party
    email PII from a free-text description, while PRESERVING paragraph breaks and
    the angle-bracket artwork titles that real descriptions contain. Only
    horizontal whitespace is collapsed — newlines are kept (capped at one blank
    line) so the rendered layout survives. Pure function."""
    if not s:
        return ""
    s = _ZERO_WIDTH.sub("", s)
    s = _HTML_COMMENT.sub(" ", s)
    s = _SCRIPT.sub(" ", s)
    s = _STYLE.sub(" ", s)
    s = _EMAIL_LABELED.sub(" ", s)
    s = _EMAIL.sub(" ", s)
    s = _HORIZ_WS.sub(" ", s)
    s = _AROUND_NL.sub("\n", s)
    s = _BLANK_RUN.sub("\n\n", s)
    return s.strip()


def normalize_name(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = clean_whitespace(s)
    s = _PUNCT.sub("", s)
    s = _WS.sub(" ", s).strip()
    return s.lower()


def normalize_address(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = _POSTAL_PREFIX.sub("", s)
    s = _SPECIAL_CITY.sub("", s)
    return clean_whitespace(s)
