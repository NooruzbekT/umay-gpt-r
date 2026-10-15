"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { addToCart, getCart, removeFromCart, safeStorage, saveStorage, searchByImage, streamChat } from "@/lib/api";
import { LANGS, t, tl } from "@/lib/i18n";
import type { Cart, ChatMeta, Lang, Message, Product } from "@/lib/types";
import { ArtifactView } from "./ArtifactView";
import { CartDrawer } from "./CartDrawer";
import { Composer } from "./Composer";
import { Logo } from "./Logo";

const EMPTY_CART: Cart = { items: [], total: 0, installment_24: 0 };
const uid = () => Math.random().toString(36).slice(2, 10);

/** **жирный** → <strong>; остальной текст как есть (без dangerouslySetInnerHTML). */
function RichText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") ? (
          <strong key={i} className="font-semibold">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

export default function Chat() {
  const [lang, setLang] = useState<Lang>("ru");
  const [chats, setChats] = useState<ChatMeta[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [cart, setCart] = useState<Cart>(EMPTY_CART);
  const [cartOpen, setCartOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [agentName, setAgentName] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  // --- восстановление состояния гостя ---
  useEffect(() => {
    setLang(safeStorage<Lang>("umay.lang", "ru"));
    setChats(safeStorage<ChatMeta[]>("umay.chats", []));
    fetch("/api/health")
      .then((r) => r.json())
      .then((h) => setAgentName(h.agent))
      .catch(() => setAgentName("offline"));
  }, []);

  useEffect(() => saveStorage("umay.lang", lang), [lang]);
  useEffect(() => {
    if (sessionId) saveStorage(`umay.msgs.${sessionId}`, messages.filter((m) => !m.pending));
  }, [messages, sessionId]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const cartIds = useMemo(() => new Set(cart.items.map((i) => i.id)), [cart]);

  const touchChat = useCallback((id: string, title: string) => {
    setChats((prev) => {
      const rest = prev.filter((c) => c.id !== id);
      const existing = prev.find((c) => c.id === id);
      const next = [{ id, title: existing?.title ?? title.slice(0, 48), updatedAt: Date.now() }, ...rest].slice(0, 30);
      saveStorage("umay.chats", next);
      return next;
    });
  }, []);

  const patchLast = (fn: (m: Message) => Message) =>
    setMessages((prev) => {
      const copy = [...prev];
      copy[copy.length - 1] = fn(copy[copy.length - 1]);
      return copy;
    });

  const send = useCallback(
    async (text: string) => {
      if (busy) return;
      setBusy(true);
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "user", text, artifacts: [] },
        { id: uid(), role: "assistant", text: "", artifacts: [], pending: true },
      ]);
      abort.current = new AbortController();
      let sid = sessionId;
      try {
        await streamChat(
          text,
          sessionId,
          (e) => {
            if (e.type === "session") {
              sid = e.session_id;
              setSessionId(e.session_id);
              touchChat(e.session_id, text);
            } else if (e.type === "status") patchLast((m) => ({ ...m, status: e.text }));
            else if (e.type === "text") patchLast((m) => ({ ...m, text: m.text + e.delta, status: undefined }));
            else if (e.type === "artifact") {
              patchLast((m) => ({ ...m, artifacts: [...m.artifacts, e.artifact] }));
              if (e.artifact.kind === "CART") setCart({ items: e.artifact.items, total: e.artifact.total, installment_24: e.artifact.installment_24 });
            } else if (e.type === "suggestions") patchLast((m) => ({ ...m, suggestions: e.items }));
            else if (e.type === "done") patchLast((m) => ({ ...m, pending: false, status: undefined }));
          },
          abort.current.signal,
        );
      } catch (err) {
        const msg = err instanceof Error && err.message === "rate" ? t(lang, "errorRate") : t(lang, "errorNet");
        patchLast((m) => ({ ...m, pending: false, status: undefined, error: msg, text: m.text }));
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = { ...copy[copy.length - 1], suggestions: undefined };
          (copy[copy.length - 1] as Message & { retry?: string }).retry = text;
          return copy;
        });
      } finally {
        setBusy(false);
        if (sid) getCart(sid).then(setCart).catch(() => {});
      }
    },
    [busy, sessionId, lang, touchChat],
  );

  const onAdd = async (p: Product) => {
    if (!sessionId) return;
    try {
      setCart(await addToCart(sessionId, p.id));
    } catch {
      /* карточка останется активной — можно нажать ещё раз */
    }
  };

  const onPhoto = async (f: File) => {
    if (busy) return;
    setBusy(true);
    const url = URL.createObjectURL(f);
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: "user", text: "", image: url, artifacts: [] },
      { id: uid(), role: "assistant", text: "", artifacts: [], pending: true, status: "…" },
    ]);
    try {
      const r = await searchByImage(f, sessionId);
      setSessionId(r.session_id);
      touchChat(r.session_id, `📷 ${r.detected_color}`);
      patchLast((m) => ({ ...m, pending: false, status: undefined, text: `${t(lang, "photoFound")} «${r.detected_color}».`, artifacts: [r.artifact] }));
    } catch {
      patchLast((m) => ({ ...m, pending: false, status: undefined, error: t(lang, "errorNet") }));
    } finally {
      setBusy(false);
    }
  };

  const openChat = (id: string) => {
    abort.current?.abort();
    setSessionId(id);
    setMessages(safeStorage<Message[]>(`umay.msgs.${id}`, []));
    getCart(id).then(setCart).catch(() => setCart(EMPTY_CART));
    setNavOpen(false);
  };

  const newChat = () => {
    abort.current?.abort();
    setSessionId(null);
    setMessages([]);
    setCart(EMPTY_CART);
    setNavOpen(false);
  };

  const empty = messages.length === 0;
  const cartCount = cart.items.reduce((s, i) => s + (i.qty ?? 1), 0);

  return (
    <div className="flex h-dvh bg-paper font-sans text-teal-deep">
      {/* ---------- боковая панель ---------- */}
      <nav
        aria-label={t(lang, "chats")}
        className={`fixed inset-y-0 left-0 z-20 flex w-72 flex-col border-r border-teal-deep/10 bg-white transition-transform motion-reduce:transition-none md:static md:translate-x-0 ${
          navOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-2.5 px-5 pb-4 pt-5">
          <Logo size={32} />
          <span className="font-display text-[17px] font-semibold tracking-tight">Umay GPT</span>
        </div>
        <div className="px-3">
          <button
            onClick={newChat}
            className="flex w-full items-center gap-2 rounded-2xl px-3 py-2.5 text-[15px] font-medium text-teal-deep ring-1 ring-teal-deep/15 hover:bg-teal-soft"
          >
            <span className="text-lg leading-none text-teal">+</span> {t(lang, "newChat")}
          </button>
        </div>
        <h2 className="px-5 pb-1 pt-5 text-[13px] text-mist">{t(lang, "chats")}</h2>
        <ul className="flex-1 space-y-0.5 overflow-y-auto px-3">
          {chats.length === 0 && <li className="px-3 py-2 text-sm text-mist/80">{t(lang, "noChats")}</li>}
          {chats.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => openChat(c.id)}
                aria-current={c.id === sessionId ? "page" : undefined}
                className={`w-full truncate rounded-xl px-3 py-2 text-left text-sm hover:bg-paper ${c.id === sessionId ? "bg-teal-soft font-medium" : ""}`}
              >
                {c.title}
              </button>
            </li>
          ))}
        </ul>
        <div className="border-t border-teal-deep/10 px-5 py-3 text-[11.5px] text-mist">
          {agentName && <>agent: {agentName}</>}
        </div>
      </nav>
      {navOpen && <div className="fixed inset-0 z-10 bg-teal-deep/20 md:hidden" onClick={() => setNavOpen(false)} aria-hidden />}

      {/* ---------- основная колонка ---------- */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 px-4 py-3 md:px-6">
          <button onClick={() => setNavOpen(true)} className="grid size-10 place-items-center rounded-full hover:bg-white md:hidden" aria-label={t(lang, "chats")}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M4 7h16M4 12h16M4 17h10" />
            </svg>
          </button>
          <div className="flex-1" />
          <div role="group" aria-label="Language" className="flex rounded-full bg-white p-0.5 ring-1 ring-teal-deep/10">
            {LANGS.map((l) => (
              <button
                key={l.id}
                onClick={() => setLang(l.id)}
                aria-pressed={lang === l.id}
                className={`rounded-full px-3 py-1.5 text-[13px] ${lang === l.id ? "bg-teal-deep text-white" : "text-mist hover:text-teal-deep"}`}
              >
                {l.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setCartOpen(true)}
            className="relative grid size-10 place-items-center rounded-full bg-white ring-1 ring-teal-deep/10 hover:bg-teal-soft"
            aria-label={`${t(lang, "cart")} (${cartCount})`}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M3 4h2l2.4 11h10.2L20 8H6.2" />
              <circle cx="9.5" cy="19.5" r="1.4" />
              <circle cx="16.5" cy="19.5" r="1.4" />
            </svg>
            {cartCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 grid min-w-5 place-items-center rounded-full bg-dot px-1 text-[11px] font-semibold text-white">{cartCount}</span>
            )}
          </button>
        </header>

        {empty ? (
          <section className="mx-auto flex w-full max-w-[720px] flex-1 flex-col justify-center px-4 pb-16">
            <h1 className="font-display text-[clamp(30px,5vw,46px)] font-semibold leading-[1.05] tracking-[-0.02em]">{t(lang, "hello")}</h1>
            <p className="mt-3 max-w-[58ch] text-[16px] leading-relaxed text-mist">{t(lang, "sub")}</p>
            <div className="mt-7">
              <Composer lang={lang} busy={busy} onSend={send} onPhoto={onPhoto} big />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {tl(lang, "starters").map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full bg-white px-3.5 py-2 text-[13.5px] text-teal-deep ring-1 ring-teal-deep/10 hover:bg-teal-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal"
                >
                  {s}
                </button>
              ))}
            </div>
            <p className="mt-6 text-xs text-mist">{t(lang, "disclaimer")}</p>
          </section>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto" aria-live="polite">
              <div className="mx-auto w-full max-w-[760px] space-y-6 px-4 py-4">
                {messages.map((m) =>
                  m.role === "user" ? (
                    <div key={m.id} className="flex justify-end">
                      {m.image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={m.image} alt="" className="max-h-48 rounded-2xl ring-1 ring-teal-deep/10" />
                      ) : (
                        <div className="max-w-[80%] rounded-[20px] rounded-br-md bg-teal-deep px-4 py-2.5 text-[15px] text-white">{m.text}</div>
                      )}
                    </div>
                  ) : (
                    <div key={m.id} className="space-y-3">
                      <div className="flex gap-3">
                        <div className="mt-0.5 shrink-0">
                          <Logo size={28} />
                        </div>
                        <div className="min-w-0 flex-1 space-y-3">
                          {m.status && (
                            <div className="flex items-center gap-2 text-sm text-mist">
                              <span className="size-2 animate-pulse rounded-full bg-teal motion-reduce:animate-none" /> {m.status}
                            </div>
                          )}
                          {m.pending && !m.status && !m.text && <span className="inline-block size-2 animate-pulse rounded-full bg-teal" />}
                          {m.artifacts.map((a, i) => (
                            <ArtifactView key={i} a={a} lang={lang} cartIds={cartIds} onAdd={onAdd} />
                          ))}
                          {m.text && (
                            <p className="max-w-[65ch] text-[15.5px] leading-relaxed">
                              <RichText text={m.text} />
                            </p>
                          )}
                          {m.error && (
                            <div className="rounded-xl bg-dot/10 px-3 py-2 text-sm text-[#9B1C21]">
                              {m.error}{" "}
                              {(m as Message & { retry?: string }).retry && (
                                <button className="ml-1 font-semibold underline" onClick={() => send((m as Message & { retry?: string }).retry!)}>
                                  {t(lang, "retry")}
                                </button>
                              )}
                            </div>
                          )}
                          {!m.pending && m.suggestions && m === messages[messages.length - 1] && (
                            <div className="flex flex-wrap gap-2">
                              {m.suggestions.map((s) => (
                                <button
                                  key={s}
                                  onClick={() => send(s)}
                                  className="rounded-full px-3 py-1.5 text-[13px] text-teal ring-1 ring-teal/40 hover:bg-teal-soft"
                                >
                                  {s}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ),
                )}
                <div ref={bottom} />
              </div>
            </div>
            <div className="mx-auto w-full max-w-[760px] px-4 pb-4">
              <Composer lang={lang} busy={busy} onSend={send} onPhoto={onPhoto} />
              <p className="mt-2 text-center text-[11.5px] text-mist">{t(lang, "disclaimer")}</p>
            </div>
          </>
        )}
      </main>

      <CartDrawer
        open={cartOpen}
        cart={cart}
        lang={lang}
        onClose={() => setCartOpen(false)}
        onRemove={async (id) => sessionId && setCart(await removeFromCart(sessionId, id))}
      />
    </div>
  );
}
