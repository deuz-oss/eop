# Advanced Payroll — Implementation Plan v1

**Status:** Draft — awaiting review (not yet authorized for implementation)
**Capability:** Payroll Calculation (Advanced tier)
**Prepared by:** Senior Engineer (Claude), per EOP Master Roadmap
**Inputs:** `business-decision-package.md` (D1–D9, E1–E8, resolved by CPO/CTO), current merged code (audited fresh, not assumed from stale governance)
**Scope of this document:** Planning only. No production code, migration, or test was written. No governance document was modified.

---

# 1. Audit Summary — What Changed Since `payroll-calculation/architecture-gap-analysis.md`

That document's blocking finding ("no capability owns compensation/rate data") is resolved: `Compensation` is implemented, effective-dated, multi-row, with overlap/correction policy (`models/compensation.py`, `services/compensation.py`). Current code, verified directly (not from governance prose):

- `PayrollRun` (`models/payroll_run.py`): `code`, `name`, `status` (`DRAFT`/`PROCESSING`/`COMPLETED`). No period, no currency.
- `Payslip` (`models/payslip.py`): `employee_id`, `payroll_run_id`, `gross_salary_amount`/`currency`, `net_salary_amount`/`currency` (nullable, always populated going forward). Immutable — no `update`/`delete` route.
- `PayrollCalculationService` (`services/payroll_calculation.py`): `calculate`/`calculate_batch`. Gross = Net = `Compensation.base_salary`. `calculate_batch` uses `CompensationService.list_active()` — **every** `is_active=True` row across all employees, unscoped by effective date (§1.1 below).
- `CompensationService.get_by_employee(employee_id, request_context=None, as_of_date=None)` already resolves via `EffectiveDatingEvaluator` — correctly handles the multi-row model. Payroll's existing call site is *not broken* by Compensation Historical; it simply never passes `as_of_date` (defaults to today).
- Alembic head: **`eb08670e87df`**.

## 1.1 One pre-existing nuance, not a new defect

`list_active()` returns every `is_active=True` `Compensation` row, and `is_active` is no longer a "one row per employee" invariant (`compensation/decision.md` §18). An employee with two `is_active=True` historical rows would be attempted twice in `calculate_batch`; the second attempt hits the existing `DuplicatePayslipError` check and is skipped. No incorrect Payslip results. Addressed opportunistically in §5 (repository change), not as a fix-first blocker.

---

# 2. Design Overview

```
Compensation (base salary)  ─┐
Allowance (new, Compensation-owned) ─┤
OvertimeRequest (approved)  ─┤        PayrollRateResolver
AttendanceEvent/Reconciliation ─┤          │
LeaveRequest/LeaveBalance   ─┤            ▼
Deduction (new, explicit)   ─┤   PayrollCalculationService
PayrollStatutoryParameter   ─┘   (composes calculator components)
                                       │
                                       ▼
                            Payslip + PayslipLineItem[] (new)
```

Every arrow into `PayrollCalculationService` is a **read-only** dependency, mirroring the already-established relationship pattern (`payroll/decision.md` §4–6). No upstream capability's model, service, or table is modified in its own business logic — only two narrowly-scoped, additive, read-only query methods are added to existing repositories (§5).

---

# 3. Schema / Model Changes

## 3.1 New models

### `PayrollStatutoryParameter` — `models/payroll_statutory_parameter.py`

Implements D2/E4: statutory *and* payroll-operational parameters as configurable data, read by code-based calculators — not a generic rule/expression engine.

```
id, key: String(100), value: Numeric(18,6),
effective_from/effective_to: EffectiveDatingMixin,
description: String(500) | None
```

