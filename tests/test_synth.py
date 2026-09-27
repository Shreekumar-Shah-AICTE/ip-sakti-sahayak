"""M7: the optional LLM layer may only organise already-cited quotes (S3 rule 8)."""

import json

import pytest
import yaml
from fastapi.testclient import TestClient

import api.synth as synth
from api.answer import answer
from api.main import app
from eval.run_eval import SETS

Q = [{"text": "The Act came into force on 1 July 2024 under section 3.",
      "doc_title": "Some Rules", "section": "Rule 170"}]


def test_check_accepts_a_cited_faithful_sentence():
    assert synth.check("It came into force on 1 July 2024 [1].", Q) is None


@pytest.mark.parametrize("text,why", [
    ("It came into force in 2019 [1].", "number"),
    ("It came into force on 1 July 2024.", "uncited"),
    ("See [2] for details.", "does not exist"),
    ("You have no need for a lawyer here [1].", "professional"),
    ("INSUFFICIENT", "insufficient"),
    ("", "empty"),
])
def test_check_rejects_contract_breaches(text, why):
    assert why in synth.check(text, Q)


def test_keyless_default_has_no_synthesis(monkeypatch):
    monkeypatch.delenv("SAHAYAK_LLM", raising=False)
    r = TestClient(app).post("/ask", json={"question": "What is codified traditional knowledge?"})
    assert r.status_code == 200 and r.json()["synthesis"] is None and not r.json()["abstain"]


def test_replay_mode_never_touches_the_network(monkeypatch, tmp_path):
    monkeypatch.setattr(synth, "REPLAY_DIR", tmp_path)
    monkeypatch.setattr(synth, "_call_live", lambda *a: pytest.fail("network in replay mode"))
    monkeypatch.setenv("GROQ_API_KEY", "x")
    a = answer("What is codified traditional knowledge?", "IN", "2026-09-01").to_dict()
    s = synth.synthesize(a, "q", provider="groq")
    assert s["accepted"] is False and "replay" in s["reason"] and a["quotes"]


def test_record_then_replay_is_deterministic(monkeypatch, tmp_path):
    monkeypatch.setattr(synth, "REPLAY_DIR", tmp_path)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    a = answer("What is codified traditional knowledge?", "IN", "2026-09-01").to_dict()
    said = " ".join(a["quotes"][0]["text"].split()[:10]).rstrip(".;:,") + " [1]."
    monkeypatch.setattr(synth, "_call_live", lambda *_: said)
    monkeypatch.setenv("SAHAYAK_LLM_REPLAY", "record")
    live = synth.synthesize(a, "q", provider="groq")
    assert live["accepted"] and live["source"] == "live"
    saved = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert "x" not in saved.values() and "GROQ_API_KEY" not in json.dumps(saved)
    monkeypatch.setattr(synth, "_call_live", lambda *a: pytest.fail("network on replay"))
    monkeypatch.setenv("SAHAYAK_LLM_REPLAY", "replay")
    again = synth.synthesize(a, "q", provider="groq")
    assert again["source"] == "replay" and again["text"] == live["text"]


def test_provider_error_leaves_the_extractive_answer(monkeypatch, tmp_path):
    monkeypatch.setattr(synth, "REPLAY_DIR", tmp_path)
    monkeypatch.setenv("SAHAYAK_LLM_REPLAY", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "x")

    def boom(*a):
        raise TimeoutError

    monkeypatch.setattr(synth, "_call_live", boom)
    a = answer("What is codified traditional knowledge?", "IN", "2026-09-01").to_dict()
    s = synth.synthesize(a, "q", provider="gemini")
    assert not s["accepted"] and "TimeoutError" in s["reason"] and "x" not in s["reason"]


def test_abstentions_are_never_synthesised():
    a = answer("Who won the FIFA World Cup final?", "IN", "2026-09-01").to_dict()
    assert a["abstain"] and synth.synthesize(a, "q", provider="groq") is None


def test_adapter_on_leaves_cited_chunk_ids_unchanged(monkeypatch, tmp_path):
    """S3 rule 8: run the answerable dev items with an adapter on; citations must not move."""
    monkeypatch.setattr(synth, "REPLAY_DIR", tmp_path)
    monkeypatch.setenv("SAHAYAK_LLM_REPLAY", "live")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setattr(synth, "_call_live", lambda *a: "Organised per the source [1].")
    qs = [q for q in yaml.safe_load((SETS / "dev.yaml").read_text(encoding="utf-8"))
          if q["set"] in "AL"]
    for q in qs:
        a = answer(q["question"], q["jurisdiction"], q["as_of"]).to_dict()
        before = json.dumps(a["quotes"], sort_keys=True)
        synth.synthesize(a, q["question"], provider="groq")
        assert json.dumps(a["quotes"], sort_keys=True) == before


def test_date_formats_compare_as_integer_runs():
    q = [{"text": "Notification dated 01.07.2024 omitted the rule.",
          "doc_title": "", "section": ""}]
    assert synth.check("A notification dated 01-07-2024 omitted the rule [1].", q) is None


def test_unverifiable_or_ungrounded_sentences_are_rejected():
    assert "cannot be checked" in synth.check("यह नियम लागू है [1]।", Q)
    assert "not grounded" in synth.check("Pharmacists must register herbal exports quickly [1].", Q)


def test_committed_replay_fixtures_hold_no_secrets():
    for p in synth.REPLAY_DIR.glob("*.json"):
        rec = json.loads(p.read_text(encoding="utf-8"))
        assert set(rec) == {"provider", "model", "prompt", "text"}
        assert p.stem == synth.cache_key(rec["provider"], rec["model"], rec["prompt"])
        assert not any(s in p.read_text(encoding="utf-8") for s in ("gsk_", "AQ.", "sk_", "Bearer"))


# ---- run 12: MIN_GROUNDING sweep + Status Ledger polarity (DECISIONS D-020) ----

def test_min_grounding_is_pinned_at_the_swept_value():
    assert synth.MIN_GROUNDING == 0.5


def test_sweep_never_accepts_a_contract_violating_recording():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "eval" / "sweep_min_grounding.py"
    spec = importlib.util.spec_from_file_location("sweep_min_grounding", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = mod.load()
    assert rows, "no committed synthesis recordings"
    for row in mod.sweep(rows):
        assert row["violating_accepted"] == 0, row
    by_t = {r["t"]: r for r in mod.sweep(rows)}
    assert by_t[0.5]["accepted"] == by_t[0.0]["accepted"]  # 0.0-0.5 is one band today


def test_synthesis_may_not_contradict_the_status_ledger():
    q = [{"text": "the said Rule is still in force and compliances have been made",
          "doc_title": "SC order", "section": "9"}]
    omitted = "Status as of 2026-09-01: omitted_stay_vacated"
    stayed = "Status as of 2024-09-15: in_force_stayed_omission (sub judice)"
    why = synth.check("The said Rule is still in force [1].", q, omitted)
    assert why and "Status Ledger" in why
    assert synth.check("The said Rule is still in force [1].", q, stayed) is None
    assert synth.ledger_conflict("It is no longer in force [1].", stayed)
    assert not synth.ledger_conflict("It is no longer in force [1].", omitted)
    assert not synth.ledger_conflict("Rule 170 is not in force [1].", omitted)
    assert not synth.ledger_conflict("The Rule is in force [1].", None)
