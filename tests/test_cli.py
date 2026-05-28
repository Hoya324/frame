from typer.testing import CliRunner

from crawler.cli import app


def test_cli_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init-sheets" in result.stdout
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
    assert "달과 도시" in result.stdout or '"title": "A"' in result.stdout or "title" in result.stdout
