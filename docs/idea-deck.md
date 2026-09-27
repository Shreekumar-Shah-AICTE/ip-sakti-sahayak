# IP-SAKTI Sahayak — SIH 2026 Idea Deck (SIH26045)

Six slides (the SIH cap). Slide text first, then speaker notes. Every factual claim carries an
evidence tag `[E#]` resolved in §7. Tense rule: **present tense only for what exists today**;
everything else is labelled *planned* with its milestone.

---

## Slide 1 — The failure: one question, three dates, three correct answers

**Title:** Ayurveda law moved three times in 2024. A static assistant answers as if it never did.

**Question:** *"Can I advertise this classical Ayurvedic formulation for a disease?"*

| As-of date | Status of Rule 170 (ASU drug advertisements) | Governing evidence |
|---|---|---|
| 30 Jun 2024 | In force | Drugs Rules, Rule 170 [E3] |
| 02 Jul 2024 | Omitted, w.e.f. 01 Jul 2024 | Notification G.S.R. 360(E) [E3] |
| 28 Aug 2024 | Omission **stayed** by the Supreme Court on 27 Aug 2024 — matter sub judice | W.P.(C) 645/2022 [E3] |

- A static retrieval system retrieved the date-applicable legal version **0%** of the time; a
  versioned, date-conditioned retriever reached **98.3%** [E8].
- Commercial legal AI tools hallucinate in **17–33%** of queries [E9].

**Line to say:** "A static system gives one answer to all three dates. At least two of them prove it wrong."

---

## Slide 2 — The solution: two switches and a Status Ledger

**Title:** IP-SAKTI Sahayak — an Ayurveda IP assistant that knows *when* the law is.

1. **The Two Switches** — *jurisdiction* (IN / US / EU / WIPO-track) and *as-of date* — sit above
   the fold and filter every retrieval before ranking.
2. **The Status Ledger** — a dated timeline per legal instrument; every entry must cite a gazette
   notification or court order. No entry → the system **abstains** and says which evidence is missing.
3. **The Answer Contract** — each statement carries a verbatim quote that must string-match its
   source chunk, the source link, retrieval date, and its status *on the date asked*.
4. **The Passport Compiler** — per-product compliance checklist (classical / proprietary /
   phytopharmaceutical) with an ABS benefit-share calculator that shows its arithmetic.

**Visual:** annotated screenshot of the two switches (current build: switches rendered, answering
*planned* for M2–M3). Label it "prototype" on the slide.

**Line to say:** "Abstention is a feature. When the ledger does not know, it says so."

---

## Slide 3 — Technical approach

**Title:** Filter first, then rank. Offline and keyless by default.

```
question ──► The Two Switches (jurisdiction, as-of) ──► filter chunk set
                                                          │
                     BM25 (sparse) ◄──────────────────────┤
                     multilingual MiniLM (dense) ◄────────┘
                               │  reciprocal rank fusion (k = 60)
                               ▼
            The Status Ledger: status of each instrument on the as-of date
                               ▼
      The Answer Contract: verbatim quote · citation · status-as-of · abstain?
                               ▼
        optional LLM re-phrasing over already-cited quotes (Gemini / Groq / Sarvam)
```

- **Stack:** Python FastAPI · bm25s + fastembed over a single numpy matrix (no vector database) ·
  YAML rules-as-code · hash-chained SQLite audit log storing query hashes, not text · React + Vite
  + TypeScript + Tailwind · en / hi / gu interface strings shipped in the bundle.
- **Keyless core:** the default answer path is extractive; LLM and translation services are optional
  adapters, so the demo survives with no network.
- **Built today:** API health service reporting keyless mode, web shell with the two switches,
  automated checks (lint, tests, evaluation gate, web build) on every commit.

---

## Slide 4 — Feasibility and evidence

**Title:** Measured on the hardware we build on — and measured against a baseline.

| Item | Value | Status |
|---|---|---|
| Build hardware | 2 vCPU, ~4 GB RAM, **no GPU** [E19] | measured |
| Embedding speed (multilingual MiniLM, CPU) | 13.9 chunks/s → ~10k chunks in ~12 min [E19] | measured |
| Corpus target | ≥40 full-text primary instruments (vs 23 summarised documents in the strongest public competitor repo) [E17] | *planned* M1 → M9 |
| Benchmark | ~100 questions in 7 sets: temporal traps, jurisdiction traps, citation faithfulness, abstention, category, ABS arithmetic, multilingual | *planned* M6 |
| Baseline | Vanilla RAG — same corpus, same embedder, no date filter, no ledger | *planned* M6 |
| Pass gates | temporal accuracy ≥30 points above baseline · citation exactness 100% · abstention 100% on out-of-corpus set | *planned* M6 |
| Cost | ₹0 — free tiers only; laptop-hosted, Docker for reproducibility | design |

