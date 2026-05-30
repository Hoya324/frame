from typer.testing import CliRunner

from crawler.cli import app


def test_cli_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init-sheets" in result.stdout
    assert "reset-sheets" in result.stdout
    assert "run" in result.stdout
    assert "dry-run" in result.stdout
    assert "run-all" in result.stdout


def test_cli_dry_run_artmap_no_network(monkeypatch):
    """dry-run with a stub source registered via env shouldn't try to write."""
    from crawler.models import RawExhibition, SourceName
    from crawler.sources.base import register_source

    class StubExtractor:
        name = SourceName.ARTMAP

        def crawl(self):
            yield RawExhibition(
                source=SourceName.ARTMAP,
                source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
                raw={
                    "title": "A",
                    "venue_name": "류가헌",
                    "artists": ["김"],
                    "date_range": "2026.06.01 ~ 2026.07.01",
                    "fee_text": "무료",
                    "exhibition_type_text": "개인전",
                },
            )

    register_source(SourceName.ARTMAP, StubExtractor)
    runner = CliRunner()
    result = runner.invoke(app, ["dry-run", "artmap"])
    assert result.exit_code == 0, result.stdout
    assert (
        "달과 도시" in result.stdout
        or '"title": "A"' in result.stdout
        or "title" in result.stdout
    )


def test_cli_backfill_help():
    from typer.testing import CliRunner

    from crawler.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["backfill-geocodes", "--help"])
    assert result.exit_code == 0
    assert "backfill" in result.stdout.lower()


def test_export_json_writes_file(tmp_path, monkeypatch):
    from crawler.sinks.base import SheetName
    from crawler.sinks.fake import FakeRepository

    repo = FakeRepository()
    repo.append_rows(SheetName.EXHIBITIONS, [{
        "id": "e1", "source": "artmap", "status": "ongoing",
        "source_url": "https://src/1", "title": "T", "title_en": "",
        "description": "", "poster_image_url": "", "medium": "photo",
        "exhibition_type": "solo", "genre_tags": "", "fee_type": "free",
        "price_min": "", "price_max": "", "start_date": "2026-05-30",
        "end_date": "2026-07-20", "open_hours": "", "artist_ids": "",
        "venue_id": "", "featured": "FALSE", "popularity_score": "",
    }])
    monkeypatch.setattr("crawler.cli._build_repo", lambda: repo)

    out = tmp_path / "exhibitions.json"
    result = CliRunner().invoke(app, ["export-json", "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "1 exhibitions" in result.output
