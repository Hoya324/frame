"""Typer CLI: init-sheets, run, dry-run, run-all."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, date, datetime

import typer

from crawler.models import SourceName
from crawler.normalize import normalize_exhibition
from crawler.pipeline import run_source
from crawler.reporter import RunReport, render_markdown
from crawler.sources.base import get_source

log = logging.getLogger(__name__)

app = typer.Typer(help="Korean photo/video/camera exhibition crawler.")


def _today() -> date:
    return datetime.now(UTC).date()


def _build_repo():
    from crawler.sinks.gspread_repo import GspreadRepository
    return GspreadRepository.from_env()


def _build_geocoder():
    from crawler.enrich.geocoder import KakaoGeocoder
    return KakaoGeocoder.from_env()


@app.command("init-sheets")
def init_sheets_cmd() -> None:
    """Create the 5 worksheets with headers (idempotent)."""
    from crawler.sinks.init_sheets import init_sheets
    repo = _build_repo()
    init_sheets(repo)
    typer.echo("init-sheets: done")


@app.command("run")
def run_cmd(source: str) -> None:
    """Crawl one source and upsert into the sheet."""
    try:
        src = SourceName(source)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    extractor_cls = get_source(src)
    report = run_source(
        extractor=extractor_cls(),
        repo=_build_repo(),
        geocoder=_build_geocoder(),
        today=_today(),
    )
    run_report = RunReport(started_at=datetime.now(UTC), sources=[report])
    typer.echo(render_markdown(run_report))
    if report.failure:
        raise typer.Exit(code=1)


@app.command("dry-run")
def dry_run_cmd(source: str) -> None:
    """Crawl one source and print normalized rows without writing."""
    try:
        src = SourceName(source)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    extractor_cls = get_source(src)
    extractor = extractor_cls()
    for raw in extractor.crawl():
        try:
            n = normalize_exhibition(raw)
            typer.echo(json.dumps(n.model_dump(mode="json"), ensure_ascii=False))
        except Exception as exc:
            typer.echo(f"# skip: {exc}", err=True)


@app.command("run-all")
def run_all_cmd() -> None:
    """Crawl every registered source. Per-source failures are isolated."""
    from crawler.pipeline import recompute_stale_status
    from crawler.reporter import SourceReport
    from crawler.sources.base import all_sources
    repo = _build_repo()
    geocoder = _build_geocoder()
    today = _today()
    reports = []
    for src, extractor_cls in all_sources().items():
        try:
            report = run_source(
                extractor=extractor_cls(),
                repo=repo,
                geocoder=geocoder,
                today=today,
                recompute_status=False,  # done once after the loop
            )
        except Exception as exc:  # site-level isolation
            report = SourceReport(
                name=src.value, extracted=0, new=0, updated=0,
                unchanged=0, errors=1, duration_s=0.0,
                failure=f"{type(exc).__name__}: {exc}",
            )
        reports.append(report)
    try:
        recompute_stale_status(repo, today)
    except Exception as exc:
        log.warning("global status recompute failed: %s", exc)
    run_report = RunReport(started_at=datetime.now(UTC), sources=reports)
    md = render_markdown(run_report)
    typer.echo(md)
    # also dump to out/report.md for CI artifacts
    import os
    os.makedirs("out", exist_ok=True)
    with open("out/report.md", "w", encoding="utf-8") as f:
        f.write(md)
    if any(r.failure for r in reports):
        sys.exit(1)


@app.command("backfill-geocodes")
def backfill_geocodes_cmd() -> None:
    """Re-geocode every venue with missing coordinates (one-time recovery)."""
    from crawler.enrich.backfill import backfill_geocodes

    repo = _build_repo()
    geocoder = _build_geocoder()
    report = backfill_geocodes(repo, geocoder)
    typer.echo(
        f"backfill: total={report.total_venues}, needed={report.needed_geocoding}, "
        f"geocoded={report.geocoded}, no_match={report.no_match}, errors={report.errors}"
    )
    if report.errors > 0 and report.geocoded == 0:
        raise typer.Exit(code=1)


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
