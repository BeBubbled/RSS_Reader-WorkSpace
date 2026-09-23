import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app import worker
from app.ai import get_translation_target, model_supports, test_provider_connection as check_provider_connection
from app.models import AIModel, AIProvider, AppSetting
from app.worker import _call_llm, _call_translator, _candidates, _deepl_target


def make_provider(provider_type: str, enabled: bool = True, health: str = "unknown") -> AIProvider:
    return AIProvider(id=uuid4(), name=f"p-{provider_type}", provider_type=provider_type, enabled=enabled, health_status=health, timeout_seconds=60, concurrency_limit=2)


def make_model(capabilities: list[str], provider_id=None) -> AIModel:
    return AIModel(provider_id=provider_id, model_key="m", display_name="m", capabilities_json=json.dumps(capabilities))


def test_model_supports_exact_and_prefix_match() -> None:
    model = make_model(["summarize", "translate", "extract.keywords"])
    assert model_supports(model, "summarize")
    assert model_supports(model, "translate.en_to_zh")
    assert model_supports(model, "translate.de_to_zh")
    assert model_supports(model, "extract.keywords")
    assert not model_supports(model, "classify")
    assert not model_supports(model, "extract.entities")


def test_deepl_target_uppercases_language() -> None:
    assert _deepl_target("zh") == "ZH"


@pytest.mark.asyncio
async def test_translation_target_defaults_to_zh() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    assert await get_translation_target(session) == "zh"


@pytest.mark.asyncio
async def test_translation_target_reads_setting() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=AppSetting(key="translation_target_language", value_json=json.dumps("en")))
    assert await get_translation_target(session) == "en"


def _session_with(providers: list[AIProvider], models: list[AIModel]) -> AsyncMock:
    session = AsyncMock()
    provider_result = MagicMock(); provider_result.all = MagicMock(return_value=providers)
    model_result = MagicMock(); model_result.all = MagicMock(return_value=models)
    session.scalars = AsyncMock(side_effect=[provider_result, model_result])
    return session


@pytest.mark.asyncio
async def test_candidates_prefer_translation_provider_for_translate() -> None:
    session = _session_with([make_provider("deepl"), make_provider("openai_compatible")], [])
    candidates = await _candidates(session, "translate.en_to_zh")
    assert len(candidates) == 1
    assert candidates[0][0].provider_type == "deepl"
    assert candidates[0][1] is None


@pytest.mark.asyncio
async def test_candidates_translation_falls_back_to_llm() -> None:
    provider = make_provider("openai_compatible")
    model = make_model(["translate"], provider_id=provider.id)
    session = _session_with([provider], [model])
    candidates = await _candidates(session, "translate.en_to_zh")
    assert len(candidates) == 1
    assert candidates[0][0].provider_type == "openai_compatible"
    assert candidates[0][1] is model


@pytest.mark.asyncio
async def test_candidates_summary_only_uses_llm() -> None:
    deepl = make_provider("deepl")
    llm = make_provider("openai_compatible")
    model = make_model(["summarize"], provider_id=llm.id)
    session = _session_with([deepl, llm], [model])
    candidates = await _candidates(session, "summarize")
    assert len(candidates) == 1
    assert candidates[0][0].provider_type == "openai_compatible"
    assert candidates[0][1] is model


@pytest.mark.asyncio
async def test_candidates_skips_unhealthy_provider() -> None:
    healthy = make_provider("deepl", health="healthy")
    unhealthy = make_provider("libretranslate", health="unhealthy")
    session = _session_with([unhealthy, healthy], [])
    candidates = await _candidates(session, "translate.en_to_zh")
    assert [c[0].name for c in candidates] == [healthy.name]


def _fake_http_response(json_body: dict | None = None, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=json_body or {})
    response.status_code = status_code
    return response


def _fake_client(response: MagicMock, method: str) -> MagicMock:
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    setattr(client, method, AsyncMock(return_value=response))
    return client


@pytest.mark.asyncio
async def test_call_llm_openai_returns_content_and_usage() -> None:
    provider = make_provider("openai_compatible"); provider.base_url = "https://api.example"
    model = make_model(["summarize"]); model.model_key = "gpt-4o-mini"
    response = _fake_http_response({"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}})
    with patch("app.worker.httpx.AsyncClient", return_value=_fake_client(response, "post")):
        text, usage = await _call_llm(provider, model, "prompt")
    assert text == "hi"
    assert usage["prompt_tokens"] == 1


@pytest.mark.asyncio
async def test_call_translator_deepl_targets_upper_language() -> None:
    provider = make_provider("deepl"); provider.base_url = "https://api.deepl.com"
    response = _fake_http_response({"translations": [{"text": "你好"}]})
    fake = _fake_client(response, "post")
    with patch("app.worker.httpx.AsyncClient", return_value=fake):
        text, _ = await _call_translator(provider, "hello", "zh")
    assert text == "你好"
    sent = fake.post.await_args
    assert sent.kwargs["data"]["target_lang"] == "ZH"


@pytest.mark.asyncio
async def test_provider_connection_success() -> None:
    provider = make_provider("ollama"); provider.base_url = "http://localhost:11434"
    with patch("app.ai.httpx.AsyncClient", return_value=_fake_client(_fake_http_response(status_code=200), "get")):
        ok, detail = await check_provider_connection(provider)
    assert ok is True
    assert "successful" in detail


@pytest.mark.asyncio
async def test_provider_connection_rejects_bad_key() -> None:
    provider = make_provider("openai_compatible"); provider.base_url = "https://api.example"
    with patch("app.ai.httpx.AsyncClient", return_value=_fake_client(_fake_http_response(status_code=401), "get")):
        ok, detail = await check_provider_connection(provider)
    assert ok is False
    assert "401" in detail
