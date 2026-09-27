# IP-SAKTI Sahayak

**An Ayurveda IP and regulatory assistant that answers as of a date.**

Smart India Hackathon 2026 · Problem statement SIH26045 · Ministry of Ayush / All India
Institute of Ayurveda.

> Status: **early scaffold (M0).** The sections below describe the design. Anything not
> yet built is marked *planned*. Measured results will be published here with a date.

## 1. The idea

The law governing Ayurveda IP and advertising changed repeatedly in 2024–2026. A question
such as "may this classical formulation be advertised for a disease?" can have a different
correct answer depending on the date it is about. IP-SAKTI Sahayak puts two switches at the
top of every query — **jurisdiction** and **as-of date** — and conditions retrieval and
answers on both.

## 2. Modules

| Module | Job | State |
|---|---|---|
| The Two Switches | Jurisdiction + as-of date, applied as hard filters | working |
| The Status Ledger | Dated legal-status timeline; every entry cites a gazette notification or court order | working (Rule 170 only) |
| The Library | Full-text primary instruments with provenance and a corpus-version hash | working (20 documents) |
| The Retriever | BM25 + optional multilingual dense (MiniLM-L12, precomputed in `corpus/index/`), fused by RRF k=60; filters applied before ranking; falls back to BM25 when the dense index or model is absent | working |
| The Answer Contract | Verbatim quotes, citations, status-as-of, abstention | working |
| The Passport Compiler | Per-product compliance passport (classical / proprietary / phytopharmaceutical, printable, compiled as of the date; judgment calls shown as risk indicators) + ABS benefit-share calculator. Rules in `rules/*.yaml`; every rule's quote is checked verbatim against The Library at load | working (v0) |
| The Conversation | Chat front door over every module: the Two Switches move from plain words ("what about 2 Jul 2024?"), tools run inside the thread, and general Ayurveda questions are answered from a curated offline note-set labelled as background. A legal question the sources cannot support is abstained on, never answered from general knowledge | working |
| The Claim Sentry | Flags risk indicators in ad copy against the DMR Act 1954 and its Schedule, quoting the section behind each flag. Flags only — it never rewrites the advertiser's words | working (lite) |
| The Proving Ground | Benchmark vs a vanilla-RAG baseline (also served at `POST /baseline` for the side-by-side demo) | working — internal dev set only, not externally validated |
| The Audit Trail | Hash-chained JSONL of every answer's decision — query hashes, never query text (§5) | working |

## 3. Run it

```sh
python run.py     # installs what it needs, builds the UI, serves http://localhost:8000
```

That is the whole command, with or without a key. `./run.sh` (`run.bat` on Windows) does the
same thing.

**Keyless is the default and is fully functional.** Retrieval, the Two Switches, the Status
Ledger, verbatim quotes, the passport and ABS calculators, the Claim Sentry and the offline
Ayurveda note-set need no network and no account. The header shows **○ Offline**.

**To turn the online path on, add one key:**

```sh
cp .env.example .env      # then paste a Gemini key after GEMINI_API_KEY=
python run.py
```

Get a free key at <https://aistudio.google.com/apikey>. Nothing else changes — same command,
same port. The header switches to **● Online · Gemini** and the console banner says `ONLINE`.
`.env` is git-ignored, so the key is never committed. `GROQ_API_KEY` or `SARVAM_API_KEY` work
instead; Gemini is tried first.

What the key buys: LLM phrasing of answers that are already retrieved and cited, free-form
Ayurveda chat, and machine translation for Hindi and Gujarati. It never buys a legal claim —
synthesis may only rephrase quotes the retriever already found, and a synthesis that
contradicts The Status Ledger is discarded in favour of the extractive answer.

Two things worth knowing about the online path:

- **Cache first.** An answer is served from `var/cache/` if it is already there, so a repeated
  question costs nothing and returns instantly. `var/` is git-ignored and separate from the
  committed fixtures in `api/*/replay/` that keep `make check` deterministic and offline.
