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


def test_hard_failures_excludes_soft_fail_sources():
    """gallery_lux fails every CI crawl (origin geo-blocks foreign datacenter
    IPs). Its failure is tolerated and must not be counted as a run failure,
    while any other source's failure still is."""
    from crawler.cli import _hard_failures
    from crawler.reporter import SourceReport

    def _rep(name, failure):
        return SourceReport(
            name=name, extracted=0, new=0, updated=0, unchanged=0,
            errors=1 if failure else 0, duration_s=0.0, failure=failure,
        )

    # Only gallery_lux failed → no hard failures.
    reports = [_rep("artmap", None), _rep("gallery_lux", "blocked: 770 bytes")]
    assert _hard_failures(reports) == []

    # A non-soft source failing → counted.
    reports = [_rep("gallery_lux", "blocked"), _rep("goeun", "selector drift")]
    hard = _hard_failures(reports)
    assert [r.name for r in hard] == ["goeun"]


def test_backfill_translations_invokes_backfill(monkeypatch):
    import crawler.cli as cli
    from crawler.enrich.translate import TranslationReport

    calls = {}

    def fake_backfill(repo, translator, max_seconds=None, reset=False):
        calls["called"] = True
        calls["max_seconds"] = max_seconds
        calls["reset"] = reset
        return TranslationReport(rows_seen=3, rows_patched=1, fields_translated=2, errors=0)

    monkeypatch.setattr(cli, "_build_repo", lambda: object())
    monkeypatch.setattr(cli, "_build_translator", lambda: object())
    monkeypatch.setattr("crawler.enrich.translate.backfill_translations", fake_backfill)

    cli.backfill_translations_cmd(max_seconds=900.0, reset=False)
    assert calls["called"] is True
    assert calls["max_seconds"] == 900.0
    assert calls["reset"] is False  # incremental by default
    # 0 disables the budget -> run to completion
    cli.backfill_translations_cmd(max_seconds=0.0, reset=False)
    assert calls["max_seconds"] is None
    # --reset rebuilds stale translations (one-shot full backfill)
    cli.backfill_translations_cmd(max_seconds=0.0, reset=True)
    assert calls["reset"] is True


def test_build_translator_prefers_gemini_when_key_set(monkeypatch):
    import crawler.cli as cli
    from crawler.enrich.translator import GeminiTranslator

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    assert isinstance(cli._build_translator(), GeminiTranslator)


def test_build_translator_falls_back_to_argos_without_key(monkeypatch):
    import crawler.cli as cli
    from crawler.enrich.translator import ArgosTranslator

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert isinstance(cli._build_translator(), ArgosTranslator)


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
