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
| The Library | Full-text primary instruments with provenance and a corpus-version hash | working (19 documents) |
| The Retriever | BM25 + optional multilingual dense (MiniLM-L12, precomputed in `corpus/index/`), fused by RRF k=60; filters applied before ranking; falls back to BM25 when the dense index or model is absent | working |
| The Answer Contract | Verbatim quotes, citations, status-as-of, abstention | working |
| The Passport Compiler | Per-product compliance passport (classical / proprietary / phytopharmaceutical, printable, compiled as of the date; judgment calls shown as risk indicators) + ABS benefit-share calculator. Rules in `rules/*.yaml`; every rule's quote is checked verbatim against The Library at load | working (v0) |
| The Proving Ground | Benchmark vs a vanilla-RAG baseline | working — internal dev set only, not externally validated |

## 3. Run it

```sh
./run.sh          # macOS / Linux  (run.bat on Windows)
curl localhost:8000/health
```

No API keys are needed. Optional adapters read keys from a git-ignored `.env`
(see `.env.example`).

## 4. Develop

```sh
make install
make check        # ruff + pytest + eval gate + web build
```

## 5. Limits

IP-SAKTI Sahayak gives guidance with sources and routes you to a qualified professional.
It is not legal advice. Where it lacks dated evidence, it abstains and says why.

## 6. Licence

MIT — see `LICENSE`.
