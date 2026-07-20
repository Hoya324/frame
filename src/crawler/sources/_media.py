"""Photo/film/media keyword gate for broad (non-specialised) venues.

Dedicated photography galleries (Bresson, LUX, Place M, …) are 100% in-scope,
so their extractors seed ``category`` unconditionally. General art museums
(MMCA, SeMA, GMoMA, …) show mostly painting/sculpture and must keep only the
photo/film/media shows. The keyword tiers differ by text provenance:

* **Broad** keywords are safe on *curated short fields* — titles, theme
  keywords, one-line summaries — where a bare "사진"/"영상" reliably describes
  the show itself.
* **Strict** compounds are required for *long prose* (full descriptions),
  where broad words false-positive constantly ("사진 촬영 가능", "전시 영상
  제공", …).

The return value doubles as the ``category`` seed for
:func:`crawler.normalize.categories.map_medium` — hence the canonical
"사진"/"영상" tokens rather than the matched substring (map_medium knows
사진→PHOTO and 영상/미디어→VIDEO, but not e.g. 영화).
"""

from __future__ import annotations

import re

# Curated short fields (title / theme keywords / one-line summary).
# 백남준 (Nam June Paik) is a name, not a genre word, but a show titled after
# the founder of video art is video art — and the name never false-positives.
# Latin-script keywords are \b-bounded so English titles like "Photosynthesis"
# or "Immediate Presence" don't false-positive on embedded substrings; Korean
# tokens don't need boundaries (Hangul doesn't embed them accidentally).
_PHOTO_BROAD_RE = re.compile(r"사진|포토|\bphoto(?:s|graph\w*)?\b", re.IGNORECASE)
_VIDEO_BROAD_RE = re.compile(
    r"영상|비디오|미디어|필름|영화|시네마|백남준"
    r"|\bvideos?\b|\bmedia\b|\bfilms?\b|\bcinema\b"
    r"|무빙\s*이미지|\bmoving\s*images?\b|nam\s*june\s*paik",
    re.IGNORECASE,
)

# Long prose (full exhibition description) — compound terms only.
_PHOTO_STRICT_RE = re.compile(
    r"사진전|사진\s*작가|사진가|포토그래퍼|photographer", re.IGNORECASE
)
_VIDEO_STRICT_RE = re.compile(
    r"미디어\s*아트|비디오\s*아트|영상\s*설치|영상\s*작업|영상전|실험\s*영화"
    r"|영화제|media\s*art|video\s*art|film\s*festival|무빙\s*이미지"
    r"|moving\s*image|백남준|nam\s*june\s*paik",
    re.IGNORECASE,
)


def media_category(short_text: str, long_text: str | None = None) -> str | None:
    """Return a ``category`` seed when the show looks photo/film/media related.

    ``short_text`` is the concatenation of curated fields (title, theme
    keywords, summary); ``long_text`` is the optional full description.
    Returns ``"사진"``, ``"영상"``, or ``"사진 영상"`` (both → MIXED downstream);
    ``None`` means the exhibition is out of scope and should be skipped.
    """
    photo = bool(_PHOTO_BROAD_RE.search(short_text))
    video = bool(_VIDEO_BROAD_RE.search(short_text))
    if long_text and not (photo and video):
        photo = photo or bool(_PHOTO_STRICT_RE.search(long_text))
        video = video or bool(_VIDEO_STRICT_RE.search(long_text))
    if photo and video:
        return "사진 영상"
    if photo:
        return "사진"
    if video:
        return "영상"
    return None
