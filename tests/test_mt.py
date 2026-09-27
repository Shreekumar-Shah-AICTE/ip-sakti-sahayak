"""The Glossary's MT fallback: off by default, replayable, and never loosens abstention."""

import json
import re

from api.i18n import mt, translate

HI_GST = "सौंदर्य प्रसाधनों पर जीएसटी की दर क्या है?"


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("SAHAYAK_MT", raising=False)
    assert mt.lookup("hi", ["जीएसटी"]) == {}
    tr = translate(HI_GST)
    assert tr is not None and tr.machine == [] and "जीएसटी" in tr.unknown


def test_replay_needs_no_key_or_network(monkeypatch):
    monkeypatch.setenv("SAHAYAK_MT", "groq")
    monkeypatch.setenv("SAHAYAK_MT_REPLAY", "replay")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    tr = translate(HI_GST)
    assert "gst" in tr.terms and "जीएसटी" not in tr.unknown and tr.machine


def test_unrecorded_words_stay_unknown_in_replay(monkeypatch):
    monkeypatch.setenv("SAHAYAK_MT", "groq")
    monkeypatch.setenv("SAHAYAK_MT_REPLAY", "replay")
    assert mt.lookup("hi", ["अनजानाशब्द"]) == {}


def test_clean_rejects_unsure_non_ascii_and_prose():
    assert mt._clean("?") is None
    assert mt._clean("जीएसटी") is None
    assert mt._clean("gst's") is None
    assert mt._clean("x" * 60) is None
    assert mt._clean("1. Patent.") == "patent"


def test_misaligned_reply_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(mt, "REPLAY_DIR", tmp_path)
    words = ["क", "ख"]
    key = mt.cache_key("groq", mt.PROVIDERS["groq"][1], "hi", words)
    (tmp_path / f"{key}.json").write_text(json.dumps({"replies": ["one"]}), encoding="utf-8")
    assert mt.lookup("hi", words, provider="groq", mode="replay") == {}


def test_mt_fixtures_hold_no_secrets():
    for f in mt.REPLAY_DIR.glob("*.json"):
        raw = f.read_text(encoding="utf-8")
        assert not re.search(r"(gsk_|sk_|AIza|AQ\.)[A-Za-z0-9_\-]{8,}", raw), f.name
        assert set(json.loads(raw)) == {"provider", "model", "lang", "words", "replies"}
