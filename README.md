# photo-exhibition-crawler

Crawler for Korean photography/video/camera exhibitions. Writes normalized data into Google Sheets.

## Quick start
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## CLI
```bash
crawler init-sheets               # Create the 5 worksheets with headers (idempotent)
crawler run <source>              # Crawl one source and upsert into the sheet
crawler dry-run <source>          # Crawl and print normalized output without writing
crawler run-all                   # Crawl every registered source
```

## Required environment variables (production)
- `GOOGLE_SERVICE_ACCOUNT_JSON` — service-account JSON contents
- `SHEET_ID` — target Google Sheet ID
- `KAKAO_REST_API_KEY` — Kakao Local REST API key
