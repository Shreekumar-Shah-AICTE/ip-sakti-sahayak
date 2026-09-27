import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AbsPanel } from "./AbsPanel";
import { type Lang, STATUS_LABELS, STRINGS } from "./i18n";

// The Two Switches live above the fold (S6 rule 1) and are sent with every question.
const JURISDICTIONS = ["IN", "US", "EU", "WIPO-track"] as const;

type Quote = {
  text: string;
  chunk_id: string;
  doc_title: string;
  section: string;
  source_url: string;
  retrieved_on: string;
  role: "status_evidence" | "retrieved";
};

type Status = {
  instrument: string;
  status: string | null;
  sub_judice: boolean;
  summary: string;
  stale: boolean;
  last_verified?: string | null;
  abstain: boolean;
  reason: string;
};

type Answer = {
  jurisdiction: string;
  as_of: string;
  corpus_version: string;
  abstain: boolean;
  reason: string;
  confidence: string;
  status_line: string | null;
  status: Status | null;
  quotes: Quote[];
  disclaimer: string;
};

function AnswerCard({ a, t, testId }: { a: Answer; t: Record<string, string>; testId: string }) {
  return (
    <article data-testid={testId} className="rounded border border-stone-200 bg-white p-4">
      <p className="text-xs text-stone-500">
        {a.jurisdiction} · {a.as_of} · {t.confidence}: {a.confidence}
      </p>
      {a.status && !a.status.abstain && (
        <div
          data-testid="status-line"
          className="mt-2 rounded bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900"
        >
          {t.statusAsOf} {a.as_of}: {STATUS_LABELS[a.status.status ?? ""] ?? a.status.status}
          {a.status.sub_judice && <span> ({t.subJudice})</span>}
          <span className="sr-only"> [{a.status.status}]</span>
          <p className="mt-1 font-normal">{a.status.summary}</p>
          {a.status.stale && (
            <p data-testid="stale" className="mt-1 font-normal text-red-800">
              {t.stale.replace("{date}", a.status.last_verified ?? "")}
            </p>
          )}
        </div>
      )}
      {a.abstain ? (
        <div data-testid="abstain" className="mt-3 rounded bg-stone-100 px-3 py-3 text-sm">
          <p className="font-medium">{t.abstainTitle}</p>
          <p className="mt-1 text-stone-600">{a.reason}</p>
          <p className="mt-2 text-stone-600">{t.abstainNext}</p>
        </div>
      ) : (
        <>
          <h3 className="mt-3 text-sm font-semibold">{t.sources}</h3>
          <ol className="mt-1 space-y-3">
            {a.quotes.map((q) => (
              <li key={q.chunk_id} className="text-sm">
                <blockquote className="border-l-4 border-stone-300 pl-3 italic">“{q.text}”</blockquote>
                <p className="mt-1 text-xs text-stone-600">
                  {q.doc_title} — {q.section} ·{" "}
                  {q.role === "status_evidence" ? t.statusEvidence : t.retrieved} ·{" "}
                  <a className="underline" href={q.source_url} target="_blank" rel="noreferrer">
                    {t.openSource}
                  </a>{" "}
                  · <code>{q.chunk_id}</code>
                </p>
              </li>
            ))}
          </ol>
        </>
      )}
      <p className="mt-3 text-xs text-stone-500">{a.disclaimer}</p>
    </article>
  );
}

export default function App() {
  const [lang, setLang] = useState<Lang>("en");
  const [jurisdiction, setJurisdiction] = useState<string>("IN");
  const [asOf, setAsOf] = useState<string>(new Date().toISOString().slice(0, 10));
  const [question, setQuestion] = useState<string>("");
  const [asked, setAsked] = useState<string>("");
  const [current, setCurrent] = useState<Answer | null>(null);
  const [previous, setPrevious] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<string>("checking…");
  const currentRef = useRef<Answer | null>(null);
  const t = STRINGS[lang];

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((b) => setHealth(`${b.status} · ${b.mode}`))
      .catch(() => setHealth("offline"));
  }, []);

  const ask = useCallback(async (q: string, j: string, d: string) => {
    setBusy(true);
    try {
      const r = await fetch("/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: q, jurisdiction: j, as_of: d }),
      });
      const body = (await r.json()) as Answer;
      // Keep the previous answer on screen so a switch change shows its effect (S6 rule 2).
      setPrevious(currentRef.current);
      currentRef.current = body;
      setCurrent(body);
    } finally {
      setBusy(false);
    }
  }, []);

  // Changing a switch re-answers the last question.
  useEffect(() => {
    if (asked) void ask(asked, jurisdiction, asOf);
  }, [asked, jurisdiction, asOf, ask]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (q.length < 3) return;
    if (q === asked) void ask(q, jurisdiction, asOf);
    else setAsked(q);
  }

  return (
    <main className="min-h-screen bg-stone-50 text-stone-900" lang={lang}>
      <header className="border-b border-stone-200 bg-white px-6 py-4">
        <h1 className="text-xl font-semibold">IP-SAKTI Sahayak</h1>
        <p className="text-sm text-stone-600">{t.tagline}</p>
        <div className="mt-4 flex flex-wrap gap-6" aria-label="The Two Switches">
          <label className="flex flex-col text-sm">
            {t.jurisdiction}
            <select
              data-testid="jurisdiction"
              className="mt-1 rounded border border-stone-300 px-2 py-1"
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
            >
              {JURISDICTIONS.map((j) => (
                <option key={j}>{j}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-sm">
            {t.asOf}
            <input
              data-testid="as-of"
              type="date"
              className="mt-1 rounded border border-stone-300 px-2 py-1"
              value={asOf}
              onChange={(e) => e.target.value && setAsOf(e.target.value)}
            />
          </label>
          <label className="flex flex-col text-sm">
            {t.language}
            <select
              className="mt-1 rounded border border-stone-300 px-2 py-1"
              value={lang}
              onChange={(e) => setLang(e.target.value as Lang)}
            >
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
              <option value="gu">ગુજરાતી</option>
            </select>
          </label>
        </div>
      </header>
      <section className="mx-auto max-w-4xl px-6 py-6">
        <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-1 flex-col text-sm">
            {t.question}
            <input
              data-testid="question"
              className="mt-1 rounded border border-stone-300 px-3 py-2"
              value={question}
              placeholder={t.placeholder}
              onChange={(e) => setQuestion(e.target.value)}
            />
          </label>
          <button
            data-testid="ask"
            type="submit"
            className="rounded bg-stone-900 px-4 py-2 text-sm text-white focus:outline-2 focus:outline-offset-2 disabled:opacity-50"
            disabled={busy}
          >
            {busy ? t.asking : t.ask}
          </button>
        </form>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {current && (
            <div>
              <AnswerCard a={current} t={t} testId="answer" />
            </div>
          )}
          {previous && (
            <div className="opacity-75">
              <h2 className="mb-1 text-xs font-semibold uppercase text-stone-500">{t.previous}</h2>
              <AnswerCard a={previous} t={t} testId="previous-answer" />
            </div>
          )}
        </div>
        <AbsPanel asOf={asOf} t={t} />
        <p className="mt-6 text-xs text-stone-500">
          {t.disclaimer} · API: {health}
          {current && <> · corpus {current.corpus_version.slice(0, 19)}…</>}
        </p>
      </section>
    </main>
  );
}
