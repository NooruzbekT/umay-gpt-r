import json
import os

os.environ.pop("ANTHROPIC_API_KEY", None)  # тесты всегда на детерминированном агенте

from fastapi.testclient import TestClient  # noqa: E402

from app.agent import detect_lang, parse_budget  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def chat(message: str, sid: str | None = None) -> tuple[str, list[dict]]:
    events = []
    with client.stream("POST", "/api/chat", json={"message": message, "session_id": sid}) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    sid = next(e["session_id"] for e in events if e["type"] == "session")
    return sid, events


def artifacts(events, kind):
    return [e["artifact"] for e in events if e["type"] == "artifact" and e["artifact"]["kind"] == kind]


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_budget_and_lang():
    assert parse_budget("куртка до 20 000 тенге") == 20000
    assert parse_budget("наушники до 25к") == 25000
    assert parse_budget("күрте 15000 теңгеге дейін") == 15000
    assert detect_lang("маған жылы күрте керек") == "kk"
    assert detect_lang("warm jacket") == "en"


def test_enforce_budget_caps_llm_args():
    from app.agent import enforce_budget

    assert enforce_budget("search_products", {"query": "куртка"}, 20000)["max_price"] == 20000
    assert enforce_budget("search_products", {"query": "куртка", "max_price": 50000}, 20000)["max_price"] == 20000
    assert enforce_budget("build_bundle", {"query": "детская", "budget": 150000}, 100000)["budget"] == 100000
    assert "max_price" not in enforce_budget("search_products", {"query": "куртка"}, None)


def test_search_respects_budget():
    _, ev = chat("тёплая куртка на осень до 20000 тенге")
    lists = artifacts(ev, "PRODUCT_LIST")
    assert lists and lists[0]["products"]
    assert all(p["price"] <= 20000 for p in lists[0]["products"])
    assert any("урт" in p["title"] for p in lists[0]["products"])


def test_bundle_within_budget():
    _, ev = chat("обустройство детской комнаты до 100000 тенге")
    b = artifacts(ev, "BUNDLE")[0]
    assert b["total"] <= 100000 and len(b["products"]) >= 3


def test_bundle_by_items_one_per_item():
    """LLM передаёт набор позициями через запятую — по товару на позицию, без дублей, в бюджете."""
    from app.catalog import catalog

    items = catalog.bundle("куртка, шапка, шарф", 60000)
    assert 2 <= len(items) <= 3
    assert len({p.id for p in items}) == len(items)
    assert sum(p.price for p in items) <= 60000


def test_followups_compare_and_cart():
    sid, _ = chat("беспроводные наушники")
    _, ev = chat("сравни первые два", sid)
    assert len(artifacts(ev, "COMPARISON")[0]["products"]) == 2
    _, ev = chat("добавь первый в корзину", sid)
    cart = artifacts(ev, "CART")[0]
    assert cart["total"] > 0
    assert client.get("/api/cart", params={"session_id": sid}).json()["total"] == cart["total"]


def test_kazakh_and_english():
    _, ev = chat("маған күзге жылы күрте керек")
    assert artifacts(ev, "PRODUCT_LIST")
    _, ev = chat("wireless headphones under 30k")
    assert all(p["price"] <= 30000 for p in artifacts(ev, "PRODUCT_LIST")[0]["products"])
