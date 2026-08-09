# Visit — Iteration 1 Scope and Discovery

**Status:** Discovery Complete — Implementation-Ready (CPO/CTO approved §4's authorization clarification)

**Capability:** Visit (Field Operations, Roadmap Phase 4)

**Owner:** Engineering (Senior Engineer authority per standing mandate), reviewed by CPO/CTO

---

# 1. Visit vs. Attendance

**Explicitly distinct capabilities — `AttendanceEvent` is not reused or modified.**

- **HR Attendance (`AttendanceEvent`/`ReconciliationService`)**: `employee_id`, `shift_id`, `event_type` (`CLOCK_IN`/`CLOCK_OUT`/`BREAK_IN`/`BREAK_OUT`), `event_time`, `source`, `remarks`. Purpose: shift-based timekeeping feeding Payroll's attendance/leave deduction (`services/payroll/attendance_leave_deduction_calculator.py`). No store reference, no geolocation, Owner Only via a dedicated `AttendanceAuthorizationEvaluator`.
- **Field Operations Visit**: a field employee visiting a `Store`. Different real-world event, different purpose (operational execution monitoring, not payroll), different natural relationships (`store_id`, not `shift_id`).

Both happen to be reachable from the word "Attendance" in product documents (`06_PRODUCT_ROADMAP.md` Phase 4 lists "Attendance" and "Visit" as two separate module names; `02_PRODUCT_SCOPE.md` §6 "Field Execution" groups "Attendance"/"Check In"/"Check Out"/"GPS Validation"/"Selfie Verification" together, distinct from "Visit"). This document does not resolve what Field-Execution "Attendance" itself should be (a separate, not-yet-scoped question) — it only establishes that `Visit` is not that, and does not touch `AttendanceEvent` in any way.

---

# 2. Minimum Visit Aggregate

Evaluated against `02_PRODUCT_SCOPE.md` §6, `06_PRODUCT_ROADMAP.md` Phase 4, MVP Scope, and `03_TARGET_CUSTOMER.md`'s field-employee/supervisor/area-manager needs lists — the only sources that mention Visit at all.

| Field | Classification |
|---|---|
| `employee_id` | **Required** — every persona description ties Visit to a specific field employee (`03_TARGET_CUSTOMER.md`: "Field Employee... Needs: ... Visit"; "Area Manager... Needs: ... Visit monitoring") |
| `store_id` | **Required** — Visit is meaningless without the store visited; `Store` (Iteration 1) already exists as the natural target |
| `visited_at` | **Required** — a visit is inherently a point-in-time event; mirrors `Interview.scheduled_at`'s exact precedent shape |
| `notes` | **Required-shape, optional-value** — mirrors `Interview.notes`/`Offer.notes`'s exact precedent: a free-text field, nullable, present on every minimal event-record in this repository |
| GPS coordinates | **Explicitly deferred** — Product Scope names "GPS Validation" as its own item, implying a *validation* concept (accuracy/radius tolerance) this document cannot decide; no field added now (mirrors how `Store.latitude`/`longitude` were added only as plain nullable data, with zero validation logic — the same minimal-representation treatment would apply here later, but is not needed for Iteration 1's aggregate to exist) |
| Selfie / Photo | **Explicitly deferred** — "Selfie Verification"/"Photo Evidence" are named as distinct product concepts; `FileObject`/`api/files.py` already exists as a general file-storage capability and is the natural future attachment point (§7), not a field on `Visit` itself |
| Check-in / Check-out timestamps | **Explicitly deferred** — see §7 |
| Survey data | **Explicitly deferred** — Product Scope lists "Survey" as its own separate Field Execution item, not a `Visit` field |
| Competitor Activity / Display Audit / Stock Check / POSM Audit | **Explicitly deferred** — each named as its own distinct Field Execution item in `02_PRODUCT_SCOPE.md` §6; no evidence any belongs on `Visit` itself rather than as a related future record |
| Mission reference | **Resolved — not included.** See §3 |
| Visit status/lifecycle/approval state | **Explicitly deferred** — see §5 |

**Iteration 1 fields: `employee_id`, `store_id`, `visited_at`, `notes`. Nothing else.**

---

# 3. Mission Relationship

**Resolved from evidence: Visit does not reference Mission in Iteration 1 — independent, ad-hoc visits.**

Every product document that mentions both treats them as parallel, separate concepts, never nested:
- MVP Scope (`02_PRODUCT_SCOPE.md`): `Attendance, Visit, Mission` — three separate bullets.
- `03_TARGET_CUSTOMER.md` Field Employee persona: `Attendance, Check-in, Mission, Visit, Survey, Photo upload` — six separate needs, not "Mission (containing Visits)."
- `02_PRODUCT_SCOPE.md` §5 "Planning" groups `Mission Planning` with `Route Planning`/`Territory Assignment`/`Target Assignment`/`Schedule Planning` — an *assignment/scheduling* concern, structurally distinct from §6 "Field Execution" where `Visit` lives.

No document states a Visit must originate from a Mission, and `Mission Planning`'s grouping with `Territory Assignment` places it adjacent to the still-blocked Territory/Region/Area cluster (§6 below) — a further reason not to couple `Visit` to it. This is evidence-resolved, not a business-policy gap: `Visit` Iteration 1 has no `mission_id` field, no FK to any Mission concept (which does not exist in this repository). A future `Mission` capability, if built, can reference existing `Visit` rows non-invasively (FK on `Mission`'s side) without requiring any change here.

---

# 4. Authorization

**Owner Only is the correct precedent — with one clarification on what "reusing the mechanism exactly" requires.**

`Visit` has a natural owner field (`employee_id`, the field employee who made the visit) — structurally identical to `AttendanceEvent`/`Compensation`/`WorkSchedule`/`LeaveRequest`, all Owner Only, not to `Store`/`JobRequisition`/`PayrollRun`/`PerformanceReview` (no owner field, `RequireRole("admin")`).

**Repository evidence check on "reuse the existing mechanism, do not create a new evaluator":** every Owner Only capability in this repository — `AttendanceAuthorizationEvaluator`, `WorkScheduleAuthorizationEvaluator`, `CompensationAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`, `AllowanceAuthorizationEvaluator`, `DeductionAuthorizationEvaluator`, `PayslipAuthorizationEvaluator` — is implemented as its own one-line evaluator class (`resource.employee_id == context.employee_context.employee.id`) invoked through `AuthorizationService`/`AuthorizationRequest` via a private `_authorize` helper on the owning service. There is no lighter-weight Owner Only shape anywhere in this codebase; a dedicated evaluator class is not a new abstraction here, it is the mandatory, unavoidable shape of "the existing mechanism" itself, repeated identically seven times.

**Resolved — CPO/CTO approved:** `VisitAuthorizationEvaluator` is approved, mirroring `WorkScheduleAuthorizationEvaluator`'s exact shape (identical one-line rule, identical `AuthorizationService`/`AuthorizationRequest` plumbing, substituting `Visit` for `WorkSchedule`) — confirmed as reuse of the existing Owner Only mechanism, not new authorization abstraction or infrastructure.

---

# 5. Lifecycle

**Flat CRUD only.** No `planned → checked_in → in_progress → completed` state machine or any other status field. Nothing in product evidence requires it for Iteration 1; "Visit verification" (`03_TARGET_CUSTOMER.md`, Supervisor's needs) reads as supervisors reviewing/monitoring existing Visit records, not as a required status field on `Visit` itself — and even if a verification step is wanted later, this repository's existing `ApprovalService` (already handling `LeaveRequest`/`OvertimeRequest`/`Timesheet` approve/reject) is the precedented mechanism to extend, not a new lifecycle invented on `Visit`. Deferred, not decided, exactly as `PayrollRun`/`JobRequisition`/`Application` all shipped lifecycle-free before a later, separate decision added one where warranted.

---

# 6. Territory / Region / Area Boundary

- `Visit` does not introduce `Territory`, `Region`, or `Area`.
- `Visit` does not implement Organization Hierarchy.
- `Visit` does not resolve the Phase 3 Territory/Region/Area collision (`docs/architecture/capabilities/store/iteration-1-scope-and-implementation-plan.md` §6, still open).
- `Visit` has no dependency on ADR-009 being lifted — it consumes only already-implemented `HrEmployee` and `Store`.

---

# 7. Check In / Check Out / GPS / Photo

None are included in Iteration 1. Logical future attachment points, for whichever later iteration resolves the business policy each requires:

- **Check In / Check Out**: would most naturally become two additional `DateTime` columns directly on `Visit` (`checked_in_at`/`checked_out_at`) — no new entity — once a decision exists on whether they're mandatory, how a missed check-out is handled, etc.
- **GPS Validation**: would attach as `latitude`/`longitude` columns on `Visit` (mirrors `Store`'s exact precedent) plus a separate validation rule (acceptable-radius-from-`Store`) — the rule itself is business policy this document cannot supply.
- **Selfie / Photo Evidence**: would attach via a FK from a new child record (or `FileObject` directly, which already exists as this repository's general file-storage capability, `models/file_object.py`) to `Visit.id` — not a field on `Visit` itself.
- **Survey / Competitor Activity / Display Audit / Stock Check / POSM Audit**: each reads as its own future child record referencing `Visit.id`, the same "owned child" shape `Interview`/`Offer` have to `Application` — not fields on `Visit`.

None of these are generic infrastructure; each is a plain future FK or plain future column on the existing shape, no framework introduced.

---

# 8. Database / Architecture Shape

## Aggregate / Model

`Visit(BaseEntity)`, table `visits`:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | via `UUIDMixin` |
| `employee_id` | UUID, FK `hr_employees.id`, `ON DELETE RESTRICT` | required, the visiting field employee (owner) |
| `store_id` | UUID, FK `stores.id`, `ON DELETE RESTRICT` | required, the store visited |
| `visited_at` | `DateTime(timezone=True)` | required |
| `notes` | `String(2000)`, nullable | optional |

No uniqueness constraint — multiple visits per employee/store over time are expected and normal.

Indexes: `(employee_id)`, `(store_id)` — mirrors `Interview`'s single-FK index precedent, doubled for two FKs.

## Repository

`VisitRepository(BaseRepository[Visit])` — persistence-only. `paginate(...)`, filterable by `employee_id`/`store_id`, mirroring `AttendanceEventRepository`'s filter shape.

## Service

`VisitService` — mirrors `AttendanceEventService`'s structure (existence checks for `employee_id`/`store_id`, Owner Only authorization via `_authorize`, `list`/`list_paginated` scoped to the caller's own `employee_id`). Exceptions: `EmployeeNotFoundError`, `StoreNotFoundError`, `VisitAuthorizationDeniedError` (per §4).

## Authorization

Owner Only — `resource.employee_id == context.employee_context.employee.id`, per §4.

## API

`APIRouter(prefix="/visits", tags=["Visit"])` — `POST`, `GET` (own), `GET /paginated`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`. Same exception→HTTP mapping convention (404/403/422) as every prior capability.

## Migration

One migration, `create_visits_table`, chained onto the current head.

## Tests

Repository/service/API tests mirroring `test_attendance_event_*`'s exact structure (owner-only enforcement: own-resource allowed, other-employee's-resource denied; existence checks; CRUD happy path).

---

# Proposed Files (not yet created — discovery only)

- `docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md` — this document
- `services/api/src/eop_api/models/visit.py`
- `services/api/src/eop_api/repositories/visit.py`
- `services/api/src/eop_api/schemas/visit.py`
- `services/api/src/eop_api/services/visit.py`
- `services/api/src/eop_api/services/visit_authorization.py` (per §4)
- `services/api/src/eop_api/api/visits.py`
- `services/api/src/eop_api/main.py` (router registration)
- `services/api/src/eop_api/models/__init__.py` (model registration)
- One Alembic migration: `create_visits_table`
- `services/api/tests/test_visit_repository.py`, `test_visit_service.py`, `test_visits_api.py`

---

# Out of Scope

- Mission (§3) — not built, not referenced
- GPS coordinates/validation, Selfie/Photo Evidence, Check-in/Check-out timestamps (§7)
- Survey, Competitor Activity, Display Audit, Stock Check, POSM Audit (§7)
- Visit status/lifecycle/approval state (§5)
- Territory/Region/Area, Organization Hierarchy (§6)
- Any generic infrastructure beyond the existing Owner Only mechanism (§4)

---

# Validation/Test Strategy (for when implementation is authorized)

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted tests then full suite.

---

# Remaining Real Risks

1. Field Execution's own "Attendance" (§1) remains an unscoped, separate future item — not a risk to `Visit` itself, flagged so it isn't later assumed solved by this document.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §6 (Field Execution), §5 (Planning), MVP Scope
- `docs/product/06_PRODUCT_ROADMAP.md` Phase 4
- `docs/product/03_TARGET_CUSTOMER.md` (Field Employee/Supervisor/Area Manager needs)
- `services/api/src/eop_api/models/interview.py`, `offer.py` (minimal flat-event-record precedent)
- `services/api/src/eop_api/services/attendance_event.py`, `work_schedule.py`, `compensation.py` (Owner Only precedent)
- `services/api/src/eop_api/models/store.py`, `hr_employee.py` (FK targets)
- `docs/architecture/capabilities/store/iteration-1-scope-and-implementation-plan.md` §6 (Territory/Region/Area boundary, referenced not reopened)
