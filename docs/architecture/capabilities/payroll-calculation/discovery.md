# Payroll Calculation — Discovery

**Status:** Complete

**Capability:** Payroll Calculation (distinct from Payroll, Payslip, Payroll Authorization, Payroll Processing, Payroll Integration)

**Owner:** EOP Architecture Governance

---

# Purpose

This document determines whether the repository contains enough architectural evidence to define a Payroll Calculation capability. It is observational only: no architecture is chosen, no schema is authored, no implementation is recommended, no ADR is created. Every conclusion is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**, per the governing instruction.

---

# Discovery Scope

Full file reads unless noted. Repository-wide, case-insensitive greps run fresh for this discovery, not reused from prior turns.

- Repository-wide grep across `services/api/src` for the full term list in § Terminology Sweep — 20 files matched; every match read in context.
- Repository-wide grep for `Decimal|Numeric|Money|Float` (type-precision search) — zero matches.
- Repository-wide grep for `RuleEngine|FormulaEngine|ExpressionEngine|StrategyPattern|PolicyEngine|Strategy\b|class.*Policy` — zero matches.
- Repository-wide grep for `cron|scheduler|celery|redis.*queue|worker` — zero relevant matches (one false positive each in `storage/minio_provider.py` and the already-known, previously-reviewed `jobs/` module).
- Repository-wide grep for `snapshot|immutable|recalculat|versioned` — 11 files matched; every match read in context.
- Repository-wide grep for the exact phrase `Payroll Calculation` across the entire repository — matches found only in documents authored within this conversation (`payroll/architecture-review.md`, `payslip/implementation-plan.md`, `payslip/architecture-review.md`), all using it as a named exclusion, never as a pre-existing governance concept.
- `docs/architecture/10-reference/MASTER_ARCHITECTURE_ROADMAP.md`, `CAPABILITY_DEPENDENCY_GRAPH.md`, `CAPABILITY_CATALOG.md`, `ARCHITECTURE_STATUS.md`, `TECHNICAL_DEBT_REGISTER.md`, `ARCHITECTURE_INVENTORY.md`, `docs/product/02_PRODUCT_SCOPE.md` — re-consulted for this discovery, not re-derived, per findings already on record in `payroll/discovery.md`/`payslip/discovery.md`.
- `docs/architecture/capabilities/payroll/*.md` (five documents), `docs/architecture/capabilities/payslip/*.md` (four documents), `docs/architecture/capabilities/payroll-authorization/*.md` (two documents) — this conversation's own prior output, carried forward as evidence of what is already established, not re-derived.
- Every model, service, repository, schema, and API file for the fifteen named producer capabilities (§1) — re-consulted from prior discoveries; `PayrollRun` and `Payslip` re-verified directly against their now-merged, implemented code, not against plan documents.
- `services/api/src/eop_api/events/`, `jobs/` (`EventPublisher`/`EventService`, `JobProvider`/`JobService`) — re-consulted from `payroll/domain-model-discovery.md` E3, not re-derived.

---

# 1. Existing Producer Capabilities

Every capability named in the investigation instruction, with owner, lifecycle, completion state, fields, computation already performed, and computation explicitly not performed.

