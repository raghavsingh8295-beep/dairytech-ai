# DairyTech AI

A desktop application for dairy farmers to manage farms, cows, daily records,
health, breeding, inventory, and finances — with an AI layer for health
scoring, yield forecasting, and plain-language recommendations.

## Current implementation

The repository includes a CustomTkinter desktop application and a FastAPI backend
for the sibling `../trimTAB` React Native / Expo mobile client.

Implemented modules include authentication, farm/cow management, daily records,
milk quality, health, breeding, inventory, finance and dashboard summaries.
The API additionally exposes herd analytics, cow insights and a book-grounded
assistant. Assistant generation and photo uploads require their configured services.
The `charts/` and `reports/` directories remain placeholders; desktop packaging
and a full phone acceptance pass are still needed.

## Mobile API

```sh
venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

For a physical phone on the same trusted network, bind to `0.0.0.0` and configure
the mobile client's `EXPO_PUBLIC_API_BASE_URL` with a reachable backend URL.
The Render blueprint is in `render.yaml`; configure `DATABASE_URL` and
`JWT_SECRET_KEY` in the deployment environment. Do not commit credentials.

Authenticated requests reload current account status and role from the database.
A deactivated/deleted account is rejected on its next request.

### Daily record API contract

`POST /cows/{cow_id}/records` upserts by date. Omitted fields retain their existing
values; explicit JSON null clears an optional field. This protects desktop-only
fields when mobile submits its smaller form. Desktop controller callers retain
the existing full-overwrite behavior unless they supply `provided_fields`.

Clients may include `expected_updated_at` with the version returned by a prior
read, or null to assert that no record exists yet. A mismatch returns HTTP 409.
PostgreSQL writes acquire a cow-row lock before reading the record version.
Confirmed records remain locked. Clients omitting the version field retain legacy
behavior; deploy this backend before releasing the updated mobile client.

### Regression checks

```sh
venv/bin/python -m unittest tests.test_review_fixes -v
```

Tests use an isolated in-memory database. They cover account changes, invalid
numbers, omitted versus explicitly cleared fields, conflicts and confirmed records.

## Setup

```bash
cd dairytech_ai
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

On first run this creates `database/dairytech.db` (SQLite) and opens the
application window.

## Configuration

Copy `.env.example` to `.env` to override defaults (database URL, log
level, theme). Nothing is required for local development — sensible
defaults are built in.

## Project layout

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design
rationale (MVC boundaries, service/repository pattern, AI service layer).

```
config/       app settings
database/     SQLAlchemy engine, session, init
models/       ORM entities (one module per feature, added incrementally)
services/     data-access layer (repository pattern) — DB-agnostic
controllers/  business logic orchestration — no UI, no raw SQL
ai/           AI service interface (implementations arrive with the AI module)
charts/       matplotlib chart components (not yet built)
reports/      PDF / Excel report generators (not yet built)
ui/           CustomTkinter views, components, styles
utils/        logging, validators, helpers
tests/        automated tests
assets/       icons, images, fonts
exports/      generated reports/exports (gitignored)
logs/         rotating log files (gitignored)
```

## Packaging

PyInstaller packaging instructions will be added once the application has
its first complete set of user-facing modules.
