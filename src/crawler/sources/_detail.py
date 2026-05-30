"""Shared helpers for detail-page enrichment across sources.

Sources fetch a per-exhibition detail page and pull a prose description out of
it. Markup differs per site, so each source picks its own body container, but
the cleanup and the meta-tag fallback are identical everywhere and live here.
"""

from __future__ import annotations

import re
from datetime import date

from selectolax.parser import HTMLParser

from crawler.normalize.text import clean_whitespace

# Descriptions shorter than this are almost always a stray label or caption
# rather than the real exhibition blurb, so callers treat them as "not found".
MIN_DESCRIPTION_LEN = 60

# Many KR/JP galleries hand-type the exhibition span into the body in varied
# forms: spaces around dots, a (요일)/(曜日) weekday in parens, and any of
# several CJK range separators. We strip the weekday parens first, then match a
# tolerant `Y.M.D ~ [Y.][M.]D` span and back-fill a yearless/monthless end.
_WEEKDAY_PAREN_RE = re.compile(r"[（(]\s*[월화수목금토일月火水木金土日]\s*[）)]")
_DATE_RANGE_RE = re.compile(
    r"(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?"  # start Y.M.D
    r"\s*[~∼〜～\-–—－−]\s*"  # range separator (incl. full-width/minus)
    r"(?:(\d{4})\s*\.\s*)?"  # optional end year
    r"(?:(\d{1,2})\s*\.\s*)?"  # optional end month
    r"(\d{1,2})\s*\.?"  # end day
)


def extract_date_range(text: str) -> str | None:
    """Pull the first ``Y.M.D ~ [Y.][M.]D`` span and canonicalize it.

    Weekday parens like ``(목)`` / ``(金)`` are stripped first so they don't sit
    between a date and its separator. A yearless/monthless end is back-filled
    from the start. Returns ``None`` when no parseable span is present. Emits a
    canonical ``YYYY.MM.DD~YYYY.MM.DD`` string that ``parse_date_range`` resolves
    cleanly.
    """
    cleaned = _WEEKDAY_PAREN_RE.sub(" ", text)
    m = _DATE_RANGE_RE.search(cleaned)
    if not m:
        return None
    sy, sm, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ey = int(m.group(4)) if m.group(4) else sy
    em = int(m.group(5)) if m.group(5) else sm
    ed = int(m.group(6))
    try:
        date(sy, sm, sd)
        date(ey, em, ed)
    except ValueError:
        return None
    return f"{sy:04d}.{sm:02d}.{sd:02d}~{ey:04d}.{em:02d}.{ed:02d}"


def meta_description(doc: HTMLParser) -> str | None:
    """Return the og:description / meta-description content, if present.

    Used as a fallback when a site exposes no stable body container. The text
    is often truncated by the CMS, but a clean summary beats nothing.
    """
    for sel in (
        'meta[property="og:description"]',
        'meta[name="description"]',
        'meta[name="twitter:description"]',
    ):
        node = doc.css_first(sel)
        if node is None:
            continue
        content = clean_whitespace(node.attributes.get("content") or "")
        if content:
            return content
    return None


def paragraphs_text(node) -> str:
    """Join a container's `<p>` children into a blank-line-separated blurb.

    Each paragraph is whitespace-collapsed; empty ones are dropped. Falls back
    to the node's whole text when it has no `<p>` children.
    """
    paras = [clean_whitespace(p.text()) for p in node.css("p")]
    paras = [p for p in paras if p]
    if paras:
        return "\n\n".join(paras)
    return clean_whitespace(node.text())
