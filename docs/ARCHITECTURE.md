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

## Breeding (Module 7)

Four more plain-CRUD entities, same reasoning as Health: `HeatCycle`,
`Insemination`, `PregnancyCheck`, `CalfBirth`. `PregnancyCheck` may
reference the `Insemination` it confirms (mirroring Treatment/DoctorVisit
→ Disease from Module 6); `PregnancyCheckFormDialog`'s "Suggest" button
fills the expected delivery date as insemination date + 283 days (average
bovine gestation) — the same "computed suggestion, not a stored rule" as
Milk Quality's grade suggestion in Module 5.

This module finally implements the `Cow.pregnancy_status` /
`expected_delivery_date` sync promised back in Module 3, via two
different rules with different confidence levels:
- `PregnancyCheckController` uses the same "most recent wins" pattern as
  Module 4's weight sync — a backdated, edited pregnancy test never
  overrides a newer one's result.
- `CalfBirthController` treats a recorded birth as unconditional ground
  truth: the mother's status resets to Open with no expected delivery
  date regardless of test recency, since a birth having happened isn't
  something a pregnancy test's timing can contradict.

**"Calf Records" is not a separate schema.** A calf is a `Cow` — reusing
the exact Cow Management module built in Module 3 rather than
duplicating tag number, breed, photo, QR code, etc. on a parallel
"Calf" entity. `CalfBirth.calf_cow_id` is a nullable FK set only once the
calf is actually registered. The registration flow
(`BreedingView._register_calf_as_cow`) opens the existing `CowFormDialog`
pre-filled with breed/gender/birth date already known from the birth
event, via two small additive hooks on that dialog:
`initial_values` (pre-fills fields only in create mode, ignored when
editing) and `on_created` (fires with the new cow's ID, separately from
the existing `on_saved` refresh callback, so linking the birth record to
the cow doesn't require changing either of the two pre-existing call
sites that don't care about the new cow's ID).

## Inventory (Module 8)

The first module scoped to a **farm**, not a cow — it lives on Farm
Detail, not Cow Detail, since feed/medicine/equipment stock belongs to
the farm as a whole.

There is no stored "current stock" column. `InventoryItem` just defines
what a thing is (name, category, unit, reorder threshold); every change
to how much of it exists — a purchase, a day's feed usage, a manual
correction for spoilage or a miscount — is one row in the `StockMovement`
ledger, and current stock is `sum(quantity_change)` computed on read
(`StockMovementService.current_stock`). This is the same "computed, not
stored" reasoning used for total milk, cow/employee counts, and every
other running total in this app, applied to a domain where it matters
even more: a stored counter can silently drift from a ledger's truth, but
a ledger's sum never can.

`StockMovementController` exposes three intention-revealing methods —
`record_purchase`, `record_usage`, `record_adjustment` — instead of one
generic call taking a signed quantity. A farmer thinks "I bought 50kg" or
"I used 50kg", not "quantity_change = ±50"; each method normalizes the
sign before writing the row (purchases always stored positive, usage
always negative, adjustments as entered), so the database column itself
is always unambiguous regardless of which UI action produced it.

Deliberately not validated: a usage or adjustment is allowed to take
computed stock negative. That's a real, legitimate situation (a farmhand
logs feed usage before someone else logs the matching purchase) rather
than a data-integrity violation, so it's something the UI can flag —
`InventoryItemEntry.is_low_stock` — not something the controller blocks.

"Suppliers" get their own entity rather than a free-text field on
`StockMovement`, since a farm reorders from the same handful of
suppliers repeatedly and picking one from a list beats retyping a name
that might not match next time.

## Finance (Module 9)

The spec's "Medicine Cost" and "Feed Cost" line items are **not** manual
`Expense` entries — those costs already exist as real data from earlier
modules (`Treatment.cost` / `Vaccination.cost` in Health,
`StockMovement.unit_cost` purchases in Inventory), so re-entering them
here would double-count. `ExpenseCategory` deliberately has no Feed or
Medicine option at all — the temptation to double-enter is designed out
at the schema level, not just documented. `FinanceSummaryService`
aggregates them fresh at report time instead, scoped to a farm and date
range, reading Health's and Inventory's tables directly (it isn't a
`BaseService[Model]` since it owns no entity of its own — it's a
reporting query, not a CRUD surface).

Two aggregation choices worth calling out:
- **Feed cost** comes only from Inventory purchases with a recorded unit
  cost; a purchase logged without one contributes nothing, because there
  is no cost to attribute — silently guessing would be worse than
  omitting it.
- **Medicine cost** comes from Health's `Treatment.cost` and *given*
  `Vaccination.cost` (`date_given` set), not from Inventory medicine
  purchases — stock bought this month might not be used until next
  month, so administration date is the right one for "when was this
  expense incurred," not purchase date.

Equipment and breeding costs are deliberately **not** auto-aggregated,
even though `StockMovement` and `Insemination.cost` track them —
unlike feed and medicine, the spec doesn't name them as Finance line
items, and equipment purchases in particular are often one-off capital
expenses a farmer would rather categorize manually (`ExpenseCategory.EQUIPMENT`)
than have silently rolled into an automatic figure.

Viewing Income/Expense/the Monthly Summary requires `MANAGE_FINANCE`,
unlike Health/Breeding/Inventory where any farm-assigned Employee can
view (just not write). Financial figures are more sensitive than herd or
stock data, and Employees don't hold this permission — `FarmDetailView`
hides the entire Finance section for roles that can't open it, rather
than showing a button that immediately errors.

## Dashboard (Module 10)

Replaces the placeholder `HomeView` from Module 0 — that file is gone;
`DashboardView` is the real post-login landing screen now, and the
sidebar/method are renamed from Home/`_show_home` to Dashboard/
`_show_dashboard` throughout.

`DashboardController` reuses `FarmController`'s exact visibility rule
(Admin: all farms, Farm Owner: owned, Employee: assigned) rather than
inventing a separate one, then aggregates KPIs across that farm set with
new single-query methods on the relevant services —
`CowService.count_by_health_status` / `count_upcoming_births`,
`DailyRecordService.sum_milk_for_farms_on_date`,
`VaccinationService.count_due_for_farms` — instead of looping per farm or
per cow in the controller. Cow and daily-record counts can get large
enough that an N+1 loop would matter; farm counts can't, so Finance is
the deliberate exception: it loops `FinanceSummaryController` once per
visible farm and sums the results rather than duplicating Module 9's
aggregation SQL for a multi-farm case that will rarely exceed a handful
of farms.

"Sick Cows" means *not Healthy* — every other `HealthStatus` (Sick, Under
Treatment, Critical, Quarantined) rolls into one "needs attention" count,
matching the two cards the spec actually asks for rather than a full
status breakdown. "Birth Alerts" reuses `Cow.expected_delivery_date`
directly (synced by Breeding in Module 7) rather than tracking anything
new, and deliberately has no lower bound — an overdue delivery date
still counts, since that's exactly when the alert matters most.

Revenue/Expenses/Profit cards are omitted entirely (not shown-then-blocked)
for roles without `MANAGE_FINANCE`, the same pattern `FarmDetailView`
established for the Finance section itself.

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
