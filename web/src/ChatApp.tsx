import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { STATUS_SHORT, STRINGS, type Lang } from "./i18n";
import {
  AnswerCard,
  VoiceButton,
  human,
  tone,
  type Answer,
  type Status,
} from "./App";
import { GlossaryDrawer } from "./Help";

// The Conversation (M4, run 14): one chat surface over every ability in the project.
// The backend router (api/chat) is deterministic; this file only renders what it returns,
// so the Two Switches, the Answer Contract and abstention all survive the move to chat.

type Cite = {
  regulation?: string;
  chunk_id: string;
  quote: string;
  source_url: string;
};
type Seg = {
  from: string;
  to: string | null;
  status: string;
  sub_judice: boolean;
  summary?: string;
  current?: boolean;
  evidence?: Cite[];
};
type Doc = {
  doc_id: string;
  title: string;
  jurisdiction: string;
  url: string;
  chunks: number;
};
type Flag = {
  id: string;
  span: [number, number];
  match: string;
  title: string;
  why: string;
  cites: Cite[];
};
type ClaimResult = {
  text: string;
  flags: Flag[];
  count: number;
  note: string;
  rule170?: { as_of: string; status: string; status_line: string };
};
type Slab = { id: string; label: string; rate_pct: string; citations: Cite[] };
type AbsResult = {
  as_of: string;
  abstain: boolean;
  reason?: string;
  turnover_inr?: number;
  high_value?: boolean;
  slab?: Slab;
  base_rule?: Cite;
  amount_inr?: string | null;
  uplift_citations?: Cite[];
  steps?: string[];
  obligations?: { id: string; obligation: string; citations: Cite[] }[];
  notes?: {
    text: string;
    human_judgment_required?: boolean;
    citations?: Cite[];
  }[];
  disclaimer?: string;
};
type PassportRule = {
  id: string;
  title: string;
  obligation: string;
  confidence: string;
  human_judgment_required: boolean;
  risk_indicator?: string | null;
  guiding_principle?: string | null;
  citations: Cite[];
};
type PassportResult = {
  category: string;
  title: string;
  as_of: string;
  covered_from?: string;
  abstain: boolean;
  reason?: string;
  definition?: Cite;
  classification?: {
    human_judgment_required: boolean;
    risk_indicator?: string;
    guiding_principle?: string;
  };
  rules?: PassportRule[];
  disclaimer?: string;
};

type Block =
  | { type: "answer"; answer: Answer }
  | {
      type: "diff";
      from: { as_of: string; status: string };
      to: { as_of: string; status: string };
    }
  | {
      type: "timeline";
      instrument: string;
      as_of: string;
      current_status?: string;
      segments: Seg[];
    }
  | { type: "abs"; result: AbsResult }
  | { type: "passport"; result: PassportResult }
  | { type: "claims"; result: ClaimResult }
  | { type: "compare"; question: string; ours: Answer; baseline: Cite[] }
  | { type: "library"; docs: Doc[] }
  | { type: "capabilities" }
  | {
      type: "knowledge";
      title: string | null;
      label: string;
      more?: string;
      provider?: string;
      source?: string;
    }
  | { type: "safety"; text: string };

type TraceStep = { tool: string; detail: string; ms: number };
type ChatReply = {
  intent: string;
  text: string;
  blocks: Block[];
  suggestions: string[];
  context: Record<string, string | null>;
  as_of: string;
  jurisdiction: string;
  trace: TraceStep[];
};

type Msg = {
  id: number;
  role: "user" | "assistant";
  text: string;
  blocks?: Block[];
  suggestions?: string[];
  trace?: TraceStep[];
  intent?: string;
  fresh?: boolean;
};

const CRORE = 10_000_000;
const SPEECH: Record<Lang, string> = { en: "en-IN", hi: "hi-IN", gu: "gu-IN" };

function reduceMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true
  );
}

function rupees(n: number): string {
  return "₹" + n.toLocaleString("en-IN");
}

// ---------------------------------------------------------------- mini markdown
// The router writes plain Markdown (bold, italics, code, links, lists). Rendering it here
// keeps the bot's voice readable without pulling a Markdown dependency into the bundle.
function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const rx = /\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\((\S+?)\)/g;
  let last = 0;
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = rx.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const k = key + "-" + i++;
    if (m[1] !== undefined)
      out.push(
        <strong key={k} className="font-semibold">
          {m[1]}
        </strong>,
      );
    else if (m[2] !== undefined) out.push(<em key={k}>{m[2]}</em>);
    else if (m[3] !== undefined)
      out.push(
        <code key={k} className="rounded bg-stone-200/70 px-1 text-[0.92em]">
          {m[3]}
        </code>,
      );
    else if (m[4] !== undefined)
      out.push(
        <a
          key={k}
          className="underline"
          href={m[5]}
          target="_blank"
          rel="noreferrer"
        >
          {m[4]}
        </a>,
      );
    last = rx.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Markdown({ text }: { text: string }) {
  const out: ReactNode[] = [];
  const lines = text.split("\n");
  let bullets: string[] = [];
  let numbers: string[] = [];
  let para: string[] = [];
  const flush = (at: number) => {
    if (para.length) {
      out.push(
        <p key={"p" + at} className="whitespace-pre-wrap">
          {inline(para.join("\n"), "p" + at)}
        </p>,
      );
      para = [];
    }
    if (bullets.length) {
      out.push(
        <ul key={"u" + at} className="ml-4 list-disc space-y-1">
          {bullets.map((b, i) => (
            <li key={i}>{inline(b, "u" + at + "-" + i)}</li>
          ))}
        </ul>,
      );
      bullets = [];
    }
    if (numbers.length) {
      out.push(
        <ol key={"o" + at} className="ml-4 list-decimal space-y-1">
          {numbers.map((b, i) => (
            <li key={i}>{inline(b, "o" + at + "-" + i)}</li>
          ))}
        </ol>,
      );
      numbers = [];
    }
  };
  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const bullet = /^\s*[-•*]\s+(.*)$/.exec(line);
    const number = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (bullet) {
      if (para.length || numbers.length) flush(idx);
      bullets.push(bullet[1]);
    } else if (number) {
      if (para.length || bullets.length) flush(idx);
      numbers.push(number[1]);
    } else if (!line.trim()) {
      flush(idx);
    } else {
      if (bullets.length || numbers.length) flush(idx);
      para.push(line);
    }
  });
  flush(lines.length);
  return <div className="space-y-2 leading-relaxed">{out}</div>;
}

