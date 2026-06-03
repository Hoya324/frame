import json
import sys
import types
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from crawler.enrich.translator import TARGET_LOCALES, detect_lang, targets_for

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


def _candidate(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_detect_lang_hangul():
    assert detect_lang("을지로의 밤") == "ko"


def test_detect_lang_kana_or_han():
    assert detect_lang("カリフォルニア") == "ja"
    assert detect_lang("世田谷") == "ja"  # 한자만 있어도 일본어로 본다 (한국어는 한글 사용)


def test_detect_lang_latin_fallback():
    assert detect_lang("BOOK AND SONS") == "en"


def test_targets_excludes_source():
    assert set(targets_for("ko")) == {"en", "ja"}
    assert set(targets_for("ja")) == {"en", "ko"}
    assert set(TARGET_LOCALES) == {"ko", "en", "ja"}


def _install_fake_argos(monkeypatch):
    pkg = types.ModuleType("argostranslate.package")
    trans = types.ModuleType("argostranslate.translate")
    pkg.get_installed_packages = MagicMock(return_value=[])
    pkg.get_available_packages = MagicMock(return_value=[])
    pkg.update_package_index = MagicMock()
    trans.translate = MagicMock(side_effect=lambda text, frm, to: f"[{to}]{text}")
    root = types.ModuleType("argostranslate")
    monkeypatch.setitem(sys.modules, "argostranslate", root)
    monkeypatch.setitem(sys.modules, "argostranslate.package", pkg)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", trans)
    return pkg, trans


def test_argos_translator_delegates(monkeypatch):
    from crawler.enrich.translator import ArgosTranslator

    _pkg, trans = _install_fake_argos(monkeypatch)
    t = ArgosTranslator()
    assert t.translate("hello", "en", "ko") == "[ko]hello"
    trans.translate.assert_called_once_with("hello", "en", "ko")


def test_argos_translator_blank_passthrough(monkeypatch):
    from crawler.enrich.translator import ArgosTranslator

    _install_fake_argos(monkeypatch)
    t = ArgosTranslator()
    assert t.translate("   ", "en", "ko") == "   "


def test_pivots_ko_to_ja_through_english(monkeypatch):
    # Argos has no direct KO<->JA package and does not auto-pivot, so a non-English
    # pair must be routed from->en then en->to. Earlier this raised AttributeError
    # in CI and dropped every Japanese translation of Korean content.
    from crawler.enrich.translator import ArgosTranslator

    _pkg, trans = _install_fake_argos(monkeypatch)
    t = ArgosTranslator()
    assert t.translate("제목", "ko", "ja") == "[ja][en]제목"
    assert trans.translate.call_args_list == [
        (("제목", "ko", "en"),),
        (("[en]제목", "en", "ja"),),
    ]


def test_ensure_installs_both_pivot_legs(monkeypatch):
    from crawler.enrich.translator import ArgosTranslator

    pkg, _trans = _install_fake_argos(monkeypatch)
    ko_en = MagicMock(from_code="ko", to_code="en")
    en_ja = MagicMock(from_code="en", to_code="ja")
    pkg.get_available_packages = MagicMock(return_value=[ko_en, en_ja])
    t = ArgosTranslator()
    t.translate("제목", "ko", "ja")
    ko_en.install.assert_called_once()
    en_ja.install.assert_called_once()


@respx.mock
def test_gemini_translates_with_target_language_and_text_in_prompt():
    from crawler.enrich.translator import GeminiTranslator

    route = respx.post(_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_candidate("정상\n"))
    )
    t = GeminiTranslator(api_key="fake-key", model="gemini-2.5-flash")
    # Single-leg, no English pivot: the LLM goes straight ja -> ko.
    assert t.translate("頂上", "ja", "ko") == "정상"

    sent = json.loads(route.calls.last.request.content)
    prompt = sent["contents"][0]["parts"][0]["text"]
    assert "頂上" in prompt  # source text is included
    assert "Korean" in prompt  # target language spelled out
    assert "Japanese" in prompt  # source language spelled out


@respx.mock
def test_gemini_preserves_proper_nouns_instruction():
    from crawler.enrich.translator import GeminiTranslator

    route = respx.post(_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_candidate("x"))
    )
    GeminiTranslator(api_key="k").translate("육명심", "ko", "en")
    prompt = json.loads(route.calls.last.request.content)["contents"][0]["parts"][0][
        "text"
    ]
    assert "proper noun" in prompt.lower()


def test_gemini_blank_passthrough_makes_no_request():
    from crawler.enrich.translator import GeminiTranslator

    # No respx routes registered: any HTTP call would raise, proving none is made.
    t = GeminiTranslator(api_key="k")
    assert t.translate("   ", "ko", "en") == "   "


@respx.mock
def test_gemini_empty_candidates_returns_original():
    from crawler.enrich.translator import GeminiTranslator

    # Safety-blocked / empty responses must not overwrite the field with "".
    respx.post(_GEMINI_URL).mock(return_value=httpx.Response(200, json={}))
    t = GeminiTranslator(api_key="k")
    assert t.translate("원문 그대로", "ko", "en") == "원문 그대로"


@respx.mock
def test_gemini_throttles_requests_to_respect_the_rate_limit():
    # The free tier caps RPM; without client-side spacing the backfill fires
    # requests flat-out, trips 429 immediately, and burns the run retrying. A
    # min interval between calls keeps it under the limit so requests succeed.
    from crawler.enrich.translator import GeminiTranslator

    respx.post(_GEMINI_URL).mock(return_value=httpx.Response(200, json=_candidate("x")))
    clock = {"t": 100.0}
    slept: list[float] = []

    def fake_sleep(s):
        slept.append(s)
        clock["t"] += s

    t = GeminiTranslator(
        api_key="k", min_interval=4.5, sleep=fake_sleep, monotonic=lambda: clock["t"]
    )
    t.translate("a", "ja", "ko")  # first call: no prior request, no wait
    t.translate("b", "ja", "ko")  # must wait one interval
    t.translate("c", "ja", "ko")  # and again
    assert slept == [4.5, 4.5]


