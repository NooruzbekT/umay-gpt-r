import type { Artifact, Cart, StreamEvent } from "./types";

/** POST /api/chat → читаем SSE-поток через fetch (а не EventSource, чтобы слать JSON-тело и отменять запрос). */
export async function streamChat(
  message: string,
  sessionId: string | null,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  });
  if (res.status === 429) throw new Error("rate");
  if (!res.ok || !res.body) throw new Error(`http ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)) as StreamEvent);
    }
  }
}

export async function addToCart(sessionId: string, productId: string): Promise<Cart> {
  const r = await fetch("/api/cart", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, product_id: productId }),
  });
  if (!r.ok) throw new Error("cart");
  return r.json();
}

export async function getCart(sessionId: string): Promise<Cart> {
  const r = await fetch(`/api/cart?session_id=${encodeURIComponent(sessionId)}`);
  return r.json();
}

export async function removeFromCart(sessionId: string, productId: string): Promise<Cart> {
  const r = await fetch(`/api/cart/${productId}?session_id=${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  return r.json();
}

export async function searchByImage(
  file: File,
  sessionId: string | null,
): Promise<{ session_id: string; detected_color: string; artifact: Artifact }> {
  const fd = new FormData();
  fd.append("file", file);
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const r = await fetch(`/api/search/image${q}`, { method: "POST", body: fd });
  if (!r.ok) throw new Error("image");
  return r.json();
}

export const money = (n: number) => `${n.toLocaleString("ru-RU").replace(/,/g, " ")} ₸`;

export function safeStorage<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function saveStorage(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* приватный режим / квота — работаем без сохранения */
  }
}