| Capability | Owner | Lifecycle | Completion State | Fields | Computation Performed | Computation Explicitly NOT Performed |
|---|---|---|---|---|---|---|
| Employee (`HrEmployee`) | `HrEmployeeService` | Plain CRUD, no status | Implemented | `employee_number`, name fields, `email`, `phone`, 10 FKs, `hire_date`, `employment_status`, `notes` | None | No salary/rate computation of any kind — no such field exists |
| Attendance (`AttendanceEvent`) | `AttendanceEventService` | Append-only in intent, mutable in practice (`update`/`delete` exposed) | Implemented, authorized (Owner Only) | `employee_id`, `shift_id`, `event_type`, `event_time`, `source` | None | "Employee-day rollups, timesheets, overtime, and payroll are all future projections built on top of this stream" — explicit, own docstring |
| Attendance Reconciliation | `ReconciliationService` | Read-time computation, not persisted | Implemented, authentication-only | Response shape only: `employee_id`, `date`, `status` (`holiday`/`leave`/`present`/`absent`) | Precedence-ordered classification of one employee/one date against `Holiday`/`LeaveRequest`/`AttendanceEvent` | "Overtime, lateness, early departure, grace periods, shift schedules, overnight-shift attribution, and timezone handling are explicitly out of scope for v1" — own docstring. No hour totals, no pay-relevant computation |
| Leave (`LeaveRequest`) | `LeaveRequestService` (CRUD) / `ApprovalService` (decision) | `pending → approved/rejected` | Implemented, authorized (Owner Only + Manager Approval) | `employee_id`, `start_date`, `end_date`, `status`, `reason`, `approved_by`, `approved_at`, `rejection_reason` | None beyond the status transition itself | "Leave balance/entitlement math or payroll deduction... those are downstream consumers... not Leave's own responsibility" — own docstring/design doc |
| Leave Balance (`LeaveBalance`) | `LeaveBalanceService` | Static snapshot, no transitions | Implemented, storage only, unauthorized | `employee_id`, `period_year`, `allocated_days`, `used_days`, `remaining_days` | None — non-negative validation only | "Automatic remaining-days calculation, deduction, accrual, carry-forward, expiration, leave reconciliation, payroll synchronization, and duplicate-period prevention are all explicitly out of scope" — own docstring. Not synchronized with `LeaveRequest` approval (named, intentional gap) |
| Overtime (`OvertimeRequest`) | `OvertimeRequestService` (CRUD, unauthorized) / `ApprovalService` (decision) | `pending → approved/rejected` | Implemented; CRUD authentication-only | `employee_id`, `overtime_date`, `start_time`, `end_time`, `status`, `approved_by`, `approved_at`, `rejection_reason` | None | No duration/hours computation exists — `start_time`/`end_time` are stored as submitted, never subtracted or aggregated anywhere in the codebase |
| Timesheet (`Timesheet`) | `TimesheetService` (CRUD, unauthorized) / `ApprovalService` (decision) | `pending → approved/rejected` | Implemented; CRUD authentication-only | `employee_id`, `start_date`, `end_date`, `status`, `approved_by`, `approved_at`, `rejection_reason` | None | "Attendance/overtime/leave/holiday reconciliation, computed hour totals, overlap detection, duplicate detection, and payroll integration remain out of scope" — own docstring |
| `PayrollRun` | `PayrollRunService` | Plain CRUD, `create`/`get`/`list`/`update`/`delete` | Implemented (Iteration 1) | `code` (unique), `name` — `BaseEntity` mixins only otherwise | None | No period, no status, no monetary field, no computation of any kind — confirmed directly against the merged model, not a plan |
| `Payslip` | `PayslipService` | `create`/`get`/`list` only — immutable after creation, no `update`, no `delete` | Implemented (Iteration 1) | `employee_id`, `payroll_run_id` — `BaseEntity` mixins only otherwise | None | No monetary field, no status, no calculation result — confirmed directly against the merged model. Existence-only FK validation (`employee_id`/`payroll_run_id`) is the only logic `PayslipService.create` performs |
| Approval | `ApprovalService` | `pending → approved/rejected`, exactly three consumers (`LeaveRequest`, `OvertimeRequest`, `Timesheet`) | Implemented, authorized (Manager Approval) | Writes `status`/`approved_by`/`approved_at`/`rejection_reason` onto the target row; owns no entity itself | State-transition validation only (`pending` precondition) | "Decision history, audit logging, and event/notification dispatch remain explicitly out of scope" — own docstring |
| Shift | `ShiftService` | Plain CRUD | Implemented | `code`, `name`, `description`, `start_time`, `end_time`, `break_duration_minutes`, `grace_period_minutes` | None | "Assigning a shift to an employee, a work calendar, and rostering are all out of scope" — own docstring. No shift-differential/premium-pay computation exists |
| Holiday | `HolidayService` | Plain CRUD | Implemented | `code`, `name`, `description`, `holiday_date` | None | No holiday-type/category field, no `is_paid`/pay-multiplier field — confirmed absent |
| JobGrade | `JobGradeService` | Plain CRUD | Implemented | `code`, `name`, `level` (int rank), `description` | None | No rate/salary-band field — `level` is a bare seniority rank with no monetary meaning anywhere in the codebase |
| EmploymentType | `EmploymentTypeService` | Plain CRUD | Implemented | `code`, `name`, `description` | None | No monetary or calculation-relevant field |
| EmploymentStatus | `EmploymentStatusService` | Plain CRUD | Implemented | `code`, `name`, `description` | None | No monetary or calculation-relevant field |

