// Plain-language layer for lay users (S6). These strings explain *words and screens*; they
// never state law on their own. Every legal fact on screen still comes from a cited quote or
// The Status Ledger. Dates below repeat the ledger's four segments (PITCH_DEFENCE §3).

export type TermKey =
  | "jurisdiction" | "asOf" | "rule170" | "in_force" | "omitted" | "stay" | "subJudice"
  | "vacated" | "gazette" | "dmr" | "ayush" | "asu" | "classical" | "proprietary"
  | "phytopharma" | "abs" | "passport" | "rag" | "staticRag" | "abstain" | "citation"
  | "verbatim" | "confidence" | "ledger" | "library" | "ip" | "patent" | "tkdl" | "keyless"
  | "synthesis" | "chunk" | "overlay";

export const GLOSSARY: Record<TermKey, { term: string; plain: string }> = {
  jurisdiction: { term: "Jurisdiction", plain: "Whose law you are asking about. IN = India, US = United States, EU = European Union, WIPO-track = the global treaty process of the World Intellectual Property Organization." },
  asOf: { term: "As-of date", plain: "The date your question is about. Laws change, so the app answers with the law that applied on that date — not just today's law." },
  rule170: { term: "Rule 170", plain: "A rule in India's Drugs Rules, 1945 that controlled advertisements of Ayurveda, Siddha and Unani medicines. Its legal status changed several times in 2024–2025 — pick different dates to see each one." },
  in_force: { term: "In force", plain: "The rule applies on that date. You must follow it." },
  omitted: { term: "Omitted", plain: "The government deleted the rule from the law book through an official notification. It no longer applies." },
  stay: { term: "Stay", plain: "A court order that temporarily pauses something. Here the Supreme Court paused the deletion of Rule 170, so the rule kept applying." },
  subJudice: { term: "Sub judice", plain: "Latin for “under judgment”: a court case about the matter is still pending." },
  vacated: { term: "Stay vacated", plain: "The court cancelled its own earlier pause order, so the deletion took effect again." },
  gazette: { term: "Gazette / G.S.R.", plain: "The Gazette of India is the government's official publication where rule changes are printed. A G.S.R. number identifies one such notification." },
  dmr: { term: "DMR Act, 1954", plain: "The Drugs and Magic Remedies (Objectionable Advertisements) Act — a separate law that bans advertising medicines as a cure or treatment for the diseases on its list. Diabetes is on that list." },
  ayush: { term: "AYUSH", plain: "Ayurveda, Yoga & Naturopathy, Unani, Siddha, Sowa-Rigpa and Homoeopathy — India's traditional medicine systems, and the Ministry that oversees them." },
  asu: { term: "ASU drug", plain: "An Ayurvedic, Siddha or Unani medicine — the drug families with their own chapter in India's drug law." },
  classical: { term: "Classical formulation", plain: "A medicine made as described in one of the authoritative classical Ayurveda texts that the law lists in its First Schedule." },
  proprietary: { term: "Patent or proprietary medicine", plain: "A company's own new formula that uses only ingredients found in the classical texts, but is not itself one of the classical recipes." },
  phytopharma: { term: "Phytopharmaceutical", plain: "A drug made from a purified, standardised plant extract, regulated closer to a modern medicine." },
  abs: { term: "ABS (Access & Benefit Sharing)", plain: "If a company commercially uses India's biological resources (for example medicinal plants), it must share part of its earnings so the communities who conserved them benefit. The 2025 Regulations set the percentages." },
  passport: { term: "Compliance passport", plain: "A one-page checklist of the rules that apply to your product type on your chosen date, each with its legal source. You can print it." },
  rag: { term: "RAG", plain: "Retrieval-Augmented Generation: the app first searches a library of real legal documents, then answers only from what it found." },
  staticRag: { term: "Static RAG", plain: "An ordinary search-then-answer assistant that ignores dates. It shows the same passage whatever date you pick — and never admits it doesn't know." },
  abstain: { term: "Abstain", plain: "When the app has no trustworthy source, it refuses to answer instead of guessing. This is deliberate — a wrong legal answer is worse than none." },
  citation: { term: "Citation", plain: "Where a quote comes from — document, section and a link — so anyone can check it." },
  verbatim: { term: "Verbatim", plain: "Word-for-word, copied exactly from the official source. Nothing is paraphrased." },
  confidence: { term: "Confidence", plain: "How closely the found sources match your question: high, medium or low. Low means: check with an expert." },
  ledger: { term: "The Status Ledger", plain: "A dated timeline of a rule's legal status. Every entry points to a gazette notification or a court order." },
  library: { term: "The Library", plain: "The collection of official legal documents (Acts, Rules, gazettes, court orders, guidelines) that the app searches." },
  ip: { term: "IP (Intellectual Property)", plain: "Legal ownership of ideas and knowledge — patents, trademarks, and protection of traditional knowledge." },
  patent: { term: "Patent", plain: "A government-granted right that stops others from copying an invention. India's Patents Act says traditional knowledge itself is not an invention." },
  tkdl: { term: "TKDL", plain: "Traditional Knowledge Digital Library — a government database of traditional formulations used by patent offices to reject copycat patents. This app only points to it; it does not search it." },
  keyless: { term: "Keyless / offline mode", plain: "The app runs fully on this laptop with no internet and no AI service. Answers are exact quotes, not AI-written text." },
  synthesis: { term: "AI summary", plain: "An optional AI-written summary of the quotes (only when an AI key is set). It is shown only if every sentence is backed by a quote — otherwise it is withheld." },
  chunk: { term: "Passage ID", plain: "A short piece of a source document. The ID shows exactly which passage was quoted." },
  overlay: { term: "Always-applies law", plain: "A second law that applies whatever the main rule's status is — here the DMR Act's ban on advertising cures for listed diseases." },
};

