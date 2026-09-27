# IP-SAKTI Sahayak — SIH 2026 Idea Deck (SIH26045)

Six slides (the SIH cap). Slide text first, then speaker notes. Every factual claim carries an
evidence tag `[E#]` resolved in §7. Tense rule: **present tense only for what exists today**;
everything else is labelled *planned* with its milestone.

---

## Slide 1 — The failure: one question, four dates, four correct answers

**Title:** Ayurveda advertising law changed status four times. A static assistant answers as if it never did.

**Question:** *"Can I advertise this classical Ayurvedic formulation for a disease?"*

| As-of date | Status of Rule 170 (ASU drug advertisements) | Governing evidence |
|---|---|---|
| 30 Jun 2024 | **In force** — inserted w.e.f. 24 Dec 2018 | Drugs Rules, Rule 170; G.S.R. 1230(E), fn 757 [E20] |
| 02 Jul 2024 | **Omitted**, w.e.f. 01 Jul 2024 | G.S.R. 360(E), fn 1345 of the compiled Rules [E21] |
| 28 Aug 2024 | Omission **stayed** — "Rule 170 shall remain on the statute book and in force"; sub judice | SC interim order 27 Aug 2024, W.P.(C) 645/2022 [E22] |
| 12 Aug 2025 | **Omitted again** — the writ petition was disposed of and the "interim order dated 27.08.2024 stands vacated" | SC order 11 Aug 2025, W.P.(C) 645/2022 [E22] |

And advertising is never governed by one rule alone: whatever Rule 170 says on a given date, the
Drugs and Magic Remedies (Objectionable Advertisements) Act 1954 Schedule independently bars
advertising a remedy for **cancer** (entry 6) and **diabetes** (entry 9) [E23].

- A static retrieval system retrieved the date-applicable legal version **0%** of the time; a
  versioned, date-conditioned retriever reached **98.3%** [E8].
- Commercial legal AI tools hallucinate in **17–33%** of queries [E9].

**Line to say:** "A static system gives one answer to all four dates. At least three of them prove it wrong —
including anyone still saying this matter is sub judice."

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

- **Litigation as a ledger state:** a pending case is `sub_judice: true` in the answer body, not a
  footnote; when it ends, the ledger gains one dated entry and no code changes. This already
  happened — the Supreme Court vacated the Rule 170 stay on 11 Aug 2025 [E22], the fourth row on
  slide 1, and it is exactly the kind of movement a static assistant misses.
- **Integrity:** benchmark questions written by teammates who do not write retriever code, committed
  as hashes before evaluation; results published with corpus hash, commit and date. *planned* M6.

---

## Slide 5 — Impact and beneficiaries

**Title:** For the people who carry the compliance risk.

- **Ayush manufacturers, especially MSMEs** — licensing category, advertising limits, ABS
  obligations and export regimes, each changing on its own clock.
- **ABS burden under the Biological Diversity (ABS) Regulations 2025**, which replaced the 2014
  Guidelines: turnover selects the slab — nil up to ₹5 crore, then 0.2% / 0.4% / 0.6%
  (₹5–50 cr / ₹50–250 cr / above ₹250 cr) — and the rate applies to the product's annual gross
  ex-factory sale price excluding taxes, not to turnover; read from the primary gazette [E24].
  The Passport Compiler's calculator shows the arithmetic and the gazette line behind each rate.
- **Codified traditional knowledge** — the Biological Diversity (Amendment) Act 2023 §2(ea) defines it
  by reference to the authoritative books in the First Schedule of the Drugs & Cosmetics Act [E5]; this
  links a *classical* formulation to ABS exemptions for Indian entities.
- **Researchers and patent applicants** — risk indicators mapped to IP India's examination guidelines
  for Ayush inventions (Sections 3(d), 3(e), 3(p)) [E25]; *never* a patentability verdict.
- **Exporters** — EU traditional-use registration needs ≥30 years of use, ≥15 of them in the EU [E11].
- **Reach** — English, Hindi and Gujarati interface; voice input with a typed fallback *(planned M4/M8)*.
- **Honesty by design** — guidance with sources, routed to a qualified professional; not legal advice [E10].

---

## Slide 6 — Research and references

1. Rule 170, Drugs Rules 1945 — inserted by G.S.R. 1230(E) w.e.f. 24-12-2018 [E20]; omitted by
   G.S.R. 360(E) w.e.f. 01-07-2024 [E21]; omission stayed 27-08-2024 and that stay **vacated** by the
   Supreme Court on 11-08-2025 in W.P.(C) 645/2022 [E22]
