"""Config parsing — especially CORS_ORIGINS from the environment, which must
accept a plain string (how docker-compose and real deploys set it), not only a
JSON array. Regression for a startup crash when CORS_ORIGINS was a bare string.
"""

from app.config import Settings


def test_cors_origins_plain_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    assert Settings(_env_file=None).cors_origins == ["http://localhost:3000"]


def test_cors_origins_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
    assert Settings(_env_file=None).cors_origins == ["http://a.com", "http://b.com"]


def test_cors_origins_json_array(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://x.com","http://y.com"]')
    assert Settings(_env_file=None).cors_origins == ["http://x.com", "http://y.com"]


def test_cors_origins_default(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == ["http://localhost:3000"]
