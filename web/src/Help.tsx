import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { GLOSSARY, TOUR, type TermKey, type TourStep } from "./explain";

// An inline "what does this word mean?" helper. Click (or Enter) opens a small plain-language
// explanation; Escape or clicking elsewhere closes it.
export function Term({ k, children, light }: { k: TermKey; children?: ReactNode; light?: boolean }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const off = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", off);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", off);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  const g = GLOSSARY[k];
  return (
    <span ref={ref} className="relative inline-flex items-center">
      {children}
      <button
        type="button"
        data-testid={`term-${k}`}
        aria-expanded={open}
        aria-controls={id}
        aria-label={`What does “${g.term}” mean?`}
        onClick={() => setOpen((o) => !o)}
        className={`ml-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold leading-none ${
          light ? "bg-white/25 text-white hover:bg-white/40" : "bg-indigo-100 text-indigo-800 hover:bg-indigo-200"
        }`}
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          role="note"
          className="pop absolute left-0 top-6 z-40 w-72 rounded-xl border border-indigo-100 bg-white p-3 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-slate-800 shadow-xl"
        >
          <span className="block text-sm font-semibold text-indigo-900">{g.term}</span>
          {g.plain}
        </span>
      )}
    </span>
  );
}

export function GlossaryDrawer({ onClose }: { onClose: () => void }) {
  const [f, setF] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    input.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);
  const items = Object.values(GLOSSARY)
    .filter((g) => (g.term + g.plain).toLowerCase().includes(f.toLowerCase()))
    .sort((a, b) => a.term.localeCompare(b.term));
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-sm" onClick={onClose}>
      <aside
        data-testid="glossary"
        role="dialog"
        aria-modal="true"
        aria-label="Glossary"
        onClick={(e) => e.stopPropagation()}
        className="slide-in flex h-full w-full max-w-md flex-col bg-white shadow-2xl"
      >
        <div className="border-b border-slate-200 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">📖 Glossary — plain English</h2>
            <button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-slate-600 hover:bg-slate-100" aria-label="Close glossary">✕</button>
          </div>
          <p className="mt-1 text-sm text-slate-600">Every legal, Ayurveda and AI word used in this app, explained simply.</p>
          <input
            ref={input}
            value={f}
            onChange={(e) => setF(e.target.value)}
            placeholder="Search a word…"
            aria-label="Search the glossary"
            className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <dl className="flex-1 space-y-3 overflow-y-auto p-5">
          {items.map((g) => (
            <div key={g.term} className="rounded-xl bg-slate-50 p-3">
              <dt className="text-sm font-semibold text-indigo-900">{g.term}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-slate-700">{g.plain}</dd>
            </div>
          ))}
        </dl>
      </aside>
    </div>
  );
}

// The guided demo: a floating coach card that walks a newcomer (or a presenter) through the
// demo script. "Do it for me" performs the step; the card says what to look at and what to say.
export function TourCard({
  step, setStep, run, onClose,
}: { step: number; setStep: (n: number) => void; run: (s: TourStep) => void; onClose: () => void }) {
  const [min, setMin] = useState(false);
  const s = TOUR[step];
  if (min) {
    return (
      <button
        type="button"
        onClick={() => setMin(false)}
        className="fixed bottom-4 right-4 z-40 rounded-full bg-gradient-to-r from-indigo-600 to-emerald-600 px-4 py-3 text-sm font-semibold text-white shadow-2xl"
      >
        🧭 Guided demo · step {step + 1}/{TOUR.length}
      </button>
    );
  }
  return (
    <aside
      data-testid="tour"
      aria-label="Guided demo"
      className="pop fixed bottom-4 right-4 z-40 w-[22rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-indigo-100 bg-white shadow-2xl"
    >
      <div className="flex items-center justify-between bg-gradient-to-r from-indigo-700 to-emerald-700 px-4 py-2 text-white">
        <p className="text-xs font-semibold uppercase tracking-wider">🧭 Guided demo · step {step + 1} of {TOUR.length}</p>
        <div className="flex gap-1">
          <button type="button" onClick={() => setMin(true)} aria-label="Minimise guided demo" className="rounded px-1.5 hover:bg-white/20">–</button>
          <button type="button" onClick={onClose} aria-label="Close guided demo" className="rounded px-1.5 hover:bg-white/20">✕</button>
        </div>
      </div>
      <div className="h-1 bg-indigo-100">
        <div className="h-1 bg-emerald-500 transition-all" style={{ width: `${((step + 1) / TOUR.length) * 100}%` }} />
      </div>
      <div className="p-4">
        <h2 className="text-base font-bold text-slate-900">{s.title}</h2>
        <button
          type="button"
          data-testid="tour-do"
          onClick={() => run(s)}
          className="mt-3 w-full rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow hover:bg-indigo-700"
        >
          ▶ {s.doLabel}
        </button>
        <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-emerald-800">👀 What you should see</p>
        <p className="text-sm leading-relaxed text-slate-700">{s.see}</p>
        <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-indigo-800">🎤 Why it matters (say this)</p>
        <p className="text-sm italic leading-relaxed text-slate-700">{s.say}</p>
        <div className="mt-4 flex items-center justify-between">
          <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)} className="rounded-lg px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-40">← Back</button>
          <div className="flex gap-1" aria-hidden="true">
            {TOUR.map((_, i) => (
              <span key={i} className={`h-1.5 w-1.5 rounded-full ${i === step ? "bg-indigo-600" : i < step ? "bg-emerald-500" : "bg-slate-300"}`} />
            ))}
          </div>
          {step < TOUR.length - 1 ? (
            <button type="button" data-testid="tour-next" onClick={() => setStep(step + 1)} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700">Next →</button>
          ) : (
            <button type="button" onClick={onClose} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white">Finish ✓</button>
          )}
        </div>
      </div>
    </aside>
  );
}
