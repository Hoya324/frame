"""Generate finished ko/en/ja editorial text for masters and their works.

Strategy: generate the Korean original with Gemini, then reuse the existing
translator to produce en/ja. Results are cached by a hash of the inputs."""

from __future__ import annotations

import hashlib
from typing import Protocol

from crawler.masters.cache import CommentaryCache, LocalizedText
from crawler.masters.models import MasterSeed, RawWork


class TextEngine(Protocol):
    def generate(self, prompt: str, *, temperature: float = ...) -> str: ...
    def translate_batch(self, jobs: list[tuple[str, str, str]]) -> list[str]: ...


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _master_prompt(seed: MasterSeed) -> str:
    years = f"{seed.birth_year or '?'}–{seed.death_year or '?'}"
    return (
        "당신은 사진사(史) 큐레이터입니다. 아래 사진 거장을 한국어로 소개하는 "
        "글을 쓰세요. 3~4문장으로, 이 작가가 왜 사진사에서 중요한지, 어떤 시선과 "
        "주제를 가졌는지 따뜻하고 읽기 좋은 문체로. 군더더기·인사말·따옴표 없이 "
        "본문만 출력하세요.\n"
        f"작가: {seed.name} ({seed.nationality}, {years})"
    )


def _tagline_prompt(seed: MasterSeed) -> str:
    return (
        "아래 사진 거장을 한 줄(15자 내외)로 표현하는 한국어 태그라인을 쓰세요. "
        "예: '파리를 기록한 사진의 선구자'. 따옴표·군더더기 없이 한 줄만.\n"
        f"작가: {seed.name}"
    )


def _work_prompt(work: RawWork, master_name: str) -> str:
    facts = ", ".join(p for p in [work.title, work.year, work.medium] if p)
    return (
        "당신은 사진 비평가입니다. 아래 사진 작품을 한국어로 2~3문장 해설하세요. "
        "왜 좋은 사진인지(빛·구도·순간·역사적 의미 등)와 어떤 맥락에서 찍혔는지를 "
        "구체적으로. 인사말·따옴표 없이 본문만 출력하세요.\n"
        f"작가: {master_name}\n작품 정보: {facts}"
    )


class CommentaryWriter:
    def __init__(self, engine: TextEngine, cache: CommentaryCache) -> None:
        self._engine = engine
        self._cache = cache

    def _localize(self, key: str, facts_hash: str, prompt: str) -> LocalizedText:
        hit = self._cache.get(key, facts_hash)
        if hit is not None:
            return hit
        ko = self._engine.generate(prompt)
        en, ja = self._engine.translate_batch([(ko, "ko", "en"), (ko, "ko", "ja")])
        value = LocalizedText(ko=ko, en=en, ja=ja)
        self._cache.put(key, facts_hash, value)
        # Persist after every generation so a run interrupted by the daily quota
        # cap keeps its progress and the next run resumes from the cache.
        self._cache.save()
        return value

    def master_text(self, seed: MasterSeed) -> LocalizedText:
        h = _hash("master", seed.name, str(seed.birth_year), str(seed.death_year))
        hit = self._cache.get(f"master:{seed.id}", h)
        if hit is not None:
            return hit
        bio_ko = self._engine.generate(_master_prompt(seed))
        tag_ko = self._engine.generate(_tagline_prompt(seed))
        en_bio, ja_bio, en_tag, ja_tag = self._engine.translate_batch([
            (bio_ko, "ko", "en"), (bio_ko, "ko", "ja"),
            (tag_ko, "ko", "en"), (tag_ko, "ko", "ja"),
        ])
        value = LocalizedText(ko=bio_ko, en=en_bio, ja=ja_bio,
                              ko_tagline=tag_ko, en_tagline=en_tag, ja_tagline=ja_tag)
        self._cache.put(f"master:{seed.id}", h, value)
        self._cache.save()  # persist incrementally (see _localize)
        return value

    def work_text(self, work: RawWork, master_name: str) -> LocalizedText:
        h = _hash("work", work.title, work.year or "", work.medium or "")
        return self._localize(f"work:{work.work_id}", h, _work_prompt(work, master_name))