def test_gemini_no_throttle_when_interval_zero():
    from crawler.enrich.translator import GeminiTranslator

    slept: list[float] = []
    t = GeminiTranslator(api_key="k", min_interval=0, sleep=lambda s: slept.append(s))
    # blank passthrough makes no request; just assert the knob disables sleeping
    t.translate("   ", "ja", "ko")
    assert slept == []


@respx.mock
def test_gemini_batch_translates_many_jobs_in_one_request():
    # The free tier caps requests, not tokens, so the backfill packs many
    # (text, src, tgt) jobs into a single call and gets an aligned JSON array.
    from crawler.enrich.translator import GeminiTranslator

    route = respx.post(_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_candidate('["정상", "頂上です"]'))
    )
    t = GeminiTranslator(api_key="k", min_interval=0)
    out = t.translate_batch([("頂上", "ja", "ko"), ("Top", "en", "ja")])
    assert out == ["정상", "頂上です"]
    assert route.call_count == 1  # one HTTP request for both jobs
    body = json.loads(route.calls.last.request.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    prompt = body["contents"][0]["parts"][0]["text"]
    assert "proper noun" in prompt.lower()


def test_gemini_batch_empty_jobs_makes_no_request():
    from crawler.enrich.translator import GeminiTranslator

    # No respx route registered: a request would raise. Empty in -> empty out.
    assert GeminiTranslator(api_key="k").translate_batch([]) == []


@respx.mock
def test_gemini_batch_keeps_original_on_blank_item():
    from crawler.enrich.translator import GeminiTranslator

    respx.post(_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_candidate('["", "x"]'))
    )
    t = GeminiTranslator(api_key="k", min_interval=0)
    out = t.translate_batch([("원문", "ko", "en"), ("a", "ko", "en")])
    assert out == ["원문", "x"]  # blank/blocked item falls back to the original


@respx.mock
def test_gemini_batch_raises_on_count_mismatch():
    # A misaligned array must not silently mis-map translations onto fields.
    from crawler.enrich.translator import GeminiTranslator

    respx.post(_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_candidate('["only one"]'))
    )
    t = GeminiTranslator(api_key="k", min_interval=0)
    with pytest.raises(ValueError):
        t.translate_batch([("a", "ja", "ko"), ("b", "ja", "ko")])


@respx.mock
def test_gemini_batch_throttles_once_per_request():
    from crawler.enrich.translator import GeminiTranslator

    respx.post(_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_candidate('["a","b","c"]'))
    )
    clock = {"t": 100.0}
    slept: list[float] = []

    def fake_sleep(s):
        slept.append(s)
        clock["t"] += s

    t = GeminiTranslator(
        api_key="k", min_interval=4.5, sleep=fake_sleep, monotonic=lambda: clock["t"]
    )
    t.translate_batch([("a", "ko", "en"), ("b", "ko", "en"), ("c", "ko", "en")])
    assert slept == []  # first request, no prior call -> no wait


@respx.mock
def test_gemini_rotates_across_multiple_keys():
    # Separate projects each have their own free-tier quota, so rotating keys
    # round-robin multiplies aggregate throughput.
    from crawler.enrich.translator import GeminiTranslator

    route = respx.post(_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_candidate("x"))
    )
    t = GeminiTranslator(api_key=["k1", "k2", "k3"], min_interval=0)
    for _ in range(4):
        t.translate("a", "ja", "ko")
    used = [c.request.url.params.get("key") for c in route.calls]
    assert used == ["k1", "k2", "k3", "k1"]


def test_gemini_from_env_parses_comma_separated_keys(monkeypatch):
    from crawler.enrich.translator import GeminiTranslator

    monkeypatch.setenv("GEMINI_API_KEY", " k1 , k2 ,k3 ")
    t = GeminiTranslator.from_env()
    assert t._keys == ["k1", "k2", "k3"]


@respx.mock
def test_gemini_throttles_each_key_independently():
    # With 3 keys round-robin, the first request on each key needs no wait, so
    # the per-key spacing only kicks in once a key is reused — ~3x the rate.
    from crawler.enrich.translator import GeminiTranslator

    respx.post(_GEMINI_URL).mock(return_value=httpx.Response(200, json=_candidate("x")))
    clock = {"t": 100.0}
    slept: list[float] = []

    def fake_sleep(s):
        slept.append(s)
        clock["t"] += s

    t = GeminiTranslator(
        api_key=["k1", "k2", "k3"],
        min_interval=4.5,
        sleep=fake_sleep,
        monotonic=lambda: clock["t"],
    )
    for _ in range(3):  # one request per key, all fresh -> no waiting
        t.translate("a", "ja", "ko")
    assert slept == []


def test_gemini_retry_predicate():
    from crawler.enrich.translator import _is_retryable_gemini

    req = httpx.Request("POST", _GEMINI_URL)

    def status_error(code: int) -> httpx.HTTPStatusError:
        resp = httpx.Response(code, request=req)
        return httpx.HTTPStatusError("err", request=req, response=resp)

    assert _is_retryable_gemini(httpx.ConnectError("boom", request=req)) is True
    assert _is_retryable_gemini(status_error(429)) is True  # rate limited
    assert _is_retryable_gemini(status_error(503)) is True  # transient
    assert _is_retryable_gemini(status_error(400)) is False  # bad request
    assert _is_retryable_gemini(status_error(404)) is False  # wrong model
