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
| The Two Switches | Jurisdiction + as-of date, applied as hard filters | planned |
| The Status Ledger | Dated legal-status timeline; every entry cites a gazette notification or court order | planned |
| The Library | Full-text primary instruments with provenance and a corpus-version hash | planned |
| The Retriever | Hybrid BM25 + dense retrieval, filters applied before ranking | planned |
| The Answer Contract | Verbatim quotes, citations, status-as-of, abstention | planned |
| The Passport Compiler | Per-product compliance passport + ABS benefit-share calculator | planned |
| The Proving Ground | Benchmark vs a vanilla-RAG baseline | planned |

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
