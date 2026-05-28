from datetime import UTC, datetime

from crawler.reporter import RunReport, SourceReport, render_markdown


def test_render_markdown_includes_table_rows():
    report = RunReport(
        started_at=datetime(2026, 5, 28, 18, 0, tzinfo=UTC),
        sources=[
            SourceReport(
                name="artmap", extracted=234, new=12, updated=45,
                unchanged=177, errors=0, duration_s=42.1, failure=None,
            ),
            SourceReport(
                name="photo_sema", extracted=0, new=0, updated=0,
                unchanged=0, errors=1, duration_s=8.0,
                failure="selector .exhibition-card missing",
            ),
        ],
    )
    md = render_markdown(report)
    assert "artmap" in md and "234" in md
    assert "photo_sema" in md
    assert "selector .exhibition-card missing" in md


def test_render_markdown_no_failures_section_when_clean():
    report = RunReport(
        started_at=datetime(2026, 5, 28, 18, 0, tzinfo=UTC),
        sources=[
            SourceReport(name="artmap", extracted=1, new=1, updated=0,
                         unchanged=0, errors=0, duration_s=1.0, failure=None),
        ],
    )
    md = render_markdown(report)
    assert "### Failures" not in md
