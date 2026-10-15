"""Каталог и поиск: BM25-подобный скоринг с лёгким стеммингом и синонимами ru/kk/en,
фильтры по цене, категории и наличию."""
from __future__ import annotations

import json
import math
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DATA = Path(__file__).resolve().parents[1] / "data" / "products.json"

# Синонимы: казахский/английский → русские корни из тегов
SYNONYMS: dict[str, list[str]] = {
    "күрте": ["куртк"], "jacket": ["куртк"], "coat": ["куртк", "тренч", "пуховик"],
    "пуховик": ["пуховик", "куртк"], "ветровк": ["куртк"],
    "жылы": ["тёпл", "тепл"], "warm": ["тёпл", "тепл"], "теплый": ["тёпл"], "тепл": ["тёпл"],
    "күз": ["осен"], "autumn": ["осен"], "fall": ["осен"],
    "қыс": ["зим"], "winter": ["зим"],
    "балалар": ["детск"], "kids": ["детск"], "child": ["детск"], "children": ["детск"],
    "бөлме": ["комнат"], "room": ["комнат"], "nursery": ["детск", "комнат"],
    "кроссовка": ["кроссовк"], "sneakers": ["кроссовк"], "shoes": ["обув"],
    "құлаққап": ["наушник"], "headphones": ["наушник"], "earbuds": ["наушник"],
    "үй": ["дом"], "home": ["дом"], "kitchen": ["кухн"], "асүй": ["кухн"],
    "gift": ["подарок", "подар"], "сыйлық": ["подарок", "подар", "сыйлық"], "подарк": ["подарок", "подар"], "подарок": ["подар"],
    "одежд": ["одежд", "куртк", "свитер", "худи"], "clothes": ["одежд"],
    "кофт": ["кофт", "свитер", "худи"],
}

CATEGORY_HINTS = {
    "clothes": ["одежд", "куртк", "свитер", "худи", "джинс", "плать", "обув", "кроссовк", "ботинк", "шапк", "шарф", "тренч", "пуховик", "киім"],
    "home": ["дом", "кухн", "посуд", "постел", "декор", "уют", "лампа", "мебел", "үй"],
    "kids": ["детск", "ребён", "ребен", "игрушк", "школ", "балалар"],
    "electronics": ["наушник", "гаджет", "электрон", "колонк", "часы", "клавиатур", "мышь", "повербанк", "зарядк"],
    "beauty": ["красот", "косметик", "уход", "фен", "макияж"],
    "food": ["еда", "сладост", "чай", "рамен", "продукт"],
}

_STOP = set("и в на для до с по от а не или мне нужно нужен нужна хочу покажи найди подбери что какие есть тенге тг тыс the a for to of in under and with me show find i want".split())


def norm(text: str) -> str:
    return text.lower().replace("ё", "е")


def stem(tok: str) -> str:
    """Лёгкий стеммер: обрезает типовые русские окончания."""
    tok = norm(tok)
    for suf in ("ями", "ами", "ого", "ему", "ыми", "ими", "ая", "ое", "ые", "ий", "ый", "ой", "ую", "ов", "ей", "ах", "ях", "ам", "ям", "ом", "ем", "а", "я", "ы", "и", "у", "ю", "е", "о"):
        if len(tok) > len(suf) + 3 and tok.endswith(suf):
            return tok[: -len(suf)]
    return tok


def tokenize(text: str) -> list[str]:
    toks = [t for t in re.findall(r"[a-zа-яёәғқңөұүһі0-9]+", norm(text)) if t not in _STOP and not t.isdigit()]
    out: list[str] = []
    for t in toks:
        s = stem(t)
        out.append(s)
        for key, syns in SYNONYMS.items():
            if s.startswith(key) or t.startswith(key):
                out.extend(syns)
    return out


@dataclass
class Product:
    raw: dict

    @property
    def id(self) -> str:
        return self.raw["id"]

    @property
    def price(self) -> int:
        return self.raw["price"]

    def doc_tokens(self) -> list[str]:
        n = self.raw["name"]
        text = " ".join([n["ru"], n["en"], n["kk"], self.raw["tags"], " ".join(self.raw["colors"])])
        return [stem(t) for t in re.findall(r"[a-zа-яёәғқңөұүһі0-9]+", norm(text))]

    def card(self, lang: str = "ru") -> dict:
        r = self.raw
        return {
            "id": r["id"],
            "title": r["name"].get(lang) or r["name"]["ru"],
            "emoji": r["emoji"],
            "category": r["category"],
            "price": r["price"],
            "old_price": r["old_price"],
            "rating": r["rating"],
            "reviews": r["reviews"],
            "colors": r["colors"],
            "installment_24": r["installment_24"],
            "delivery_days": r["delivery_days"],
            "source": r["source"],
            "in_stock": r["stock"] > 0,
            "image": r.get("image"),
            "url": r.get("url"),
        }


