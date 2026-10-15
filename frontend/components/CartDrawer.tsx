"use client";
import { useEffect, useRef } from "react";
import { money } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Cart, Lang } from "@/lib/types";

export function CartDrawer({
  open,
  cart,
  lang,
  onClose,
  onRemove,
}: {
  open: boolean;
  cart: Cart;
  lang: Lang;
  onClose: () => void;
  onRemove: (id: string) => void;
}) {
  const closeBtn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-30 bg-teal-deep/30 transition-opacity motion-reduce:transition-none ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={t(lang, "cart")}
        className={`fixed right-0 top-0 z-40 flex h-full w-full max-w-[380px] flex-col bg-paper shadow-2xl transition-transform duration-300 motion-reduce:transition-none ${
          open ? "translate-x-0" : "invisible translate-x-full"
        }`}
      >
        <header className="flex items-center justify-between px-5 pb-3 pt-5">
          <h2 className="font-display text-lg font-semibold text-teal-deep">{t(lang, "cart")}</h2>
          <button ref={closeBtn} onClick={onClose} aria-label="×" className="grid size-9 place-items-center rounded-full text-xl text-mist hover:bg-teal-soft">
            ×
          </button>
        </header>
        <div className="flex-1 space-y-2 overflow-y-auto px-5">
          {cart.items.length === 0 && <p className="mt-6 text-sm leading-relaxed text-mist">{t(lang, "cartEmpty")}</p>}
          {cart.items.map((i) => (
            <div key={i.id} className="flex items-center gap-3 rounded-2xl bg-white p-3 ring-1 ring-teal-deep/10">
              <span className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-xl bg-teal-soft text-2xl" aria-hidden>
                {i.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={i.image} alt="" className="h-full w-full object-cover" onError={(e) => (e.currentTarget.style.display = "none")} />
                ) : (
                  i.emoji
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-teal-deep">{i.title}</div>
                <div className="text-xs text-mist">
                  {i.qty} × {money(i.price)}
                </div>
              </div>
              <button onClick={() => onRemove(i.id)} className="text-xs text-mist underline-offset-2 hover:text-dot hover:underline">
                {t(lang, "remove")}
              </button>
            </div>
          ))}
        </div>
        {cart.items.length > 0 && (
          <footer className="space-y-3 border-t border-teal-deep/10 p-5">
            <div className="flex items-baseline justify-between text-teal-deep">
              <span>{t(lang, "total")}</span>
              <span className="font-display text-xl font-semibold">{money(cart.total)}</span>
            </div>
            <div className="rounded-lg bg-steppe/20 px-3 py-2 text-sm text-[#7A5A12]">
              {t(lang, "installment")}: {money(cart.installment_24)}
              {t(lang, "perMonth")}
            </div>
            <button className="w-full rounded-2xl bg-teal py-3 font-semibold text-white hover:bg-teal-deep">{t(lang, "checkout")}</button>
          </footer>
        )}
      </aside>
    </>
  );
}
