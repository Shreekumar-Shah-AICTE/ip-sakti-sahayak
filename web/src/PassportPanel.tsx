import { type FormEvent, useState } from "react";

// The Passport Compiler — category passports. Compiled as of the as-of switch; every obligation
// shows its verbatim source line; judgment calls render as risk indicators, never verdicts (S4).
// "Print" uses print CSS (index.css) so only the passport reaches paper.
type Cite = { regulation: string; chunk_id: string; quote: string; source_url: string };
type Rule = {
  id: string;
  title: string;
  obligation: string;
  confidence: string;
  human_judgment_required: boolean;
  risk_indicator?: string | null;
  guiding_principle?: string | null;
  status_line?: string;
  citations: Cite[];
};
type Passport = {
  category: string;
  title: string;
  jurisdiction: string;
  as_of: string;
  covered_from: string;
  abstain: boolean;
  reason?: string;
  definition?: Cite;
  classification?: { risk_indicator: string; guiding_principle: string };
  rules?: Rule[];
  gaps?: string[];
  disclaimer: string;
};

const CATS = ["classical", "proprietary", "phytopharma"] as const;

function Quote({ c }: { c: Cite }) {
  return (
    <li className="text-xs text-stone-600">
      {c.regulation}: “{c.quote}” —{" "}
      <a className="underline" href={c.source_url} target="_blank" rel="noreferrer">
        {c.chunk_id}
      </a>
    </li>
  );
}

export function PassportPanel({ asOf, t }: { asOf: string; t: Record<string, string> }) {
  const [cat, setCat] = useState<(typeof CATS)[number]>("classical");
  const [p, setP] = useState<Passport | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const r = await fetch(`/passport/${cat}?${new URLSearchParams({ as_of: asOf })}`);
    setP(await r.json());
  }

  return (
    <section className="mt-8 rounded border border-stone-300 p-4">
      <h2 className="font-semibold">{t.passportTitle}</h2>
      <form className="no-print mt-2 flex flex-wrap items-end gap-3" onSubmit={onSubmit}>
        <label className="text-sm">
          {t.passportCategory}
          <select
            data-testid="passport-category"
            className="ml-2 rounded border px-2 py-1"
            value={cat}
            onChange={(e) => setCat(e.target.value as (typeof CATS)[number])}
          >
            {CATS.map((c) => (
              <option key={c} value={c}>
                {t[`passport_${c}`]}
              </option>
            ))}
          </select>
        </label>
        <button data-testid="passport-compile" className="rounded bg-stone-800 px-3 py-1 text-white">
          {t.passportCompile}
        </button>
        {p && !p.abstain && (
          <button
            type="button"
            data-testid="passport-print"
            className="rounded border px-3 py-1"
            onClick={() => window.print()}
          >
            {t.passportPrint}
          </button>
        )}
      </form>
      {p && p.abstain && (
        <p data-testid="passport-abstain" className="mt-3 rounded bg-amber-50 p-2 text-sm">
          {p.reason}
        </p>
      )}
      {p && !p.abstain && (
        <article data-testid="passport" data-print-root className="mt-4 text-sm">
          <h3 className="text-base font-semibold">{p.title}</h3>
          <p className="text-xs text-stone-500">
            {p.jurisdiction} · {t.passportAsOf} {p.as_of} · {t.passportCovered} {p.covered_from}
          </p>
          {p.definition && (
            <ul className="mt-2">
              <Quote c={p.definition} />
            </ul>
          )}
          {p.classification && (
            <p className="mt-2 rounded bg-amber-50 p-2 text-xs">
              ⚠ {t.absJudgment}: {p.classification.risk_indicator} ({p.classification.guiding_principle})
            </p>
          )}
          <ol className="mt-3 space-y-3">
            {p.rules?.map((r) => (
              <li key={r.id} data-testid={`passport-rule-${r.id}`} className="border-l-2 border-stone-300 pl-2">
                <p className="font-medium">
                  {r.id} — {r.title}
                </p>
                <p>{r.obligation}</p>
                {r.status_line && <p className="text-xs font-semibold">{r.status_line}</p>}
                {r.human_judgment_required && (
                  <p className="text-xs text-amber-800">
                    ⚠ {t.absJudgment}: {r.risk_indicator} ({r.guiding_principle})
                  </p>
                )}
                <ul className="mt-1 space-y-1">
                  {r.citations.map((c) => (
                    <Quote key={c.chunk_id + c.quote} c={c} />
                  ))}
                </ul>
              </li>
            ))}
          </ol>
          {p.gaps && p.gaps.length > 0 && (
            <div data-testid="passport-gaps" className="mt-3 rounded bg-stone-100 p-2 text-xs">
              <p className="font-semibold">{t.passportGaps}</p>
              <ul>
                {p.gaps.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-3 text-xs text-stone-500">{p.disclaimer}</p>
        </article>
      )}
    </section>
  );
}
