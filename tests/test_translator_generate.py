import httpx
import respx

from crawler.enrich.translator import GeminiTranslator


@respx.mock
def test_generate_returns_model_text():
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(return_value=httpx.Response(200, json={
        "candidates": [{"content": {"parts": [{"text": "생성된 해설"}]}}]
    }))
    t = GeminiTranslator(api_key="k", min_interval=0)
    out = t.generate("write a caption")
    assert out == "생성된 해설"
    assert route.called


@respx.mock
def test_generate_empty_response_returns_empty_string():
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(return_value=httpx.Response(200, json={"candidates": []}))
    t = GeminiTranslator(api_key="k", min_interval=0)
    assert t.generate("x") == ""
