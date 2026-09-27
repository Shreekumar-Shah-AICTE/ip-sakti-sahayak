"""The one-key promise (api/config.py): a key in `.env` turns the app online; nothing
there, or SAHAYAK_MODE=offline, means no network call and no behaviour change."""

import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from api import config, gemini, main
from api.chat import llm as chat_llm

KEYS = (*config.PROVIDER_KEYS, "SAHAYAK_LLM", "SAHAYAK_MT", "SAHAYAK_CHAT_LLM",
        "SAHAYAK_LLM_REPLAY", "SAHAYAK_MT_REPLAY", "SAHAYAK_CHAT_REPLAY")


@pytest.fixture
def clean(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SAHAYAK_MODE", "auto")
    return monkeypatch


def test_env_file_never_overrides_a_real_env_var(clean, tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=from-file\nGROQ_API_KEY='quoted-file'\n", encoding="utf-8")
    clean.setenv("GEMINI_API_KEY", "from-shell")
    loaded = config.load_env(env)
    assert loaded == ["GROQ_API_KEY"]  # names only, never values
    import os
    assert os.environ["GEMINI_API_KEY"] == "from-shell"
    assert os.environ["GROQ_API_KEY"] == "quoted-file"


@pytest.mark.parametrize("body", [b"", b"\xff\xfe garbage \x00", b"no equals sign\n=\n#c\n",
                                  b"GEMINI_API_KEY=\n"])
def test_missing_or_garbage_env_is_harmless(clean, tmp_path, body):
    env = tmp_path / ".env"
    env.write_bytes(body)
    config.load_env(env)
    config.load_env(tmp_path / "absent.env")
    assert config.mode() == "offline" and config.llm_provider() is None


def test_offline_skips_the_env_file_entirely(clean, tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=x\n", encoding="utf-8")
    clean.setenv("SAHAYAK_MODE", "offline")
    assert config.load_env(env) == []


def test_one_gemini_key_turns_everything_on_cache_first(clean):
    clean.setenv("GEMINI_API_KEY", "x")
    assert config.mode() == "online"
    assert (config.llm_provider(), config.chat_provider(), config.mt_provider()) == \
        ("gemini", "gemini", "gemini")
    assert config.replay_mode("SAHAYAK_LLM_REPLAY") == "record"  # free-tier quota
    # online reads only this machine's cache, never the committed eval fixtures
    assert config.cache_dirs("SAHAYAK_LLM_REPLAY", config.ROOT, "synth") == \
        [config.USER_CACHE / "synth"]


def test_offline_makes_no_network_call(clean, monkeypatch):
    clean.setenv("GEMINI_API_KEY", "x")
    clean.setenv("SAHAYAK_MODE", "offline")

    def no_network(*a, **k):
        raise AssertionError("network call in offline mode")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    c = TestClient(main.app)
    for msg in ("Is Rule 170 in force?", "What is Vata dosha?", "Tell me about Ashwagandha"):
        r = c.post("/chat", json={"message": msg, "as_of": "2026-09-01"})
        assert r.status_code == 200
    body = c.get("/health").json()
    assert body["mode"] == "keyless" and body["online"] is False
    assert chat_llm.provider() == "replay"


def test_keys_never_appear_in_health(clean):
    clean.setenv("GEMINI_API_KEY", "sentinel-gemini-987")
    clean.setenv("GROQ_API_KEY", "sentinel-groq-654")
    text = TestClient(main.app).get("/health").text
    assert "sentinel" not in text
    assert "sentinel" not in str(config.summary())


def test_gemini_chain_skips_retired_and_exhausted_models(clean, monkeypatch):
    calls = []

    class Resp:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self.body

    def fake(req, timeout):
        model = req.full_url.split("/models/")[1].split(":")[0]
        calls.append(model)
        code = {gemini.MODELS[0]: 404, gemini.MODELS[1]: 429, gemini.MODELS[2]: 503}.get(model)
        if code:
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)
        return Resp(b'{"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(gemini, "_dead", set())
    assert gemini.generate("k", "s", "p") == ("ok", gemini.MODELS[3])
    calls.clear()
    gemini.generate("k", "s", "p")  # 404/429 remembered; the overloaded one is retried
    assert calls == [gemini.MODELS[2], gemini.MODELS[3]]
