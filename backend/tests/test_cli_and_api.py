"""The command-line tool and the FastAPI health check."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.scraping.__main__ import main
from tests.conftest import FakeHttp, FakeResponse, fixture_html

PAGE_URL = "https://en.wikivoyage.org/wiki/Testville"


def test_cli_prints_summary_and_saves_json(make_fetcher, tmp_path, capsys):
    http = FakeHttp(
        {
            "https://en.wikivoyage.org/robots.txt": FakeResponse(404),
            PAGE_URL: FakeResponse(200, fixture_html("wikivoyage_city.html")),
        }
    )
    out = tmp_path / "testville.json"

    code = main(["Testville", "--no-districts", "--out", str(out)], fetcher=make_fetcher(http))

    printed = capsys.readouterr().out
    assert code == 0
    assert "Places found: 4" in printed
    assert "[see] Fire Museum" in printed
    saved = json.loads(out.read_text())
    assert saved["city"] == "Testville"
    assert len(saved["listings"]) == 4
    assert saved["listings"][0]["source_url"].startswith(PAGE_URL)


def test_cli_returns_error_code_when_nothing_found(make_fetcher, tmp_path, capsys):
    http = FakeHttp({"https://en.wikivoyage.org/robots.txt": FakeResponse(404)})
    code = main(["Nowhere", "--out", str(tmp_path / "x.json")], fetcher=make_fetcher(http))
    assert code == 1
    assert "Problems (1)" in capsys.readouterr().out


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
