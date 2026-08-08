# Payslip — Implementation Plan

**Capability:** Payslip (data-owning capability)

**Status:** Approved — First Iteration: Bounded Context Structure Only

**Version:** 1

**Depends On**

- `docs/architecture/capabilities/payslip/discovery.md`
- `docs/architecture/capabilities/payslip/decision.md`

---

# 1. Summary

This plan implements Payslip Iteration 1: `create`/`get`/`list` only, derived strictly from `decision.md`. No new architectural decision is made here. No item marked `Unknown` or `Deferred` in `decision.md` is resolved here — each is carried forward unchanged (§11).

---

# 2. Scope

## In Scope

- `Payslip` — model, repository, service, API, migration, tests, limited to `create`/`get`/`list` (`decision.md` §4).

## Out of Scope

`PayrollRun` changes; Payroll Calculation; Payroll Authorization; Payroll Processing; Payroll Integration; Payroll export; Payroll reporting; Payroll period engine; Salary calculation; Tax; Benefit; Deduction engine.

---

# 3. Aggregate

`Payslip` — one Aggregate Root, as decided in `decision.md` §1. Not revisited here.

---

# 4. Model

### Repository Evidence

`BaseEntity` mixin fields, present on every persisted entity without exception (`discovery.md` §7): `id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `deleted_at`, `is_deleted`, `version`.

### Required by Decision

- `employee_id` — FK → `hr_employees.id` (`decision.md` §3: "employee_id belongs to Payslip"; §6: `ON DELETE RESTRICT`).
- `payroll_run_id` — FK → `payroll_runs.id` (`decision.md` §2: "ownership direction: Payslip → PayrollRun"). `ON DELETE RESTRICT`, per `decision.md` §6 (Architecture Governance decision).

### Deferred

No field beyond the two FKs above and the `BaseEntity` mixin set is decided. `decision.md`'s own Deferred Decisions list states Payslip's "exact schema, fields... explicitly out of this document's scope." No monetary field, no status field, no period field, and no other business attribute is included in this iteration.

---

# 5. Repository

`PayslipRepository(BaseRepository[Payslip])`. `create`, `get`, `list` only — all inherited from `BaseRepository` unmodified; no override is required for any of the three, since none needs Payslip-specific search or filter behavior. No pagination method (`.paginate`) is exposed, consistent with `decision.md` §4/§5's `create`/`get`/`list`-only scope. No `update`, no `delete`.

---

# 6. Service

`PayslipService`. Methods:

- `create()`
- `get()`
- `list()`

No `update`. No `delete`. No calculation. No orchestration. No authorization.

`create()` validates that the referenced `employee_id` and `payroll_run_id` rows exist (via `HrEmployeeRepository.exists()`/`PayrollRunRepository.exists()`) before creating — the same bounded existence check every other FK-bearing service in the repository already performs on its own required FKs (`discovery.md` §2, §9; e.g. `AttendanceEventService`, `LeaveRequestService`). This is not orchestration in the sense `decision.md` §7 excludes (reaching into another capability to compose or mutate its data) — it is the uniform, existing validate-before-create pattern, unchanged.

---

# 7. API

Router `POST /payslips`, `GET /payslips`, `GET /payslips/{id}`.

No `PUT`. No `PATCH`. No `DELETE`.

`CurrentUser` authentication only. No `CurrentRequestContext`. No `AuthorizationService`.

---

# 8. Migration

One migration: create the `payslips` table only.

Columns: `BaseEntity` mixin columns (§4) plus `employee_id` (FK → `hr_employees.id`, `ON DELETE RESTRICT`) and `payroll_run_id` (FK → `payroll_runs.id`, `ON DELETE RESTRICT`).

Implement `payroll_run_id` using `ON DELETE RESTRICT`, per `decision.md` §6 (Architecture Governance decision, final, no longer Deferred).

---

# 9. Tests

## Repository
- `create` persists and returns a row.
- `get` returns the created row; returns `None` for a missing id.
- `list` returns all rows.

## Service
- `create`/`get`/`list` round-trip.
- `create` with a missing `employee_id` or `payroll_run_id` raises the corresponding not-found error.
- `get` not-found handling.

## API
- `201`/`200`/`404` status codes for `POST`/`GET`/`GET /{id}`.
- Authentication-required check (`401` without `CurrentUser`).

No authorization test. No calculation test. No payroll-processing test.

---

# 10. Validation

```
ruff check .
mypy src
alembic upgrade head
alembic downgrade -1
pytest
```

---

# 11. Deferred Decisions

Carried forward unchanged from `decision.md`. None resolved here:

- Compensation/rate data source (`decision.md` § Deferred Decisions).
- Pay-period cadence (`decision.md` § Deferred Decisions).
- Whether convention-level immutability (no `update`/`delete` exposed) is sufficient for financial/compliance requirements (`decision.md` § Deferred Decisions).
- Whether Payslip is generated synchronously with `PayrollRun` or as a separate downstream step (`decision.md` § Deferred Decisions).
- Payslip Authorization policy (`decision.md` §8) — blocked; no Payslip resource exists until this plan is implemented.
- Batch/period computation mechanism (`decision.md` § Deferred Decisions).

---

# 12. Remaining Risks

Carried forward unchanged from `decision.md`'s Open Questions and Deferred Decisions. None resolved, none invented:

- Whether the convention-level immutability this plan implements (§6, no `update`/`delete`) is adequate to whoever eventually needs to trust a payslip's figures — no repository evidence answers this either way.
- Whether `AuditMixin`'s repository-wide non-population (`decision.md` §9) is a gap that should be addressed before or alongside Payslip, given Payslip's own governance rationale depends on an audit trail existing.

---

# Recommendation

```
Implementation of Payslip Iteration 1 may proceed within the boundaries
defined above.
```

---

# References

- `docs/architecture/capabilities/payslip/discovery.md`
- `docs/architecture/capabilities/payslip/decision.md`
