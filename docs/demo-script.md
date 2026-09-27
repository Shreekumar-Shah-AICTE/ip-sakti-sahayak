# Demo script — IP-SAKTI Sahayak

≈70 seconds of screen time, plus two optional beats. It implements PITCH_DEFENCE §3 exactly.
Every line below is asserted by `smoke/test_ui_smoke.py` and `tests/test_demo_script.py`, so if
the script drifts from the product, `make check` fails.

## Before you start

```sh
./run.sh            # or: run.bat on Windows
```

Keyless is the demo mode. No API keys, no network: BM25 retrieval, the Status Ledger, the DMR
overlay, the ABS calculator and the Passport Compiler all work offline. If keys happen to be
set, the only visible difference is the AI-organised synthesis card above the quotes — the
quotes, the status line and the abstention behaviour are identical. Open the app, leave the
jurisdiction on **IN**, and use the **Demo** chip bar under the question box.

**Easiest path for a first-time presenter:** click **🧭 Guided demo** (top right). It performs
each beat below with one click (**▶ Do it**), says what should appear on screen, and gives the
line to say. Every legal or Ayurveda word with a small **?** opens a plain-English explanation,
and **📖 Glossary** lists them all.

## The beats

**0:00 — One question.** Click the **Diabetes advertisement** chip:

> Can I advertise this classical formulation as a treatment for diabetes?

Say: *this is the question a manufacturer actually asks, and its answer changed four times in
fourteen months.*

**0:10 — Step the date.** Click the four **Key dates** chips in order. The status line, the
highlighted timeline segment and the quoted evidence change each time; nothing else does.

| Chip | Status line | The evidence it quotes |
|---|---|---|
| `2024-06-30` | In force | Drugs Rules, 1945 — Rule 170 |
| `2024-07-02` | Omitted | G.S.R. 360(E), omission w.e.f. 01-07-2024 |
| `2024-08-28` | In force — omission stayed by the Supreme Court (**sub judice**) | SC interim order 27-08-2024, W.P.(C) 645/2022 |
| `2025-08-12` | Omitted — Supreme Court stay vacated | SC order 11-08-2025 (petition disposed, stay vacated) |

Point at the timeline strip: *the ledger is not a guess about the present, it is four dated
segments with a primary source each.*

**0:35 — What a normal assistant does.** Tick **Compare with static RAG**. The dashed card is
the same corpus and the same BM25 search with the as-of date and the ledger removed. It returns
one passage and returns it on every date — and it never abstains.

**0:50 — The closing beat.** Every one of the four answers also carries the Drugs and Magic
Remedies (Objectionable Advertisements) Act, 1954 overlay — s.3(d) and the Schedule entry
"9. Diabetes." — labelled *applies whatever the rule's status*. So:

> The practical answer is "no" on all four dates — for four different reasons, with four
> different citations. A toy gives you a verdict. This gives you the chain.

**1:05 — Abstention, on purpose.** Click the **Out of scope (abstains)** chip:

> What is the GST rate on ayurvedic churna?

The Library holds no tax law, so the app says so and names the next step. Say: *we never invent
law. Abstention is a feature, and it is a designed screen, not an error.*

## Optional beats

- **Hindi** — click the **हिन्दी** chip (the same advertising question in Hindi). It routes to
  the same ledger entry and the same evidence; the interface labels change, the legal quotes
  stay verbatim in their original language. With a microphone, use the 🎤 button instead and
  speak it. Note: Chrome's speech recognition sends the audio to Google's speech service, so
  say so if asked — typing keeps everything on the machine.
- **ABS calculator** — set the date to `2026-09-27` and open the benefit-share panel. It applies
  the Biological Diversity Regulations, 2025 slabs and abstains for dates before their
  commencement, the same way the ledger does.

## If something goes wrong on stage

- The first question after a cold start can wait a few seconds on the retriever warm-up; the
  button says so and retries by itself.
- No network is required. If the venue's Wi-Fi fails, nothing in this script changes.
- If a synthesis card says *withheld*, that is the Answer Contract rejecting an LLM sentence
  that was not grounded in the quotes or contradicted the ledger. Read it out — it is the point.