---

# 2. Terminology Sweep

Repository-wide, case-insensitive search for: `gross, net, salary, allowance, deduction, tax, benefit, earning, pay, amount, money, currency, decimal, rate, hourly, monthly, annual, income, compensation, base pay, basic pay, premium, multiplier, calculation, formula, compute, engine, rule, accrual, deduction, balance` (`balance`/`deduction` listed twice in the instruction; searched once each).

**Repository Evidence**: 20 files under `services/api/src` matched at least one term. Every match, read in context, falls into one of these categories — no new category emerged beyond what prior Payroll/Payslip discoveries already found:

- **Docstring "out of scope" disclaimers** in already-implemented, non-Payroll modules (`timesheet.py`, `overtime_request.py`, `leave_balance.py`, `reconciliation.py`) — each explicitly states payroll-adjacent computation is not its responsibility (§1).
- **Authorization-policy "rule" language** (`attendance_authorization.py`, `leave_authorization.py`, `approval_authorization.py`, `authorization_evaluator.py`) — "rule" here means an authorization comparison (e.g. "Owner Only rule," "Manager Approval rule"), not a payroll calculation rule.
- **`approval.py`**'s own "deduction calculation... unresolved" language — concerns leave-balance *day* deduction, not currency (already known, re-confirmed).
- **`job_grade.py`**'s "pay grade" docstring phrase — descriptive language about rank ordering; no monetary field backs it (already known, re-confirmed directly against the current model).
- **Platform infrastructure files** (`main.py`, `db/session.py`, `db/engine.py`, `exceptions/department.py`, `services/shift.py`) — matched on generic English usage (SQLAlchemy `engine`, "business rule" meaning validation logic) with zero payroll relevance, confirmed by direct read.
- **`payroll_run.py`/`payslip.py`** — this conversation's own merged code, matched on "pay" as a substring of "Payroll"/"Payslip."

**Logical Consequence**: No new payroll-relevant vocabulary exists in the codebase beyond what `payroll/discovery.md` and `payslip/discovery.md` already catalogued. The terminology sweep for this discovery, run independently and more broadly, converges on the identical conclusion.

**Unknown**: None — the sweep is exhaustive and every match was individually classified.

---

# 3. Monetary Model

**No monetary model exists anywhere in the repository.**

**Repository Evidence**: Repository-wide grep for `Decimal|Numeric|Money|Float` across `services/api/src` returns zero matches. No model, schema, or migration anywhere defines a monetary, currency, or fractional-precision column. This holds true for `PayrollRun` and `Payslip` themselves, confirmed directly against their current, merged models (§1) — neither carries a `gross`, `net`, `amount`, or any other monetary field.

**Logical Consequence**: None required — this is a direct, unambiguous absence.

**Unknown**: Where a monetary model would eventually be added (a new field on an existing entity, or a new dedicated entity) is not addressed anywhere in the repository — restated from `payroll/decision.md` §7, not re-litigated here.

---

# 4. Calculation Engine Precedent

**No calculation engine exists anywhere in the repository**, checked against every example named in the investigation instruction:

- **Leave accrual**: `LeaveBalanceService`'s own docstring explicitly excludes "automatic remaining-days calculation, deduction, accrual, carry-forward, expiration" (§1). `allocated_days`/`used_days`/`remaining_days` are plain, independently-settable integer fields with only a non-negative validation — no arithmetic relates them to each other anywhere in the service.
- **Attendance reconciliation**: `ReconciliationService` performs classification (which of four fixed labels applies), not calculation — no hours, rates, or amounts are computed (§1).
- **Timesheet totals**: no computed-hours field or method exists anywhere; `Timesheet` stores only a submitted date range (§1).
- **Overtime totals**: no computed-duration field or method exists anywhere; `OvertimeRequest` stores only submitted `start_time`/`end_time` (§1).
- **Holiday pay**: `Holiday` carries no `is_paid`/pay-multiplier field (§1, re-confirmed).
- **Shift differential**: `Shift` carries `break_duration_minutes`/`grace_period_minutes` (attendance-timing concepts) but no rate multiplier or differential-pay field of any kind (§1).
- **Anything rule-driven**: no capability in the repository branches its behavior on a caller-configurable or stored "rule" — every business behavior found in this and prior discoveries is a fixed, hard-coded comparison (e.g. `resource.employee_id == context.employee_context.employee.id`), not an evaluated rule/expression.

