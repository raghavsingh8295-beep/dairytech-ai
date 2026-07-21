# Architecture

## Layering (MVC, strictly enforced)

```
ui/ (View)  ->  controllers/ (Controller)  ->  services/ (data access)  ->  models/ (ORM entities)
```

- **Views** (`ui/`) build the CustomTkinter widgets and call controller
  methods. They never import `database/` or `services/` directly, and never
  hold a database session.
- **Controllers** (`controllers/`) orchestrate one or more services inside a
  single `get_db_session()` transaction and return plain data (dicts,
  dataclasses, or detached model instances) to the view.
- **Services** (`services/`) are the only layer that talks to SQLAlchemy.
  Every service inherits `BaseService`, a generic repository giving it
  `create` / `get_by_id` / `get_all` / `update` / `delete` for free.
- **Models** (`models/`) are SQLAlchemy declarative entities, composing
  `TimestampMixin` and `SoftDeleteMixin` from `models/mixins.py`.

This boundary is what makes two things possible later without a rewrite:
1. **SQLite → PostgreSQL**: only `DATABASE_URL` in `.env` changes. No
   service, controller, or view references SQLite-specific behavior.
2. **Desktop → SaaS**: controllers and services have no CustomTkinter
   import anywhere. A future web API layer could sit directly on top of the
   existing controllers.

## Database sessions

`database/session.py` exposes `get_db_session()` as a context manager:
commits on success, rolls back and logs on exception, always closes. No
other module should call `SessionLocal()` directly.

SQLite foreign key enforcement is off by default at the driver level — a
connection-level `PRAGMA foreign_keys=ON` is installed via an SQLAlchemy
event listener so relationship integrity is actually enforced during
development, matching what PostgreSQL will do in production.

## Soft deletes

Farm, cow, health, and financial records are never physically deleted by
default — `SoftDeleteMixin` adds an `is_active` flag, and `BaseService.delete()`
flips it instead of removing the row. This preserves history for reports
and AI trend analysis. A model opts out simply by not using the mixin.

## AI Service Layer

`ai/ai_service.py` defines `AIServiceInterface`, an ABC covering every AI
capability from the spec (health score, milk yield forecast, disease risk,
abnormal temperature detection, pregnancy success prediction, and
plain-language recommendations via the `Recommendation` dataclass).

`AIService` is a concrete placeholder implementing that interface —
controllers can depend on and instantiate it today. Each method currently
raises `NotImplementedError` and gets a real body (starting with
statistical/rule-based logic, later trainable models) as its owning feature
module is built. Because callers depend on the interface, swapping the
implementation later requires no caller changes.

## Configuration

`config/settings.py` is the single place reading environment variables
(via `.env`, loaded with `python-dotenv`). Nothing else in the codebase
calls `os.environ` — this keeps every configurable value discoverable and
keeps the PostgreSQL migration a one-line change.

## Logging

`utils/logger.py` configures one root logger (`dairytech`) with a rotating
file handler (`logs/dairytech.log`, 5MB x 5 backups) and a console handler.
Every module gets a namespaced child logger via `get_logger(__name__)`.

## Why not build models/services for every entity yet?

Per the agreed development strategy, entity models (User, Farm, Cow, ...)
are introduced with their owning feature module, not all at once in the
foundation. This keeps each module reviewable and testable in isolation.
The infrastructure built here (mixins, base service, base controller,
session handling) is what every future module composes.
