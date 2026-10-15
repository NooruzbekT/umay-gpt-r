"""Umay GPT Next — API (список эндпоинтов в README)."""
from __future__ import annotations

import io
import json
import logging
import os
import time
from collections import defaultdict

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

try:  # .env из корня репозитория или из backend/ (ключи LLM, режим каталога)
    from pathlib import Path

    from dotenv import load_dotenv

    if not os.getenv("UMAY_TESTING"):  # тесты всегда без ключей и сети
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        load_dotenv()
except ImportError:
    pass

from .agent import RuleAgent, make_agent  # noqa: E402
from .catalog import catalog
from .store import store
from .tools import cart_view, run_tool

log = logging.getLogger("umay")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Umay GPT Next API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = make_agent()
fallback = RuleAgent()

# простейший rate-limit в памяти процесса
_hits: dict[str, list[float]] = defaultdict(list)
RATE = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))


def check_rate(key: str) -> None:
    now = time.time()
    _hits[key] = [t for t in _hits[key] if now - t < 60]
    if len(_hits[key]) >= RATE:
        raise HTTPException(429, "Слишком много запросов, попробуйте через минуту")
    _hits[key].append(now)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class CartIn(BaseModel):
    session_id: str
    product_id: str
    qty: int = Field(default=1, ge=1, le=20)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/api/health")
def health():
    return {"status": "ok", "agent": agent.name, "catalog": catalog.name, "products": len(catalog.products)}


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    check_rate(request.client.host if request.client else "anon")
    s = store.get_or_create(body.session_id)
    if not s.history:
        s.title = body.message[:48]

    async def gen():
        yield sse({"type": "session", "session_id": s.id, "agent": agent.name})
        answer: list[str] = []
        t0 = time.time()
        try:
            async for ev in agent.run(s, body.message):
                if ev["type"] == "text":
                    answer.append(ev["delta"])
                yield sse(ev)
        except Exception as e:  # LLM недоступна → graceful degradation на rule-агента
            log.warning("agent failed (%s), falling back", e)
            yield sse({"type": "status", "text": "Переключаюсь на резервный режим…"})
            async for ev in fallback.run(s, body.message):
                if ev["type"] == "text":
                    answer.append(ev["delta"])
                yield sse(ev)
        s.history.append({"role": "user", "content": body.message})
        s.history.append({"role": "assistant", "content": "".join(answer) or "(карточки)"})
        log.info("chat sid=%s lang=%s latency=%.2fs", s.id[:8], s.lang, time.time() - t0)
        yield sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             # no-transform: прокси Next.js (и другие) не сжимают и не буферизуют SSE
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@app.get("/api/sessions/{sid}")
def session(sid: str):
    s = store.get(sid)
    if not s:
        raise HTTPException(404, "session not found")
    return {"id": s.id, "title": s.title, "history": s.history, "cart": cart_view(s)}


@app.get("/api/cart")
def get_cart(session_id: str = Query(...)):
    return cart_view(store.get_or_create(session_id))


@app.post("/api/cart")
def add_cart(body: CartIn):
    s = store.get_or_create(body.session_id)
    res, art = run_tool("add_to_cart", {"product_id": body.product_id, "qty": body.qty}, s)
    if "error" in res:
        raise HTTPException(404, res["error"])
    return cart_view(s)


@app.delete("/api/cart/{pid}")
def del_cart(pid: str, session_id: str = Query(...)):
    s = store.get_or_create(session_id)
    s.cart.pop(pid, None)
    return cart_view(s)


@app.get("/api/products/{pid}")
def product(pid: str, lang: str = "ru"):
    p = catalog.get(pid)
    if not p:
        raise HTTPException(404, "not found")
    return p.card(lang)


if os.getenv("UMAY_DEV", "1") == "1":
    from fastapi.responses import FileResponse

    @app.get("/inspector", include_in_schema=False)
    def inspector():
        """Dev-страница: сырой SSE-поток агента и состояние сессии. В проде UMAY_DEV=0."""
        return FileResponse(os.path.join(os.path.dirname(__file__), "static", "inspector.html"))


COLOR_MAP = {
    "чёрный": (30, 30, 30), "белый": (235, 235, 235), "серый": (128, 128, 128), "бежевый": (215, 195, 165),
    "коричневый": (110, 70, 40), "синий": (40, 70, 160), "розовый": (230, 150, 180), "зелёный": (60, 130, 70),
    "хаки": (120, 120, 80), "бордовый": (120, 20, 40), "молочный": (245, 240, 225), "мятный": (170, 225, 200),
}


@app.post("/api/search/image")
async def search_image(file: UploadFile = File(...), session_id: str | None = None):
    """Демо поиска по фото: берём доминирующий цвет и ищем товары этого цвета."""
    from PIL import Image

    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Файл больше 8 МБ")
    img = Image.open(io.BytesIO(data)).convert("RGB").resize((64, 64))
    px = list(img.getdata())
    r, g, b = (sum(c[i] for c in px) // len(px) for i in range(3))
    color = min(COLOR_MAP, key=lambda k: sum((a - c) ** 2 for a, c in zip(COLOR_MAP[k], (r, g, b))))
    s = store.get_or_create(session_id)
    found = [p for p in catalog.products if color in p.raw["colors"]][:6]
    s.last_results = [p.id for p in found]
    return {"session_id": s.id, "detected_color": color,
            "artifact": {"kind": "PRODUCT_LIST", "products": [p.card(s.lang) for p in found]}}