**Logical Consequence**: Every capability that touches pay-adjacent raw data (attendance, leave, overtime, timesheet) stops at storing or classifying the raw fact, never at computing a derived, pay-relevant total. This is a repeated, independent pattern across five separate modules, not a single isolated gap.

**Unknown**: None.

---

# 5. Architectural Patterns

**None of the following exist anywhere in the repository**, confirmed by repository-wide grep for `RuleEngine|FormulaEngine|ExpressionEngine|StrategyPattern|PolicyEngine|Strategy\b|class.*Policy` (zero matches) and by the absence of any comparable unnamed pattern found across every service reviewed in this and prior discoveries:

- Rule Engine
- Formula Engine
- Expression Engine
- Strategy Pattern
- Policy Pattern (as a code abstraction — "policy" is used only as prose, e.g. "Owner Only Policy," never as a class/interface)
- Calculation abstraction (no base class or interface for "a thing that computes a value from inputs" exists anywhere)
- Event-driven calculation (no calculation is triggered by an event — see §6, `EventService` has zero callers)
- Batch calculation (no service iterates "all employees"/"all records for a period" anywhere — `payroll/domain-model-discovery.md` A3, re-confirmed)
- Scheduled calculation (no scheduler exists — §6)

**Logical Consequence**: The three service shapes already catalogued in `payroll/discovery.md` §5 (per-entity CRUD service; `ApprovalService`'s cross-entity status-transition orchestrator; `ReconciliationService`'s read-only, multi-repository, no-persistence classifier) remain the complete set of orchestration shapes in the repository. None is a calculation abstraction in the sense this investigation asks about.

**Unknown**: None.

---

# 6. Infrastructure: Background Execution

**Repository Evidence**, re-confirmed directly, not merely re-cited from `payroll/domain-model-discovery.md` E3:

- `EventPublisher`/`EventService` (`events/base.py`, `events/memory_publisher.py`, `services/event.py`) exist. `EventService`'s own docstring: *"Nothing in this PR calls it yet — it is infrastructure for later adoption."* Zero callers anywhere in the repository.
- `JobProvider`/`JobService` (`jobs/base.py`, `jobs/memory_provider.py`, `services/job.py`) exist, identical docstring, identical zero-callers finding.
- `InMemoryEventPublisher`/`InMemoryJobProvider` are the only implementations of either abstraction — both explicitly documented as recording-only: *"There is no broker, queue, or subscriber behind this"* / *"There is no worker, scheduler, or poller behind this... nothing in this class ever executes a job."*
- Repository-wide grep for `cron|scheduler|celery|redis.*queue|worker` returns no relevant match — the two files matched (`storage/minio_provider.py`, and `jobs/`'s own files, already covered above) contain no scheduler/cron/worker implementation.

**Logical Consequence**: Background execution infrastructure is present, typed, and documented as intentionally unused pending later adoption — but has no working execution mechanism (no broker, no queue consumer, no scheduler) and no existing caller anywhere. A Payroll Calculation capability requiring asynchronous or batch execution would be the first real caller of this dormant infrastructure, not a capability following an established, exercised pattern.

**Unknown**: Whether this infrastructure is expected to be adopted as-is, or replaced, when a real batch-execution need arises — no repository evidence addresses this.

---

# 7. Precision

**Repository Evidence**: Repository-wide grep for `Decimal|Numeric|Money|Float` across `services/api/src` returns zero matches (§3, restated here as the precision-specific finding). No fractional-precision or currency-precision type is used anywhere in the repository, for any purpose — not only absent for monetary data, but absent as a *type* the codebase has ever used at all. Every numeric field reviewed across every capability (`LeaveBalance.allocated_days`/`used_days`/`remaining_days`, `JobGrade.level`) is a plain `Integer`.

**Logical Consequence**: There is no repository precedent for how fractional or currency-precision values would be stored, computed, or serialized — not even a partial or analogous one (e.g., no percentage field, no ratio field). This is a complete absence, not a gap in an otherwise-established pattern.

**Unknown**: None — the absence is total and unambiguous.

---

# 8. Lifecycle Precedent

**Repository Evidence**: Repository-wide grep for `snapshot|immutable|recalculat|versioned` returns 11 files. Read in context:

- **`AuditLog`** (`models/audit_log.py`) is documented as immutable/append-only, enforced by service-layer convention only (no `update`/`delete` exposed) — already catalogued in `payslip/discovery.md` §1. It performs no calculation; it records that an action occurred.
- **`Payslip`** (`models/payslip.py`, `services/payslip.py`) is immutable after creation by this conversation's own decision (`payslip/decision.md` §4) — already implemented, confirmed directly against the merged code. It performs no calculation either (§1).
- **`LeaveBalance`**'s own docstring calls it "a persisted allocation/usage snapshot" — but this is a static, independently-editable stored value, not a computed or versioned snapshot: nothing recomputes it, nothing tracks prior versions of it, and it is explicitly documented as unsynchronized with `LeaveRequest` approval (§1, §4).
- **`AuthorizationRequest`/`AuthorizationDecision`** (`services/authorization_request.py`, `authorization_decision.py`) are frozen dataclasses — immutable as Python value objects, not as persisted, versioned computations.
- The remaining matches (`events/memory_publisher.py`, `notifications/memory_provider.py`, `jobs/memory_provider.py`, `repositories/file.py`, `models/file_object.py`) concern defensive copying of caller-supplied data (*"the caller's mapping is never mutated"*) or file-upload handling — unrelated to computation lifecycle.

**Logical Consequence**: The repository has exactly two "immutable record" precedents (`AuditLog`, `Payslip`), and neither is a calculation — both are, respectively, a generic action log and a to-be-computed-later structural placeholder. **No capability anywhere in the repository performs an irreversible calculation, produces a versioned computation, or supports recalculation of a previously-computed value.** There is no precedent to draw on for what "recalculating a payroll figure" would mean operationally (replace in place? version? supersede with a new row referencing the old one?).

**Unknown**: Whether a future Payroll Calculation capability's own immutability/versioning model would follow `Payslip`'s convention-based pattern (§ Payslip governance) or require something new — no repository evidence answers this, since no capability has ever needed to recalculate anything.

---

# 9. Ownership — Where Payroll Calculation Would Naturally Stop

Determined by direct inspection of each named boundary's current owner and current completion state:

| Boundary | Current Owner | Current State |
|---|---|---|
| Leave deduction | **No owner exists.** `LeaveBalanceService` owns the storage of `used_days`/`remaining_days`, but no service computes or writes a deduction — `LeaveBalance` is manually settable, unsynchronized with `LeaveRequest` approval (§1). |
| Attendance reconciliation | `ReconciliationService`, fully owned and implemented — produces a per-day classification (`holiday`/`leave`/`present`/`absent`), not an hours or pay figure (§1). |
| Overtime duration | **No owner exists.** No service computes `end_time - start_time` for `OvertimeRequest` anywhere in the repository (§1, §4). |
| Timesheet aggregation | **No owner exists.** No service sums or aggregates hours for a `Timesheet`'s date range anywhere in the repository (§1, §4). |

**Logical Consequence**: A Payroll Calculation capability would find three of these four boundaries (leave deduction, overtime duration, timesheet aggregation) entirely unowned — not partially built, not deferred with a stub, simply absent. Only attendance reconciliation has an existing, complete owner (`ReconciliationService`), and that owner's own output stops at classification, one step short of any hours or pay figure. This means Payroll Calculation's upstream inputs are, in three of four cases, raw, unaggregated submitted data (`OvertimeRequest.start_time`/`end_time`, `Timesheet.start_date`/`end_date`) rather than any pre-computed total — there is no existing "hours engine" for Payroll Calculation to simply read from.

**Unknown**: Whether duration/aggregation computation is expected to be built as part of Overtime's/Timesheet's own capability (upstream of Payroll Calculation) or as part of Payroll Calculation itself is not addressed by any repository evidence — no document assigns this responsibility either way.

---

# 10. Governance Documents Defining Boundaries

**Repository Evidence**: No governance document predating this conversation defines a boundary for "Payroll Calculation" as a named capability. `MASTER_ARCHITECTURE_ROADMAP.md` and `CAPABILITY_DEPENDENCY_GRAPH.md` name only "Payroll" (`Planned`, `MASTER_ARCHITECTURE_ROADMAP.md`) and "Payroll Integration" (`CAPABILITY_DEPENDENCY_GRAPH.md`'s separate, differently-rooted "Secondary" critical path) — already catalogued in `payroll/discovery.md` §7/§8 as two differently-named, unreconciled framings. Neither document, nor any other reviewed in this or prior discoveries (`CAPABILITY_CATALOG.md`, `ARCHITECTURE_STATUS.md`, `TECHNICAL_DEBT_REGISTER.md`, `ARCHITECTURE_INVENTORY.md`, ADRs, `docs/product/02_PRODUCT_SCOPE.md`), names "Payroll Calculation" specifically or defines its boundary relative to "Payroll," "Payroll Processing," "Payroll Integration," or "Payroll Authorization."

The exact phrase "Payroll Calculation" occurs only in three documents, all authored within this conversation: `payroll/architecture-review.md`, `payslip/implementation-plan.md`, `payslip/architecture-review.md` — in every occurrence, it is named as an *excluded* item ("out of scope"), never as a capability with its own defined responsibilities.

**Logical Consequence**: This conversation's own governance trail (`payroll/decision.md` §4, `payslip/decision.md` §7-8) is the only place any boundary language exists for what Payroll Calculation is *not* — restated here as the boundary already established: Payroll Calculation must not own Attendance capture/reconciliation, Leave/Overtime/Timesheet request lifecycle or approval, HR master data, or the generic authorization mechanism. No document anywhere states what Payroll Calculation *is*, beyond its name.

**Unknown**: Whether "Payroll Calculation" is intended as a synonym for, a subset of, or a successor to the roadmap's "Payroll Authorization"-adjacent, generically-named "Payroll" entry — no document resolves this naming relationship, the same class of ambiguity already flagged for "Payroll"/"Payroll Integration"/"Payroll Processing" in `payroll/discovery.md` §7-8.

---

# Findings Summary

- No monetary model, no precision type (`Decimal`/`Numeric`/`Money`/`Float`), and no calculation engine of any kind exists anywhere in the repository (§3, §4, §7) — confirmed by exhaustive, independent search, not merely re-cited from prior discoveries.
- No architectural pattern named in the investigation (Rule/Formula/Expression/Strategy/Policy/Calculation-abstraction/event-driven/batch/scheduled) exists anywhere (§5).
- Background-execution infrastructure (`EventService`, `JobService`) exists but is entirely unused, with no working execution mechanism behind either (§6) — a Payroll Calculation capability needing async/batch execution would be the first real caller.
- The repository has exactly two "immutable record" precedents (`AuditLog`, `Payslip`), neither a calculation, and no precedent anywhere for recalculation or versioned computation (§8).
- Three of the four named ownership boundaries (leave deduction, overtime duration, timesheet aggregation) have **no existing owner at all** — not partially built, entirely absent; only attendance reconciliation is fully owned, and its output stops at classification, short of any hours or pay figure (§9).
- No governance document predating this conversation defines "Payroll Calculation" as a named capability or assigns it a boundary; the phrase exists only as an exclusion item in this conversation's own Payroll/Payslip documents (§10).

The repository does not currently contain sufficient architectural evidence — either upstream computation to consume, or structural precedent for how a calculation-shaped capability would be built — to define a Payroll Calculation capability's own boundary beyond what it must not own. This is a repository-evidence finding, not a recommendation.

---

# Recommended Next Step

```
Payroll Calculation Capability Decision
```
