"use client";
import { useEffect, useRef, useState } from "react";
import { LANGS, t } from "@/lib/i18n";
import type { Lang } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
export function Composer({
  lang,
  busy,
  onSend,
  onPhoto,
  big,
}: {
  lang: Lang;
  busy: boolean;
  onSend: (text: string) => void;
  onPhoto: (f: File) => void;
  big?: boolean;
}) {
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceOk, setVoiceOk] = useState(false);
  const ta = useRef<HTMLTextAreaElement>(null);
  const file = useRef<HTMLInputElement>(null);
  const rec = useRef<any>(null);

  useEffect(() => {
    setVoiceOk(typeof window !== "undefined" && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition));
  }, []);

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }, [text]);

  const submit = () => {
    const v = text.trim();
    if (!v || busy) return;
    onSend(v);
    setText("");
  };

  // Голос: Web Speech API в браузере; распознавание kk-KZ поддерживается не во всех браузерах.
  const toggleVoice = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    if (listening) {
      rec.current?.stop();
      return;
    }
    const r = new SR();
    r.lang = LANGS.find((l) => l.id === lang)?.speech ?? "ru-RU";
    r.interimResults = true;
    r.onresult = (e: any) => setText(Array.from(e.results).map((x: any) => x[0].transcript).join(""));
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  };

  const iconBtn =
    "grid size-10 place-items-center rounded-full text-mist transition-colors hover:bg-teal-soft hover:text-teal-deep focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal";

  return (
    <div
      className={`rounded-[22px] bg-white ring-1 ring-teal-deep/10 transition-shadow focus-within:ring-2 focus-within:ring-teal ${
        big ? "p-4 shadow-[0_18px_40px_-24px_rgba(15,59,62,0.45)]" : "p-2.5"
      }`}
    >
      <label htmlFor="composer" className="sr-only">
        {t(lang, "placeholder")}
      </label>
      <textarea
        id="composer"
        ref={ta}
        rows={big ? 2 : 1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder={listening ? t(lang, "listening") : t(lang, "placeholder")}
        className={`w-full resize-none bg-transparent px-2 text-teal-deep placeholder:text-mist/80 focus:outline-none ${
          big ? "text-[17px]" : "text-[15px]"
        }`}
      />
      <div className="mt-1 flex items-center gap-1">
        <input
          ref={file}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onPhoto(f);
            e.target.value = "";
          }}
        />
        <button type="button" className={iconBtn} aria-label={t(lang, "photo")} title={t(lang, "photo")} onClick={() => file.current?.click()}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
            <circle cx="12" cy="13" r="3.5" />
          </svg>
        </button>
        {voiceOk && (
          <button
            type="button"
            className={`${iconBtn} ${listening ? "!bg-dot !text-white" : ""}`}
            aria-label={t(lang, "voice")}
            aria-pressed={listening}
            title={t(lang, "voice")}
            onClick={toggleVoice}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
              <rect x="9" y="3" width="6" height="12" rx="3" />
              <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
            </svg>
          </button>
        )}
        <div className="flex-1" />
        <button
          type="button"
          onClick={submit}
          disabled={busy || !text.trim()}
          aria-label={t(lang, "send")}
          className="grid size-10 place-items-center rounded-full bg-teal text-white transition-colors hover:bg-teal-deep focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-deep disabled:bg-teal-soft disabled:text-mist"
        >
          {busy ? (
            <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
