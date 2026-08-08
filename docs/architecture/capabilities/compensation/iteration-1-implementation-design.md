# Compensation — Iteration 1 Implementation Design

**Capability:** Compensation

**Status:** Frozen Scope — Design Complete

**Scope Source:** Direct business/scope decision, given explicitly in-conversation (not a generated document), 2026-08-07

**Depends On:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `discovery-addendum-monetary-representation.md` (baseline, unchanged)

---

# 1. Frozen Iteration 1 Scope

Restated verbatim from the scope decision, not reinterpreted:

- One active Compensation per Employee.
- Base Salary only.
- Base Salary is represented by `Money`.
- Effective From date.
- No allowance, bonus, deduction, or salary components.
- No approval workflow.
- No historical versioning beyond the single active record.

Everything not listed here is explicitly out of scope for Iteration 1 and is not introduced anywhere in this design.

---

# 2. What This Scope Resolves From Prior Governance

This is the first concrete business content Compensation has ever had. It resolves two previously-`Unknown` items, for Iteration 1 specifically — not retroactively for any future iteration:

- **Monetary content** (`decision.md` §9, `architecture-gap-analysis.md` §8): Base Salary, and only Base Salary.
- **Lifecycle** (`domain-model-discovery.md` §2.6, previously tied between `LeaveBalance`'s mutable precedent and `Payslip`'s immutable precedent): **mutable, current-value-only** — "one active record, no historical versioning" directly selects the `LeaveBalance`-shaped precedent over the `Payslip`-shaped one, for this iteration.

Still not addressed by this scope, and not introduced here: relationship to `JobGrade`, relationship to `PayrollRun`/`Payslip`, authorization, and any future component/history model. These remain exactly as open as `discovery-addendum-monetary-representation.md` §6 described.

---

# 3. Aggregate

**`Compensation`** — Aggregate Root, per `decision.md` §4 (restated, not re-derived).

- `employee_id` — FK to `hr_employees.id`, `ON DELETE RESTRICT` (matching the uniform HR-domain convention), **unique** — this is the mechanism that enforces "one active Compensation per Employee" at the database level, not merely by convention.
- `base_salary_amount` — the normalized amount half of a `Money` value.
- `base_salary_currency` — the currency half of the same `Money` value.
- `effective_from` — a plain date, no `effective_to` (consistent with "single active record": there is nothing for a range to bound).

No relationship to `JobGrade`, `PayrollRun`, or `Payslip` is introduced — none is in scope.

---

# 4. Money Integration

**`Money` has no persistence of its own** (`discovery-addendum-monetary-representation.md` §4, restated) — `Compensation` owns two plain columns representing what a `Money` value holds, not a mapped `Money` column.

- **On write** (`create`/`update`): the service constructs `Money(amount, currency)` from the caller's raw input. Construction itself performs validation (currency mandatory, amount required, precision normalized to 2 decimal places via half-up rounding) — this is exactly the mechanism Monetary Representation's own governance decided Compensation would consume. The service then persists `Money.amount`/`Money.currency` as the two plain columns.
- **On read**: the service reconstructs `Money(base_salary_amount, base_salary_currency)` before returning it, so any caller working with the returned value gets the same validated, normalized type — not raw columns.
- `InvalidMoneyError` (from `eop_api.foundation.monetary.types`) is allowed to propagate as a validation failure at the service boundary, the same way existing services propagate their own domain-specific validation errors.

---

# 5. Column Precision — An Implementation Detail, Not a New Business Decision

The approved business decision fixed **scale** (2 decimal places) but not overall **precision** (total significant digits) — that was never asked, and this design does not invent one as business policy. `Numeric` requires both to be specified in standard SQL. This design proposes `NUMERIC(14, 2)` (supports amounts up to ~999,999,999,999.99) purely as a generously-sized technical default, explicitly flagged as **not** a ratified business decision — if actual salary magnitudes ever approach this bound, that is new information for Business, not something this design pre-empts.

`base_salary_currency` is sized `String(3)`, matching the shape of the currency examples already given (`IDR`, `USD`) — a column-sizing choice, not an ISO 4217 validation or registry (which remains explicitly out of scope for Monetary Representation itself).