class Catalog:
    name = "demo"

    def __init__(self, products: list[dict]):
        self.products: list[Product] = []
        self.by_id: dict[str, Product] = {}
        self.add(products)

    def add(self, raws: list[dict]) -> list[Product]:
        out = []
        for raw in raws:
            p = self.by_id.get(raw["id"])
            if p is None:
                p = Product(raw)
                self.products.append(p)
                self.by_id[p.id] = p
            out.append(p)
        self._index()
        return out

    def _index(self) -> None:
        self._docs = {p.id: p.doc_tokens() for p in self.products}
        self._names = {p.id: [stem(t) for n in p.raw["name"].values() for t in re.findall(r"[a-zа-яёәғқңөұүһі0-9]+", norm(n))]
                       for p in self.products}
        n = len(self.products)
        df: dict[str, int] = {}
        for toks in self._docs.values():
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self._avg = sum(len(d) for d in self._docs.values()) / max(n, 1)

    def get(self, pid: str) -> Product | None:
        return self.by_id.get(pid)

    def _score(self, q: list[str], pid: str) -> float:
        doc = self._docs[pid]
        score = 0.0
        k1, b = 1.4, 0.7
        name = self._names[pid]
        for t in set(q):
            if any(n.startswith(t) for n in name):  # совпадение в названии весит больше тегов
                score += 1.5
            tf = sum(1 for d in doc if d.startswith(t) or t.startswith(d) and len(d) >= 4)
            if not tf:
                continue
            idf = max((v for k, v in self._idf.items() if k.startswith(t)), default=1.0)
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(doc) / self._avg))
        return score

    @staticmethod
    def guess_category(q: Iterable[str]) -> str | None:
        hits = {c: sum(1 for t in q for h in hints if t.startswith(h) or h.startswith(t) and len(t) >= 4) for c, hints in CATEGORY_HINTS.items()}
        best = max(hits, key=hits.get)
        return best if hits[best] else None

    def search(self, query: str, max_price: int | None = None, min_price: int | None = None,
               category: str | None = None, limit: int = 6, in_stock_only: bool = True) -> list[Product]:
        q = tokenize(query)
        scored = []
        for p in self.products:
            if max_price and p.price > max_price:
                continue
            if min_price and p.price < min_price:
                continue
            if category and p.raw["category"] != category:
                continue
            if in_stock_only and p.raw["stock"] <= 0:
                continue
            s = self._score(q, p.id) if q else 0.1
            if s > 0:
                # буст за рейтинг и скидку
                s *= 1 + (p.raw["rating"] - 4) * 0.2 + (0.1 if p.raw["old_price"] else 0)
                scored.append((s, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:limit]]

    def bundle(self, query: str, budget: int, category: str | None = None) -> list[Product]:
        """Подборка «под ключ» в рамках бюджета (жадно по релевантности, без дублей типов)."""
        parts = [p.strip() for p in re.split(r"(?<!\d),|,(?!\d)", query) if p.strip()]  # «30,000» не делим
        if len(parts) > 1:
            return self._bundle_parts(parts[:8], budget, category)
        candidates = self.search(query, max_price=budget, category=category, limit=30)
        chosen: list[Product] = []
        total = 0
        seen_kind = set()
        for p in candidates:
            kind = p.raw.get("kind") or p.raw["emoji"]
            if kind in seen_kind:
                continue
            if total + p.price <= budget:
                chosen.append(p)
                total += p.price
                seen_kind.add(kind)
        return chosen

    def _bundle_parts(self, parts: list[str], budget: int, category: str | None) -> list[Product]:
        """Набор из конкретных позиций («плед, свеча, кружка»): по одному товару на позицию.
        Позиции ищутся параллельно (в live-режиме это отдельные запросы к API Umay);
        потолок на позицию не даёт первой позиции съесть весь бюджет."""
        cap = min(budget, int(budget / len(parts) * 1.5))
        with ThreadPoolExecutor(max_workers=len(parts)) as ex:
            found = list(ex.map(lambda q: self.search(q, max_price=cap, category=category, limit=5)
                                or self.search(q, max_price=cap, limit=5), parts))
        chosen: list[Product] = []
        total = 0
        for cands in found:
            for p in cands:
                if p.id not in {c.id for c in chosen} and total + p.price <= budget:
                    chosen.append(p)
                    total += p.price
                    break
        return chosen


# ---------- реальные данные Umay ----------

CAT_EMOJI = {"clothes": "🧥", "electronics": "🎧", "kids": "🧸", "beauty": "💄", "home": "🛋️", "food": "🍵"}
S3 = "https://umayshop.s3.amazonaws.com/public/translate/"
_CJK = re.compile(r"[㐀-鿿豈-﫿]+")