// A short reveal makes the bot feel alive; it is capped so nothing is ever slow to read,
// and it is skipped entirely when the visitor asked for reduced motion.
function useReveal(text: string, animate: boolean): string {
  const [n, setN] = useState(animate ? 0 : text.length);
  useEffect(() => {
    if (!animate) {
      setN(text.length);
      return;
    }
    const frames = Math.min(40, Math.max(1, text.length));
    const per = Math.ceil(text.length / frames);
    let shown = 0;
    const id = window.setInterval(() => {
      shown += per;
      if (shown >= text.length) {
        setN(text.length);
        window.clearInterval(id);
      } else setN(shown);
    }, 600 / frames);
    return () => window.clearInterval(id);
  }, [text, animate]);
  return text.slice(0, n);
}

// ---------------------------------------------------------------- shared bits
function CiteList({ cs, label }: { cs: Cite[]; label?: string }) {
  if (!cs?.length) return null;
  return (
    <ul className="mt-1 space-y-1 text-xs text-stone-600">
      {label ? (
        <li className="font-semibold uppercase tracking-wide">{label}</li>
      ) : null}
      {cs.map((c, i) => (
        <li key={c.chunk_id + "-" + i}>
          {c.regulation ? c.regulation + ": " : ""}“{c.quote}” —{" "}
          <a
            className="underline"
            href={c.source_url}
            target="_blank"
            rel="noreferrer"
          >
            {c.chunk_id}
          </a>
        </li>
      ))}
    </ul>
  );
}

function Card({ children, tint }: { children: ReactNode; tint?: string }) {
  return (
    <div
      className={
        "fade-in rounded-2xl border p-4 " +
        (tint ?? "border-stone-200 bg-white")
      }
    >
      {children}
    </div>
  );
}

function CardTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-semibold text-stone-900">{children}</h3>;
}