// What each ledger status means, in one sentence a newcomer can repeat to a judge.
export const PLAIN_STATUS: Record<string, string> = {
  in_force: "On this date the rule was part of the law and applied.",
  omitted: "On this date the rule had been deleted by a government notification, so it did not apply.",
  in_force_stayed_omission: "The government had deleted the rule, but the Supreme Court paused that deletion — so on this date the rule still applied while the case was pending.",
  omitted_stay_vacated: "The Supreme Court closed the case and cancelled its pause, so on this date the rule stays deleted.",
};

export const STATUS_TONE: Record<string, "green" | "red" | "amber"> = {
  in_force: "green",
  omitted: "red",
  in_force_stayed_omission: "amber",
  omitted_stay_vacated: "red",
};

// Caption under each key-date chip (one per ledger segment).
export const DATE_CAPTIONS: Record<string, string> = {
  "2024-06-30": "rule applies",
  "2024-07-02": "rule deleted",
  "2024-08-28": "court pauses deletion",
  "2025-08-12": "court lifts pause",
};

export const CONFIDENCE_PLAIN: Record<string, string> = {
  high: "The sources match the question closely.",
  medium: "The sources are relevant but only partly match — read them carefully.",
  low: "Weak match — treat as a pointer and check with an expert.",
};

export type TourAction =
  | { kind: "ask"; q: string; date?: string; lang?: "en" | "hi" }
  | { kind: "date"; date: string }
  | { kind: "compare" }
  | { kind: "scroll"; target: string; date?: string };

export type TourStep = { title: string; action: TourAction; doLabel: string; see: string; say: string };

export const AD_Q = "Can I advertise this classical formulation as a treatment for diabetes?";

export const TOUR: TourStep[] = [
  {
    title: "Ask the real-world question",
    action: { kind: "ask", q: AD_Q, date: "2024-06-30" },
    doLabel: "Ask it for me (date 30 Jun 2024)",
    see: "A green “In force” status for Rule 170, a timeline, and exact quotes from the Drugs Rules with links.",
    say: "This is the question an Ayurveda manufacturer actually asks. Its answer changed four times in about fourteen months.",
  },
  {
    title: "Move the date: the rule is deleted",
    action: { kind: "date", date: "2024-07-02" },
    doLabel: "Set date to 2 Jul 2024",
    see: "The status turns red: “Omitted”. The earlier answer stays on the side so you can compare.",
    say: "Same question, different date, different law. The quote now comes from the government notification that deleted the rule.",
  },
  {
    title: "The Supreme Court pauses the deletion",
    action: { kind: "date", date: "2024-08-28" },
    doLabel: "Set date to 28 Aug 2024",
    see: "Amber status: “In force — omission stayed … (sub judice)”. The timeline highlights the third segment.",
    say: "A court case put the deletion on hold, so the rule applied again. An ordinary chatbot cannot know this.",
  },
  {
    title: "The Court lifts its pause",
    action: { kind: "date", date: "2025-08-12" },
    doLabel: "Set date to 12 Aug 2025",
    see: "Red again: “Omitted — Supreme Court stay vacated”, quoting the court order of 11 Aug 2025.",
    say: "Four dates, four legal statuses, each with its primary source. That is our core idea: an assistant that knows *when* the law is.",
  },
  {
    title: "Compare with an ordinary AI assistant",
    action: { kind: "compare" },
    doLabel: "Turn on “Compare with static RAG”",
    see: "A grey dashed card: the same library searched without dates. It shows one passage on every date.",
    say: "This is what a normal search-and-answer bot does — it gives the same answer whatever the date, and never says ‘I don't know’.",
  },
  {
    title: "The practical answer: still “no”",
    action: { kind: "scroll", target: "overlay-quote" },
    doLabel: "Show the always-applies law",
    see: "A purple quote from the DMR Act, 1954 including “9. Diabetes.”, marked “applies whatever the rule’s status”.",
    say: "So you cannot advertise it as a diabetes treatment on any of the four dates — for four different reasons, with four different citations.",
  },
  {
    title: "It refuses to guess",
    action: { kind: "ask", q: "What is the GST rate on ayurvedic churna?" },
    doLabel: "Ask an out-of-scope question",
    see: "A calm “No sourced answer” screen with next steps — no made-up number.",
    say: "Our library holds no tax law, so the app says so. We never invent law — abstaining is a feature.",
  },
  {
    title: "Ask in Hindi",
    action: { kind: "ask", q: "क्या मैं इस आयुर्वेदिक दवा का मधुमेह के इलाज के रूप में विज्ञापन कर सकता हूँ?", date: "2024-08-28", lang: "hi" },
    doLabel: "Ask the same question in Hindi",
    see: "The labels switch to Hindi and the answer reaches the same Rule 170 status. Legal quotes stay in their original words.",
    say: "Works in English, Hindi and Gujarati, fully offline. You can also speak the question with the 🎤 button.",
  },
  {
    title: "Benefit-sharing calculator",
    action: { kind: "scroll", target: "abs-panel", date: "2026-09-27" },
    doLabel: "Open the calculator (date 27 Sep 2026)",
    see: "Enter a turnover (e.g. 60 crore) and press Calculate: the applicable slab, the arithmetic, and the gazette lines behind it.",
    say: "If a company uses Indian medicinal plants, it must share benefits. We compute the slab from the 2025 Regulations and show the source line.",
  },
  {
    title: "Compliance passport",
    action: { kind: "scroll", target: "passport-panel" },
    doLabel: "Open the passport builder",
    see: "Pick a product type and press Compile: a printable checklist of rules, each with its status on your date and its source.",
    say: "One page a manufacturer can hand to their regulatory consultant — with every rule traceable to the law.",
  },
];