def clean_title(text: str | None, fallback: str = "") -> str:
    """Чистка машинного перевода: в данных Umay встречаются иероглифы внутри русских/казахских
    названий («свитер из羊毛», «ұйықтайтын袋»). Убираем их; пустое название — берём запасное."""
    t = _CJK.sub("", text or "").replace("  ", " ").strip(" ,.-")
    return t or fallback


def umay_raw(p: dict, cat: str | None = None, kind: str | None = None) -> dict:
    """Нормализация товара из API Umay (или из среза) в формат прототипа."""
    ru = clean_title(p.get("ru") or p.get("subject"))
    price = int(float(p.get("price") or 0))
    old = int(float(p.get("old") or p.get("underlinedPrice") or 0)) or None
    image = p.get("image") or ""
    if image.startswith("~"):
        image = S3 + image[1:]
    source = p.get("source") or "UMAY"
    cat = cat or p.get("cat") or "clothes"
    return {
        "id": str(p.get("id") or p.get("productId")),
        "category": cat,
        "kind": kind or p.get("query") or cat,
        "emoji": CAT_EMOJI.get(cat, "🛍️"),
        "name": {"ru": ru, "kk": clean_title(p.get("kk") or p.get("subjectKZ"), ru), "en": clean_title(p.get("en") or p.get("subjectEN"), ru)},
        "price": price,
        "old_price": old if old and old > price else None,
        "rating": float(p.get("score") or p.get("showScore") or 4.5),
        "reviews": int(float(p.get("sales") or p.get("showSale") or 0)),
        "colors": [],
        # теги — только данные самого товара (категории), без служебного запроса, которым он был найден
        "tags": " ".join(filter(None, [p.get("category"), p.get("categoryKK"), p.get("categoryEN")])),
        "season": "all",
        "installment_24": round(price / 24),
        # SELF — склад в Казахстане; ALIBABA/TAOBAO — доставка из Китая (оценка для прототипа)
        "delivery_days": 3 if source == "SELF" else 12,
        "source": {"ALIBABA": "1688", "TAOBAO": "Taobao", "SELF": "Umay"}.get(source, source),
        "stock": 1,
        "image": image or None,
        "url": f"https://umayshop.kz/product/{p.get('id') or p.get('productId')}",
    }


def load_snapshot(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [umay_raw(dict(zip(head, ln.split("\t")))) for ln in lines[1:] if ln.strip()]


class LiveCatalog(Catalog):
    """Публичный поиск Umay (без авторизации):
    POST https://endpoint.umayshop.kz/product/public/web/product/search/v2
    {keywords, pageNo, pageSize, minPrice, maxPrice} — цена фильтруется на стороне Umay.
    Результат дополнительно ранжируется локально; при сбое сети — запасной срез."""

    name = "live"
    API = "https://endpoint.umayshop.kz/product/public/web/product/search/v2"
    _lock = threading.Lock()

    def search(self, query: str, max_price: int | None = None, min_price: int | None = None,
               category: str | None = None, limit: int = 6, in_stock_only: bool = True) -> list[Product]:
        import httpx

        keywords = " ".join(w for w in re.findall(r"[^\W\d_]+", query) if norm(w) not in _STOP)[:60] or query
        body = {"keywords": keywords, "pageNo": 1, "pageSize": max(limit * 4, 20)}
        if max_price:
            body["maxPrice"] = max_price
        if min_price:
            body["minPrice"] = min_price
        try:
            r = httpx.post(self.API, json=body, timeout=8)
            items = (r.json().get("data") or {}).get("list") or []
        except Exception:
            items = None
        # запрос к API идёт параллельно, а индекс общий: пополнение и ранжирование — под блокировкой
        with self._lock:
            if items is None:
                return super().search(query, max_price, min_price, category, limit, in_stock_only)
            fresh = self.add([umay_raw(p, cat=category or guess_cat_from_text(p.get("category", "")), kind=p.get("category"))
                              for p in items if not p.get("adult")])
            ids = {p.id for p in fresh}
            ranked = [p for p in super().search(query, max_price, min_price, None, limit * 3, in_stock_only) if p.id in ids]
            return (ranked or fresh)[:limit]


def guess_cat_from_text(text: str) -> str:
    c = Catalog.guess_category(tokenize(text))
    return c or "clothes"


def load_catalog() -> Catalog:
    """UMAY_CATALOG: demo (синтетика) | snapshot (срез реального каталога) | live (API Umay + срез как запас)."""
    mode = os.getenv("UMAY_CATALOG", "snapshot").lower()
    snap = DATA.parent / "umay_snapshot.tsv"
    if mode == "demo" or not snap.exists():
        cat = Catalog(json.loads(DATA.read_text(encoding="utf-8")))
        cat.name = "demo"
        return cat
    raws = load_snapshot(snap)
    if mode == "live":
        return LiveCatalog(raws)
    cat = Catalog(raws)
    cat.name = "snapshot"
    return cat


catalog = load_catalog()
