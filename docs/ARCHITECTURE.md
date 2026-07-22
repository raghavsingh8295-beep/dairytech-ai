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

Rollback logging distinguishes expected from unexpected failures:
exceptions deriving from `utils.exceptions.AppError` (e.g. `AuthenticationError`
— wrong password, duplicate username, permission denied) are logged at
WARNING with no stack trace, since they're normal user-facing outcomes, not
bugs. Anything else is logged at ERROR with a full traceback. Every future
controller-layer exception should subclass `AppError` to get this for free.

SQLite foreign key enforcement is off by default at the driver level — a
connection-level `PRAGMA foreign_keys=ON` is installed via an SQLAlchemy
event listener so relationship integrity is actually enforced during
development, matching what PostgreSQL will do in production.

## Soft deletes

Farm, cow, health, and financial records are never physically deleted by
default — `SoftDeleteMixin` adds an `is_active` flag, and `BaseService.delete()`
flips it instead of removing the row. This preserves history for reports
and AI trend analysis. A model opts out simply by not using the mixin.

## Farm ownership & visibility

A farm's owner is a real `User` account (role `FARM_OWNER`), not a free-text
"owner name" field — this is a deliberate upgrade over the original spec so
the name can never drift out of sync with the account, and so visibility can
be enforced in code. `FarmController` scopes every query by the acting
user's role: Admin sees all farms, a Farm Owner sees only farms they own,
an Employee sees only farms they're assigned to (via the `farm_employees`
join table). This scoping is the foundation every later module (Cows,
Health, Finance, ...) will reuse for its own farm-level data isolation —
important both for today's multi-role desktop app and for the eventual
multi-tenant SaaS version.

`FarmEmployee` is a many-to-many join table rather than a `farm_id` column
on `User`, for two reasons: it avoids a circular foreign key between
`users` and `farms` (SQLite handles a third table referencing both far more
reliably than two tables referencing each other), and it lets an employee
be assigned to more than one farm without a schema change later.

"Number of Employees" and "Number of Cows" are intentionally *not* stored
columns — they're computed on read (`FarmService.count_employees`,
`CowService.count_for_farm`). A stored count can silently drift from
reality; a computed one can't.

## Cow Management (Module 3)

A `Cow` belongs to exactly one `Farm` (`farm_id`), so it reuses the exact
same visibility/permission rule as farms — Admin sees all, a Farm Owner
sees cows on farms they own, an Employee sees cows on farms they're
assigned to. Rather than duplicate that logic in `CowController`, it was
extracted out of `FarmController` into `controllers/farm_access.py`
(`ensure_can_access_farm`, `get_farm_or_raise`), which both controllers —
and every future farm-scoped module (Health, Breeding, Inventory, Finance,
Daily Recording) — now share.

`Cow.tag_number` (the farmer-facing ear-tag ID) is unique per farm, not
globally — different farms can both have a "#105". `Cow.rfid_number` and
`Cow.qr_code_value` *are* globally unique, since they identify a physical
tag/chip. The QR value itself is a random opaque token (`utils/qr_code.py`),
not the database row ID — printing an internal primary key onto a physical
tag would leak schema details and break if the ID space is ever
reorganized (e.g. during a future Postgres migration).

`Cow.health_status` and `Cow.pregnancy_status` are current-state snapshots
on the profile card, not event logs — the Health and Breeding modules will
own the detailed history (treatments, vaccinations, heat cycles, AI dates)
and are expected to keep these snapshot fields in sync when they're built.
Likewise `Cow.weight_kg` is the profile's reference weight, not a time
series — the Daily Recording module owns weight-over-time for graphs/AI
trend analysis.

## Daily Recording (Module 4)

One `DailyRecord` per (cow, date) — enforced by a unique constraint, not
just application logic. `DailyRecordController.save_record` upserts:
there's no separate create/edit call, because a farmer reopening today's
entry to add the evening milk reading after already logging the morning
one is the normal flow, not an edge case. `total_milk_liters` is computed
from morning+evening on read, same reasoning as every other computed field
in this codebase.