- **Model chain.** Gemini models are tried in order, starting with `gemini-3.1-flash-lite`
  (measured ~0.9 s per answer, against 12–45 s for the thinking-flash models, which exceeded
  our 25 s timeout). A model that answers 404 or 429 is dropped for the rest of the process,
  so a spent free-tier quota degrades to the next model and finally to keyless mode instead of
  failing. Pin one with `SAHAYAK_GEMINI_MODEL=`.

```sh
curl localhost:8000/health   # mode, online true/false, provider, replay mode — never keys
```

For the guided walkthrough — one advertising question stepped across the four dates on which
Rule 170's status changed, next to a static-RAG baseline on the same corpus — see
[`docs/demo-script.md`](docs/demo-script.md). It runs keyless and offline, and
`tests/test_demo_script.py` asserts every outcome it claims.

**The chat is the front door.** Open http://localhost:8000 and just ask. Every ability is
reachable in the thread — status of a rule on a date, the ABS calculator, a licence passport,
the claim checker, the timeline, the static-RAG comparison, and ordinary Ayurveda questions.
Type `/` for commands. A bare date ("what about 2 Jul 2024?") re-asks your last question and
shows what changed. **▶ Autopilot demo** walks a presenter through thirteen beats with
narration and a Next button. Answers keep the verbatim quotes, the status-as-of line and the
abstention card, and **🔧 How I answered** lists the tools each turn used.

The single-question view is still at http://localhost:8000/?view=classic, with the **🧭 Guided
demo** coach. Every legal, Ayurveda and AI term carries a **?** with a plain-English
explanation, each answer has an *In plain words* box, and **📖 Glossary** lists every term.

General Ayurveda chat works offline from a curated note-set. With `GROQ_API_KEY` or
`GEMINI_API_KEY` in `.env` it also phrases free-form answers through an LLM
(`SAHAYAK_CHAT_LLM=auto|groq|gemini|none`); that path is barred from making legal statements
and is never used for a legal answer.

## 4. Develop

```sh
make install
make check        # ruff + pytest + eval gate + web build
```

## 5. Privacy and the audit trail

Data minimisation, stated as what the tests actually prove (`tests/test_audit.py`):

- **Your question text is never stored.** Every answered `/ask` appends one JSONL row to
  `var/audit.jsonl` holding a salted SHA-256 of the question plus the decision: jurisdiction,
  as-of date, retrieval mode, the chunk ids served, abstain/confidence, and the ledger status.
  A test asserts that no word of the question appears in the file and that no undeclared field
  is written. Set `SAHAYAK_AUDIT_SALT` to keep hashes comparable across restarts; unset, a
  fresh random salt is used per process.
- **The trail is tamper-evident.** Rows are hash-chained (`prev` → `row_hash`).
  `GET /audit/verify` walks the chain and returns only the verdict. Editing or deleting a past
  row is detected.
- **`SAHAYAK_AUDIT=off`** disables logging entirely. An unwritable audit path is ignored rather
  than failing the answer.
- **Keyless mode sends nothing anywhere.** Enabling an LLM or translation adapter sends your
  question text to that provider; the UI says so as soon as an adapter is detected.
- Purpose limitation: this data exists to let a decision be reproduced and challenged. It is
  not shared with third parties.

Threat model we design against: **prompt injection from corpus text** — corpus content is
never executed, and the optional LLM may only rephrase quotes already retrieved and cited;
**source spoofing** — every quote carries a chunk id, source URL and the corpus hash;
**stale law shown as current** — the ledger carries `last_verified` and the UI shows a
staleness warning.

## 6. Limits

IP-SAKTI Sahayak gives guidance with sources and routes you to a qualified professional.
It is not legal advice. Where it lacks dated evidence, it abstains and says why.

## 7. Licence

MIT — see `LICENSE`.
