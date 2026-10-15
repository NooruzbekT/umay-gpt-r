"""Инструменты агента: JSON-схема для LLM + реализация. Результат — данные для модели
и артефакт для фронта (карточки, сравнение, корзина)."""
from __future__ import annotations

from typing import Any

from .catalog import catalog
from .store import Session

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_products",
        "description": "Поиск товаров в каталоге Umay. Используй для любых запросов на подбор товара. Запрос пиши на русском ключевыми словами.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "ключевые слова, напр. 'тёплая куртка осень'"},
                "max_price": {"type": "integer", "description": "максимальная цена в тенге"},
                "min_price": {"type": "integer"},
                "category": {"type": "string", "enum": ["clothes", "home", "kids", "electronics", "beauty", "food"]},
                "limit": {"type": "integer", "default": 6},
            },
            "required": ["query"],
        },
    },
    {
        "name": "build_bundle",
        "description": "Собрать набор товаров под общий бюджет (обустройство комнаты, образ, подарки).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "3–6 конкретных видов товаров на русском через запятую, напр. 'плед, свеча, подушка, кружка'"},
                "budget": {"type": "integer", "description": "общий бюджет в тенге"},
                "category": {"type": "string", "enum": ["clothes", "home", "kids", "electronics", "beauty", "food"]},
            },
            "required": ["query", "budget"],
        },
    },
    {
        "name": "compare_products",
        "description": "Сравнить 2-4 товара по цене, рейтингу, доставке, рассрочке.",
        "input_schema": {
            "type": "object",
            "properties": {"product_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4}},
            "required": ["product_ids"],
        },
    },
    {
        "name": "add_to_cart",
        "description": "Добавить товар в корзину пользователя.",
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "string"}, "qty": {"type": "integer", "default": 1}},
            "required": ["product_id"],
        },
    },
    {
        "name": "get_cart",
        "description": "Показать содержимое корзины и итоговую сумму.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def cart_view(s: Session) -> dict:
    items = []
    total = 0
    for pid, qty in s.cart.items():
        p = catalog.get(pid)
        if not p:
            continue
        items.append({**p.card(s.lang), "qty": qty})
        total += p.price * qty
    return {"items": items, "total": total, "installment_24": round(total / 24)}


def run_tool(name: str, args: dict, s: Session) -> tuple[dict, dict | None]:
    """Возвращает (результат для модели, артефакт для UI)."""
    lang = s.lang
    if name == "search_products":
        res = catalog.search(args.get("query", ""), args.get("max_price"), args.get("min_price"),
                             args.get("category"), int(args.get("limit") or 6))
        if not res and args.get("category"):  # мягкий фолбэк без категории
            res = catalog.search(args.get("query", ""), args.get("max_price"), args.get("min_price"), None, int(args.get("limit") or 6))
        s.last_results = [p.id for p in res]
        cards = [p.card(lang) for p in res]
        return ({"count": len(cards), "products": [{k: c[k] for k in ("id", "title", "price", "rating")} for c in cards]},
                {"kind": "PRODUCT_LIST", "products": cards})
    if name == "build_bundle":
        res = catalog.bundle(args.get("query", ""), int(args["budget"]), args.get("category"))
        s.last_results = [p.id for p in res]
        cards = [p.card(lang) for p in res]
        total = sum(c["price"] for c in cards)
        return ({"total": total, "budget": args["budget"], "products": [{k: c[k] for k in ("id", "title", "price")} for c in cards]},
                {"kind": "BUNDLE", "products": cards, "total": total, "budget": int(args["budget"])})
    if name == "compare_products":
        ps = [catalog.get(i) for i in args.get("product_ids", [])]
        cards = [p.card(lang) for p in ps if p]
        return ({"products": cards}, {"kind": "COMPARISON", "products": cards})
    if name == "add_to_cart":
        pid = args["product_id"]
        p = catalog.get(pid)
        if not p:
            return ({"error": f"товар {pid} не найден"}, None)
        s.cart[pid] = s.cart.get(pid, 0) + int(args.get("qty") or 1)
        view = cart_view(s)
        return ({"ok": True, "added": p.card(lang)["title"], "cart_total": view["total"]}, {"kind": "CART", **view})
    if name == "get_cart":
        view = cart_view(s)
        return (view, {"kind": "CART", **view})
    return ({"error": f"unknown tool {name}"}, None)
