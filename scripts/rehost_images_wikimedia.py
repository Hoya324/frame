"""Re-point the masters' images to Wikimedia Commons (PD), which—unlike AIC's
Cloudflare-gated IIIF server—hotlinks reliably from any origin. For each work we
search Commons for the same artist + title, keep the existing commentary, and
swap the image URL. Works with no confident PD match on Commons are dropped.
Master portraits are filled from a Commons portrait of the photographer.

Run from repo root:  python scripts/rehost_images_wikimedia.py
"""
from __future__ import annotations

import json
import os
import re
import time

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MJ = os.path.join(ROOT, "web", "public", "data", "masters.json")
API = "https://commons.wikimedia.org/w/api.php"
H = {"User-Agent": "frame-photo/1.0 (hoyana1225@gmail.com)"}

client = httpx.Client(headers=H, timeout=40)


def _is_pd(extmeta: dict) -> bool:
    lic = (extmeta.get("LicenseShortName", {}).get("value") or "").lower()
    return "public domain" in lic or "cc0" in lic or "pd-" in lic


def _clean_title(title: str) -> str:
    t = re.sub(r"\([^)]*\)", " ", title)            # drop parentheticals
    t = re.sub(r"\bfrom the series\b.*", " ", t, flags=re.I)
    t = re.sub(r"[\"']", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _search_files(query: str, limit: int = 8) -> list[dict]:
    r = client.get(API, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": 1200,
    })
    pages = (r.json().get("query") or {}).get("pages", {})
    # search results carry an 'index'; sort by it for relevance order
    return sorted(pages.values(), key=lambda p: p.get("index", 999))


def _pick(pages: list[dict], surname: str) -> dict | None:
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii or "image" not in (ii.get("mime") or ""):
            continue
        em = ii.get("extmetadata") or {}
        if not _is_pd(em):
            continue
        hay = (p.get("title", "") + " " + (em.get("Artist", {}).get("value") or "")).lower()
        if surname.lower() not in hay:
            continue
        return ii
    return None


# NOTE: do NOT hand-edit the width token of a Commons thumburl — Wikimedia
# rejects arbitrary width/filename combinations (HTTP 400). Use the exact
# API-rendered thumburl (iiurlwidth) as-is; it is verified to hotlink (200).


def main() -> None:
    data = json.load(open(MJ, encoding="utf-8"))
    kept = dropped = 0
    for m in data["masters"]:
        surname = m["name"].split("(")[0].strip().split()[-1]
        # master portrait
        pp = _search_files(f"{m['name']} portrait", 8) or _search_files(m["name"], 8)
        port = _pick(pp, surname)
        if port:
            m["portraitUrl"] = port["thumburl"]
        time.sleep(0.2)

        new_works = []
        for w in m["works"]:
            ct = _clean_title(w["title"])
            ii = _pick(_search_files(f'{m["name"]} {ct}', 8), surname)
            if not ii:
                ii = _pick(_search_files(f'{surname} {ct}', 8), surname)
            time.sleep(0.2)
            if not ii:
                dropped += 1
                continue
            w["imageUrl"] = ii["thumburl"]   # API-rendered ~1200px, reliable
            w["thumbUrl"] = ii["thumburl"]   # reuse; grids scale it down
            w["source"] = "wikimedia"
            w["sourceUrl"] = ii.get("descriptionurl") or ii.get("url")
            w["credit"] = "Wikimedia Commons · Public domain"
            new_works.append(w)
            kept += 1
        m["works"] = new_works
        print(f"  {m['id']:24s} {len(new_works)} works (portrait={'y' if m.get('portraitUrl') else 'n'})")

    # drop masters that ended up with no works
    before = len(data["masters"])
    data["masters"] = [m for m in data["masters"] if m["works"]]
    json.dump(data, open(MJ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    client.close()
    print(f"kept {kept} works, dropped {dropped}; masters {before}->{len(data['masters'])}")


if __name__ == "__main__":
    main()
