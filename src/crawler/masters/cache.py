"""On-disk cache of generated commentary so reruns don't re-call Gemini."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalizedText:
    ko: str
    en: str
    ja: str
    ko_tagline: str = ""
    en_tagline: str = ""
    ja_tagline: str = ""


class CommentaryCache:
    """JSON file mapping ``id -> {"facts_hash": str, "text": {ko,en,ja}}``."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._data: dict[str, dict] = {}
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self._data = {}

    def get(self, key: str, facts_hash: str) -> LocalizedText | None:
        entry = self._data.get(key)
        if not entry or entry.get("facts_hash") != facts_hash:
            return None
        t = entry.get("text") or {}
        return LocalizedText(
            ko=t.get("ko", ""),
            en=t.get("en", ""),
            ja=t.get("ja", ""),
            ko_tagline=t.get("ko_tagline", ""),
            en_tagline=t.get("en_tagline", ""),
            ja_tagline=t.get("ja_tagline", ""),
        )

    def put(self, key: str, facts_hash: str, value: LocalizedText) -> None:
        self._data[key] = {"facts_hash": facts_hash, "text": asdict(value)}

    def clear(self) -> None:
        self._data = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
