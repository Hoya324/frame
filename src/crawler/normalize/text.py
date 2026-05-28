"""Text cleanup and matching-key normalization. Pure functions."""

from __future__ import annotations

import re
import unicodedata


_ZERO_WIDTH = re.compile(r"[​-‍﻿]")
_WS = re.compile(r"\s+")
_POSTAL_PREFIX = re.compile(r"^\(\s*\d{3,5}\s*\)\s*")
_SPECIAL_CITY = re.compile(r"(특별시|광역시|특별자치시|특별자치도)")
_PUNCT = re.compile(r"[^\w\s가-힣]", re.UNICODE)


def clean_whitespace(s: str) -> str:
    s = _ZERO_WIDTH.sub("", s)
    return _WS.sub(" ", s).strip()


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