This module is the first consumer of the `RECORD_DAILY_DATA` permission
defined all the way back in Module 1 — an Employee can log data for a farm
they're assigned to but cannot touch the Cow master record (that still
needs `MANAGE_COWS`, which Employees don't have).

Closing a loop noted in Module 3: when a saved record includes a weight or
pregnancy-status observation *and it's the most recent record for that
cow* (`DailyRecordController._sync_cow_snapshot`), it's written back onto
`Cow.weight_kg` / `Cow.pregnancy_status` so the profile card always
reflects the latest known reading without a farmer having to update it in
two places. Backdating an old, non-latest record never overwrites a newer
snapshot.

## Milk Quality (Module 5)

`MilkQualityTest` is a separate entity from `DailyRecord`, not extra
columns on it: quality tests are per milking *session* (morning, evening,
or a composite sample) and aren't necessarily logged on the same cadence
as daily volume, so its identity is `(cow, date, session)` rather than
just `(cow, date)`. It reuses `RECORD_DAILY_DATA` rather than introducing
a new permission — the same people who log milk volume log its quality;
a finer split can be introduced later if that stops being true.

`quality_grade` is a stored, farmer-editable field (a lab slip might
assign it directly), but `MilkQualityController.suggest_grade` offers a
heuristic suggestion from fat%/SNF%/bacteria count that the UI's "Suggest"
button can fill in. The thresholds are explicitly documented as a
starting point, not a regulatory standard — real grading cutoffs vary by
country and cooperative.

Same upsert as Daily Recording, same risk, same fix: `MilkQualityFormDialog`
detects a collision with an existing test (on date or session change, and
again at submit as a safety net) and reloads its full state before
allowing a save, so a targeted edit can never silently blank out
previously recorded metrics.

## Health (Module 6)

Four entities, not one: `Disease`, `Vaccination`, `Treatment`,
`DoctorVisit`. None of them are date-uniqueness-constrained per cow — a
cow can have several vaccinations, treatments, or diagnoses over its
life — so unlike Daily Recording / Milk Quality there's no upsert-by-date
key here, just plain CRUD rows and no collision-detection dance needed.

`Treatment` and `DoctorVisit` optionally reference the `Disease` they
relate to (`disease_id`), so a disease's full story — diagnosis, vet
visits, treatments, recovery — can be viewed together. "Recovery History"
isn't its own table; it's simply `Disease` rows with `status=RECOVERED`
and a `recovery_date`. `Vaccination` similarly needs no separate
"schedule" table: a future dose is just a row with `date_given` still
null, and "giving" it is editing that same row rather than a distinct
action.

This module finally implements the `Cow.health_status` sync promised back
in Module 3: `DiseaseController._sync_cow_health_status` derives the
cow's overall status from its currently unresolved diseases (any active
severe disease → Critical, any active disease → Sick, any recovering →
Under Treatment, otherwise → Healthy) every time a disease is created,
edited, or removed. It deliberately never overwrites `QUARANTINED` — that
status is a manual biosecurity decision, orthogonal to disease severity,
and would otherwise get silently clobbered by the next unrelated disease
edit.

"Automatic Reminder" is an on-demand due/overdue query
(`VaccinationController.list_due_for_cow`,
`DoctorVisitController.list_upcoming_follow_ups_for_cow`), surfaced as a
banner on the Health screen — not an OS push notification, since a
desktop MVC app has no background service to deliver one. These same
per-cow query methods are what a future Dashboard module will call across
every cow to build its "Upcoming Vaccinations" KPI card, rather than
needing a separate aggregation mechanism.

Reused `_require_cow`, now used a seventh time across Cow/DailyRecord/
MilkQuality/the four Health controllers, was finally worth centralizing:
`get_cow_or_raise` moved into `controllers/farm_access.py` alongside
`get_farm_or_raise`, and all seven call sites were switched over.

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
