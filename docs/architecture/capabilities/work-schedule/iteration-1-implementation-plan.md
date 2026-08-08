# Work Schedule — Iteration 1 Implementation Plan

**Status:** Authorized — Gaps Resolved Under CPO/CTO Directive

**Capability:** Work Schedule

**Owner:** Engineering (CPO/CTO-directed resolution)

**Supersedes:** `implementation-plan.md`'s "Not Authorized" verdict, for Iteration 1 scope only. Does not reopen or reverse any `Accepted`/`Approved` finding in `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, or `capability-boundary-analysis.md` — every decision below either directly applies an already-accepted finding or resolves a genuinely open item using explicit business/product authority granted for this purpose.

---

# 0. Authority and Method

The prior governance chain correctly identified fifteen Blocking Unknowns and six Missing-Concepts classifications, and correctly declined to resolve product/business-shaped questions without authority to do so (`architecture-gap-analysis.md` §6, §9). That authority has now been explicitly granted. Two things changed since that chain was written, both directly load-bearing here:

1. **Effective Dating now exists.** `EffectiveDatingMixin` (`db/mixins.py`) and `EffectiveDatingEvaluator` (`services/effective_dating_evaluator.py`) were built and accepted after `architecture-gap-analysis.md`/`architecture-review.md` were written, and are now proven in production code (`Compensation`, `Allowance`). Several items below that the governance chain correctly called "no precedent exists anywhere" are no longer true — a precedent now exists, and per instruction it is preferred over inventing a new one.
2. **A correction-and-history pattern now exists.** `Compensation`/`Allowance`'s `corrects_id` self-reference + append-only correction rows is a proven, working answer to "historical preservation without a versioning table," directly closing the "Repository Gap: historical schedule lookup" item and the "lifecycle beyond create-then-overwrite" Blocking Unknown.

Every decision below follows the seven rules given: prefer repository precedent, prefer the simplest model, preserve historical integrity and the accepted Effective Dating architecture, no unrelated capabilities, no unnecessary generic infrastructure, no modification to Payroll/Compensation/Payslip/Effective Dating semantics, and no stopping to produce another decision package.

---

# 1. Blocking Unknowns — Resolved

**#1 Aggregate shape.** **Decision: Aggregate Root.** `WorkSchedule` is its own `BaseEntity`-rooted aggregate, effective-dated via `EffectiveDatingMixin`, following `Compensation`'s exact shape (employee-scoped, multi-row-per-employee, no compound uniqueness). Association Aggregate is rejected per `domain-model-discovery.md` §1's own finding (`Assignment`'s pair-uniqueness is structurally incompatible with a row that must be supersedable over time). Projection is rejected: Work Schedule is durable business data an employee/HR record must be able to create, correct, and audit — not a derived, transient read-time computation like `ReconciliationService`'s classification.

**#2 Relationship with Shift Assignment.** **Decision: No relationship in Iteration 1.** Per explicit instruction not to implement Shift Assignment as a side effect, Work Schedule depends only on the already-implemented `Shift` (per `decision.md` §2, unchanged). Documented assumption: if Shift Assignment is ever built, reconciling any overlap between the two capabilities is that future capability's own governance to resolve — Work Schedule does not reference, depend on, or anticipate it.

**#3 Whether "recurring schedules" and "effective dates" are one concern or two.** **Decision: Two separable concerns**, confirmed rather than merged. Effective dating (when a schedule *version* applies) is handled entirely by the existing `EffectiveDatingMixin`/`EffectiveDatingEvaluator` mechanism, unmodified. "Recurrence" (which days of the week are worked) is modelled as plain content — seven boolean columns on one effective-dated row — not as a row-generating/template mechanism. This is the key simplification: no "template spawns dated instances" infrastructure is needed at all, because a weekly pattern is fully expressible as data on a single row, the same way `Shift`'s own fixed time-of-day fields are plain data on a single row.

**#4 Authorization posture.** **Decision: Owner Only**, identical mechanism and policy to `CompensationAuthorizationEvaluator` (`resource.employee_id == context.employee_context.employee.id`). Rationale: Work Schedule is employee-scoped HR data that directly affects attendance/payroll interpretation (the same sensitivity class as Compensation/Allowance), not undifferentiated project-tracking data like `Assignment`. This is the narrowest safe choice consistent with the repository's own precedent for comparably sensitive, employee-scoped data.

