import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AbsPanel } from "./AbsPanel";
import { PassportPanel } from "./PassportPanel";
import { DEMO_DATES, DEMO_QUESTIONS, type Lang, STATUS_LABELS, STATUS_SHORT, STRINGS } from "./i18n";
import { CONFIDENCE_PLAIN, DATE_CAPTIONS, PLAIN_STATUS, STATUS_TONE, type TourStep } from "./explain";
import { GlossaryDrawer, Term, TourCard } from "./Help";

// The Two Switches live above the fold (S6 rule 1) and are sent with every question.
const JURISDICTIONS = ["IN", "US", "EU", "WIPO-track"] as const;

export type Quote = {
  text: string;
  chunk_id: string;
  doc_title: string;
  section: string;
  source_url: string;
  retrieved_on: string;
  role: "status_evidence" | "retrieved" | "overlay";
};

export type Segment = { from: string; to: string | null; status: string; sub_judice: boolean };

export type Status = {
  instrument: string;
  status: string | null;
  sub_judice: boolean;
  summary: string;
  stale: boolean;
  last_verified?: string | null;
  abstain: boolean;
  reason: string;
  segment_from?: string | null;
  segment_to?: string | null;
  timeline?: Segment[];
};

export type BaselineQuote = {
  text: string;
  chunk_id: string;
  doc_title: string;
  section: string;
  source_url: string;
};

export type Baseline = { kind: string; uses_as_of: boolean; quotes: BaselineQuote[] };

export type Synthesis = {
  provider: string;
  model: string;
  accepted: boolean;
  text: string | null;
  reason: string;
  source: string;
};

