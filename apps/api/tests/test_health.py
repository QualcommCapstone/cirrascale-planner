from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers.get("x-request-id")  # correlation id is attached


def test_ready_mock_mode_is_ready():
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["providers"] == {
        "embedding": "mock",
        "vector_store": "memory",
        "llm": "mock",
    }
    # readiness must not leak secrets / infra detail
    text = r.text.lower()
    assert "key" not in text
    assert "qdrant_url" not in text and "http://" not in text


def test_request_id_echoed_from_header():
    r = client.get("/health", headers={"x-request-id": "test-rid-123"})
    assert r.headers["x-request-id"] == "test-rid-123"


def test_plan_requires_a_valid_body():
    # Empty body fails validation (goal is required); planning is covered in test_rag.
    assert client.post("/api/v1/plan", json={}).status_code == 422