**#5 / #9 Whether `HrEmployee` is a dependency / whether Work Schedule is employee-scoped.** **Decision: Yes, confirmed.** `employee_id` FK to `hr_employees.id`, `ON DELETE RESTRICT` — the universal, exceptionless convention for every employee-scoped entity in this repository.

**#6 Whether `ReconciliationService`/Attendance becomes a real consumer.** **Decision: Not in Iteration 1.** Work Schedule ships as a standalone, independently queryable capability. `ReconciliationService` and `AttendanceLeaveDeductionCalculator` (the latter's own docstring, authored during Advanced Payroll, already names this exact gap and already safely defaults to `None`) are not modified by this work. Wiring Work Schedule into Attendance/Payroll is future, separately-scoped integration work — implementing it here would violate the explicit instruction not to expand scope into other capabilities as a side effect.

**#7 Whether `LeaveRequest`/`Timesheet`/Payroll Calculation ever consume Work Schedule.** **Decision: Not in Iteration 1**, same reasoning as #6. No changes to any of the three.

**#8 Identity convention.** **Decision: UUID only, no compound uniqueness constraint**, following `Compensation`'s exact convention: overlap prevention is a service-layer business rule (via `EffectiveDatingEvaluator` + a repository overlap query), not a database constraint. No new identity scheme is invented.

**#10 Which weaker temporal shape fits.** **Decision: `EffectiveDatingMixin`** (the now-existing, accepted mechanism), not any of the three weaker precedents the original analysis compared against (all of which predate Effective Dating's own acceptance). This directly satisfies the standing instruction to preserve the accepted effective-dating architecture.

**#11 Lifecycle beyond create-then-overwrite.** **Decision: `corrects_id` correction pattern**, identical to `Compensation`/`Allowance`: `update()` is narrowed to `is_active` only; any change to `shift_id`, the weekday pattern, or the effective period is recorded as a new row, optionally a correction (`corrects_id` set), never an in-place mutation of historical fact.

**#12 Whether "employee work calendars" ownership overlaps with `Holiday`/`HolidayCalendar`'s declined scope.** **Decision: No overlap.** Work Schedule models a per-employee weekly working-day pattern only. It does not model named calendars, holiday exception lists, or calendar-year containers — those remain exactly as `HOLIDAY_CALENDAR_DESIGN.md` left them, untouched.

**#13 `BaseRepository` `BETWEEN`-query gap.** **Decision: Not required.** Following `Compensation`'s own resolution of the identical gap, overlap/effective-as-of queries are hand-written directly on `WorkScheduleRepository` (mirroring `CompensationRepository.list_effective_as_of`/`find_overlapping_periods` exactly) — no generic range-query capability is added to `BaseRepository`.

**#14 Overnight-shift/timezone attribution ambiguities.** **Decision: Out of scope**, unchanged. Work Schedule models day-of-week working patterns only; time-of-day and timezone semantics remain entirely `Shift`'s own, referenced but not extended, exactly as `decision.md` §2 already established.

**#15 Capability naming.** **Decision: "Work Schedule" confirmed final.** Model `WorkSchedule`, table `work_schedules`.

---

# 2. Missing-Concepts Classifications — Resolved