export type Answer = {
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
  synthesis?: Synthesis | null;
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// "2024-08-28" -> "28 Aug 2024": readable for a lay audience, still unambiguous.
export function human(d: string | null | undefined): string {
  if (!d) return "today";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : d;
}

const JUR_NAME: Record<string, string> = {
  IN: "🇮🇳 India",
  US: "🇺🇸 United States",
  EU: "🇪🇺 European Union",
  "WIPO-track": "🌐 WIPO (global treaty)",
};

const TONE = {
  green: { box: "border-emerald-300 bg-emerald-50 text-emerald-950", dot: "bg-emerald-500", chip: "border-emerald-500 bg-emerald-100 text-emerald-950" },
  red: { box: "border-rose-300 bg-rose-50 text-rose-950", dot: "bg-rose-500", chip: "border-rose-500 bg-rose-100 text-rose-950" },
  amber: { box: "border-amber-300 bg-amber-50 text-amber-950", dot: "bg-amber-500", chip: "border-amber-500 bg-amber-100 text-amber-950" },
} as const;

export function tone(status: string | null | undefined) {
  return TONE[STATUS_TONE[status ?? ""] ?? "amber"];
}

// An accepted synthesis is shown above the quotes it organises; every [n] links to quote n.
// The model may only re-phrase quoted, cited text (S3 rule 8) — the quotes stay the authority.
function SynthesisCard({ s, t, testId }: { s: Synthesis; t: Record<string, string>; testId: string }) {
  if (!s.accepted || !s.text) {
    return (
      <p data-testid="synthesis-withheld" className="mt-3 text-xs text-slate-600">
        {t.synthWithheld}: {s.reason}
      </p>
    );
  }
  const parts = s.text.split(/(\[\d+\])/);
  return (
    <section data-testid="synthesis" className="mt-4 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm">
      <p className="text-xs font-semibold text-sky-900">✨ {t.synthLabel}</p>
      <p className="mt-1 leading-relaxed text-slate-900">
        {parts.map((part, i) => {
          const m = /^\[(\d+)\]$/.exec(part);
          return m ? (
            <a key={i} href={`#${testId}-q${m[1]}`} className="font-semibold text-sky-800 underline" aria-label={`${t.synthCite} ${m[1]}`}>
              [{m[1]}]
            </a>
          ) : (
            <span key={i}>{part}</span>
          );
        })}
      </p>
      <p className="mt-1 text-xs text-slate-600">
        {s.provider} · {s.model} · {s.source}
      </p>
    </section>
  );
}

const ROLE_KEY: Record<Quote["role"], string> = {
  status_evidence: "statusEvidence",
  overlay: "overlay",
  retrieved: "retrieved",
};

const ROLE_STYLE: Record<Quote["role"], string> = {
  status_evidence: "bg-amber-100 text-amber-900",
  overlay: "bg-violet-100 text-violet-900",
  retrieved: "bg-slate-100 text-slate-700",
};

// The Status Ledger, drawn (S6 rule 2): every segment the instrument has had, with the
// segment covering the as-of date highlighted. It makes "as of a date" visible at a glance.
export function TimelineStrip({ st, t }: { st: Status; t: Record<string, string> }) {
  const segs = st.timeline ?? [];
  if (segs.length < 2) return null;
  return (
    <div data-testid="timeline" className="mt-3">
      <p className="text-xs font-semibold uppercase tracking-wide opacity-80">
        {t.timeline} <span className="font-normal normal-case">— the highlighted box is the law on your date</span>
      </p>
      <ol className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {segs.map((sg, i) => {
          const active = sg.from === st.segment_from;
          const tn = tone(sg.status);
          return (
            <li
              key={sg.from}
              data-testid={active ? "timeline-active" : "timeline-segment"}
              aria-current={active ? "true" : undefined}
              className={`relative rounded-lg border-2 px-2 py-1.5 text-xs transition ${
                active ? `${tn.chip} font-semibold shadow-md ring-2 ring-offset-1 ring-indigo-400` : "border-slate-200 bg-white/80 text-slate-700"
              }`}
            >
              <span className="flex items-center gap-1">
                <span className={`inline-block h-2 w-2 rounded-full ${tn.dot}`} aria-hidden="true" />
                <span className="text-[10px] uppercase tracking-wide opacity-70">Step {i + 1}</span>
              </span>
              <span className="block">
                {human(sg.from)} → {sg.to ? human(sg.to) : "now"}
              </span>
              <span className="block">{STATUS_SHORT[sg.status] ?? sg.status}</span>
              {active && <span className="sr-only"> ({t.timelineNow})</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

// The static-RAG card (BENCH_SPEC §3): the same corpus without the as-of machinery, shown
// next to the real answer so the difference is the demo's argument, not a claim.
export function BaselineCard({ b, t }: { b: Baseline; t: Record<string, string> }) {
  return (
    <article data-testid="baseline" className="fade-in rounded-2xl border-2 border-dashed border-slate-300 bg-slate-100 p-4">
      <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">🤖 What an ordinary assistant says</p>
      <h2 className="mt-1 text-sm font-semibold text-slate-900">
        <Term k="staticRag">{t.baselineTitle}</Term>
      </h2>
      <p className="mt-1 text-xs text-slate-700">{t.baselineNote}</p>
      {b.quotes.length === 0 ? (
        <div className="mt-2">
          <p className="text-sm">{t.baselineEmpty}</p>
          <p className="mt-1 text-xs text-slate-600">{t.baselineEmptyWhy}</p>
        </div>
      ) : (
        <ol className="mt-3 space-y-3">
          {b.quotes.map((q) => (
            <li key={q.chunk_id} className="text-sm">
              <blockquote className="line-clamp-5 border-l-4 border-slate-300 pl-3 italic text-slate-700">“{q.text}”</blockquote>
              <p className="mt-1 text-xs text-slate-600">
                {q.doc_title} — {q.section}
              </p>
            </li>
          ))}
        </ol>
      )}
      <p className="mt-3 rounded-lg bg-white px-3 py-2 text-xs text-slate-700">
        ⚠️ Notice: no date, no status, no refusal. Change the date — this card will not change.
      </p>
    </article>
  );
}

// "In plain words": a newcomer's reading of the answer. It only re-states the ledger status
// label and the presence of the DMR overlay quote — it never adds a legal fact of its own.
function PlainWords({ a }: { a: Answer }) {
  const hasOverlay = a.quotes.some((q) => q.role === "overlay");
  const lines: string[] = [];
  if (a.abstain) {
    lines.push("The app could not find an official source that answers this, so it refuses to guess. That is on purpose.");
  } else {
    if (a.status && !a.status.abstain && a.status.status) {
      lines.push(PLAIN_STATUS[a.status.status] ?? a.status.summary);
    }
    if (hasOverlay) {
      lines.push("Separately, the DMR Act, 1954 bans advertising a medicine as a treatment for the diseases on its list — and Diabetes is on it. That applies on every date.");
    }
    lines.push(CONFIDENCE_PLAIN[a.confidence] ?? "");
    lines.push("Read the exact quotes below — they are the real authority, copied word-for-word.");
  }
  return (
    <div data-testid="plain" className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/60 px-4 py-3">
      <p className="text-xs font-bold uppercase tracking-wider text-indigo-800">💬 In plain words</p>
      <ul className="mt-1 space-y-1 text-sm leading-relaxed text-slate-800">
        {lines.filter(Boolean).map((l) => (
          <li key={l}>• {l}</li>
        ))}
      </ul>
    </div>
  );
}

export function AnswerCard({ a, t, testId, compact }: { a: Answer; t: Record<string, string>; testId: string; compact?: boolean }) {
  const tn = tone(a.status?.status);
  const sources = (
    <ol className="mt-2 space-y-3">
      {a.quotes.map((q, i) => (
        <li
          key={q.chunk_id}
          id={`${testId}-q${i + 1}`}
          data-testid={q.role === "overlay" && !compact ? "overlay-quote" : undefined}
          className={`rounded-xl border p-3 text-sm ${q.role === "overlay" ? "border-violet-200 bg-violet-50/50" : "border-slate-200 bg-slate-50/60"}`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">{i + 1}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${ROLE_STYLE[q.role]}`}>
              {t[ROLE_KEY[q.role]] ?? q.role}
            </span>
            {q.role === "overlay" && <Term k="overlay" />}
          </div>
          <blockquote className="mt-2 border-l-4 border-indigo-300 pl-3 font-serif italic leading-relaxed text-slate-800">“{q.text}”</blockquote>
          <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600">
            <span className="font-semibold text-slate-800">📄 {q.doc_title}</span>
            <span>— {q.section}</span>
            <a className="rounded-md bg-white px-2 py-0.5 font-semibold text-indigo-700 underline ring-1 ring-indigo-200 hover:bg-indigo-50" href={q.source_url} target="_blank" rel="noreferrer">
              {t.openSource} ↗
            </a>
            <code className="text-[10px] text-slate-500" title="Passage ID — exactly which passage was quoted">{q.chunk_id}</code>
          </p>
        </li>
      ))}
    </ol>
  );
  return (
    <article data-testid={testId} className={`fade-in rounded-2xl border border-slate-200 bg-white shadow-sm ${compact ? "p-4" : "p-5 shadow-lg shadow-indigo-100/60"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">{JUR_NAME[a.jurisdiction] ?? a.jurisdiction}</span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">📅 {human(a.as_of)} <span className="sr-only">{a.as_of}</span></span>
        <span className={`rounded-full px-2.5 py-1 font-semibold ${a.confidence === "high" ? "bg-emerald-100 text-emerald-900" : a.confidence === "medium" ? "bg-amber-100 text-amber-900" : "bg-rose-100 text-rose-900"}`}>
          <Term k="confidence">{t.confidence}: {a.confidence}</Term>
        </span>
      </div>
      {a.status && !a.status.abstain && (
        <div data-testid="status-line" className={`mt-3 rounded-xl border-2 px-4 py-3 text-sm ${tn.box}`}>
          <p className="text-[11px] font-bold uppercase tracking-wider opacity-80">
            <Term k="ledger">⚖️ {a.status.instrument}</Term> — {t.statusAsOf} {human(a.as_of)}
          </p>
          <p className={`mt-1 font-bold ${compact ? "text-base" : "text-xl"}`}>
            {STATUS_LABELS[a.status.status ?? ""] ?? a.status.status}
            {a.status.sub_judice && (
              <span className="font-semibold">
                {" "}({t.subJudice})<Term k="subJudice" />
              </span>
            )}
          </p>
          <span className="sr-only"> [{a.status.status}]</span>
          <p className="mt-1 font-normal opacity-90">{a.status.summary}</p>
          {!compact && <TimelineStrip st={a.status} t={t} />}
          {a.status.stale && (
            <p data-testid="stale" className="mt-1 font-normal text-red-800">
              {t.stale.replace("{date}", a.status.last_verified ?? "")}
            </p>
          )}
        </div>
      )}
      {!compact && <PlainWords a={a} />}
      {!a.abstain && a.synthesis && <SynthesisCard s={a.synthesis} t={t} testId={testId} />}
      {a.abstain ? (
        <div data-testid="abstain" className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm">
          <p className="text-base font-semibold text-slate-900">🛑 {t.abstainTitle}</p>
          <p className="mt-1 text-slate-700">{a.reason}</p>
          <p className="mt-2 text-slate-700">{t.abstainNext}</p>
          <p className="mt-2 text-xs text-slate-700">
            <Term k="abstain">Why refusing is a feature</Term>
          </p>
        </div>
      ) : compact ? (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-xs font-semibold text-slate-600">{t.sources} ({a.quotes.length})</summary>
          {sources}
        </details>
      ) : (
        <>
          <h3 className="mt-5 flex items-center text-sm font-bold text-slate-900">
            <Term k="verbatim">📜 {t.sources}</Term>
            <span className="ml-2 text-xs font-normal text-slate-500">exact words from the official documents</span>
          </h3>
          {sources}
        </>
      )}
      {(a.abstain || a.confidence === "low") && (
        <p data-testid="escalation" className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-slate-800">
          🧑‍⚖️ {t.escalation}
        </p>
      )}
      <p className="mt-3 text-xs text-slate-500">{a.disclaimer}</p>
    </article>
  );
}

// Voice input (S6 rule 5): the Web Speech API when the browser has it; the typed field is
// always present. Audio goes to the browser's own speech service, never to our API.
type Recognizer = {
  lang: string;
  interimResults: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};
const SPEECH_LANG: Record<Lang, string> = { en: "en-IN", hi: "hi-IN", gu: "gu-IN" };

function speechCtor(): (new () => Recognizer) | null {
  const w = window as unknown as Record<string, unknown>;
  return ((w.SpeechRecognition ?? w.webkitSpeechRecognition) as new () => Recognizer) ?? null;
}

export function VoiceButton({ lang, t, onText }: { lang: Lang; t: Record<string, string>; onText: (s: string) => void }) {
  const [listening, setListening] = useState(false);
  const rec = useRef<Recognizer | null>(null);
  const Ctor = speechCtor();
  const supported = Ctor !== null;
  function toggle() {
    if (!Ctor) return;
    if (listening) {
      rec.current?.stop();
      return;
    }
    const r = new Ctor();
    r.lang = SPEECH_LANG[lang];
    r.interimResults = false;
    r.onresult = (e) => {
      const said = Array.from(e.results).map((x) => x[0].transcript).join(" ").trim();
      if (said) onText(said);
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  }
  const label = !supported ? t.micUnsupported : listening ? t.micStop : t.mic;
  return (
    <button
      type="button"
      data-testid="mic"
      data-lang={SPEECH_LANG[lang]}
      onClick={toggle}
      disabled={!supported}
      aria-pressed={supported ? listening : undefined}
      aria-label={label}
      title={label}
      className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-lg text-slate-800 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span aria-hidden="true">{listening ? "■" : "🎤"}</span>
    </button>
  );
}

const SAMPLE_HINT: Record<string, string> = {
  "Diabetes advertisement": "📣 Can I advertise a classical Ayurveda medicine for diabetes?",
  "Rule 170 status": "⚖️ Is the Ayurveda advertising rule (Rule 170) in force?",
  "Out of scope (abstains)": "🛑 A tax question it should refuse",
};

export default function App() {
  const [lang, setLang] = useState<Lang>("en");
  const [jurisdiction, setJurisdiction] = useState<string>("IN");
  const [asOf, setAsOf] = useState<string>(new Date().toISOString().slice(0, 10));
  const [question, setQuestion] = useState<string>("");
  const [asked, setAsked] = useState<string>("");
  const [current, setCurrent] = useState<Answer | null>(null);
  const [previous, setPrevious] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [warming, setWarming] = useState(false);
  const [health, setHealth] = useState<string>("checking…");
  const [offline, setOffline] = useState<boolean | null>(null);
  // DPDP data minimisation (S7 rule 6): say plainly where the question goes, and change the
  // wording the moment an AI adapter is enabled.
  const [sendsText, setSendsText] = useState(false);
  const [compare, setCompare] = useState(false);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [glossary, setGlossary] = useState(false);
  const [tour, setTour] = useState<number | null>(null);
  const currentRef = useRef<Answer | null>(null);
  const t = STRINGS[lang];

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((b) => {
        setHealth(`${b.status} · ${b.mode}${b.retrieval ? ` · ${b.retrieval.mode}` : ""}`);
        setSendsText(b.mode === "adapters");
        setOffline(b.mode !== "adapters");
      })
      .catch(() => setHealth("offline"));
  }, []);

  const ask = useCallback(async (q: string, j: string, d: string) => {
    setBusy(true);
    try {
      let r: Response;
      // D-017: while the retriever settles the API answers 503 + Retry-After; wait and
      // retry rather than show an answer from a mode that is about to change.
      for (let attempt = 0; ; attempt++) {
        r = await fetch("/ask", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ question: q, jurisdiction: j, as_of: d }),
        });
        if (r.status !== 503 || attempt >= 30) break;
        setWarming(true);
        const wait = Number(r.headers.get("retry-after") ?? "2") * 1000;
        await new Promise((res) => setTimeout(res, wait));
      }
      setWarming(false);
      const body = (await r.json()) as Answer;
      // Keep the previous answer on screen so a switch change shows its effect (S6 rule 2).
      setPrevious(currentRef.current);
      currentRef.current = body;
      setCurrent(body);
    } finally {
      setBusy(false);
    }
  }, []);

  // The baseline is fetched only while the comparison is on, and only for the asked question.
  useEffect(() => {
    if (!compare || !asked) {
      setBaseline(null);
      return;
    }
    let live = true;
    void fetch("/baseline", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: asked, jurisdiction }),
    })
      .then((r) => r.json())
      .then((b: Baseline) => live && setBaseline(b))
      .catch(() => live && setBaseline(null));
    return () => {
      live = false;
    };
  }, [compare, asked, jurisdiction]);

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

  function scrollTo(target: string) {
    window.setTimeout(() => {
      const el = document.querySelector(`[data-testid="${target}"]`) ?? document.getElementById(target);
      el?.scrollIntoView({ behavior: "smooth", block: target === "results" ? "start" : "center" });
    }, 350);
  }

  // One guided-demo step: perform it, then bring the part of the screen it talks about into view.
  function runStep(s: TourStep) {
    const a = s.action;
    if (a.kind === "ask") {
      if (a.lang) setLang(a.lang);
      if (a.date) setAsOf(a.date);
      setJurisdiction("IN");
      setQuestion(a.q);
      setAsked(a.q);
      scrollTo("results");
    } else if (a.kind === "date") {
      setAsOf(a.date);
      scrollTo("results");
    } else if (a.kind === "compare") {
      setCompare(true);
      scrollTo("results");
    } else {
      if (lang !== "en") setLang("en");
      if (a.date) setAsOf(a.date);
      scrollTo(a.target);
    }
  }

  const changed =
    current && previous && current.status && previous.status && current.status.status !== previous.status.status
      ? { from: previous.status.status ?? "", to: current.status.status ?? "", d0: previous.as_of, d1: current.as_of }
      : null;
  const side = (compare && baseline) || previous;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900" lang={lang}>
      <header className="hero relative overflow-hidden text-white">
        <div className="relative mx-auto max-w-6xl px-6 pb-8 pt-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/15 text-2xl shadow-inner ring-1 ring-white/30" aria-hidden="true">🌿</span>
              <div>
                <h1 className="text-2xl font-extrabold tracking-tight">IP-SAKTI Sahayak</h1>
                <p className="text-xs text-emerald-100">{t.tagline}</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                data-testid="tour-open"
                onClick={() => setTour(0)}
                className="rounded-full bg-amber-400 px-4 py-2 text-sm font-bold text-slate-900 shadow-lg shadow-amber-500/30 hover:bg-amber-300"
              >
                🧭 Guided demo
              </button>
              <button
                type="button"
                data-testid="glossary-open"
                onClick={() => setGlossary(true)}
                className="rounded-full bg-white/15 px-4 py-2 text-sm font-semibold text-white ring-1 ring-white/30 hover:bg-white/25"
              >
                📖 Glossary
              </button>
              <label className="flex items-center gap-2 rounded-full bg-white/15 px-3 py-1.5 text-sm ring-1 ring-white/30">
                <span aria-hidden="true">🌐</span>
                <span className="sr-only">{t.language}</span>
                <select
                  data-testid="language"
                  aria-label={t.language}
                  className="bg-transparent font-semibold text-white [&>option]:text-slate-900"
                  value={lang}
                  onChange={(e) => setLang(e.target.value as Lang)}
                >
                  <option value="en">English</option>
                  <option value="hi">हिन्दी</option>
                  <option value="gu">ગુજરાતી</option>
                </select>
              </label>
            </div>
          </div>

          <div className="mt-6 max-w-3xl">
            <p className="inline-block rounded-full bg-white/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-widest text-emerald-50 ring-1 ring-white/25">
              Smart India Hackathon 2026 · SIH26045 · Ministry of Ayush
            </p>
            <p className="mt-3 text-3xl font-extrabold leading-tight sm:text-4xl">
              The Ayurveda law assistant that knows <span className="text-amber-300">when</span> the law is.
            </p>
            <p className="mt-2 text-base text-emerald-50">
              Ask about Ayurveda patents, advertising or licensing rules. Pick a date. Get the{" "}
              <b>exact words of the law that applied on that date</b>, with the official source — and an honest “I don't know” when no source exists.
            </p>
          </div>

          {/* The Two Switches (S6 rule 1): above the fold, never in a menu. */}
          <div className="mt-6 grid gap-3 rounded-2xl bg-white/10 p-4 ring-1 ring-white/25 backdrop-blur md:grid-cols-[auto_auto_1fr]" aria-label="The Two Switches">
            <div className="flex flex-col text-sm">
              <span className="flex items-center text-xs font-bold uppercase tracking-wider text-emerald-50">
                <label htmlFor="sw-jur">① {t.jurisdiction}</label>
                <Term k="jurisdiction" light />
              </span>
              <select
                id="sw-jur"
                data-testid="jurisdiction"
                className="mt-1 rounded-xl border-0 bg-white px-3 py-2 font-semibold text-slate-900 shadow"
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
              >
                {JURISDICTIONS.map((j) => (
                  <option key={j} value={j}>
                    {JUR_NAME[j]}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col text-sm">
              <span className="flex items-center text-xs font-bold uppercase tracking-wider text-emerald-50">
                <label htmlFor="sw-date">② {t.asOf}</label>
                <Term k="asOf" light />
              </span>
              <input
                id="sw-date"
                data-testid="as-of"
                type="date"
                className="mt-1 rounded-xl border-0 bg-white px-3 py-2 font-semibold text-slate-900 shadow"
                value={asOf}
                onChange={(e) => e.target.value && setAsOf(e.target.value)}
              />
            </div>
            <div className="flex flex-col text-sm">
              <span className="flex items-center text-xs font-bold uppercase tracking-wider text-emerald-50">
                {t.demoDates} — the four moments <Term k="rule170" light /> <span className="ml-1 normal-case tracking-normal">changed</span>
              </span>
              <div className="mt-1 flex flex-wrap gap-2">
                {DEMO_DATES.map((d) => (
                  <button
                    key={d}
                    type="button"
                    data-testid="demo-date"
                    aria-pressed={asOf === d}
                    onClick={() => setAsOf(d)}
                    className={`rounded-xl px-3 py-1.5 text-left text-xs shadow transition ${
                      asOf === d ? "bg-amber-300 font-bold text-slate-900 ring-2 ring-white" : "bg-white/90 text-slate-800 hover:bg-white"
                    }`}
                  >
                    <span className="block font-semibold">{d}</span>
                    <span className="block text-[10px] opacity-80">{DATE_CAPTIONS[d]}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-6">
        {!current && (
          <ol className="mb-5 grid gap-3 sm:grid-cols-3" aria-label="How to use this app">
            {[
              ["1", "Set the two switches", "Whose law (India, US, EU, WIPO) and which date. They sit at the top because they change the answer."],
              ["2", "Ask — or tap a sample", "Type any question in English, हिन्दी or ગુજરાતી, speak it with 🎤, or tap a sample question below."],
              ["3", "Read the evidence", "You get the legal status on your date, a plain-words summary, and the exact quotes with links. No source → it says so."],
            ].map(([n, h, p]) => (
              <li key={n} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="flex items-center gap-2 font-bold text-slate-900">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-emerald-600 text-sm text-white">{n}</span>
                  {h}
                </p>
                <p className="mt-1 text-sm text-slate-600">{p}</p>
              </li>
            ))}
          </ol>
        )}
        {!current && tour === null && (
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-sm text-amber-950">
              <b>New here?</b> The guided demo clicks through everything for you and tells you what to look at — about 2 minutes, 10 steps.
            </p>
            <button type="button" onClick={() => setTour(0)} className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">
              Start the guided demo →
            </button>
          </div>
        )}

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-[16rem] flex-1 flex-col text-sm font-semibold text-slate-800">
              ③ {t.question}
              <input
                data-testid="question"
                className="mt-1 rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-base font-normal shadow-inner focus:bg-white"
                value={question}
                placeholder={t.placeholder}
                onChange={(e) => setQuestion(e.target.value)}
              />
            </label>
            <VoiceButton lang={lang} t={t} onText={setQuestion} />
            <button
              data-testid="ask"
              type="submit"
              className="rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 px-6 py-3 text-base font-bold text-white shadow-lg shadow-indigo-200 hover:from-indigo-700 hover:to-emerald-700 disabled:opacity-60"
              disabled={busy}
            >
              {warming ? t.warming : busy ? t.asking : `${t.ask} →`}
            </button>
          </form>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs" data-testid="demo-bar">
            <span className="font-bold uppercase tracking-wider text-slate-500">{t.demo} · try:</span>
            {DEMO_QUESTIONS.map((d) => (
              <button
                key={d.q}
                type="button"
                data-testid="demo-question"
                title={d.q}
                onClick={() => {
                  setQuestion(d.q);
                  setAsked(d.q);
                }}
                className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 font-medium text-indigo-900 hover:bg-indigo-100"
              >
                {d.label}
                {SAMPLE_HINT[d.label] && <span className="sr-only"> — {SAMPLE_HINT[d.label]}</span>}
              </button>
            ))}
            <label className="ml-auto flex items-center gap-2 rounded-full border border-slate-300 bg-slate-50 px-3 py-1.5 font-semibold text-slate-800">
              <input type="checkbox" data-testid="compare" checked={compare} onChange={(e) => setCompare(e.target.checked)} className="h-4 w-4 accent-indigo-600" />
              {t.compare}
            </label>
            <Term k="staticRag" />
          </div>
        </div>

        <div id="results" className="mt-6 scroll-mt-4">
          {busy && !current && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
              <span className="mr-2 inline-block h-3 w-3 animate-ping rounded-full bg-indigo-500" />
              {warming ? t.warming : t.asking}
            </div>
          )}
          {changed && (
            <p data-testid="changed" className="fade-in mb-3 rounded-xl border border-indigo-200 bg-gradient-to-r from-indigo-50 to-emerald-50 px-4 py-2 text-sm text-slate-800">
              🔁 <b>The date changed the law.</b> {human(changed.d0)}: {STATUS_SHORT[changed.from] ?? changed.from} →{" "}
              {human(changed.d1)}: <b>{STATUS_SHORT[changed.to] ?? changed.to}</b>. Same question — only the date is different.
            </p>
          )}
          <div className={`grid gap-4 ${side ? "lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]" : ""}`} aria-live="polite" aria-busy={busy}>
            {current && (
              <div>
                <p className="mb-1 text-xs font-bold uppercase tracking-wider text-indigo-700">✅ IP-SAKTI answer</p>
                <AnswerCard a={current} t={t} testId="answer" />
              </div>
            )}
            {side && (
              <div className="space-y-4">
                {compare && baseline && <BaselineCard b={baseline} t={t} />}
                {previous && (
                  <div className="opacity-90">
                    <p className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-500">⏪ {t.previous} — for comparison</p>
                    <AnswerCard a={previous} t={t} testId="previous-answer" compact />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="mt-10">
          <h2 className="text-xl font-extrabold text-slate-900">🧰 Tools for Ayurveda businesses</h2>
          <p className="mt-1 text-sm text-slate-600">Both tools use the as-of date at the top, exactly like the question box.</p>
          <div className="mt-4 grid gap-5 lg:grid-cols-2">
            <div className="rounded-2xl border border-emerald-200 bg-white p-1 shadow-sm">
              <div className="rounded-t-xl bg-emerald-50 px-4 py-3">
                <p className="flex items-center font-bold text-emerald-950">
                  💰 Benefit-sharing calculator <Term k="abs" />
                </p>
                <p className="mt-1 text-sm text-slate-700">
                  Using Indian medicinal plants commercially? Enter your yearly turnover (in crore rupees) and press Calculate to see which slab of the 2025 Regulations applies — with the gazette lines behind it.
                </p>
              </div>
              <div className="px-3 pb-3">
                <AbsPanel asOf={asOf} t={t} />
              </div>
            </div>
            <div id="passport-panel" className="rounded-2xl border border-indigo-200 bg-white p-1 shadow-sm">
              <div className="rounded-t-xl bg-indigo-50 px-4 py-3">
                <p className="flex items-center font-bold text-indigo-950">
                  🛂 Compliance passport <Term k="passport" />
                </p>
                <p className="mt-1 text-sm text-slate-700">
                  Pick what kind of product you make — <Term k="classical">classical</Term>, <Term k="proprietary">proprietary</Term> or{" "}
                  <Term k="phytopharma">phytopharmaceutical</Term> — and press Compile for a printable checklist of the rules on your date.
                </p>
              </div>
              <div className="px-3 pb-3">
                <PassportPanel asOf={asOf} t={t} />
              </div>
            </div>
          </div>
        </div>

        <footer className="mt-10 grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 text-xs text-slate-600 shadow-sm md:grid-cols-[1fr_auto]">
          <div>
            <p data-testid="privacy" className="text-slate-700">
              🔒 {sendsText ? t.privacyAdapters : t.privacyKeyless}
            </p>
            <p className="mt-2">
              ⚖️ {t.disclaimer} Every legal statement comes from an official document in <Term k="library">The Library</Term>; if none applies, the app abstains.
            </p>
          </div>
          <div className="flex flex-col items-start gap-1 md:items-end">
            <span className={`rounded-full px-3 py-1 font-semibold ${offline ? "bg-emerald-100 text-emerald-900" : "bg-sky-100 text-sky-900"}`}>
              ● {offline === null ? "connecting…" : offline ? "Offline mode — no internet or AI key needed" : "AI adapters enabled"}
              {offline && <Term k="keyless" />}
            </span>
            <span className="text-slate-500">
              API: {health}
              {current && <> · corpus {current.corpus_version.slice(0, 19)}…</>}
            </span>
          </div>
        </footer>
      </section>

      {glossary && <GlossaryDrawer onClose={() => setGlossary(false)} />}
      {tour !== null && <TourCard step={tour} setStep={setTour} run={runStep} onClose={() => setTour(null)} />}
    </main>
  );
}
