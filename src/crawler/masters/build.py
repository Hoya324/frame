"""Assemble masters.json from the roster, museum clients and the writer."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from crawler.masters.cache import LocalizedText
from crawler.masters.commentary import CommentaryWriter
from crawler.masters.models import MasterSeed, RawWork
from crawler.masters.museums.base import MuseumClient
from crawler.masters.select import select_works

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = "web/public/data/masters.json"


def _work_json(work: RawWork, text: LocalizedText) -> dict:
    return {
        "id": work.work_id,
        "title": work.title,
        "year": work.year,
        "medium": work.medium,
        "imageUrl": work.image_url,
        "thumbUrl": work.thumb_url,
        "source": work.source,
        "sourceUrl": work.source_url,
        "credit": work.credit,
        "commentary": text.ko,  # ko flat
        "tr": {"en": {"commentary": text.en}, "ja": {"commentary": text.ja}},
    }


def build_masters(
    roster: list[MasterSeed],
    clients: dict[str, MuseumClient],
    writer: CommentaryWriter,
    generated_at: datetime,
    cap: int = 10,
) -> dict:
    masters: list[dict] = []
    for seed in roster:
        works = select_works(seed, clients, cap=cap)
        if not works:
            logger.warning("masters: %s has no usable works; skipping", seed.id)
            continue
        mt = writer.master_text(seed)
        work_jsons = [_work_json(w, writer.work_text(w, seed.name)) for w in works]
        masters.append({
            "id": seed.id,
            "name": seed.name,
            "lang": "ko",
            "region": seed.region,
            "nationality": seed.nationality,
            "birthYear": seed.birth_year,
            "deathYear": seed.death_year,
            "tagline": mt.ko_tagline,
            "bio": mt.ko,
            "portraitUrl": seed.portrait_url,
            "tr": {
                "en": {"tagline": mt.en_tagline, "bio": mt.en},
                "ja": {"tagline": mt.ja_tagline, "bio": mt.ja},
            },
            "works": work_jsons,
        })
    return {"generated_at": generated_at.isoformat(), "masters": masters}


def write_masters(catalog: dict, path: str = DEFAULT_OUTPUT) -> int:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2, allow_nan=False)
    return len(catalog["masters"])
