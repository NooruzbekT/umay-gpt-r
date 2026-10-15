"""Хранилище сессий, корзины и истории.

Прототип: in-memory dict (сбрасывается при рестарте).
Прод: Redis (сессии/корзина гостя, TTL 30 дней) + PostgreSQL (история чатов, заказы).
Гостевая корзина мержится в пользовательскую при логине.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    lang: str = "ru"
    history: list[dict] = field(default_factory=list)      # [{role, content}]
    last_results: list[str] = field(default_factory=list)  # id товаров из последней выдачи
    cart: dict[str, int] = field(default_factory=dict)     # product_id -> qty
    created_at: float = field(default_factory=time.time)
    title: str = "Новый чат"


class Store:
    def __init__(self) -> None:
        self._s: dict[str, Session] = {}

    def get_or_create(self, sid: str | None) -> Session:
        if sid and sid in self._s:
            return self._s[sid]
        sid = sid or uuid.uuid4().hex
        self._s[sid] = Session(id=sid)
        return self._s[sid]

    def get(self, sid: str) -> Session | None:
        return self._s.get(sid)


store = Store()