---

# 6. Repository

`CompensationRepository(BaseRepository[Compensation])` — the proven, zero-exception pattern used by every entity in this repository.

One additional method, directly implied by "one active Compensation per Employee": `get_by_employee_id(employee_id) -> Compensation | None`, mirroring `ShiftRepository.get_by_code`'s exact shape (a single natural-key lookup alongside the generic `get(id)`).

---

# 7. Service

`CompensationService`, mirroring `PayslipService`'s existence-validation pattern and `ShiftService`'s duplicate-prevention pattern:

- `create(data)` — validates `employee_id` exists (`EmployeeNotFoundError`, mirroring `PayslipService`), validates no `Compensation` already exists for that employee (`DuplicateCompensationError`, mirroring `DuplicateShiftCodeError`/`DuplicateHolidayCodeError` — a service-layer pre-check in addition to the DB unique constraint, matching established convention), constructs and validates `Money`, persists.
- `get(id)`, `get_by_employee(employee_id)`, `list()`, `list_paginated()` — standard shape.
- `update(id, data)` — mutates the **same row** in place (amount, currency, and/or `effective_from`); this is what "no historical versioning" means concretely: the prior value is simply overwritten, not retained anywhere.
- `delete(id)` — included by default CRUD convention (every comparable master-data-adjacent entity in this repository has one, e.g. `Shift`, `Holiday`); not explicitly requested by the frozen scope, but not excluded either. Flagged here as a judgment call, not a silent assumption — remove if undesired.

No calculation, no approval, no authorization evaluator — none is in scope.

---

# 8. Schemas

- `CompensationCreate`: `employee_id: UUID`, `base_salary_amount: Decimal`, `base_salary_currency: str`, `effective_from: date`.
- `CompensationUpdate`: same four fields, all optional (`exclude_unset` pattern, matching `ShiftUpdate`/`HolidayUpdate`).
- `CompensationResponse`: `id`, `employee_id`, `base_salary_amount`, `base_salary_currency`, `effective_from`, `created_at`, `updated_at`.

Raw `Decimal`/`str` fields at the schema boundary, not `Money` directly — `Money` is a service/domain-layer concept; the service constructs it from these fields and reconstructs it on the way out, per §4.

---

# 9. API

`/hr/compensation` — matching `HrEmployee`'s own `/hr/` prefix, since this is HR-domain data. `POST` / `GET` (list) / `GET /{id}` / `PUT /{id}` / `DELETE /{id}`. `CurrentUser`-only dependency — no dedicated authorization evaluator, matching "No approval workflow" and the majority unauthorized-CRUD pattern already established across this repository (`decision.md` §7 remains "not decidable today" for anything beyond this iteration's plain access).

---

# 10. Migration

One new table, `compensations`:

- Standard `BaseEntity` mixin columns (`id`, `created_at`/`updated_at`, `created_by`/`updated_by`, `deleted_at`/`is_deleted`, `version` — present by inheritance, unused, exactly as everywhere else in this repository; not a new decision).
- `employee_id UUID NOT NULL REFERENCES hr_employees(id) ON DELETE RESTRICT`, with a `UNIQUE` constraint.
- `base_salary_amount NUMERIC(14, 2) NOT NULL`.
- `base_salary_currency VARCHAR(3) NOT NULL`.
- `effective_from DATE NOT NULL`.
- Index on `employee_id` (mirroring every other employee-scoped FK in this repository).

---

# 11. Explicitly Not Introduced

Per the frozen scope, none of the following appears anywhere in this design: allowance, bonus, deduction, salary components, approval workflow fields (`status`/`approved_by`/`approved_at`), any history/version/snapshot table, `effective_to`, `JobGrade` relationship, `PayrollRun`/`Payslip` relationship, or a dedicated authorization evaluator.

---

# References

- `docs/architecture/capabilities/compensation/decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `discovery-addendum-monetary-representation.md`
- `services/api/src/eop_api/foundation/monetary/types.py`
- `services/api/src/eop_api/models/shift.py`, `holiday.py`, `payslip.py`, `hr_employee.py` (structural precedent)
