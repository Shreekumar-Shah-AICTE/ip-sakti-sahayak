import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AbsPanel } from "./AbsPanel";
import { PassportPanel } from "./PassportPanel";
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

type Synthesis = {
  provider: string;
  model: string;
  accepted: boolean;
  text: string | null;
  reason: string;
  source: string;
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
  synthesis?: Synthesis | null;
};

// An accepted synthesis is shown above the quotes it organises; every [n] links to quote n.
// The model may only re-phrase quoted, cited text (S3 rule 8) — the quotes stay the authority.
function SynthesisCard({ s, t, testId }: { s: Synthesis; t: Record<string, string>; testId: string }) {
  if (!s.accepted || !s.text) {
    return (
      <p data-testid="synthesis-withheld" className="mt-3 text-xs text-stone-500">
        {t.synthWithheld}: {s.reason}
      </p>
    );
  }
  const parts = s.text.split(/(\[\d+\])/);
  return (
    <section data-testid="synthesis" className="mt-3 rounded border border-sky-200 bg-sky-50 px-3 py-2 text-sm">
      <p className="text-xs font-semibold text-sky-900">{t.synthLabel}</p>
      <p className="mt-1">
        {parts.map((part, i) => {
          const m = /^\[(\d+)\]$/.exec(part);
          return m ? (
            <a
              key={i}
              href={`#${testId}-q${m[1]}`}
              className="text-sky-800 underline"
              aria-label={`${t.synthCite} ${m[1]}`}
            >
              [{m[1]}]
            </a>
          ) : (
            <span key={i}>{part}</span>
          );
        })}
      </p>
      <p className="mt-1 text-xs text-stone-600">
        {s.provider} · {s.model} · {s.source}
      </p>
    </section>
  );
}

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
      {!a.abstain && a.synthesis && <SynthesisCard s={a.synthesis} t={t} testId={testId} />}
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
            {a.quotes.map((q, i) => (
              <li key={q.chunk_id} id={`${testId}-q${i + 1}`} className="text-sm">
                <span className="mr-1 text-xs font-semibold text-stone-500">[{i + 1}]</span>
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
      {(a.abstain || a.confidence === "low") && (
        <p data-testid="escalation" className="mt-3 text-sm text-stone-700">
          {t.escalation}
        </p>
      )}
      <p className="mt-3 text-xs text-stone-500">{a.disclaimer}</p>
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

function VoiceButton({ lang, t, onText }: { lang: Lang; t: Record<string, string>; onText: (s: string) => void }) {
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
      className="rounded border border-stone-400 bg-white px-3 py-2 text-sm text-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span aria-hidden="true">{listening ? "■" : "🎤"}</span>
    </button>
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
  const [warming, setWarming] = useState(false);
  const [health, setHealth] = useState<string>("checking…");
  const currentRef = useRef<Answer | null>(null);
  const t = STRINGS[lang];

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((b) =>
        setHealth(`${b.status} · ${b.mode}${b.retrieval ? ` · ${b.retrieval.mode}` : ""}`),
      )
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
              data-testid="language"
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
          <VoiceButton lang={lang} t={t} onText={setQuestion} />
          <button
            data-testid="ask"
            type="submit"
            className="rounded bg-stone-900 px-4 py-2 text-sm text-white focus:outline-2 focus:outline-offset-2 disabled:opacity-50"
            disabled={busy}
          >
            {warming ? t.warming : busy ? t.asking : t.ask}
          </button>
        </form>
        <div className="mt-6 grid gap-4 md:grid-cols-2" aria-live="polite" aria-busy={busy}>
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
        <PassportPanel asOf={asOf} t={t} />
        <p className="mt-6 text-xs text-stone-500">
          {t.disclaimer} · API: {health}
          {current && <> · corpus {current.corpus_version.slice(0, 19)}…</>}
        </p>
      </section>
    </main>
  );
}
