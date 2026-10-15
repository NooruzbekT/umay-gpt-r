"""Агент Umay GPT.

Два провайдера с одинаковым контрактом (async-генератор событий):
  • LLMAgent   — настоящая LLM с tool use (Anthropic Claude; провайдер легко заменить);
  • RuleAgent  — детерминированный планировщик без LLM: парсит намерение, бюджет и
                 ссылки «первый/второй», вызывает те же инструменты. Нужен для офлайн-демо,
                 тестов и как фолбэк при недоступности LLM (graceful degradation).

События (уходят на фронт через SSE):
  {"type":"session","session_id":...}
  {"type":"status","text":"Ищу товары…"}
  {"type":"text","delta":"..."}
  {"type":"artifact","artifact":{kind: PRODUCT_LIST|BUNDLE|COMPARISON|CART, ...}}
  {"type":"suggestions","items":[...]}
  {"type":"done"}
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import AsyncIterator

from .catalog import catalog, norm
from .store import Session
from .tools import TOOL_SCHEMAS, run_tool

Event = dict

# ---------- общие утилиты ----------

KK_CHARS = set("әғқңөұүһі")


def detect_lang(text: str) -> str:
    t = text.lower()
    if any(c in KK_CHARS for c in t) or re.search(r"\b(маған|керек|дейін|сәлем|бөлме|қыс|күз|жылы)\b", t):
        return "kk"
    if re.search(r"[а-яё]", t):
        return "ru"
    return "en"


def parse_budget(text: str) -> int | None:
    t = norm(text).replace(" ", " ")
    best = None
    for m in re.finditer(r"(\d[\d\s]*\d|\d)\s*(к|k|тыс\w*|мың)?(?![\w])", t):
        num = int(m.group(1).replace(" ", ""))
        if m.group(2):
            num *= 1000
        if num >= 1000:
            best = num
    return best


ORDINALS = {
    0: ["перв", "1-", "№1", "#1", "first", "бірінші", "біріншісін"],
    1: ["втор", "2-", "№2", "#2", "second", "екінші"],
    2: ["трет", "3-", "№3", "#3", "third", "үшінші"],
    3: ["четв", "4-", "№4", "#4", "fourth", "төртінші"],
}


def parse_refs(text: str, last: list[str]) -> list[str]:
    t = norm(text)
    idx = [i for i, keys in ORDINALS.items() if any(k in t for k in keys)]
    if re.search(r"последн|last|соңғы", t) and last:
        idx.append(len(last) - 1)
    ids = re.findall(r"\bp\d{3}\b", t)
    return ids + [last[i] for i in sorted(set(idx)) if i < len(last)]


T = {
    "searching": {"ru": "Ищу товары в каталоге…", "kk": "Каталогтан іздеп жатырмын…", "en": "Searching the catalog…"},
    "bundling": {"ru": "Собираю подборку под бюджет…", "kk": "Бюджетке жиынтық құрастырып жатырмын…", "en": "Building a bundle within budget…"},
    "comparing": {"ru": "Сравниваю товары…", "kk": "Тауарларды салыстырып жатырмын…", "en": "Comparing products…"},
    "cart": {"ru": "Обновляю корзину…", "kk": "Себетті жаңартып жатырмын…", "en": "Updating the cart…"},
}

SUGGEST = {
    "ru": ["Сравни первые два", "Добавь первый в корзину", "Покажи дешевле", "Что в корзине?"],
    "kk": ["Алғашқы екеуін салыстыр", "Біріншісін себетке қос", "Арзанырақ көрсет", "Себетте не бар?"],
    "en": ["Compare the first two", "Add the first one to cart", "Show cheaper", "What's in my cart?"],
}


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " ₸"


async def stream_text(text: str) -> AsyncIterator[Event]:
    for chunk in re.findall(r"\S+\s*", text):
        yield {"type": "text", "delta": chunk}
        await asyncio.sleep(0.018)


# ---------- RuleAgent ----------

class RuleAgent:
    name = "rule-based (demo)"

    async def run(self, s: Session, message: str) -> AsyncIterator[Event]:
        lang = detect_lang(message)
        s.lang = lang
        t = norm(message)
        budget = parse_budget(message)
        refs = parse_refs(message, s.last_results)

        def say(ru: str, kk: str, en: str) -> str:
            return {"ru": ru, "kk": kk, "en": en}[lang]

        # 1. корзина: добавить
        if re.search(r"добав|в корзин|положи|возьму|add|себетке|қос", t) and (refs or s.last_results):
            pid = (refs or s.last_results[:1])[0]
            yield {"type": "status", "text": T["cart"][lang]}
            res, art = run_tool("add_to_cart", {"product_id": pid}, s)
            if art:
                yield {"type": "artifact", "artifact": art}
            text = say(
                f"Готово — **{res.get('added')}** в корзине. Итого: {fmt(res.get('cart_total', 0))}. Можно оформить в рассрочку 0-0-24.",
                f"Дайын — **{res.get('added')}** себетте. Барлығы: {fmt(res.get('cart_total', 0))}. 0-0-24 бөліп төлеуге болады.",
                f"Done — **{res.get('added')}** is in your cart. Total: {fmt(res.get('cart_total', 0))}. 0-0-24 installments available.",
            )
            async for e in stream_text(text):
                yield e
            yield {"type": "suggestions", "items": SUGGEST[lang][2:]}
            return

        # 2. корзина: показать
        if re.search(r"корзин|cart|себет", t):
            res, art = run_tool("get_cart", {}, s)
            if art:
                yield {"type": "artifact", "artifact": art}
            text = (say("Корзина пока пуста — давайте что-нибудь подберём?", "Себет әзірге бос — бірдеңе таңдайық па?", "Your cart is empty — shall we find something?")
                    if not res["items"] else
                    say(f"В корзине {len(res['items'])} {plural_ru(len(res['items']), 'товар', 'товара', 'товаров')} на {fmt(res['total'])} (≈{fmt(res['installment_24'])}/мес в рассрочку на 24 мес.).",
                        f"Себетте {len(res['items'])} тауар, {fmt(res['total'])} (24 айға ≈{fmt(res['installment_24'])}/ай).",
                        f"{len(res['items'])} items, {fmt(res['total'])} total (≈{fmt(res['installment_24'])}/mo over 24 months)."))
            async for e in stream_text(text):
                yield e
            return

        # 3. сравнение
        if re.search(r"сравн|compare|салыстыр|vs|чем отлич", t):
            ids = refs if len(refs) >= 2 else s.last_results[:2]
            if len(ids) < 2:
                async for e in stream_text(say("Сначала найдём товары — что сравниваем?", "Алдымен тауарларды табайық — нені салыстырамыз?", "Let's find products first — what should I compare?")):
                    yield e
                return
            yield {"type": "status", "text": T["comparing"][lang]}
            res, art = run_tool("compare_products", {"product_ids": ids[:4]}, s)
            yield {"type": "artifact", "artifact": art}
            ps = res["products"]
            cheaper = min(ps, key=lambda p: p["price"])
            better = max(ps, key=lambda p: p["rating"])
            fast = min(ps, key=lambda p: p["delivery_days"])
            same_days = len({p["delivery_days"] for p in ps}) == 1
            if cheaper is better:
                parts = [say(f"По цене и рейтингу выигрывает **{cheaper['title']}** ({fmt(cheaper['price'])}, ★{cheaper['rating']})",
                             f"Бағасы мен рейтингі бойынша **{cheaper['title']}** ұтады ({fmt(cheaper['price'])}, ★{cheaper['rating']})",
                             f"**{cheaper['title']}** wins on both price and rating ({fmt(cheaper['price'])}, ★{cheaper['rating']})")]
            else:
                parts = [say(f"Коротко: дешевле — **{cheaper['title']}** ({fmt(cheaper['price'])}), выше рейтинг — **{better['title']}** (★{better['rating']})",
                             f"Қысқаша: арзаны — **{cheaper['title']}** ({fmt(cheaper['price'])}), рейтингі жоғары — **{better['title']}** (★{better['rating']})",
                             f"In short: cheapest — **{cheaper['title']}** ({fmt(cheaper['price'])}), best rated — **{better['title']}** (★{better['rating']})")]
            parts.append(say(f"доставка одинаковая, около {fast['delivery_days']} дн." if same_days else f"быстрее доставка — **{fast['title']}** ({fast['delivery_days']} дн.)",
                             f"жеткізу мерзімі бірдей, шамамен {fast['delivery_days']} күн" if same_days else f"жылдам жеткізу — **{fast['title']}** ({fast['delivery_days']} күн)",
                             f"delivery time is the same, about {fast['delivery_days']} days" if same_days else f"fastest delivery — **{fast['title']}** ({fast['delivery_days']} days)"))
            text = "; ".join(parts).rstrip(".") + "."
            async for e in stream_text(text):
                yield e
            yield {"type": "suggestions", "items": [SUGGEST[lang][1], SUGGEST[lang][3]]}
            return

        # 4. «дешевле» — повтор последнего поиска с меньшим бюджетом
        if re.search(r"дешевл|cheaper|арзан", t) and s.last_results:
            first = catalog.get(s.last_results[0])
            budget = first.price - 1 if first else budget  # дешевле лучшего совпадения
            last_q = next((h["content"] for h in reversed(s.history) if h["role"] == "user" and not re.search(r"дешевл|cheaper|арзан", norm(h["content"]))), message)
            message = last_q
            t = norm(message)

        # 5. подборка под бюджет
        if budget and re.search(r"комнат|набор|образ|обустро|под ключ|room|outfit|bundle|бөлме|жиынтық|всё для|все для", t):
            yield {"type": "status", "text": T["bundling"][lang]}
            res, art = run_tool("build_bundle", {"query": message, "budget": budget, "category": catalog.guess_category(re.findall(r"\w+", t))}, s)
            yield {"type": "artifact", "artifact": art}
            text = say(
                f"Собрал набор из {len(res['products'])} {plural_ru(len(res['products']), 'товара', 'товаров', 'товаров')} на {fmt(res['total'])} при бюджете {fmt(budget)} — остаётся {fmt(budget - res['total'])}. Любую позицию можно заменить или сразу добавить в корзину.",
                f"{fmt(budget)} бюджетке {len(res['products'])} тауардан тұратын жиынтық құрастырдым: {fmt(res['total'])}. Қалғаны {fmt(budget - res['total'])}.",
                f"Here's a bundle of {len(res['products'])} items for {fmt(res['total'])} within your {fmt(budget)} budget — {fmt(budget - res['total'])} left over.",
            )
            async for e in stream_text(text):
                yield e
            yield {"type": "suggestions", "items": SUGGEST[lang]}
            return

        # 6. приветствие
        if re.fullmatch(r"\W*(привет|здравствуй\w*|салем|сәлем|hi|hello|hey)\W*", t):
            async for e in stream_text(say(
                "Привет! Я Umay GPT. Опишите, что ищете — можно с бюджетом, на русском, казахском или английском. Например: «тёплая куртка на осень до 20 000 ₸».",
                "Сәлем! Мен Umay GPT. Не іздеп жүргеніңізді жазыңыз — бюджетпен бірге. Мысалы: «күзге жылы күрте 20 000 ₸ дейін».",
                "Hi! I'm Umay GPT. Tell me what you're looking for, budget included — e.g. “warm autumn jacket under 20,000 ₸”.")):
                yield e
            return

        # 7. поиск
        yield {"type": "status", "text": T["searching"][lang]}
        cat = catalog.guess_category([w for w in re.findall(r"\w+", t)])
        res, art = run_tool("search_products", {"query": message, "max_price": budget, "category": cat}, s)
        if not res["count"]:
            async for e in stream_text(say(
                "Не нашёл подходящего. Попробуйте уточнить запрос или поднять бюджет.",
                "Сәйкес тауар табылмады. Сұранысты нақтылап немесе бюджетті көтеріп көріңіз.",
                "Nothing matched. Try rephrasing or raising the budget.")):
                yield e
            return
        yield {"type": "artifact", "artifact": art}
        top = res["products"][0]
        bud = say(f" в пределах {fmt(budget)}", f" {fmt(budget)} дейін", f" under {fmt(budget)}") if budget else ""
        text = say(
            f"Нашёл {res['count']} {plural_ru(res['count'], 'вариант', 'варианта', 'вариантов')}{bud}. Лучшее совпадение — **{top['title']}** за {fmt(top['price'])} (★{top['rating']}). Могу сравнить варианты или сразу добавить в корзину.",
            f"{res['count']} нұсқа таптым{bud}. Ең сәйкесі — **{top['title']}**, {fmt(top['price'])} (★{top['rating']}). Салыстыра аламын немесе себетке қосамын.",
            f"Found {res['count']} options{bud}. Best match — **{top['title']}** at {fmt(top['price'])} (★{top['rating']}). I can compare them or add one to your cart.",
        )
        async for e in stream_text(text):
            yield e
        yield {"type": "suggestions", "items": SUGGEST[lang]}


# ---------- LLMAgent ----------

SYSTEM_PROMPT = """Ты — Umay GPT, ИИ-консультант маркетплейса Umay (Казахстан): товары UmayHome, UMI, UMI FOOD и 5 млн+ товаров с 1688/Taobao, рассрочка 0-0-24, доставка по Казахстану.
Правила:
- Отвечай на языке пользователя (русский, казахский или английский), коротко и по делу, 1–3 предложения.
- Для любого подбора товаров ВСЕГДА вызывай инструменты, не выдумывай товары и цены.
- Цены в тенге (₸). Если назван бюджет — передай его в max_price/budget.
- Карточки товаров пользователь видит сам — не перечисляй их списком, дай вывод и следующий шаг.
- «Первый/второй» = позиции из последней выдачи (см. ниже).
- Не обсуждай темы вне шопинга дольше одной фразы; вежливо верни к покупкам."""


def enforce_budget(tool: str, args: dict, user_budget: int | None) -> dict:
    """Страховка поверх LLM: бюджет из запроса пользователя — жёсткий потолок цены,
    даже если модель забыла передать его или передала больше."""
    if not user_budget:
        return args
    if tool == "search_products":
        args["max_price"] = min(int(args.get("max_price") or user_budget), user_budget)
    elif tool == "build_bundle":
        args["budget"] = min(int(args.get("budget") or user_budget), user_budget)
    return args


class LLMAgent:
    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic()
        self.model = os.getenv("UMAY_LLM_MODEL", "claude-sonnet-5-5")
        self.name = f"llm:{self.model}"

    async def run(self, s: Session, message: str) -> AsyncIterator[Event]:
        s.lang = detect_lang(message)
        last = [catalog.get(i) for i in s.last_results]
        ctx = "\nПоследняя выдача: " + ("; ".join(f"{n+1}) {p.id} {p.card(s.lang)['title']} {p.price}₸" for n, p in enumerate(last) if p) or "пусто")
        msgs: list[dict] = [{"role": h["role"], "content": h["content"]} for h in s.history[-12:]]
        msgs.append({"role": "user", "content": message})
        user_budget = parse_budget(message)

        for _ in range(5):  # максимум 5 шагов tool-loop
            async with self.client.messages.stream(model=self.model, max_tokens=800, system=SYSTEM_PROMPT + ctx,
                                                   tools=TOOL_SCHEMAS, messages=msgs) as stream:
                async for ev in stream:
                    if ev.type == "content_block_delta" and getattr(ev.delta, "type", "") == "text_delta":
                        yield {"type": "text", "delta": ev.delta.text}
                final = await stream.get_final_message()
            msgs.append({"role": "assistant", "content": [b.model_dump() for b in final.content]})
            if final.stop_reason != "tool_use":
                break
            results = []
            for b in final.content:
                if b.type == "tool_use":
                    yield {"type": "status", "text": T.get({"search_products": "searching", "build_bundle": "bundling", "compare_products": "comparing"}.get(b.name, "cart"))[s.lang]}
                    args = enforce_budget(b.name, dict(b.input), user_budget)
                    res, art = run_tool(b.name, args, s)
                    if art:
                        yield {"type": "artifact", "artifact": art}
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(res, ensure_ascii=False)})
            msgs.append({"role": "user", "content": results})
        yield {"type": "suggestions", "items": SUGGEST[s.lang]}


class OpenAICompatAgent:
    """LLM-агент для любого OpenAI-совместимого API с function calling:
    Qwen (DashScope compatible-mode), OpenAI, локальные vLLM/Ollama.
    Тот же контракт событий и те же инструменты, что у LLMAgent."""

    PRESETS = {
        "qwen": ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen-plus", ("QWEN_API_KEY", "DASHSCOPE_API_KEY")),
        "openai": ("https://api.openai.com/v1", "gpt-4o-mini", ("OPENAI_API_KEY",)),
    }

    def __init__(self, provider: str) -> None:
        import httpx

        base, model, key_envs = self.PRESETS.get(provider, self.PRESETS["qwen"])
        self.base_url = os.getenv("LLM_BASE_URL", base).rstrip("/")
        self.model = os.getenv("UMAY_LLM_MODEL", model)
        self.api_key = next((os.environ[k] for k in key_envs if os.getenv(k)), os.getenv("LLM_API_KEY", ""))
        if not self.api_key:
            raise RuntimeError(f"no API key for {provider}")
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10))
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
                      for t in TOOL_SCHEMAS]
        self.name = f"{provider}:{self.model}"

    async def _stream(self, messages: list[dict]) -> AsyncIterator[dict]:
        """Один шаг модели: отдаёт {'text': дельта} и в конце {'tool_calls': [...], 'finish': reason}."""
        body = {"model": self.model, "messages": messages, "tools": self.tools, "stream": True, "temperature": 0.3}
        calls: dict[int, dict] = {}
        finish = None
        async with self.http.stream("POST", f"{self.base_url}/chat/completions", json=body,
                                    headers={"Authorization": f"Bearer {self.api_key}"}) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"LLM HTTP {r.status_code}: {(await r.aread())[:300]!r}")
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                for ch in chunk.get("choices", []):
                    d = ch.get("delta") or {}
                    if d.get("content"):
                        yield {"text": d["content"]}
                    for tc in d.get("tool_calls") or []:
                        c = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "arguments": ""})
                        c["id"] = tc.get("id") or c["id"]
                        fn = tc.get("function") or {}
                        c["name"] += fn.get("name") or ""
                        c["arguments"] += fn.get("arguments") or ""
                    finish = ch.get("finish_reason") or finish
        yield {"tool_calls": [calls[i] for i in sorted(calls)], "finish": finish}

    async def run(self, s: Session, message: str) -> AsyncIterator[Event]:
        s.lang = detect_lang(message)
        last = [catalog.get(i) for i in s.last_results]
        ctx = "\nПоследняя выдача: " + ("; ".join(f"{n+1}) {p.id} {p.card(s.lang)['title']} {p.price}₸" for n, p in enumerate(last) if p) or "пусто")
        msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT + ctx}]
        msgs += [{"role": h["role"], "content": h["content"]} for h in s.history[-12:]]
        msgs.append({"role": "user", "content": message})
        user_budget = parse_budget(message)

        for _ in range(5):
            text, tool_calls = "", []
            async for part in self._stream(msgs):
                if "text" in part:
                    text += part["text"]
                    yield {"type": "text", "delta": part["text"]}
                else:
                    tool_calls = part["tool_calls"]
            if not tool_calls:
                break
            msgs.append({"role": "assistant", "content": text or None,
                         "tool_calls": [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                                        for c in tool_calls]})
            for c in tool_calls:
                try:
                    args = json.loads(c["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "status", "text": T[{"search_products": "searching", "build_bundle": "bundling", "compare_products": "comparing"}.get(c["name"], "cart")][s.lang]}
                args = enforce_budget(c["name"], args, user_budget)
                res, art = run_tool(c["name"], args, s)
                if art:
                    yield {"type": "artifact", "artifact": art}
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(res, ensure_ascii=False)})
        yield {"type": "suggestions", "items": SUGGEST[s.lang]}


def make_agent():
    """LLM_PROVIDER: auto (по найденному ключу) | qwen | openai | anthropic | rule."""
    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    if os.getenv("UMAY_AGENT") == "rule" or provider == "rule":
        return RuleAgent()
    if provider == "auto":
        if os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY"):
            provider = "qwen"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        else:
            return RuleAgent()
    try:
        return LLMAgent() if provider == "anthropic" else OpenAICompatAgent(provider)
    except Exception as e:  # нет ключа / SDK — работаем на демо-агенте
        logging.getLogger("umay").warning("LLM agent unavailable (%s), using rule agent", e)
        return RuleAgent()
