# DairyTech AI

A desktop application for dairy farmers to manage farms, cows, daily records,
health, breeding, inventory, and finances — with an AI layer for health
scoring, yield forecasting, and plain-language recommendations.

## Status

All 10 core modules are complete:

0. Foundation — project skeleton, config, logging, database layer,
   base service/controller patterns, AI service interface, app shell
1. Authentication — roles (Admin/Farm Owner/Employee), permissions, login,
   forgot password
2. Farm Management — ownership-scoped farms, employee assignment, photos
3. Cow Management — profiles, QR codes, farm-scoped permissions
4. Daily Recording — per-cow daily logs, cow-profile snapshot sync
5. Milk Quality — per-session tests, quality grade suggestion
6. Health — diseases, vaccinations, treatments, doctor visits, reminders
7. Breeding — heat cycles, AI, pregnancy tests, calf births (a calf is a Cow)
8. Inventory — farm-scoped stock ledger, suppliers, purchases
9. Finance — income, expenses, non-duplicating monthly summary/profit
10. Dashboard — KPI cards aggregated across every farm a user can see

Still ahead: charts/data visualization, the AI feature set (health scoring,
yield forecasting, recommendations — the interface already exists in
`ai/ai_service.py`), PDF/Excel reports, and PyInstaller packaging.

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