- No fixed enum for `key` — free-form string (e.g. `STATUTORY_TAX_RATE`, `OVERTIME_MULTIPLIER_WEEKDAY`, `STANDARD_WORKING_DAYS_PER_MONTH`, `STANDARD_DAILY_HOURS`). Inventing a closed vocabulary now would assert business content this document does not have.
- Effective-dated (parameters change over time, e.g. annual tax-rate changes) — reuses `EffectiveDatingMixin` mechanically (§3, already-approved mechanism, no new architecture decision, per Claude's implementation authority).
- Overlap policy: same shape as Compensation's O1, scoped per `key` instead of per `employee_id` (two values for the same `key` may not have overlapping effective periods).
- `Numeric(18,6)` (not `14,2`, unlike money columns): rates/multipliers need more than 2 decimal places (e.g. a multiplier of `1.5`, a tax rate of `0.050000`). This is not a `Money` value — no currency, not a monetary amount — so it deliberately does not use the `Money` type/columns convention.

### `Allowance` — `models/allowance.py`

Implements D6: Compensation owns allowance definition/value. Mirrors `Compensation`'s shape closely (same aggregate family, Compensation-owned, physically a separate file the same way `JobGrade`/`EmploymentType` are separate files within one HR domain):

```
id, employee_id: FK(hr_employees, RESTRICT),
allowance_type: String(50),
allowance_amount: Numeric(14,2), allowance_currency: String(3),  # Money
EffectiveDatingMixin, is_active: Boolean, corrects_id: FK(allowances.id, RESTRICT) | None
```

- `allowance_type` is a free-form code, not a fixed enum — no allowance catalog content has been specified; inventing one (e.g. `TRANSPORT`/`MEAL`) would be business content this plan does not have.
- Overlap policy scoped to `(employee_id, allowance_type)` — an employee may hold multiple *simultaneous* allowances of different types (governance's own stated requirement, `compensation/decision.md` §4: "may require multiple simultaneous values"), but not two overlapping periods of the *same* type. Direct extension of Compensation's already-accepted O1 policy, not a new pattern.
- `corrects_id` mirrors Compensation's C2b correction shape exactly, for the same reason (auditable correction of a financial record).

### `DeductionType` — `models/deduction_type.py`

Implements D7's "catalog." Mirrors `EmploymentType`/`JobGrade` exactly:

```
id, code: String(50) unique, name: String(255), description: String | None
```

### `Deduction` — `models/deduction.py`

Implements D7's "explicit deduction records." Owned by Payroll (already-decided: `compensation/decision.md` §4, "Deduction... Belongs to Payroll Calculation / Payroll Run").

```
id, employee_id: FK(hr_employees, RESTRICT),
deduction_type_id: FK(deduction_types, RESTRICT),
payroll_run_id: FK(payroll_runs, RESTRICT),
deduction_amount: Numeric(14,2), deduction_currency: String(3),  # Money
note: String(500) | None
```

- Scoped to one specific `(employee_id, payroll_run_id)` — an explicit, per-run record, not a recurring/effective-dated entitlement. **Recurring deductions (e.g. an auto-repeating loan installment) are explicitly out of scope for v1** — inventing recurrence/termination semantics (when does a loan finish repaying? what if the balance changes?) would be new business content nobody has specified. An admin enters a `Deduction` row for each run it applies to.
- Mutable only while the parent `PayrollRun` is not `COMPLETED` (mirrors Payslip's own completed-immutability extension, §3.3).

### `PayslipLineItem` — `models/payslip_line_item.py`

Implements E1 (structured calculation result).

```
id, payslip_id: FK(payslips, CASCADE),
component_type: PayslipLineItemType (enum, native_enum=False — mirrors PayrollRunStatus's convention),
label: String(255),
line_amount: Numeric(14,2), line_currency: String(3),  # Money
source_id: UUID | None  # untyped reference (Allowance.id / Deduction.id / OvertimeRequest.id) — no FK, since it can point to different tables; no polymorphic-FK precedent exists anywhere in this repository to build on
```

`PayslipLineItemType` (new enum, `core/payroll.py`): `BASE_SALARY`, `ALLOWANCE`, `OVERTIME`, `ATTENDANCE_DEDUCTION`, `LEAVE_DEDUCTION`, `STATUTORY_DEDUCTION`, `NON_STATUTORY_DEDUCTION`.

- `CASCADE` on `payslip_id` — deliberate departure from the `RESTRICT` convention used everywhere else. Rationale: a line item has no independent identity or meaning apart from its parent Payslip (the same "owned child, no independent existence" shape `payslip/discovery.md` §9 already identified in `Task`/`Assignment`'s `CASCADE` precedent, as distinct from `Payslip`'s own `RESTRICT` relationship to `PayrollRun`, where `Payslip` *does* have independent identity). Consistent, not a new pattern.
- `line_amount` is always stored **unsigned** (positive). Earning vs. deduction is determined by `component_type`, never by sign — avoids an entire class of sign-convention bugs. `PayrollCalculationService` computes `gross = Σ(earning line items)`, `net = gross - Σ(deduction line items)`.

## 3.2 `PayrollRun` changes

Implements D1 (monthly period), D8/E7 (single currency), E6 (`PayrollRun` owns the period).

```
+ period_start: Date | None   # nullable — see §6 migration safety
+ period_end: Date | None
+ currency: String(3) | None
```

Service-layer validation (`PayrollRunService.create`, new, not decided by any prior document — Claude's implementation authority):
- `period_start` must be the first day of a calendar month; `period_end` must be the last day of the *same* month (enforces D1's monthly cadence without inventing a separate `PayPeriod` entity, per Architecture recommendation E6).
- No two `PayrollRun` rows may have overlapping periods **for the same `currency`** (new `PayrollRunRepository.find_overlapping_period`, mirroring Compensation's `find_overlapping_periods` pattern exactly). Different currencies may have a run for the same month (D8/E7's segmentation).

## 3.3 `PayrollRun` lifecycle changes (D9/E5)

No new `PayrollRunStatus` value. Transition rule changes only:

- `PayrollRunService.start_processing`: relaxed to accept current status ∈ `{DRAFT, PROCESSING}` (idempotent re-entry for a rerun), rejects only `COMPLETED` (new `PayrollRunAlreadyCompletedError`).
- **Rerun mechanism** lives in `PayrollCalculationService.calculate_batch`, not in `PayrollRunService`: before recomputing, it calls a new, **not publicly API-exposed** `PayslipService.delete_by_payroll_run(payroll_run_id)`, itself guarded to raise if the parent run is `COMPLETED` (defense in depth even though the caller already checked). This is how E5 ("immutable completed results") and D9 ("rerun allowed before completion") coexist: Payslip's public contract (`create`/`get`/`list`, no `update`/`delete`) is **unchanged**; the new delete path exists only for this one internal, guarded, pre-completion use.

## 3.4 `Payslip` impact

- No column removed. `gross_salary_amount`/`net_salary_amount`/currencies remain as top-level convenience fields for fast reads/reporting; they are computed *from* the sum of `PayslipLineItem` rows, not independently.
- `PayslipService.create` signature extended to accept `line_items: Sequence[PayslipLineItemCreate]`, persisted in the same transaction as the `Payslip` row — `Payslip`'s persistence ownership is unchanged (`PayslipService` still owns it; `PayrollCalculationService` still only calls it, per the already-decided boundary).
- `Payslip` responses eager-load `line_items` (`selectinload`, matching the `relationship()` pattern already used by `AttendanceEvent`).
- Public immutability contract (no `update`/`delete` route) is **unchanged**. Only the new internal `delete_by_payroll_run` (§3.3) exists, and only while the parent run is not `COMPLETED`.

---

# 4. Migration Sequence

Chained sequentially off current head **`eb08670e87df`**. Six new migrations, in this order (dependency-driven):

1. `create_payroll_statutory_parameters_table` — no dependencies.
2. `create_allowances_table` — depends on `hr_employees` (exists).
3. `create_deduction_types_table` — no dependencies.
4. `create_deductions_table` — depends on `hr_employees`, `payroll_runs`, `deduction_types` (all exist by step 3).
5. `add_period_and_currency_to_payroll_runs` — alters `payroll_runs`, all three columns **nullable** (see §6).
6. `create_payslip_line_items_table` — depends on `payslips` (exists).

Each migration: full explicit `BaseEntity` column set where applicable, indexes on every FK, matching every migration reviewed in this repository (`docs/architecture/capabilities/effective-dating`/`compensation` migrations as the most recent, directly-analogous precedent for the effective-dated tables).

---

# 5. Repository Changes

**New** (each `BaseRepository[Model]` subclass, mirroring `CompensationRepository`'s exact shape):
- `PayrollStatutoryParameterRepository` — `list_effective_as_of(key, as_of_date)`, `find_overlapping_periods(key, ...)`.
- `AllowanceRepository` — `list_by_employee_id`, `list_effective_as_of(employee_id, allowance_type, as_of_date)`, `find_overlapping_periods(employee_id, allowance_type, ...)`, `list_active_for_employee(employee_id, as_of_date)`.
- `DeductionTypeRepository` — plain CRUD, mirrors `EmploymentTypeRepository`.
- `DeductionRepository` — `list_by_employee_and_payroll_run(employee_id, payroll_run_id)`.
- `PayslipLineItemRepository` — `list_by_payslip(payslip_id)`.

**Modified, additive only — no change to existing method behavior:**
- `PayrollRunRepository`: **+** `find_overlapping_period(currency, period_start, period_end, exclude_id=None)`.
- `PayslipRepository`: **+** `list_by_payroll_run(payroll_run_id)` (used by the rerun-delete path).
- `CompensationRepository`: **+** `list_active_as_of(as_of_date)` — resolves the §1.1 nuance by scoping `list_active` to rows actually effective on a given date, not just `is_active=True`. `calculate_batch` switches to this method. Purely additive; existing `list_active()` is untouched (still used nowhere else, kept for API/test compatibility — no removal without a reason to).
- `OvertimeRequestRepository`: **+** `list_approved_in_range(employee_id, start_date, end_date)` — read-only query addition. Does not change `OvertimeRequest`'s ownership, model, or business logic; Overtime capability still owns its own table and repository, Payroll only calls it (same "shared-session, second repository" pattern already used for existence checks, extended to a real query — consistent with the read-only relationship already established, `payroll/decision.md` §6).
- `ReconciliationService`: **+** `get_range(employee_id, start_date, end_date) -> Sequence[DailyStatus]` — internally loops its own existing single-date classification logic; no change to per-day classification rules.

No existing repository or service has any method's *behavior* changed.

---

# 6. Migration / Data Safety

- **New tables** (`payroll_statutory_parameters`, `allowances`, `deduction_types`, `deductions`, `payslip_line_items`): zero risk — additive, no pre-existing data.
- **`payroll_runs` alteration**: `period_start`/`period_end`/`currency` added as **nullable**, no backfill. This mirrors the exact precedent already in this codebase for the identical situation — `Payslip.gross_salary_amount`/`net_salary_amount` were added nullable to an already-existing table for the same reason (`models/payslip.py`'s own docstring: *"Nullable at the database level only because these columns were added by a later migration to an already-existing table"*). Existing `PayrollRun` rows (Iteration 1–3 test data) keep `NULL` period/currency — an accepted historical gap, not a data-loss risk. Every `PayrollRun` created going forward always populates all three (enforced by `PayrollRunCreate` schema requiring them, not by a DB `NOT NULL` constraint, matching the Payslip precedent exactly).
- No column is removed, renamed, or has its type changed anywhere in this plan.
- No data backfill or transformation script is required.
- Validation per migration: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` (upgrade/downgrade/re-upgrade cycle), matching the validation already performed for the Compensation Historical migration (PR #62's own description).

---

# 7. Service Architecture

**New, full CRUD services** (mirror `CompensationService`'s shape: UoW-owned transaction boundary, `_authorize` delegation):
- `PayrollStatutoryParameterService` — `create`/`get`/`list`/`update(effective period fields excluded, same narrow-update pattern as Compensation)`; **+** `get_value(key, as_of_date) -> Decimal`, raising `MissingStatutoryParameterError` if no row is effective — a deliberate fail-loud default (§9) rather than silently computing with an absent rate.
- `AllowanceService` — near-identical to `CompensationService`: `create` (O1 overlap + C2b correction, scoped per `allowance_type`), `get_by_employee`, `list_history`, `update` (`is_active` only), authorization Owner Only (mirrors Compensation's already-resolved policy).
- `DeductionTypeService` — plain CRUD, mirrors `EmploymentTypeService`.
- `DeductionService` — `create`/`get`/`list`/`update`/`delete`, each rejecting if the parent `PayrollRun.status == COMPLETED` (new `PayrollRunCompletedError` check, mirroring the immutability-after-completion principle established for Payslip).

**New calculation components** (Domain-Service-shaped — no owned table, no repository of their own; E8: plain composition, not a framework):
- `PayrollRateResolver` — `daily_rate(compensation, as_of_date) -> Money`, `hourly_rate(compensation, as_of_date) -> Money`. Implements D3 exactly: reads `Compensation.base_salary` plus `STANDARD_WORKING_DAYS_PER_MONTH`/`STANDARD_DAILY_HOURS` from `PayrollStatutoryParameterService`, and lives inside Payroll Calculation's own module — never inside Attendance, Leave, Overtime, or Timesheet.
- `OvertimeCalculator` — `compute(employee_id, period_start, period_end) -> PayslipLineItem`. Reads `OvertimeRequestRepository.list_approved_in_range` (duration = Σ `end_time - start_time` for approved requests), multiplies by `PayrollRateResolver.hourly_rate` × `OVERTIME_MULTIPLIER_WEEKDAY` (configurable parameter). Implements D4.
- `AttendanceLeaveDeductionCalculator` — `compute(employee_id, period_start, period_end) -> PayslipLineItem`. Reads `ReconciliationService.get_range`, applies `PayrollRateResolver.daily_rate` per deductible day. Implements D5. **Day-classification default** (documented assumption, not a business rule invention): only days classified `absent` are deductible; `holiday` and `leave` are treated as non-deductible, because no paid/unpaid leave-type distinction exists anywhere in the repository today (`LeaveRequest` has no leave-type field). Flagged in §10 as revisable, not a blocker.
- `StatutoryTaxCalculator` — `compute(gross: Money) -> PayslipLineItem`. Reads a single `STATUTORY_TAX_RATE` parameter and applies a flat-percentage formula. **This is the narrowest defensible v1 formula shape** given zero specified bracket/formula structure (§10) — the calculation engine is code-based per D2/E4; only the rate is data. Swapping in a real progressive-bracket formula later is a code change to this one class, not a schema change (the parameter store already supports arbitrarily many named keys for that future formula).

**Modified:**
- `PayrollCalculationService` — composes all four calculators above via constructor DI (same pattern as its existing `compensation_service`/`payslip_service`/`payroll_run_service` injection). `calculate(payroll_run_id, employee_id)`:
  1. Load `PayrollRun`; reject if `status == COMPLETED` (`PayrollRunAlreadyCompletedError`).
  2. Resolve `Compensation` via `get_by_employee(employee_id, as_of_date=payroll_run.period_end)` — **implementation-level choice**: period **end** date is used as the compensation-resolution cutoff (documented, revisable; not a business rule this plan invents — the alternative, period-start, is equally defensible and can be changed without any schema impact).
  3. Reject if `Compensation.base_salary_currency != payroll_run.currency` (D8/E7 enforcement at the individual-employee level, mirroring the run-level segmentation).
  4. Build line items: `BASE_SALARY` (from Compensation) + `AllowanceService`'s active-as-of-period-end allowances (`ALLOWANCE`, one line item per active allowance) + `OvertimeCalculator` result + `AttendanceLeaveDeductionCalculator` result + each `DeductionRepository.list_by_employee_and_payroll_run` row (`NON_STATUTORY_DEDUCTION`) + `StatutoryTaxCalculator` result (`STATUTORY_DEDUCTION`).
  5. `gross = Σ(earning-typed line items)`, `net = gross − Σ(deduction-typed line items)`.
  6. `PayslipService.create(..., line_items=...)`.
  - `calculate_batch(payroll_run_id)`: switches eligibility source to the new `CompensationRepository.list_active_as_of(payroll_run.period_end)` (§5, resolves §1.1), additionally filtered to `base_salary_currency == payroll_run.currency`. Before recomputing, calls `PayslipService.delete_by_payroll_run(payroll_run_id)` if any Payslips already exist for this run (rerun support, D9) — no-op if none exist (first run).
- `PayrollRunService` — `create` gains period/currency validation (§3.2); `start_processing` transition relaxed (§3.3).
- `PayslipService` — `create` accepts `line_items`; **+** `delete_by_payroll_run` (internal, guarded, not API-routed).

---

# 8. Integration Boundaries — Explicitly Restated

| Capability | Payroll's relationship | Changed by this plan? |
|---|---|---|
| Compensation | Read-only, via existing `get_by_employee`/new `list_active_as_of` | No change to Compensation's own model/service/API |
| Attendance | Read-only, via new `ReconciliationService.get_range` (additive) | No change to `AttendanceEvent`'s own model or per-day classification rules |
| Leave | Read-only, via `ReconciliationService.get_range` (Leave's own classification is already a `ReconciliationService` input, unchanged) | No change to `LeaveRequest`/`LeaveBalance` |
| Overtime | Read-only, via new `OvertimeRequestRepository.list_approved_in_range` (additive) | No change to `OvertimeRequest`'s own model or approval workflow |
| Timesheet | **Not consumed.** No repository evidence ties Timesheet to Payroll anywhere (`TIMESHEET_DESIGN.md` itself notes Payroll has no dependency on it); Advanced Payroll computes its own period-scoped attendance/overtime/leave reads directly, not through Timesheet's own unresolved query-orchestration ambiguity (`TIMESHEET_DESIGN.md` §7, still open, not resolved by this plan and not needed to be) | Not touched |
| Allowance (new) | Owned by Compensation-domain (per D6); consumed read-only by Payroll | New capability, Compensation-owned |
| Deduction/DeductionType (new) | Owned by Payroll (already-decided exclusion) | New, Payroll-owned |
| PayrollStatutoryParameter (new) | Owned by Payroll | New, Payroll-owned |

No upstream capability's authorization boundary, approval workflow, or business logic is modified anywhere in this plan.

---

# 9. Test Strategy

Mirrors the existing `test_compensation_{api,repository,service}.py` three-file-per-capability pattern:

- **New unit/repository/service test files**: `test_payroll_statutory_parameter_{repository,service}.py`, `test_allowance_{api,repository,service}.py`, `test_deduction_type_{repository,service}.py`, `test_deduction_{repository,service}.py`, `test_payslip_line_item_repository.py`.
- **Calculator component tests** (pure/near-pure logic, fixed fixtures, no DB needed beyond fixture setup): `test_payroll_rate_resolver.py`, `test_overtime_calculator.py`, `test_attendance_leave_deduction_calculator.py`, `test_statutory_tax_calculator.py` — including `MissingStatutoryParameterError` coverage.
- **`test_payroll_calculation_service.py`** (extend existing), covering:
  - Structured line items sum correctly to gross/net.
  - Currency-scoped eligibility (`calculate_batch` skips employees whose Compensation currency ≠ run currency).
  - Rerun before completion: two `calculate_batch` calls on the same `DRAFT`/`PROCESSING` run produce a fresh, non-duplicated Payslip set (old line items gone, replaced).
  - `PayrollRunAlreadyCompletedError` on any `calculate`/`calculate_batch` attempt against a `COMPLETED` run.
  - Allowance, overtime, and attendance-deduction line items each independently verified against hand-computed expected values.
- **`PayrollRun` lifecycle tests**: period-must-be-one-calendar-month validation, overlap rejection scoped by currency, idempotent `start_processing`.
- **Payslip immutability regression test**: confirm no `PUT`/`DELETE` route exists at the API layer (unchanged contract); confirm `delete_by_payroll_run` raises once the parent run is `COMPLETED`.
- **Full-suite regression**: run entire existing suite (1833 tests as of the last validated state) to confirm zero regression in Compensation/Payroll/Payslip/Authorization.

---

# 10. Remaining Genuine Gaps (Not Blockers to This Plan)

Per D2/E4, statutory and payroll-operational parameters are explicitly **configurable data** — meaning their actual values are populated *after* deployment by Finance/Payroll admins, not required before implementation. Nothing below blocks building or merging this plan's scaffolding; each is either an operational data-entry step or a documented, revisable implementation default.

1. **Actual statutory tax rate(s)/bracket structure** — content, not architecture. `StatutoryTaxCalculator`'s flat-rate shape (§7) is the narrowest defensible placeholder; a real progressive formula is a future code change to one class, using the same parameter store.
2. **Actual overtime multiplier, standard working days/month, standard daily hours** — operational data, entered via `PayrollStatutoryParameterService` post-deployment.
3. **Attendance/leave deduction day-classification** — resolved via a documented conservative default (only `absent` is deductible) pending a real paid/unpaid leave-type distinction, which does not exist anywhere in this repository today. Revisable without schema impact.
4. **Admin/write authorization for `Deduction`/`DeductionType`/`PayrollStatutoryParameter`** — genuine, pre-existing Architecture gap: no RBAC/permission-actor concept exists anywhere in this codebase (`TECHNICAL_DEBT_REGISTER.md` TD-004, already tracked). `RequireRole` exists but is unused by any capability. **Recommendation, not a plan blocker**: do not expose public write API routes for these three resources in v1 — build the services (fully testable, usable internally/seeded directly), expose Owner-Only read routes only (e.g. an employee viewing their own `Deduction` rows), and defer admin-write routes until TD-004 is resolved or an interim authenticated-only posture is explicitly accepted by Architecture Governance. This affects only the **public API surface**, not the calculation engine itself, which has no remaining blocker.
5. **Compensation-resolution cutoff date within a period** (period-start vs. period-end) — implementation-level choice, documented in §7, revisable without schema impact.
6. **Hourly-rate-based overtime for genuinely hourly employees** — `Compensation.hourly_rate` is named "Supported" in governance but not implemented (`compensation/decision.md` §4); all employees are currently `base_salary`-only, so this has no practical effect yet, but overtime/proration for a future hourly-designated employee population would need that field before it could use a negotiated rate instead of a derived one.

None of these require stopping this plan. They are listed because the audit found them, not because they block implementation.

---

# 11. Validation Commands

```
cd services/api
DATABASE_URL=postgresql+asyncpg://eop:eop@localhost:5432/eop uv run pytest -q
uv run ruff check .
uv run mypy src
uv run alembic upgrade head
uv run alembic downgrade -1   # per new migration, repeated 6x in sequence
uv run alembic upgrade head
```

---

# 12. Files To Modify / Create — Consolidated

**Create:**
```
models/payroll_statutory_parameter.py
models/allowance.py
models/deduction_type.py
models/deduction.py
models/payslip_line_item.py
repositories/payroll_statutory_parameter.py
repositories/allowance.py
repositories/deduction_type.py
repositories/deduction.py
repositories/payslip_line_item.py
services/payroll_statutory_parameter.py
services/allowance.py
services/allowance_authorization.py        # Owner Only, mirrors compensation_authorization.py
services/deduction_type.py
services/deduction.py
services/payroll/rate_resolver.py
services/payroll/overtime_calculator.py
services/payroll/attendance_leave_deduction_calculator.py
services/payroll/statutory_tax_calculator.py
schemas/payroll_statutory_parameter.py
schemas/allowance.py
schemas/deduction_type.py
schemas/deduction.py
schemas/payslip_line_item.py
api/payroll_statutory_parameters.py   # read-only routes only, per §10.4
api/allowances.py
api/deduction_types.py                # deferred write routes, per §10.4
api/deductions.py                     # deferred write routes, per §10.4
alembic/versions/<6 new migrations, sequence in §4>
tests/... (per §9)
```

**Modify:**
```
models/payroll_run.py                 # + period_start, period_end, currency
core/payroll.py                       # + PayslipLineItemType enum
repositories/payroll_run.py           # + find_overlapping_period
repositories/payslip.py               # + list_by_payroll_run
repositories/compensation.py          # + list_active_as_of
repositories/overtime_request.py      # + list_approved_in_range
services/reconciliation.py            # + get_range
services/payroll_run.py               # create validation; start_processing relaxed; new error classes
services/payslip.py                   # create() accepts line_items; + delete_by_payroll_run (internal only)
services/payroll_calculation.py       # composes new calculators; currency-scoped batch; rerun support
schemas/payroll_run.py                # + period_start, period_end, currency on Create/Response
schemas/payslip.py                    # + line_items on Create/Response
main.py                               # register new routers (allowances, payroll_statutory_parameters; deduction routers deferred per §10.4)
```

---

# References

- `docs/architecture/capabilities/payroll-calculation/business-decision-package.md` (D1–D9, E1–E8)
- `docs/architecture/capabilities/{payroll,payslip,compensation,monetary-representation,effective-dating}/decision.md`
- `docs/architecture/00-governance/TECHNICAL_DEBT_REGISTER.md` (TD-004, cited §10.4)
- Current merged code: `models/{payroll_run,payslip,compensation}.py`, `services/{payroll_calculation,compensation,payslip,payroll_run}.py`, `repositories/compensation.py`, `services/effective_dating_evaluator.py`, `db/mixins.py`
