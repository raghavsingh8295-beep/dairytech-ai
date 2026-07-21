# DairyTech AI

A desktop application for dairy farmers to manage farms, cows, daily records,
health, breeding, inventory, and finances — with an AI layer for health
scoring, yield forecasting, and plain-language recommendations.

## Status

**Module 0 — Foundation** is complete: project skeleton, configuration,
logging, database layer, base service/controller patterns, and the
CustomTkinter application shell. No feature modules (Authentication, Farms,
Cows, ...) exist yet — they're built incrementally, one at a time.

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
ai/           AI service interface + implementations
charts/       matplotlib chart components (added with the Dashboard module)
reports/      PDF / Excel report generators
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
