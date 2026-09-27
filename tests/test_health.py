from fastapi.testclient import TestClient

from api import main


def test_health_keyless(monkeypatch):
    for var in main.OPTIONAL_ADAPTERS.values():
        monkeypatch.delenv(var, raising=False)
    r = TestClient(main.app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "keyless"
    assert not any(body["adapters"].values())


def test_health_never_leaks_key_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sentinel-value-123")
    r = TestClient(main.app).get("/health")
    assert "sentinel-value-123" not in r.text
    assert r.json()["adapters"]["llm.gemini"] is True
