"""Markdown crawl report rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SourceReport:
    name: str
    extracted: int
    new: int
    updated: int
    unchanged: int
    errors: int
    duration_s: float
    failure: str | None


@dataclass
class RunReport:
    started_at: datetime
    sources: list[SourceReport]


def render_markdown(report: RunReport) -> str:
    started = report.started_at.strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"## Crawl Report — {started}",
        "",
        "| source | extracted | new | updated | unchanged | errors | duration |",
        "|--------|-----------|-----|---------|-----------|--------|----------|",
    ]
    for s in report.sources:
        lines.append(
            f"| {s.name} | {s.extracted} | {s.new} | {s.updated} | "
            f"{s.unchanged} | {s.errors} | {s.duration_s:.1f}s |"
        )
    failures = [s for s in report.sources if s.failure]
    if failures:
        lines += ["", "### Failures"]
        for f in failures:
            lines.append(f"- **{f.name}**: {f.failure}")
    return "\n".join(lines) + "\n"
