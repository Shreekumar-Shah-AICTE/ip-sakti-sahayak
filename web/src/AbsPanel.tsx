import { type FormEvent, useState } from "react";

// The Passport Compiler — ABS benefit-share calculator. Uses the as-of switch like /ask does,
// and always shows the arithmetic and the verbatim gazette lines behind the rate (S4 rule 5).
type Cite = { regulation: string; chunk_id: string; quote: string; source_url: string };
type AbsResult = {
  as_of: string;
  abstain: boolean;
  reason?: string;
  slab?: { id: string; label: string; rate_pct: string; citations: Cite[] };
  amount_inr?: string | null;
  steps?: string[];
  obligations?: { id: string; obligation: string; citations: Cite[] }[];
  notes?: { text: string; human_judgment_required: boolean; citations: Cite[] }[];
  uplift_citations?: Cite[];
  disclaimer?: string;
};

const CRORE = 10_000_000;

function Cites({ cs }: { cs: Cite[] }) {
  return (
    <ul className="mt-1 space-y-1 text-xs text-stone-600">
      {cs.map((c) => (
        <li key={c.chunk_id + c.regulation}>
          Reg. {c.regulation}: “{c.quote}” —{" "}
          <a className="underline" href={c.source_url} target="_blank" rel="noreferrer">
            {c.chunk_id}
          </a>
        </li>
      ))}
    </ul>
  );
}

export function AbsPanel({ asOf, t }: { asOf: string; t: Record<string, string> }) {
  const [turnover, setTurnover] = useState("60");
  const [sales, setSales] = useState("");
  const [highValue, setHighValue] = useState(false);
  const [res, setRes] = useState<AbsResult | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const p = new URLSearchParams({
      turnover_inr: String(Math.round(Number(turnover) * CRORE)),
      as_of: asOf,
      high_value: String(highValue),
    });
    if (sales.trim()) p.set("ex_factory_sales_inr", String(Math.round(Number(sales) * CRORE)));
    const r = await fetch(`/passport/abs?${p}`);
    setRes((await r.json()) as AbsResult);
  }

  return (
    <section data-testid="abs-panel" className="mt-8 rounded border border-stone-200 bg-white p-4">
      <h2 className="text-sm font-semibold">{t.absTitle}</h2>
      <form onSubmit={onSubmit} className="mt-2 flex flex-wrap items-end gap-3 text-sm">
        <label className="flex flex-col">
          {t.absTurnover}
          <input data-testid="abs-turnover" type="number" min="0" step="any" value={turnover}
            onChange={(e) => setTurnover(e.target.value)}
            className="mt-1 w-40 rounded border border-stone-300 px-2 py-1" />
        </label>
        <label className="flex flex-col">
          {t.absSales}
          <input data-testid="abs-sales" type="number" min="0" step="any" value={sales}
            onChange={(e) => setSales(e.target.value)}
            className="mt-1 w-40 rounded border border-stone-300 px-2 py-1" />
        </label>
        <label className="flex items-center gap-1">
          <input data-testid="abs-high-value" type="checkbox" checked={highValue}
            onChange={(e) => setHighValue(e.target.checked)} />
          {t.absHighValue}
        </label>
        <button data-testid="abs-compute" type="submit"
          className="rounded bg-stone-900 px-3 py-1 text-white focus:outline-2 focus:outline-offset-2">
          {t.absCompute}
        </button>
      </form>
      {res && res.abstain && (
        <p data-testid="abs-abstain" className="mt-3 rounded bg-stone-100 px-3 py-2 text-sm">
          {t.abstainTitle} ({res.as_of}). {res.reason}
        </p>
      )}
      {res && !res.abstain && res.slab && (
        <div data-testid="abs-result" className="mt-3 text-sm">
          <p className="font-medium">
            {res.as_of} · {res.slab.label} · {res.slab.rate_pct}%
            {res.amount_inr != null && <> · ₹{res.amount_inr}</>}
          </p>
          <ol className="mt-1 list-decimal pl-5">
            {res.steps?.map((s) => <li key={s}>{s}</li>)}
          </ol>
          <Cites cs={res.slab.citations} />
          {res.uplift_citations && res.uplift_citations.length > 0 && <Cites cs={res.uplift_citations} />}
          {res.obligations?.map((o) => (
            <div key={o.id} className="mt-2">
              <p>{o.obligation}</p>
              <Cites cs={o.citations} />
            </div>
          ))}
          {res.notes?.map((n) => (
            <div key={n.text} className="mt-2 text-amber-900">
              <p>{t.absJudgment}: {n.text}</p>
              <Cites cs={n.citations} />
            </div>
          ))}
          <p className="mt-2 text-xs text-stone-500">{res.disclaimer}</p>
        </div>
      )}
    </section>
  );
}
