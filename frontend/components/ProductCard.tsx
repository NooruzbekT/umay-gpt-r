"use client";
import { useState } from "react";
import { money } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Lang, Product } from "@/lib/types";

const TINT: Record<string, string> = {
  clothes: "#E3EEF5",
  home: "#E4F2EC",
  kids: "#F7E8EC",
  electronics: "#E8E8F5",
  beauty: "#F6E9F2",
  food: "#F5EEDC",
};

export function ProductCard({
  p,
  lang,
  inCart,
  onAdd,
}: {
  p: Product;
  lang: Lang;
  inCart: boolean;
  onAdd: (p: Product) => void;
}) {
  const discount = p.old_price ? Math.round((1 - p.price / p.old_price) * 100) : 0;
  const [imgOk, setImgOk] = useState(true);
  return (
    <article className="flex w-[212px] shrink-0 snap-start flex-col rounded-[18px] bg-white p-2.5 ring-1 ring-teal-deep/10">
      <div
        className="relative grid aspect-[4/3] place-items-center overflow-hidden rounded-[12px] text-5xl"
        style={{ background: TINT[p.category] ?? "#EEF3F3" }}
      >
        {p.image && imgOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={p.image} alt="" loading="lazy" onError={() => setImgOk(false)} className="h-full w-full object-cover" />
        ) : (
          <span aria-hidden>{p.emoji}</span>
        )}
        {discount > 0 && (
          <span className="absolute left-2 top-2 rounded-full bg-dot px-2 py-0.5 text-[11px] font-semibold text-white">
            −{discount}%
          </span>
        )}
      </div>
      <h3 className="mt-2.5 line-clamp-2 min-h-[2.6em] text-[13.5px] font-medium leading-snug text-teal-deep">
        {p.url ? (
          <a href={p.url} target="_blank" rel="noopener noreferrer" className="hover:underline focus-visible:underline">
            {p.title}
          </a>
        ) : (
          p.title
        )}
      </h3>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="font-display text-[15px] font-semibold text-teal-deep">{money(p.price)}</span>
        {p.old_price && <s className="text-xs text-mist">{money(p.old_price)}</s>}
      </div>
      <div className="mt-1.5 inline-flex w-fit items-center gap-1 rounded-md bg-steppe/20 px-1.5 py-0.5 text-[11.5px] font-medium text-[#7A5A12]">
        {t(lang, "installment")} <span className="opacity-60">|</span> {money(p.installment_24)}
        {t(lang, "perMonth")}
      </div>
      <div className="mt-2 flex items-center justify-between text-[12px] text-mist">
        <span>
          ★ {p.rating} <span className="opacity-70">({p.reviews})</span>
        </span>
        <span>
          {p.delivery_days} {t(lang, "days")}
        </span>
      </div>
      <button
        onClick={() => onAdd(p)}
        disabled={inCart}
        className="mt-2.5 rounded-xl bg-teal px-3 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-teal-deep focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-deep disabled:bg-teal-soft disabled:text-teal-deep"
      >
        {inCart ? `✓ ${t(lang, "added")}` : t(lang, "addToCart")}
      </button>
    </article>
  );
}