- **Recurring relationships (Repository Gap)** → Resolved without new infrastructure: recurrence is plain weekday-boolean content on one effective-dated row (§1 #3). No template/instance mechanism is built.
- **Recurrence identity (Repository Gap)** → Moot: no recurring instances are ever spawned, so there is nothing requiring a new identity scheme.
- **Temporal uniqueness (Repository Gap)** → Resolved via service-layer overlap validation, mirroring `Compensation` exactly (§1 #8, #13). No database constraint invented.
- **Overlap validation (Repository Gap)** → Resolved the same way, hand-written repository query, no `BaseRepository` change (§1 #13).
- **Historical schedule lookup (Repository Gap)** → Resolved by the `corrects_id` correction pattern (§1 #11) plus `list_by_employee_id` (full history, oldest first), mirroring `CompensationRepository` exactly.
- **Planned-versus-actual comparison (Governance Gap)** → Deferred, not solved, per §1 #6. Explicitly out of scope for Iteration 1.

---

# 3. Aggregate / Model

`WorkSchedule(BaseEntity, EffectiveDatingMixin)`, table `work_schedules`:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | via `UUIDMixin` |
| `employee_id` | UUID, FK `hr_employees.id`, `RESTRICT` | required |
| `shift_id` | UUID, FK `shifts.id`, `RESTRICT` | required — the shift worked on working days |
| `works_monday` … `works_sunday` | Boolean, not null, default `False` | 7 columns, plain content, no default work-week assumed |
| `effective_from` / `effective_to` | via `EffectiveDatingMixin` | unchanged mechanism |
| `is_active` | Boolean, default `True` | business/eligibility flag, independent of temporal validity — mirrors `Compensation` |
| `corrects_id` | UUID, nullable, FK `work_schedules.id`, `RESTRICT` | correction pattern, mirrors `Compensation` |

Indexes: `(employee_id, effective_from)`, `(corrects_id)`, `(shift_id)` — mirroring `Compensation`'s and `HrEmployee`'s own indexing conventions.

No uniqueness constraint on `employee_id` — multiple historical/current rows are expected, exactly as `Compensation` §17 established.

---

# 4. Repository

`WorkScheduleRepository(BaseRepository[WorkSchedule])`:
- `list_by_employee_id(employee_id)` — full history, oldest first.
- `list_effective_as_of(employee_id, as_of_date)` — point-in-time candidates, mirrors `CompensationRepository.list_effective_as_of` exactly (inclusive bounds, `is_active` plays no part).
- `find_overlapping_periods(employee_id, effective_from, effective_to, exclude_id=None)` — mirrors `CompensationRepository.find_overlapping_periods` exactly.
- `paginate(...)` — filterable by `employee_id`, `shift_id`, `is_active`.

No `BETWEEN`/range support added to `BaseRepository` (§1 #13).

---

# 5. Service — `WorkScheduleService`

Mirrors `CompensationService`'s structure and policy directly:
- `create(data, request_context)` — validates `employee_id` exists (`EmployeeNotFoundError`), `shift_id` exists (`ShiftNotFoundError`), authorizes (Owner Only), validates `corrects_id` target if set (`CorrectionTargetNotFoundError`/`CorrectionTargetEmployeeMismatchError`), rejects overlap against the same employee's existing rows except the exact row a correction corrects (`OverlappingWorkSchedulePeriodError`).
- `get(id, request_context)`, `get_by_employee(employee_id, request_context=None, as_of_date=None)` (correction-precedence resolution via `_exclude_corrected_targets` + `EffectiveDatingEvaluator.resolve`, propagates `AmbiguousEffectiveStateError`).
- `list(request_context)` / `list_paginated(...)` — scoped to caller's own `employee_id`.
- `list_history(request_context)` — full history for caller's own employee.
- `update(id, data, request_context)` — `is_active` only, narrow by design (§1 #11).
- `delete(id, request_context)`.

All exceptions and the authorization gate mirror `CompensationService`'s naming and shape 1:1, substituting "WorkSchedule" for "Compensation".

---

# 6. Authorization

`WorkScheduleAuthorizationEvaluator(AuthorizationEvaluator)` — Owner Only, identical rule and structure to `CompensationAuthorizationEvaluator`.

---

# 7. API

`APIRouter(prefix="/hr/work-schedules", tags=["Work Schedule"])`, routes mirroring `api/compensation.py` exactly: `POST`, `GET` (own), `GET /paginated`, `GET /by-employee/{employee_id}?as_of=`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`. Same exception→HTTP mapping pattern (404/409/422/403).

---

# 8. Migration

One migration, `create_work_schedules_table`, chained onto the current head (`f6a1b2c3d4e5`), following `create_allowances_table`'s exact column/constraint/index shape.

---

# 9. Tests

Repository tests, service tests (create/overlap/correction/authorization/effective-as-of resolution), and API tests (auth required, owner-only enforcement, CRUD happy path) — mirroring the existing `test_compensation_*`/`test_allowances_api.py` suites' structure and fixture conventions exactly.

---

# 10. Integration Boundaries (explicit)

Not touched by this iteration: `ReconciliationService`, `AttendanceLeaveDeductionCalculator`, `PayrollCalculationService`, `LeaveRequest`, `Timesheet`, `Shift` (referenced only), `Holiday`. Work Schedule ships as a complete, independently usable capability; consuming it from Attendance/Payroll is future, separately-governed work.

---

# References

- `docs/architecture/capabilities/work-schedule/discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `capability-boundary-analysis.md`, `implementation-plan.md`
- `services/api/src/eop_api/models/compensation.py`, `allowance.py`, `db/mixins.py`, `services/effective_dating_evaluator.py`, `services/compensation.py`, `services/compensation_authorization.py`, `repositories/compensation.py`, `api/compensation.py`
