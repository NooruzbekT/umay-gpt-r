"""Проверка OpenAI-совместимого агента (Qwen/OpenAI) на мок-сервере: без сети и без ключа.

Мок на первом шаге «вызывает» search_products, НЕ передавая бюджет, а на втором — отвечает текстом.
Проверяем: tool-loop работает, карточки приходят артефактом, бюджет из запроса всё равно соблюдён.
"""
import asyncio
import json

import httpx

from app.agent import OpenAICompatAgent
from app.store import Session


def sse(obj) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode()


def mock_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer test-key"
    assert body["tools"][0]["type"] == "function"
    has_tool_result = any(m["role"] == "tool" for m in body["messages"])
    if not has_tool_result:
        chunks = [
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "search_products", "arguments": ""}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"query": "тёплая куртка осень"'}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "}"}}]}, "finish_reason": "tool_calls"}]},
        ]
    else:
        chunks = [
            {"choices": [{"delta": {"content": "Нашёл несколько курток "}}]},
            {"choices": [{"delta": {"content": "в пределах бюджета."}, "finish_reason": "stop"}]},
        ]
    payload = b"".join(sse(c) for c in chunks) + b"data: [DONE]\n\n"
    return httpx.Response(200, content=payload, headers={"content-type": "text/event-stream"})


def test_qwen_compatible_tool_loop(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://mock-llm/v1")
    agent = OpenAICompatAgent("qwen")
    agent.http = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    async def collect():
        return [e async for e in agent.run(Session(id="t"), "тёплая куртка на осень до 15000 тенге")]

    events = asyncio.run(collect())
    arts = [e["artifact"] for e in events if e["type"] == "artifact"]
    text = "".join(e["delta"] for e in events if e["type"] == "text")
    assert arts and arts[0]["kind"] == "PRODUCT_LIST" and arts[0]["products"]
    assert all(p["price"] <= 15000 for p in arts[0]["products"])  # модель бюджет не передала — код ограничил
    assert "бюджета" in text
    assert agent.name == "qwen:qwen-plus"
