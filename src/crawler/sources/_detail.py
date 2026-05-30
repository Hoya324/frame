"""Shared helpers for detail-page enrichment across sources.

Sources fetch a per-exhibition detail page and pull a prose description out of
it. Markup differs per site, so each source picks its own body container, but
the cleanup and the meta-tag fallback are identical everywhere and live here.
"""

from __future__ import annotations

from selectolax.parser import HTMLParser

from crawler.normalize.text import clean_whitespace

# Descriptions shorter than this are almost always a stray label or caption
# rather than the real exhibition blurb, so callers treat them as "not found".
MIN_DESCRIPTION_LEN = 60


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
