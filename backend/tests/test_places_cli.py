"""The `python -m app.places` command."""

from __future__ import annotations

from app.places.__main__ import main
from app.scraping.models import ScrapeResult
from tests.factories import WHEN, raw

HERE = {"lat": 35.6895, "lng": 139.6917}


def write_scrape(tmp_path, listings):
    path = tmp_path / "scrape.json"
    result = ScrapeResult(source="wikivoyage", city="Testville", started_at=WHEN, listings=listings)
    path.write_text(result.model_dump_json(), encoding="utf-8")
    return path


LISTINGS = [
    raw("Fire Museum", hours="9-5", **HERE),
    raw(
        "Fire Museum",
        source_url="https://en.wikivoyage.org/wiki/Testville/Annex#Fire_Museum",
        **HERE,
    ),
    raw("Pasta House", section="eat", price="¥1200"),
    raw("x").model_copy(update={"name": "--"}),
]


def test_dry_run_reports_without_a_database(tmp_path, capsys):
    code = main(["ingest", str(write_scrape(tmp_path, LISTINGS)), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Kept 3 of 4" in out and "dropped 1: no usable name" in out
    assert "Duplicates removed: 1" in out and '"Fire Museum" absorbed "Fire Museum"' in out
    assert "Dry run: nothing was saved." in out


def test_ingest_show_and_stats(tmp_path, engine, capsys):
    assert main(["ingest", str(write_scrape(tmp_path, LISTINGS))], engine=engine) == 0
    assert "Database: 2 new, 0 updated, 0 removed." in capsys.readouterr().out

    assert main(["show", "testville", "--category", "eat"], engine=engine) == 0
    shown = capsys.readouterr().out
    assert "[eat] Pasta House" in shown and "¥1200" in shown
    assert "https://en.wikivoyage.org/wiki/Testville#Pasta_House" in shown  # source link
    assert "fetched 2026-11-08" in shown

    assert main(["stats"], engine=engine) == 0
    stats = capsys.readouterr().out
    assert "Testville" in stats and "with coordinates" in stats


def test_show_with_no_results_says_so(engine, capsys):
    assert main(["show", "Nowhere"], engine=engine) == 1
    assert "No places found" in capsys.readouterr().out


def test_missing_file_is_a_clean_error(tmp_path, capsys):
    assert main(["ingest", str(tmp_path / "nope.json"), "--dry-run"]) == 2
    assert "File not found" in capsys.readouterr().err


def test_init_db_reset_erases_places(tmp_path, engine, capsys):
    main(["ingest", str(write_scrape(tmp_path, LISTINGS))], engine=engine)
    assert main(["init-db", "--reset"], engine=engine) == 0
    capsys.readouterr()
    assert main(["stats"], engine=engine) == 1


def test_enrich_command_applies_changed_rules_to_saved_places(tmp_path, engine, capsys):
    from app.places import repo
    from app.places.db import session_scope
    from tests.factories import place

    stale = place(
        "Zenpukuji Park", tags=["nightlife"], indoor=True
    )  # as saved by an older rule set
    with session_scope(engine) as session:
        repo.save_places(session, [stale])

    assert main(["enrich"], engine=engine) == 0
    assert "Checked 1 places; 1 changed." in capsys.readouterr().out
    with session_scope(engine) as session:
        (fixed,) = repo.search_places(session)
    assert fixed.tags == ["nature", "outdoors"] and fixed.indoor is False

    assert main(["enrich"], engine=engine) == 0  # nothing left to fix
    assert "1 places; 0 changed" in capsys.readouterr().out


def test_stats_and_show_report_the_new_fields(tmp_path, engine, capsys):
    listings = [
        raw(
            "Pasta House",
            section="eat",
            hours="Daily 11:00-22:00",
            price="¥1,200",
            subsection="Budget",
        )
    ]
    main(["ingest", str(write_scrape(tmp_path, listings))], engine=engine)
    capsys.readouterr()

    main(["stats"], engine=engine)
    stats = capsys.readouterr().out
    for label in ("price level", "interest tags", "indoor/outdoor", "hours understood"):
        assert f"with {label}" in stats and "1 / 1  (100%)" in stats

    main(["show", "Testville"], engine=engine)
    shown = capsys.readouterr().out
    assert "[low] ¥1,200" in shown and "tags     food" in shown and "indoor   indoor" in shown
    assert "hours*   Mo-Su 11:00-22:00" in shown


def test_out_of_date_tables_give_a_helpful_message(tmp_path, engine, capsys):
    from sqlalchemy import text

    main(["ingest", str(write_scrape(tmp_path, LISTINGS))], engine=engine)
    with engine.begin() as conn:  # pretend the table was made by an older version
        conn.execute(text("ALTER TABLE places DROP COLUMN price_estimate"))
    capsys.readouterr()

    assert main(["show", "Testville"], engine=engine) == 2
    # Postgres reports a missing column as ProgrammingError (we explain the fix);
    # SQLite reports it as OperationalError (we point at DATABASE_URL).
    err = capsys.readouterr().err
    assert "init-db --reset" in err or "no such column" in err