// ---------------------------------------------------------------- block renderers
function DiffCard({
  b,
  t,
}: {
  b: Extract<Block, { type: "diff" }>;
  t: Record<string, string>;
}) {
  return (
    <Card tint="border-amber-300 bg-amber-50">
      <CardTitle>⚡ {t.chatDiff}</CardTitle>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {[b.from, b.to].map((side, i) => (
          <div
            key={i}
            className={
              "rounded-xl border p-3 text-sm " +
              (i === 1
                ? "border-amber-400 bg-white font-semibold"
                : "border-stone-200 bg-white/60")
            }
          >
            <p className="text-xs uppercase tracking-wide text-stone-500">
              {human(side.as_of)}
            </p>
            <p className={"mt-1 " + tone(side.status)}>
              {STATUS_SHORT[side.status] ?? side.status}
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function TimelineCard({
  b,
  t,
  onDate,
}: {
  b: Extract<Block, { type: "timeline" }>;
  t: Record<string, string>;
  onDate: (d: string) => void;
}) {
  return (
    <Card>
      <CardTitle>
        🕒 {b.instrument.replace(/_/g, " ")} — {t.timeline}
      </CardTitle>
      <ol className="mt-3 space-y-2">
        {b.segments.map((s, i) => (
          <li
            key={s.from + "-" + i}
            className={
              "rounded-xl border p-3 " +
              (s.current
                ? "border-indigo-400 bg-indigo-50"
                : "border-stone-200")
            }
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-semibold">
                {t.chatStep} {i + 1}: {human(s.from)} →{" "}
                {s.to ? human(s.to) : "—"}
              </p>
              <button
                type="button"
                onClick={() => onDate(s.from)}
                className="rounded-full border border-indigo-300 px-2 py-0.5 text-xs text-indigo-800 hover:bg-indigo-100"
              >
                {t.chatAskThisDate}
              </button>
            </div>
            <p className={"mt-1 text-sm " + tone(s.status)}>
              {STATUS_SHORT[s.status] ?? s.status}
              {s.sub_judice ? " · " + t.subJudice : ""}
            </p>
            {s.summary ? (
              <p className="mt-1 text-xs text-stone-600">{s.summary}</p>
            ) : null}
            <CiteList cs={s.evidence ?? []} />
          </li>
        ))}
      </ol>
    </Card>
  );
}

function ClaimsCard({
  b,
  t,
}: {
  b: Extract<Block, { type: "claims" }>;
  t: Record<string, string>;
}) {
  const r = b.result;
  // Highlight the flagged spans inside the advertiser's own words: the point is to show
  // *where* the risk sits, never to rewrite the copy for them.
  const parts: ReactNode[] = [];
  const sorted = [...r.flags].sort((a, b2) => a.span[0] - b2.span[0]);
  let at = 0;
  sorted.forEach((f, i) => {
    const s = f.span[0];
    const e = f.span[1];
    if (s < at) return;
    if (s > at) parts.push(r.text.slice(at, s));
    parts.push(
      <mark
        key={i}
        className="rounded bg-rose-200 px-0.5 font-semibold text-rose-950"
      >
        {r.text.slice(s, e)}
      </mark>,
    );
    at = e;
  });
  if (at < r.text.length) parts.push(r.text.slice(at));
  return (
    <Card
      tint={
        r.count
          ? "border-rose-300 bg-rose-50"
          : "border-emerald-300 bg-emerald-50"
      }
    >
      <CardTitle>
        🔍 {t.chatFlags} · {r.count}
      </CardTitle>
      <blockquote className="mt-2 rounded-xl border border-stone-200 bg-white p-3 text-sm leading-relaxed">
        {parts}
      </blockquote>
      {r.count ? (
        <ol className="mt-3 space-y-2" data-testid="claim-flags">
          {sorted.map((f, i) => (
            <li
              key={f.id + i}
              className="rounded-xl border border-stone-200 bg-white p-3"
            >
              <p className="text-sm font-semibold">{f.title}</p>
              <p className="mt-1 text-sm text-stone-700">{f.why}</p>
              <CiteList cs={f.cites} />
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm">{t.chatNoFlags}</p>
      )}
      {r.rule170 ? (
        <p className="mt-3 text-xs text-stone-600">
          Rule 170 as of {human(r.rule170.as_of)}:{" "}
          {STATUS_SHORT[r.rule170.status] ?? r.rule170.status}
        </p>
      ) : null}
      <p className="mt-2 text-xs text-stone-500">{r.note}</p>
    </Card>
  );
}

function AbsCard({
  b,
  t,
  asOf,
}: {
  b: Extract<Block, { type: "abs" }>;
  t: Record<string, string>;
  asOf: string;
}) {
  const [res, setRes] = useState<AbsResult>(b.result);
  const [crore, setCrore] = useState<string>(
    b.result.turnover_inr ? String(b.result.turnover_inr / CRORE) : "40",
  );
  const [busy, setBusy] = useState(false);
  useEffect(() => setRes(b.result), [b.result]);

  const recompute = useCallback(async () => {
    const n = Number(crore);
    if (!Number.isFinite(n) || n < 0) return;
    setBusy(true);
    try {
      const q = new URLSearchParams({
        turnover_inr: String(Math.round(n * CRORE)),
        as_of: asOf,
      });
      if (res.high_value) q.set("high_value", "true");
      const r = await fetch("/passport/abs?" + q.toString());
      setRes((await r.json()) as AbsResult);
    } finally {
      setBusy(false);
    }
  }, [crore, asOf, res.high_value]);

  return (
    <Card>
      <CardTitle>🧮 {t.absTitle}</CardTitle>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <label className="text-xs text-stone-600">
          {t.absTurnover}
          <input
            type="number"
            min="0"
            step="0.01"
            value={crore}
            onChange={(e) => setCrore(e.target.value)}
            data-testid="chat-abs-turnover"
            className="mt-1 block w-32 rounded-lg border border-stone-300 px-2 py-1 text-sm"
          />
        </label>
        <button
          type="button"
          onClick={recompute}
          disabled={busy}
          data-testid="chat-abs-compute"
          className="rounded-lg bg-indigo-700 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {t.absCompute}
        </button>
      </div>
      {res.abstain ? (
        <p className="mt-3 text-sm">{res.reason}</p>
      ) : (
        <div className="mt-3 space-y-2 text-sm" data-testid="chat-abs-result">
          <p>
            <span className="text-stone-600">{res.slab?.label}</span> ·{" "}
            <b>{res.slab?.rate_pct}%</b>
            {res.amount_inr ? " · " + rupees(Number(res.amount_inr)) : ""}
          </p>
          {res.steps?.length ? (
            <ol className="ml-4 list-decimal space-y-0.5 text-xs text-stone-700">
              {res.steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          ) : null}
          <CiteList cs={res.slab?.citations ?? []} />
          {res.obligations?.length ? (
            <ul className="mt-2 space-y-1">
              {res.obligations.map((o) => (
                <li
                  key={o.id}
                  className="rounded-lg border border-stone-200 p-2 text-xs"
                >
                  {o.obligation}
                  <CiteList cs={o.citations} />
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
      <p className="mt-3 text-xs text-stone-500">{res.disclaimer}</p>
    </Card>
  );
}

function PassportCard({
  b,
  t,
}: {
  b: Extract<Block, { type: "passport" }>;
  t: Record<string, string>;
}) {
  const p = b.result;
  return (
    <div data-print-root>
      <Card>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <CardTitle>🛂 {p.title}</CardTitle>
          <button
            type="button"
            onClick={() => window.print()}
            className="no-print rounded-full border border-stone-300 px-2 py-0.5 text-xs hover:bg-stone-100"
          >
            {t.passportPrint}
          </button>
        </div>
        <p className="mt-1 text-xs text-stone-600">
          {t.passportAsOf} {human(p.as_of)}
          {p.covered_from
            ? " · " + t.passportCovered + " " + human(p.covered_from)
            : ""}
        </p>
        {p.definition ? <CiteList cs={[p.definition]} /> : null}
        {p.abstain ? (
          <p className="mt-3 text-sm">{p.reason}</p>
        ) : (
          <ol className="mt-3 space-y-2" data-testid="chat-passport-rules">
            {(p.rules ?? []).map((r) => (
              <li key={r.id} className="rounded-xl border border-stone-200 p-3">
                <p className="text-sm font-semibold">{r.title}</p>
                <p className="mt-1 text-sm text-stone-700">{r.obligation}</p>
                {r.human_judgment_required ? (
                  <p className="mt-1 rounded-lg bg-amber-50 p-2 text-xs text-amber-900">
                    {t.absJudgment} {r.risk_indicator ?? ""}{" "}
                    {r.guiding_principle ?? ""}
                  </p>
                ) : null}
                <CiteList cs={r.citations} />
              </li>
            ))}
          </ol>
        )}
        <p className="mt-3 text-xs text-stone-500">{p.disclaimer}</p>
      </Card>
    </div>
  );
}

function CompareCard({
  b,
  t,
  id,
}: {
  b: Extract<Block, { type: "compare" }>;
  t: Record<string, string>;
  id: string;
}) {
  return (
    <div className="grid gap-3 lg:grid-cols-2" data-testid="chat-compare">
      <div className="rounded-2xl border-2 border-emerald-400 bg-emerald-50/60 p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-900">
          ✅ {t.chatOurs}
        </p>
        <div className="mt-2">
          <AnswerCard a={b.ours} t={t} testId={id + "-ours"} compact />
        </div>
      </div>
      <div className="rounded-2xl border-2 border-dashed border-stone-300 bg-stone-50 p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-stone-600">
          ⚠️ {t.chatBaseline}
        </p>
        <p className="mt-1 text-xs text-stone-600">{t.baselineNote}</p>
        {b.baseline.length ? (
          <ol className="mt-2 space-y-2">
            {b.baseline.map((q, i) => (
              <li
                key={q.chunk_id + "-" + i}
                className="rounded-xl border border-stone-200 bg-white p-2 text-xs"
              >
                “{q.quote}” —{" "}
                <a
                  className="underline"
                  href={q.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {q.chunk_id}
                </a>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-2 text-sm">{t.baselineEmpty}</p>
        )}
      </div>
    </div>
  );
}

function LibraryCard({ b }: { b: Extract<Block, { type: "library" }> }) {
  return (
    <Card>
      <CardTitle>📚 The Library — {b.docs.length} documents</CardTitle>
      <ul className="mt-2 grid gap-1 sm:grid-cols-2">
        {b.docs.map((d) => (
          <li key={d.doc_id} className="text-xs text-stone-700">
            <span className="rounded bg-stone-200 px-1 font-mono">
              {d.jurisdiction}
            </span>{" "}
            <a
              className="underline"
              href={d.url}
              target="_blank"
              rel="noreferrer"
            >
              {d.title}
            </a>{" "}
            <span className="text-stone-500">· {d.chunks}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const ABILITIES: { icon: string; label: string; send: string }[] = [
  {
    icon: "⚖️",
    label: "Is a law in force on a date?",
    send: "Is Rule 170 in force?",
  },
  { icon: "🔍", label: "Check ad copy for risky claims", send: "/check" },
  { icon: "🧮", label: "ABS benefit share", send: "/abs" },
  { icon: "🛂", label: "Licence passport", send: "/passport" },
  { icon: "🕒", label: "Timeline of an instrument", send: "/timeline" },
  { icon: "🆚", label: "Compare with an ordinary chatbot", send: "/compare" },
  { icon: "📚", label: "What is in The Library?", send: "/library" },
  {
    icon: "🌿",
    label: "Ayurveda, generally",
    send: "What are the three doshas?",
  },
];

function CapabilitiesCard({
  t,
  onSend,
}: {
  t: Record<string, string>;
  onSend: (s: string) => void;
}) {
  return (
    <Card>
      <CardTitle>✨ {t.chatTools}</CardTitle>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {ABILITIES.map((a) => (
          <button
            key={a.send}
            type="button"
            onClick={() => onSend(a.send)}
            className="rounded-xl border border-stone-200 p-2 text-left text-sm hover:border-indigo-300 hover:bg-indigo-50"
          >
            <span aria-hidden>{a.icon}</span> {a.label}
          </button>
        ))}
      </div>
    </Card>
  );
}

function KnowledgeCard({
  b,
  t,
}: {
  b: Extract<Block, { type: "knowledge" }>;
  t: Record<string, string>;
}) {
  return (
    <div
      className="fade-in rounded-2xl border border-emerald-200 bg-emerald-50/70 p-3"
      data-testid="chat-knowledge"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-emerald-900">
        🌿 {b.label ?? t.chatBg}
      </p>
      {b.title ? <p className="mt-1 text-sm font-semibold">{b.title}</p> : null}
      <p className="mt-1 text-xs text-stone-600">
        {b.provider ? b.provider : ""}
        {b.more ? (
          <>
            {b.provider ? " · " : ""}
            <a
              className="underline"
              href={b.more}
              target="_blank"
              rel="noreferrer"
            >
              {t.chatMore}
            </a>
          </>
        ) : null}
      </p>
    </div>
  );
}

function Blocks({
  blocks,
  t,
  lang,
  id,
  asOf,
  onSend,
  onDate,
}: {
  blocks: Block[];
  t: Record<string, string>;
  lang: Lang;
  id: string;
  asOf: string;
  onSend: (s: string) => void;
  onDate: (d: string) => void;
}) {
  return (
    <div className="mt-3 space-y-3">
      {blocks.map((b, i) => {
        switch (b.type) {
          case "answer":
            return (
              <AnswerCard
                key={i}
                a={b.answer}
                t={t}
                testId={id + "-a" + i}
                lang={lang}
              />
            );
          case "diff":
            return <DiffCard key={i} b={b} t={t} />;
          case "timeline":
            return <TimelineCard key={i} b={b} t={t} onDate={onDate} />;
          case "claims":
            return <ClaimsCard key={i} b={b} t={t} />;
          case "abs":
            return <AbsCard key={i} b={b} t={t} asOf={asOf} />;
          case "passport":
            return <PassportCard key={i} b={b} t={t} />;
          case "compare":
            return <CompareCard key={i} b={b} t={t} id={id + "-c" + i} />;
          case "library":
            return <LibraryCard key={i} b={b} />;
          case "capabilities":
            return <CapabilitiesCard key={i} t={t} onSend={onSend} />;
          case "knowledge":
            return <KnowledgeCard key={i} b={b} t={t} />;
          case "safety":
            return (
              <div
                key={i}
                className="rounded-2xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"
              >
                ⚠️ {b.text}
              </div>
            );
          default:
            return null;
        }
      })}
    </div>
  );
}

function TraceView({
  trace,
  t,
}: {
  trace: TraceStep[];
  t: Record<string, string>;
}) {
  if (!trace?.length) return null;
  return (
    <details className="mt-3 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2">
      <summary className="cursor-pointer text-xs font-semibold text-stone-700">
        🔧 {t.chatTrace}
      </summary>
      <ol className="mt-2 space-y-1 text-xs text-stone-600">
        {trace.map((s, i) => (
          <li key={i}>
            <span className="font-semibold">{s.tool}</span> — {s.detail}{" "}
            <span className="text-stone-400">{s.ms.toFixed(0)} ms</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

// ---------------------------------------------------------------- one message
function Bubble({
  m,
  t,
  lang,
  asOf,
  onSend,
  onDate,
}: {
  m: Msg;
  t: Record<string, string>;
  lang: Lang;
  asOf: string;
  onSend: (s: string) => void;
  onDate: (d: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [reading, setReading] = useState(false);
  const animate = Boolean(m.fresh) && !reduceMotion();
  const shown = useReveal(m.text, animate);

  if (m.role === "user") {
    return (
      <div className="flex justify-end" data-testid="chat-msg-user">
        <div className="pop max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-700 px-4 py-2.5 text-white">
          <p className="whitespace-pre-wrap">{m.text}</p>
        </div>
      </div>
    );
  }

  const speak = () => {
    const s = window.speechSynthesis;
    if (!s) return;
    if (reading) {
      s.cancel();
      setReading(false);
      return;
    }
    const u = new SpeechSynthesisUtterance(m.text);
    u.lang = SPEECH[lang];
    u.onend = () => setReading(false);
    setReading(true);
    s.speak(u);
  };

  return (
    <div className="flex gap-2" data-testid="chat-msg-assistant">
      <div
        aria-hidden
        className="mt-1 hidden h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-700 to-emerald-600 text-sm text-white sm:flex"
      >
        स
      </div>
      <div className="min-w-0 flex-1">
        <div className="fade-in rounded-2xl rounded-bl-sm border border-stone-200 bg-white px-4 py-3 text-stone-900 shadow-sm">
          <Markdown text={shown} />
          {m.blocks?.length ? (
            <Blocks
              blocks={m.blocks}
              t={t}
              lang={lang}
              id={"m" + m.id}
              asOf={asOf}
              onSend={onSend}
              onDate={onDate}
            />
          ) : null}
          <TraceView trace={m.trace ?? []} t={t} />
          <div className="no-print mt-2 flex gap-2 text-xs text-stone-500">
            <button
              type="button"
              className="hover:text-stone-900 hover:underline"
              onClick={() => {
                void navigator.clipboard?.writeText(m.text);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? t.chatCopied : t.chatCopy}
            </button>
            <button
              type="button"
              className="hover:text-stone-900 hover:underline"
              onClick={speak}
            >
              🔊 {reading ? t.chatStop : t.chatRead}
            </button>
          </div>
        </div>
        {m.suggestions?.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {m.suggestions.map((s) => (
              <button
                key={s}
                type="button"
                data-testid="chat-suggestion"
                onClick={() => onSend(s)}
                className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs text-indigo-900 hover:bg-indigo-100"
              >
                {s}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- autopilot
type Step = { narration: string; message: string; date?: string; lang?: Lang };
const AUTOPILOT: Step[] = [
  {
    narration:
      "Rule 170 banned advertising ayurvedic drugs for named diseases. Watch the answer, then watch the date change it.",
    message: "Can I advertise an ayurvedic medicine for diabetes?",
    date: "2024-06-30",
  },
  {
    narration: "Two days later the Ministry asked states to stop acting on it.",
    message: "What about 2 Jul 2024?",
  },
  {
    narration:
      "Then the Supreme Court stayed that omission — the rule is back.",
    message: "28 Aug 2024",
  },
  {
    narration: "A year on, the position has moved again.",
    message: "12 Aug 2025",
  },
  {
    narration:
      "Here is what an ordinary RAG chatbot says to the same question — no date, no ledger.",
    message: "compare",
  },
  {
    narration: "The whole life of the rule, in one strip.",
    message: "Show the timeline of Rule 170",
  },
  {
    narration:
      "Now the advertiser's side: paste real ad copy and get risk indicators with the law quoted.",
    message:
      'check this claim: "Cures diabetes 100% guaranteed, no side effects, miracle ayurvedic remedy"',
  },
  {
    narration: "Sahayak also computes. Ask for the ABS benefit share.",
    message: "Calculate my ABS benefit share",
  },
  {
    narration: "It asked for turnover. Answer it in plain words.",
    message: "₹40 crore",
  },
  {
    narration:
      "A licence passport for a classical formulation, compiled as of the date on the switch.",
    message: "Do I need a licence for a classical formulation?",
  },
  {
    narration: "And when the sources do not say, abstention is the feature.",
    message: "What is the GST rate on churna?",
  },
  {
    narration: "The same ledger, asked in Hindi.",
    message: "क्या नियम 170 लागू है?",
    lang: "hi",
  },
  {
    narration:
      "Finally, ordinary Ayurveda conversation — clearly marked as background.",
    message: "What are the three doshas?",
    lang: "en",
  },
];

const SLASH: { cmd: string; hint: string; send: string }[] = [
  {
    cmd: "/abs",
    hint: "ABS benefit share calculator",
    send: "Calculate my ABS benefit share",
  },
  {
    cmd: "/passport",
    hint: "Licence passport by category",
    send: "Do I need a licence passport?",
  },
  {
    cmd: "/check",
    hint: "Check ad copy for risky claims",
    send: "Check this claim: ",
  },
  {
    cmd: "/timeline",
    hint: "Timeline of an instrument",
    send: "Show the timeline of Rule 170",
  },
  {
    cmd: "/compare",
    hint: "Compare with an ordinary RAG chatbot",
    send: "compare",
  },
  {
    cmd: "/library",
    hint: "What is in The Library",
    send: "What documents do you have?",
  },
  { cmd: "/help", hint: "Everything I can do", send: "help" },
];

// ---------------------------------------------------------------- the app
export default function ChatApp() {
  const [lang, setLang] = useState<Lang>("en");
  const [jurisdiction, setJurisdiction] = useState("IN");
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [warming, setWarming] = useState(false);
  const [health, setHealth] = useState("checking…");
  const [sendsText, setSendsText] = useState(false);
  const [glossary, setGlossary] = useState(false);
  const [clock, setClock] = useState<Seg[]>([]);
  const [pilot, setPilot] = useState<number | null>(null);
  const ctxRef = useRef<Record<string, string | null>>({});
  const histRef = useRef<{ role: string; text: string }[]>([]);
  const idRef = useRef(1);
  const endRef = useRef<HTMLDivElement | null>(null);
  const lastRef = useRef<HTMLDivElement | null>(null);
  const boxRef = useRef<HTMLTextAreaElement | null>(null);
  const t = STRINGS[lang];

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((b) => {
        const llm =
          b.chat_llm && b.chat_llm !== "none" ? " · chat:" + b.chat_llm : "";
        setHealth(
          b.status +
            " · " +
            b.mode +
            (b.retrieval ? " · " + b.retrieval.mode : "") +
            llm,
        );
        setSendsText(b.mode === "adapters");
      })
      .catch(() => setHealth("offline"));
  }, []);

  const post = useCallback(
    async (
      message: string,
      over?: { as_of?: string; jurisdiction?: string; lang?: Lang },
    ) => {
      for (let attempt = 0; ; attempt++) {
        const r = await fetch("/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            message,
            jurisdiction: over?.jurisdiction ?? jurisdiction,
            as_of: over?.as_of ?? asOf,
            lang: over?.lang ?? lang,
            context: ctxRef.current,
            history: histRef.current.slice(-20),
          }),
        });
        // D-017: the retriever answers 503 + Retry-After while it settles.
        if (r.status !== 503 || attempt >= 30)
          return (await r.json()) as ChatReply;
        setWarming(true);
        await new Promise((res) =>
          setTimeout(res, Number(r.headers.get("retry-after") ?? "2") * 1000),
        );
      }
    },
    [jurisdiction, asOf, lang],
  );

  // The law clock is fetched once through the same router the chat uses, so the strip on
  // screen and the answers in the thread can never disagree.
  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const r = await fetch("/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            message: "Show the timeline of Rule 170",
            lang: "en",
          }),
        });
        if (!r.ok) return;
        const body = (await r.json()) as ChatReply;
        const tl = body.blocks.find(
          (b): b is Extract<Block, { type: "timeline" }> =>
            b.type === "timeline",
        );
        if (live && tl) setClock(tl.segments);
      } catch {
        /* the strip is decoration; the thread still works without it */
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const send = useCallback(
    async (
      raw: string,
      over?: { as_of?: string; jurisdiction?: string; lang?: Lang },
    ) => {
      const message = raw.trim();
      if (!message || busy) return;
      const slash = SLASH.find((s) => s.cmd === message.toLowerCase());
      const text = slash ? slash.send : message;
      if (slash && slash.send.endsWith(": ")) {
        setInput(slash.send);
        boxRef.current?.focus();
        return;
      }
      setInput("");
      setBusy(true);
      const uid = idRef.current++;
      setMessages((prev) => [
        ...prev.map((m) => ({ ...m, fresh: false })),
        { id: uid, role: "user", text },
      ]);
      try {
        const body = await post(text, over);
        ctxRef.current = body.context ?? {};
        histRef.current = [
          ...histRef.current,
          { role: "user", text },
          { role: "assistant", text: body.text },
        ].slice(-20);
        setAsOf(body.as_of);
        setJurisdiction(body.jurisdiction);
        setMessages((prev) => [
          ...prev,
          {
            id: idRef.current++,
            role: "assistant",
            text: body.text,
            blocks: body.blocks,
            suggestions: body.suggestions,
            trace: body.trace,
            intent: body.intent,
            fresh: true,
          },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: idRef.current++,
            role: "assistant",
            text: "I could not reach the server. Please try again.",
            fresh: true,
          },
        ]);
      } finally {
        setWarming(false);
        setBusy(false);
      }
    },
    [busy, post],
  );

  // Scroll to the *start* of the newest reply. Answers carry their quotes with them and can
  // be long; landing at the bottom would show a demo audience the footnotes, not the answer.
  useEffect(() => {
    const behavior = reduceMotion() ? "auto" : "smooth";
    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && lastRef.current) {
      lastRef.current.scrollIntoView({ behavior, block: "start" });
    } else {
      endRef.current?.scrollIntoView({ behavior, block: "end" });
    }
  }, [messages, busy]);

  const onDate = useCallback(
    (d: string) => {
      setAsOf(d);
      void send("What about " + human(d) + "?", { as_of: d });
    },
    [send],
  );

  const runStep = useCallback(
    (i: number) => {
      const s = AUTOPILOT[i];
      if (!s) return;
      if (s.lang) setLang(s.lang);
      if (s.date) setAsOf(s.date);
      setPilot(i);
      void send(s.message, { as_of: s.date, lang: s.lang });
    },
    [send],
  );

  const slashOpen = input.startsWith("/");
  const slashHits = useMemo(
    () =>
      slashOpen
        ? SLASH.filter((s) => s.cmd.startsWith(input.toLowerCase().trim()))
        : [],
    [slashOpen, input],
  );

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (slashHits.length === 1) void send(slashHits[0].cmd);
      else void send(input);
    }
  };

  const clockStatus = useMemo<Status | null>(() => {
    if (clock.length < 2) return null;
    return {
      instrument: "rule_170",
      status: "",
      sub_judice: false,
      summary: "",
      segment_from: asOf,
      segment_to: null,
      stale: false,
      last_verified: "",
      abstain: false,
      reason: "",
      timeline: clock.map((s) => ({
        from: s.from,
        to: s.to,
        status: s.status,
        sub_judice: s.sub_judice,
      })),
    } as unknown as Status;
  }, [clock, asOf]);

  return (
    <div className="flex min-h-screen flex-col bg-stone-100 text-stone-900">
      <header className="hero no-print relative text-white">
        <div className="relative mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
          <div className="mr-auto flex items-center gap-2">
            <span
              aria-hidden
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 text-lg backdrop-blur"
            >
              🌿
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-tight">
                {t.chatTitle}
              </h1>
              <p className="text-xs text-white/70">{t.chatSub}</p>
            </div>
          </div>

          <label className="text-xs text-white/80">
            {t.jurisdiction}
            <select
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
              data-testid="chat-jurisdiction"
              className="ml-1 rounded-lg border border-white/30 bg-white/15 px-2 py-1 text-sm text-white backdrop-blur"
            >
              {["IN", "US", "EU", "WIPO-track"].map((j) => (
                <option key={j} value={j} className="text-stone-900">
                  {j}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-white/80">
            {t.asOf}
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              data-testid="chat-as-of"
              className="ml-1 rounded-lg border border-white/30 bg-white/15 px-2 py-1 text-sm text-white backdrop-blur"
            />
          </label>
          <label className="text-xs text-white/80">
            {t.language}
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as Lang)}
              data-testid="chat-lang"
              className="ml-1 rounded-lg border border-white/30 bg-white/15 px-2 py-1 text-sm text-white backdrop-blur"
            >
              <option value="en" className="text-stone-900">
                English
              </option>
              <option value="hi" className="text-stone-900">
                हिंदी
              </option>
              <option value="gu" className="text-stone-900">
                ગુજરાતી
              </option>
            </select>
          </label>

          <button
            type="button"
            data-testid="chat-autopilot"
            onClick={() => (pilot === null ? runStep(0) : setPilot(null))}
            className="rounded-full bg-amber-300 px-3 py-1.5 text-sm font-semibold text-stone-900 hover:bg-amber-200"
          >
            {pilot === null
              ? "▶ " + t.chatAutopilot
              : "■ " + t.chatAutopilotStop}
          </button>
          <button
            type="button"
            onClick={() => setGlossary(true)}
            className="rounded-full border border-white/30 px-3 py-1.5 text-sm hover:bg-white/10"
          >
            {t.chatGlossary}
          </button>
          <a
            href="?view=classic"
            className="rounded-full border border-white/30 px-3 py-1.5 text-sm hover:bg-white/10"
          >
            {t.chatClassic}
          </a>
        </div>

        {clockStatus ? (
          <div
            className="relative mx-auto max-w-7xl px-4 pb-3"
            data-testid="law-clock"
          >
            <div className="rounded-2xl bg-white/10 p-3 backdrop-blur">
              <p className="text-xs font-semibold uppercase tracking-wide text-white/80">
                {t.chatLawClock}{" "}
                <span className="font-normal normal-case">
                  — {t.chatLawClockHint}
                </span>
              </p>
              <ol className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {clock.map((s, i) => {
                  const on = asOf >= s.from && (!s.to || asOf < s.to);
                  return (
                    <li key={s.from + "-" + i}>
                      <button
                        type="button"
                        onClick={() => onDate(s.from)}
                        className={
                          "w-full rounded-xl border px-2 py-1.5 text-left text-xs transition " +
                          (on
                            ? "border-amber-300 bg-amber-300/90 font-semibold text-stone-900"
                            : "border-white/25 bg-white/5 text-white/85 hover:bg-white/15")
                        }
                      >
                        <span className="block">{human(s.from)}</span>
                        <span className="block truncate opacity-80">
                          {STATUS_SHORT[s.status] ?? s.status}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>
        ) : null}
      </header>

      {pilot !== null ? (
        <div
          className="no-print border-b border-amber-300 bg-amber-100"
          data-testid="autopilot-bar"
        >
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-2 text-sm">
            <span className="rounded-full bg-amber-300 px-2 py-0.5 text-xs font-semibold">
              {t.chatStep} {pilot + 1}/{AUTOPILOT.length}
            </span>
            <p className="mr-auto min-w-0 flex-1 text-amber-950">
              {AUTOPILOT[pilot].narration}
            </p>
            <button
              type="button"
              data-testid="autopilot-next"
              disabled={busy || pilot >= AUTOPILOT.length - 1}
              onClick={() => runStep(pilot + 1)}
              className="rounded-full bg-stone-900 px-3 py-1 text-xs font-semibold text-white disabled:opacity-40"
            >
              {t.chatNext} →
            </button>
          </div>
        </div>
      ) : null}

      <main className="mx-auto flex w-full max-w-7xl flex-1 gap-4 px-4 py-4">
        <section className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 space-y-4" data-testid="chat-log">
            {messages.length === 0 ? (
              <div className="fade-in rounded-3xl border border-stone-200 bg-white p-6">
                <h2 className="text-xl font-semibold">{t.chatWelcome}</h2>
                <p className="mt-1 max-w-2xl text-sm text-stone-600">
                  {t.chatWelcomeSub}
                </p>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-stone-500">
                  {t.chatTry}
                </p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {ABILITIES.map((a) => (
                    <button
                      key={a.send}
                      type="button"
                      data-testid="chat-starter"
                      onClick={() => void send(a.send)}
                      className="rounded-2xl border border-stone-200 p-3 text-left text-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:bg-indigo-50"
                    >
                      <span aria-hidden className="text-lg">
                        {a.icon}
                      </span>
                      <span className="mt-1 block font-medium">{a.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, i) => (
                <div
                  key={m.id}
                  ref={i === messages.length - 1 ? lastRef : undefined}
                  className="scroll-mt-4"
                >
                  <Bubble
                    m={m}
                    t={t}
                    lang={lang}
                    asOf={asOf}
                    onSend={(s) => void send(s)}
                    onDate={onDate}
                  />
                </div>
              ))
            )}
            {busy ? (
              <div
                className="flex items-center gap-2 text-sm text-stone-500"
                data-testid="chat-busy"
              >
                <span className="pop h-2 w-2 rounded-full bg-indigo-600" />
                {warming ? t.warming : t.chatThinking}
              </div>
            ) : null}
            <div ref={endRef} />
          </div>

          <div className="no-print sticky bottom-0 mt-4 bg-stone-100 pt-2">
            {slashHits.length ? (
              <ul className="mb-2 overflow-hidden rounded-2xl border border-stone-200 bg-white text-sm shadow-lg">
                {slashHits.map((s) => (
                  <li key={s.cmd}>
                    <button
                      type="button"
                      onClick={() => void send(s.cmd)}
                      className="flex w-full items-baseline gap-2 px-3 py-2 text-left hover:bg-indigo-50"
                    >
                      <code className="font-mono font-semibold text-indigo-800">
                        {s.cmd}
                      </code>
                      <span className="text-xs text-stone-600">{s.hint}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="flex items-end gap-2 rounded-3xl border border-stone-300 bg-white p-2 shadow-sm focus-within:border-indigo-400">
              <textarea
                ref={boxRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                placeholder={t.chatPlaceholder}
                aria-label={t.question}
                data-testid="chat-input"
                className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none"
              />
              <VoiceButton lang={lang} t={t} onText={(s) => void send(s)} />
              <button
                type="button"
                data-testid="chat-send"
                disabled={busy || !input.trim()}
                onClick={() => void send(input)}
                className="rounded-2xl bg-indigo-700 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-800 disabled:opacity-40"
              >
                {t.chatSend}
              </button>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-3 px-2 text-xs text-stone-500">
              <span>{t.chatEnter}</span>
              <span className="ml-auto" data-testid="mode">
                {health}
              </span>
              <span>{sendsText ? t.privacyAdapters : t.privacyKeyless}</span>
              {messages.length ? (
                <button
                  type="button"
                  onClick={() => {
                    setMessages([]);
                    ctxRef.current = {};
                    histRef.current = [];
                    setPilot(null);
                  }}
                  className="hover:text-stone-900 hover:underline"
                >
                  {t.chatClear}
                </button>
              ) : null}
            </div>
            <p className="mt-1 px-2 text-xs text-stone-500">{t.disclaimer}</p>
          </div>
        </section>

        <aside className="no-print hidden w-72 shrink-0 space-y-3 xl:block">
          <div className="rounded-2xl border border-stone-200 bg-white p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              {t.chatTools}
            </p>
            <div className="mt-2 space-y-1.5">
              {ABILITIES.map((a) => (
                <button
                  key={a.send}
                  type="button"
                  onClick={() => void send(a.send)}
                  className="flex w-full gap-2 rounded-xl border border-stone-200 px-2 py-1.5 text-left text-xs hover:border-indigo-300 hover:bg-indigo-50"
                >
                  <span aria-hidden>{a.icon}</span>
                  <span>{a.label}</span>
                </button>
              ))}
            </div>
          </div>
        </aside>
      </main>

      {glossary ? <GlossaryDrawer onClose={() => setGlossary(false)} /> : null}
    </div>
  );
}
