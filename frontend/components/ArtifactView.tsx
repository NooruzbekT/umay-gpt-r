"use client";
import { money } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Artifact, Lang, Product } from "@/lib/types";
import { ProductCard } from "./ProductCard";

type Props = { a: Artifact; lang: Lang; cartIds: Set<string>; onAdd: (p: Product) => void };

function Shelf({ products, lang, cartIds, onAdd }: { products: Product[] } & Omit<Props, "a">) {
  return (
    <div className="-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-2 [scrollbar-width:thin]">
      {products.map((p) => (
        <ProductCard key={p.id} p={p} lang={lang} inCart={cartIds.has(p.id)} onAdd={onAdd} />
      ))}
    </div>
  );
}

export function ArtifactView({ a, lang, cartIds, onAdd }: Props) {
  if (a.kind === "PRODUCT_LIST") return <Shelf products={a.products} lang={lang} cartIds={cartIds} onAdd={onAdd} />;

  if (a.kind === "BUNDLE") {
    const pct = Math.min(100, Math.round((a.total / a.budget) * 100));
    return (
      <div className="space-y-3">
        <div className="rounded-2xl bg-teal-soft/60 p-3">
          <div className="flex items-baseline justify-between text-sm text-teal-deep">
            <span className="font-medium">{t(lang, "bundle")}</span>
            <span>
              <b className="font-display">{money(a.total)}</b> {t(lang, "of")} {money(a.budget)}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full rounded-full bg-teal" style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-1 text-right text-xs text-mist">
            {t(lang, "left")} {money(a.budget - a.total)}
          </div>
        </div>
        <Shelf products={a.products} lang={lang} cartIds={cartIds} onAdd={onAdd} />
      </div>
    );
  }

  if (a.kind === "COMPARISON") {
    const ps = a.products;
    const minPrice = Math.min(...ps.map((p) => p.price));
    const maxRating = Math.max(...ps.map((p) => p.rating));
    const minDays = Math.min(...ps.map((p) => p.delivery_days));
    const best = "bg-teal-soft font-semibold";
    const rows: [string, (p: Product) => React.ReactNode, (p: Product) => boolean][] = [
      [t(lang, "price"), (p) => money(p.price), (p) => p.price === minPrice],
      [t(lang, "rating"), (p) => `★ ${p.rating} (${p.reviews})`, (p) => p.rating === maxRating],
      [t(lang, "deliveryRow"), (p) => `${p.delivery_days} ${t(lang, "days")}`, (p) => p.delivery_days === minDays],
      [t(lang, "installmentRow"), (p) => `${money(p.installment_24)}${t(lang, "perMonth")}`, (p) => p.price === minPrice],
      [t(lang, "sourceRow"), (p) => p.source, () => false],
    ];
    return (
      <div className="overflow-x-auto rounded-2xl bg-white ring-1 ring-teal-deep/10">
        <table className="w-full min-w-[420px] text-left text-[13px] text-teal-deep">
          <caption className="sr-only">{t(lang, "compare")}</caption>
          <thead>
            <tr>
              <th className="w-32 p-3" />
              {ps.map((p) => (
                <th key={p.id} className="p-3 align-top font-medium">
                  <div className="text-2xl" aria-hidden>{p.emoji}</div>
                  {p.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, cell, isBest]) => (
              <tr key={label} className="border-t border-teal-deep/5">
                <th scope="row" className="p-3 font-normal text-mist">{label}</th>
                {ps.map((p) => (
                  <td key={p.id} className={`p-3 ${isBest(p) && ps.length > 1 ? best : ""}`}>{cell(p)}</td>
                ))}
              </tr>
            ))}
            <tr className="border-t border-teal-deep/5">
              <td />
              {ps.map((p) => (
                <td key={p.id} className="p-3">
                  <button
                    onClick={() => onAdd(p)}
                    disabled={cartIds.has(p.id)}
                    className="rounded-lg bg-teal px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-deep disabled:bg-teal-soft disabled:text-teal-deep"
                  >
                    {cartIds.has(p.id) ? `✓ ${t(lang, "added")}` : t(lang, "addToCart")}
                  </button>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  // CART — компактное превью; полная корзина в выезжающей панели
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white p-3 text-sm text-teal-deep ring-1 ring-teal-deep/10">
      <span className="text-xl" aria-hidden>🛒</span>
      <span className="flex-1">
        {a.items.map((i) => i.emoji).join(" ")}{" "}
        <span className="text-mist">({a.items.length})</span>
      </span>
      <b className="font-display">{money(a.total)}</b>
    </div>
  );
}
