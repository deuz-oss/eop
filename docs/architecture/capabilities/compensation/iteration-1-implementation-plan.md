# Compensation — Iteration 1 Implementation Plan

**Capability:** Compensation

**Status:** Authorized — Iteration 1, Frozen Scope Only

**Version:** 1

**Depends On:** `iteration-1-implementation-design.md`

---

# 1. Objective

Implement Compensation Iteration 1 exactly to the frozen scope: one active `Compensation` per `HrEmployee`, Base Salary only (as `Money`), an `effective_from` date, nothing else. This unblocks Payroll's own Iteration 1 by giving it a real, evidenced upstream capability to depend on instead of an unimplemented one.

This plan does not reopen anything `iteration-1-implementation-design.md` already decided, and does not introduce anything the frozen scope excludes.

---

# 2. Scope

## Included

- `Compensation` model (`models/compensation.py`).
- `CompensationRepository` (`repositories/compensation.py`).
- `CompensationService` (`services/compensation.py`).
- Schemas: `CompensationCreate`, `CompensationUpdate`, `CompensationResponse` (`schemas/compensation.py`).
- API router (`api/compensation.py`), registered in `main.py`.
- One Alembic migration creating the `compensations` table.
- Registration in `models/__init__.py`.
- Tests: repository, service, API — mirroring the three-file-per-entity pattern used throughout this repository (e.g. `test_shift_repository.py`/`test_shift_service.py`/`test_shifts_api.py`).

## Not Included

Per the frozen scope, restated: allowance, bonus, deduction, salary components, approval workflow, any history/version/snapshot mechanism, `effective_to`, `JobGrade`/`PayrollRun`/`Payslip` relationships, dedicated authorization.

---

# 3. Aggregate

`Compensation(BaseEntity)` — Aggregate Root. Fields: `employee_id` (FK, unique, `RESTRICT`), `base_salary_amount` (`Numeric(14, 2)`), `base_salary_currency` (`String(3)`), `effective_from` (`Date`). No relationships mapped to `JobGrade`, `PayrollRun`, or `Payslip`.

---

# 4. Model

```
compensations
    id                    (BaseEntity mixin)
    created_at/updated_at (BaseEntity mixin)
    created_by/updated_by (BaseEntity mixin, unused, matches repo-wide convention)
    deleted_at/is_deleted (BaseEntity mixin, unused, matches repo-wide convention)
    version               (BaseEntity mixin, unused, matches repo-wide convention)
    employee_id           UUID, FK -> hr_employees.id, ON DELETE RESTRICT, UNIQUE
    base_salary_amount    NUMERIC(14, 2), NOT NULL
    base_salary_currency  VARCHAR(3), NOT NULL
    effective_from        DATE, NOT NULL
```

No column beyond these four business fields plus the standard mixins.

---

# 5. Repository

`CompensationRepository(BaseRepository[Compensation])`:
- Inherits `get`/`list`/`create`/`update`/`delete`/`exists`/`count`/`paginate` unmodified.
- Adds `get_by_employee_id(employee_id: UUID) -> Compensation | None`.

---

# 6. Service

`CompensationService`:

- `EmployeeNotFoundError`, `DuplicateCompensationError` — module-local exceptions, matching the established per-service exception pattern (e.g. `PayslipService`'s `EmployeeNotFoundError`, `ShiftService`'s `DuplicateShiftCodeError`).
- `create(data: CompensationCreate) -> Compensation`:
  1. Verify `employee_id` exists via `HrEmployeeRepository.exists()` (mirroring `PayslipService.create`'s existing-FK-validation pattern) — else `EmployeeNotFoundError`.
  2. Verify no existing `Compensation` for that `employee_id` (`CompensationRepository.get_by_employee_id`) — else `DuplicateCompensationError`.
  3. Construct `Money(data.base_salary_amount, data.base_salary_currency)` — `InvalidMoneyError` propagates uncaught if construction fails.
  4. Persist `employee_id`, `Money.amount`, `Money.currency`, `effective_from`.
- `get(compensation_id) -> Compensation | None`
- `get_by_employee(employee_id) -> Compensation | None`
- `list() -> Sequence[Compensation]`
- `list_paginated(pagination, search=None, filters=None) -> Page[Compensation]`
- `update(compensation_id, data: CompensationUpdate) -> Compensation | None` — mutates the same row; if either amount or currency is present in the update, both are read together (defaulting the unset one to the existing stored value) and passed through `Money(...)` again before persisting, so a partial update can never leave a row with a validated-then-silently-corrupted amount/currency pair.
- `delete(compensation_id) -> bool`

Every method follows the established UoW-per-call, expunge-before-return convention used by every other service in this repository (e.g. `ShiftService`).

---

# 7. Schemas

```python
class CompensationCreate(BaseModel):
    employee_id: UUID
    base_salary_amount: Decimal
    base_salary_currency: str
    effective_from: date

class CompensationUpdate(BaseModel):
    base_salary_amount: Decimal | None = None
    base_salary_currency: str | None = None
    effective_from: date | None = None

class CompensationResponse(BaseModel):
    id: UUID
    employee_id: UUID
    base_salary_amount: Decimal
    base_salary_currency: str
    effective_from: date
    created_at: datetime
    updated_at: datetime
```

---

# 8. API

`/hr/compensation`, `CurrentUser`-only:

- `POST /hr/compensation` → `create`
- `GET /hr/compensation` → `list`
- `GET /hr/compensation/paginated` → `list_paginated`
- `GET /hr/compensation/{id}` → `get`
- `GET /hr/compensation/by-employee/{employee_id}` → `get_by_employee`
- `PUT /hr/compensation/{id}` → `update`
- `DELETE /hr/compensation/{id}` → `delete`

Error mapping: `EmployeeNotFoundError` → 404, `DuplicateCompensationError` → 409, `InvalidMoneyError` → 422, missing record on `get`/`update`/`delete` → 404.

---

# 9. Migration

New migration, `down_revision` set to the current head — creates `compensations` exactly per §4, with an index on `employee_id` (in addition to the unique constraint) mirroring every other employee-scoped FK in this repository.

---

# 10. Tests

- **Repository**: create/get/get_by_employee_id/list/update/delete against the real, migration-managed table (mirroring `test_shift_repository.py`'s pattern).
- **Service**: valid creation with a real `Money`-normalized amount; `EmployeeNotFoundError` on a missing employee; `DuplicateCompensationError` on a second `Compensation` for the same employee; `InvalidMoneyError` propagation on invalid amount/currency; update mutating the same row (not creating a new one); delete.
- **API**: full request/response cycle for each endpoint, plus the 404/409/422 error-mapping cases.

---

# 11. Deferred Decisions (unchanged, not resolved by this plan)

Carried forward from `discovery-addendum-monetary-representation.md` §6, restated: relationship to `JobGrade`, relationship to `PayrollRun`/`Payslip`, authorization, any future history/component model, capability naming.

---

# 12. Recommendation

```
Implementation may begin.
```

Every open item that previously blocked Iteration 1 (`architecture-gap-analysis.md` §7) is resolved for this narrow scope by the frozen business decision: monetary content is fixed (Base Salary only), lifecycle is fixed (mutable, single active record), and `Money` supplies the representation mechanism. Nothing in this plan invents content beyond what was explicitly authorized.

---

# References

- `docs/architecture/capabilities/compensation/iteration-1-implementation-design.md`
- `services/api/src/eop_api/models/shift.py`, `payslip.py`, `hr_employee.py`
- `services/api/src/eop_api/foundation/monetary/types.py`