- **Sub judice handling:** a pending case is a ledger state (`sub_judice: true`) shown in the answer
  body, not a footnote. When the Supreme Court rules, the ledger gains one dated entry — no code change.
- **Integrity:** benchmark questions written by teammates who do not write retriever code, committed
  as hashes before evaluation; results published with corpus hash, commit and date. *planned* M6.

---

## Slide 5 — Impact and beneficiaries

**Title:** For the people who carry the compliance risk.

- **Ayush manufacturers, especially MSMEs** — licensing category, advertising limits, ABS
  obligations and export regimes, each changing on its own clock.
- **ABS burden under the Biological Diversity (ABS) Regulations 2025**, which replaced the 2014
  Guidelines: benefit sharing is nil up to ₹5 crore annual turnover, then 0.2% / 0.4% / 0.6% by slab
  (₹5–50 cr / ₹50–250 cr / above ₹250 cr) [E4]. The calculator shows the arithmetic *(planned M5;
  figures to be checked against the primary Regulations at M1)*.
- **Codified traditional knowledge** — the Biological Diversity (Amendment) Act 2023 §2(ea) defines it
  by reference to the authoritative books in the First Schedule of the Drugs & Cosmetics Act [E5]; this
  links a *classical* formulation to ABS exemptions for Indian entities.
- **Researchers and patent applicants** — risk indicators mapped to IP India's examination guidelines
  for Ayush inventions (Sections 3(d), 3(e), 3(p)) [E7]; *never* a patentability verdict.
- **Exporters** — EU traditional-use registration needs ≥30 years of use, ≥15 of them in the EU [E11].
- **Reach** — English, Hindi and Gujarati interface; voice input with a typed fallback *(planned M4/M8)*.
- **Honesty by design** — guidance with sources, routed to a qualified professional; not legal advice [E10].

---

## Slide 6 — Research and references

1. Rule 170 omission (G.S.R. 360(E), w.e.f. 01-07-2024), Supreme Court stay 27-08-2024 in
   W.P.(C) 645/2022, sub judice — [E3]
2. Biological Diversity (Amendment) Act 2023, §2(ea) "codified traditional knowledge" — [E5]
3. Biological Diversity (ABS) Regulations 2025 benefit-sharing slabs — [E4] (primary text: M1)
4. IP India, Guidelines for Examination of Ayush Related Inventions — [E7]
5. WIPO Treaty on IP, Genetic Resources and Associated TK: not in force; India not a signatory
   (status 8 Jul 2026) — horizon item only — [E6]
6. Temporal misgrounding in legal RAG: 0% vs 98.3% — [E8]
7. Hallucination in commercial legal AI: 17–33% — [E9]
8. EMA traditional-use registration — [E11]
9. Public SIH26045 repositories surveyed: 213 — [E16]

---

## 7. Evidence register

| Tag | Source | Link |
|---|---|---|
| E3 | PIB release PRID 2148433 — Rule 170 status | https://pib.gov.in/PressReleasePage.aspx?PRID=2148433 |
| E4 | Analysis of the Biological Diversity (ABS) Regulations 2025 (secondary; primary text to be added to The Library) | — |
| E5 | Biological Diversity (Amendment) Act 2023, Gazette of India text | egazette.gov.in (archived snapshot) |
| E6 | WIPO treaty status, GRATK, 8 Jul 2026 | wipo.int |
| E7 | IP India — Guidelines for Examination of Ayush Related Inventions | ipindia.gov.in |
| E8 | Temporal misgrounding in legal RAG | https://arxiv.org/abs/2608.09393 |
| E9 | Hallucination-free? Assessing the reliability of leading AI legal research tools | https://arxiv.org/abs/2405.20362 |
| E10 | US FTC order, DoNotPay | ftc.gov |
| E11 | EMA — herbal medicinal products, traditional-use registration | ema.europa.eu |
| E16 | GitHub repository search for SIH26045 (27 Sep 2026) | github.com |
| E17 | dgexplores/ip-sakti-sahayak-SIH26045 | https://github.com/dgexplores/ip-sakti-sahayak-SIH26045 |
| E19 | Build-machine measurements, 27 Sep 2026 | this repository |

## 8. Deliberately left off the slides (unverified until the primary text is in The Library)

The DMR Act schedule of diseases (the demo's closing "DMR overlay" beat), Rule 158B, Rule 2(eb)
marker counts, FSSAI Ayurveda Aahara Category A, US FDA import alerts, India's share of IRCCs, GI
examples, TKDL access terms, and the official SIH evaluation criteria. Each returns to the deck only
after verification.