2. Drugs and Magic Remedies (Objectionable Advertisements) Act 1954 and its Schedule — [E23]
3. Biological Diversity (Amendment) Act 2023, §2(ea) "codified traditional knowledge" — [E5]
4. Biological Diversity (ABS) Regulations 2025 benefit-sharing slabs, primary gazette — [E24]
5. IP India, Guidelines for Examination of Ayush Related Inventions — [E25]
6. Temporal misgrounding in legal RAG: 0% vs 98.3% — [E8]
7. Hallucination in commercial legal AI: 17–33% — [E9]
8. EMA traditional-use registration — [E11]
9. Public SIH26045 repositories surveyed: 213 — [E16]

---

## 7. Evidence register

| Tag | Source | Link |
|---|---|---|
| E3 | PIB release PRID 2148433 — Rule 170 status (corroboration only, never the sole citation) | https://pib.gov.in/PressReleasePage.aspx?PRID=2148433 |
| E5 | Biological Diversity (Amendment) Act 2023, Gazette of India text | egazette.gov.in (archived snapshot) |
| E20 | Drugs Rules 1945, CDSCO compilation to G.S.R. 823(E) 17-11-2022 — Rule 170 text and footnote 757 | https://cdsco.gov.in/opencms/resources/UploadCDSCOWeb/2022/drug_rules/Drugs%20Rules%2C%201945%20%281%29.pdf |
| E21 | Drugs Rules 1945, compilation to G.S.R. 360(E) 01-07-2024 — Rule 170 shown as `[*****]`, footnote 1345 | https://statedrugs.gov.in/SFDA/resources/app_srv/SFDA/global/newLandingPage_assests/licence_Forms/Drugs%20Rules%201945_2024%2009.pdf |
| E22 | Supreme Court of India — order dated 11-08-2025, W.P.(C) 645/2022 (with W.P.(C) 400/2025) | https://api.sci.gov.in/supremecourt/2022/24832/24832_2022_5_42_63155_Order_11-Aug-2025.pdf |
| E23 | Drugs and Magic Remedies (Objectionable Advertisements) Act 1954 and Rules 1955, with the Schedule | http://cari.gov.in/PDF/Drug%20and%20magic%20remedies%20act%201954%20rules%201955.pdf |
| E24 | Biological Diversity (ABS) Regulations 2025 — Gazette of India CG-TN-E-30042025-262783 | https://cdnbbsr.s3waas.gov.in/s3fcdb3b4550e745d29a64a696047067b7/uploads/2025/05/202505151889481287.pdf |
| E25 | IP India — Guidelines for Examination of Ayush Related Inventions (2025) | https://ipindia.gov.in/storage/uploads/docs-operator/335e2746-58c1-4b56-a1e5-cdd172a92a3c.pdf |
| E8 | Temporal misgrounding in legal RAG | https://arxiv.org/abs/2608.09393 |
| E9 | Hallucination-free? Assessing the reliability of leading AI legal research tools | https://arxiv.org/abs/2405.20362 |
| E10 | US FTC order, DoNotPay | ftc.gov |
| E11 | EMA — herbal medicinal products, traditional-use registration | ema.europa.eu |
| E16 | GitHub repository search for SIH26045 (27 Sep 2026) | github.com |
| E17 | dgexplores/ip-sakti-sahayak-SIH26045 | https://github.com/dgexplores/ip-sakti-sahayak-SIH26045 |
| E19 | Build-machine measurements, 27 Sep 2026 | this repository |

## 8. Deliberately left off the slides (unverified until the primary text is in The Library)

Verified at M1 and now on the slides: the DMR Act Schedule diseases [E23] and the ABS slabs from the
primary gazette [E24]. Rule 158B and the phytopharmaceutical marker count are verified too (the
latter is **Rule 2(ec)**, not 2(eb)) but are product-layer detail, not slide material.

Still off the slides: the **WIPO GRATK signatory and ratification counts** — the WIPO treaty page in
The Library carries no such figures, so the horizon item was removed entirely rather than softened.
Also off: FSSAI Ayurveda Aahara Category A (the 2025 order PDF is a scan with no text layer), US FDA
import alert 99-42, India's share of IRCCs, GI examples, TKDL's "paid phased public model" (the site
states only that sixteen Patent Offices have access under a non-disclosure agreement), and the
official SIH evaluation criteria. Each returns to the deck only after verification.
