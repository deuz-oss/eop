# Payroll — Implementation Plan

**Capability:** Payroll (data-owning capability)

**Status:** Approved — First Iteration: Bounded Context Structure Only

**Version:** 3 (refined — reconsiders v2's field-less `PayrollRun` per new repository evidence about identity fields; `Payslip` deferral re-evaluated and confirmed unchanged)

**Depends On**

- `docs/architecture/capabilities/payroll/discovery.md`
- `docs/architecture/capabilities/payroll/decision.md`
- `docs/architecture/capabilities/payroll/domain-model-discovery.md`

---

# Objective

This is the first Payroll implementation iteration. Its sole purpose is to introduce the Payroll bounded context's structural skeleton into the codebase — one persisted aggregate, its repository, its service, its API, and its migration — with zero business behavior of any kind. The objective is to prove the bounded context exists and is reachable (a table, a CRUD surface) using exactly the same shape the repository already uses for its simplest existing modules, not to make any progress on payroll computation, which `decision.md` §7/§9 and `domain-model-discovery.md`'s Remaining Unknowns both found unsupported by repository evidence.

This refinement (v3) revisits one point from v2: `PayrollRun` was scaffolded with no field beyond `BaseEntity`'s mixins. Repository evidence — checked again below, not merely re-asserted — shows every persisted aggregate in the repository carries an identity beyond its UUID, even in every case where business behavior was deferred. `PayrollRun`'s field-less shape was an outlier against that pattern, not a neutral minimal default. This document corrects that, without introducing any business rule.

This document is a plan only. No production code, no test code, and no ADR are created by it.

---

# Scope

## Included

- `PayrollRun` — model, repository, service, schemas, API, tests (§ Model–§ Tests).
- One migration creating the `payroll_runs` table only.
- Model registration (`models/__init__.py`) and router registration (`main.py`).

## Excluded

Per the governing instruction, restated here as binding, not as a reminder:

No business behavior. No payroll calculations. No authorization. No approval workflow. No batch execution. No event publishing. No integration. No salary computation. No tax. No allowance. No deduction. No posting. No closing. No export. No import. No reporting. No notifications. No effective dating. No historical payroll. No currency handling. No policy engine. No payroll period. No status/lifecycle field. No employee scope. No monetary field. No totals. No processing timestamps beyond the standard `created_at`/`updated_at` every entity already has.

`Payslip` is not created in this iteration, in any form (§ Aggregate).

---

# Aggregate

**Only `PayrollRun` belongs in this first implementation.** Unchanged from v2.

## Why `PayrollRun` Only

`domain-model-discovery.md` A1 classifies both `PayrollRun` and `Payslip` as separate Aggregate Roots, each with its own repository and service. What this document sequences is which one is built first, under the "same size and complexity as a standalone master-data module" constraint.

Every module reviewed as a "standalone master-data module" (`JobGrade`, `Holiday`, `Shift`, `EmploymentType`, `EmploymentStatus` — `ARCHITECTURE_INVENTORY.md`'s own "HR — Status: Mature" grouping) has **zero foreign keys**. `Payslip`, per `decision.md` §5, requires at minimum two — `payroll_run_id` and `employee_id` — the same shape `ARCHITECTURE_INVENTORY.md` already categorizes separately, under "Leave"/"Attendance"/"Workflow" (`Status: Partial`), not under the zero-FK master-data group. Building `Payslip` now would already exceed the complexity bar this iteration is bound to, independent of the field-identity question re-evaluated below.

## Payslip — Re-Evaluated

The instruction asks this deferral to be re-checked, not merely repeated. Re-checking against the same evidence: nothing about `Payslip`'s required shape has changed. It still needs `payroll_run_id` (a reference to a table this plan is only now creating, so the FK target would not yet exist at the point `Payslip` would be scaffolded) and `employee_id` (still excluded from `PayrollRun` itself by this iteration's own scope, § Model). Both FKs remain outside the zero-FK bound every reviewed master-data module observes. **The deferral decision is unchanged**, and scope is not expanded to include it. `Payslip`'s name remains reserved in documentation only (`decision.md` §3, `domain-model-discovery.md` A1), following the same reservation-without-code convention already used for `AttendanceAuthorizationEvaluator` (`attendance-authorization/decision.md` §4).

---

# Files to Create

Unchanged from v2 — the field additions below do not add or remove any file, only their contents:

- `services/api/src/eop_api/models/payroll_run.py`
- `services/api/src/eop_api/repositories/payroll_run.py`
- `services/api/src/eop_api/schemas/payroll_run.py`
- `services/api/src/eop_api/services/payroll_run.py`
- `services/api/src/eop_api/api/payroll_runs.py`
- `services/api/alembic/versions/<timestamp>_<hash>_create_payroll_runs_table.py`
- `services/api/tests/test_payroll_run_repository.py`
- `services/api/tests/test_payroll_run_service.py`
- `services/api/tests/test_payroll_runs_api.py`

## Files to Modify (registration only)

- `services/api/src/eop_api/models/__init__.py` — add `from eop_api.models.payroll_run import PayrollRun`, alphabetically ordered (between `Organization` and `OvertimeRequest`), and `"PayrollRun"` to `__all__` in the same position.
- `services/api/src/eop_api/main.py` — add `from eop_api.api.payroll_runs import router as payroll_runs_router` and `app.include_router(payroll_runs_router, responses=PROBLEM_RESPONSES)`, following the existing ordering exactly (`main.py:9-36`, `82-112`).

No other file is created or modified.

---

# Model

`PayrollRun(BaseEntity)`, `__tablename__ = "payroll_runs"`.

## Re-Evaluation of `code` / `name` / `description`

Repository-wide check across every persisted aggregate reviewed in prior Payroll documents, redone here specifically for this question:

| Entity | Has identity beyond UUID? |
|---|---|
| `HrEmployee` | Yes — `employee_number` (unique), `email` (unique), `full_name` |
| `AttendanceEvent` | Yes — no `code`/`name`, but `employee_id` + `event_time` + `event_type` form its natural identity (event-shaped, not reference-shaped) |
| `LeaveRequest` | Yes — `employee_id` + `start_date`/`end_date` |
| `LeaveBalance` | Yes — `employee_id` + `period_year` |
| `OvertimeRequest` | Yes — `employee_id` + `overtime_date` |
| `Timesheet` | Yes — `employee_id` + `start_date`/`end_date` |
| `Shift`, `Holiday`, `JobGrade`, `EmploymentType`, `EmploymentStatus` | Yes — all five carry `code` (`UniqueConstraint`) + `name` (indexed); all five also carry `description` (nullable, no constraint, no index) |

No persisted entity anywhere in the repository has zero fields beyond `BaseEntity`'s mixins. v2's field-less `PayrollRun` was inconsistent with this uniform pattern — every other entity's "minimal" shape still includes at least one business-key field. This document corrects that.

`PayrollRun` is not employee/date-scoped (that role stays with `Payslip`, out of scope here, § Aggregate), so the event/transactional identity shape (`employee_id` + date) does not apply. The applicable precedent is the reference/master-data shape (`code`/`name`/`description`), evaluated field by field:

### `code` — **Supported by repository precedent**

Evidence: `Shift.code`, `Holiday.code`, `JobGrade.code`, `EmploymentType.code`, `EmploymentStatus.code` — 5 of 5 reviewed master-data entities, each `String(50)`, each under a `UniqueConstraint`.

Why identity, not business data: `code` is an opaque, caller-assigned, globally-unique external identifier. It carries no computation, no monetary value, no period/date semantics, and no status — nothing about *what a run computed* or *when it covers*, only *which row this is*, exactly matching every other module's use of `code`. **Accepted.**

### `name` — **Supported by repository precedent**

Evidence: same 5 of 5 entities, `String(255)`, indexed (`ix_*_name`), never unique.

Why identity, not business data: a human-readable label paired with `code`, for display/lookup only — same rationale as `code`. Does not imply a period, a computation, or a state. **Accepted.**

### `description` — **Weak precedent (as identity)**

Evidence: the same 5 of 5 entities also carry a nullable `description: String(1000)` — presence-precedent is as strong as `code`/`name`'s. But `description` is never part of a `UniqueConstraint`, never indexed, and serves no lookup or identity function anywhere in the repository — its role in every reviewed module is optional free-text annotation, not identity.

Disposition: **not added in this iteration.** The instruction scopes this reconsideration to "minimal domain identity," not "replicate every field a master-data module happens to carry." `description` fails the identity test even though its presence-precedent is strong. This is not a rejection on evidentiary grounds — the precedent for its *presence* is solid — it is a scope discipline decision: it is deferred, not excluded, and could be added later as a purely additive, nullable column with no migration conflict, should a future iteration find a reason to.

## Fields

```
id                (UUID, PK — UUIDMixin)
code              String(50), unique
name              String(255), indexed
created_at        DateTime(timezone=True) — TimestampMixin
updated_at        DateTime(timezone=True) — TimestampMixin
created_by        UUID | None — AuditMixin
updated_by        UUID | None — AuditMixin
deleted_at        DateTime(timezone=True) | None — SoftDeleteMixin
is_deleted        Boolean — SoftDeleteMixin
version           Integer — VersionMixin
```

No other field. Every field excluded by the governing instruction (`payroll period`, `status`, `employee scope`, `monetary fields`, `totals`, `currency`, `processing timestamps` beyond the standard mixin pair, `approval state`, `lifecycle state`, `effective dating`) remains excluded — none of the two accepted fields (`code`, `name`) touches any of these; both are opaque identity, not payroll data.

---

# Repository

`PayrollRunRepository(BaseRepository[PayrollRun])`, matching `EmploymentTypeRepository`'s shape exactly (`repositories/employment_type.py:19-28`) — the closest precedent now that `PayrollRun`'s field set (`code`+`name`, no second unique field) matches `EmploymentType`'s (`code`+`name`+`description`) more closely than `JobGrade`'s (`code`+`name`+`level`+`description`):

```python
SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (PayrollRun.code, PayrollRun.name)

class PayrollRunRepository(BaseRepository[PayrollRun]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PayrollRun)

    async def get_by_code(self, code: str) -> PayrollRun | None:
        stmt = select(PayrollRun).where(PayrollRun.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[PayrollRun]:
        """Paginated listing, text-searched against `code`/`name`."""
        return await super().paginate(
            offset=offset, limit=limit, search=search,
            search_fields=search_fields, filters=filters, filterable_fields=filterable_fields,
        )
```

No `FILTERABLE_FIELDS` — `JobGrade`'s equivalent exists only to support its `level` field, which `PayrollRun` does not have (§ Model); `EmploymentType`'s repository has none either, for the same reason. CRUD only, matching every reviewed repository: no orchestration, no business logic, no cross-capability access.

---

# Service

`PayrollRunService`, matching `EmploymentTypeService`'s exact shape (`services/employment_type.py`), including its single duplicate-code guard:

```python
class DuplicatePayrollRunCodeError(Exception):
    """Raised when a payroll run code is already in use."""


class PayrollRunService:
    def __init__(self, uow_factory=SQLAlchemyUnitOfWork) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: PayrollRunCreate) -> PayrollRun:
        async with self._uow_factory() as uow:
            repo = PayrollRunRepository(uow.session)
            if await repo.get_by_code(data.code):
                raise DuplicatePayrollRunCodeError(data.code)
            payroll_run = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(payroll_run)
            return payroll_run

    # get / list / list_paginated: identical shape to EmploymentTypeService, no change

    async def update(self, payroll_run_id: uuid.UUID, data: PayrollRunUpdate) -> PayrollRun | None:
        async with self._uow_factory() as uow:
            repo = PayrollRunRepository(uow.session)
            payroll_run = await repo.get(payroll_run_id)
            if payroll_run is None:
                return None
            values = data.model_dump(exclude_unset=True)
            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != payroll_run_id:
                    raise DuplicatePayrollRunCodeError(values["code"])
            updated = await repo.update(payroll_run_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    # delete: identical shape to EmploymentTypeService, no change
```

The uniqueness check on `code` enforces identity integrity only — it is the same kind of check every reviewed master-data service performs, not a business rule about payroll. No existence-check against another entity (`PayrollRun` references nothing, § Model), no `_authorize` method, no computation method, no call to any other capability's repository or service, no call to `EventService`/`JobService` (both confirmed unused-by-design infrastructure, `domain-model-discovery.md` E3).

---

# API

`api/payroll_runs.py`, prefix `/hr/payroll-runs`, mirroring `api/employment_types.py`'s route set exactly (`api/employment_types.py:30-109`):

| Route | Behavior |
|---|---|
| `POST /hr/payroll-runs` | `201`, creates and returns; `409` on duplicate `code` |
| `GET /hr/payroll-runs` | `200`, full list |
| `GET /hr/payroll-runs/paginated` | `200`, paginated, text-searched against `code`/`name` |
| `GET /hr/payroll-runs/{id}` | `200` or `404` |
| `PUT /hr/payroll-runs/{id}` | `200`, `404`, or `409` on duplicate `code` |
| `DELETE /hr/payroll-runs/{id}` | `204` or `404` |

Every route depends on `CurrentUser` only, matching every master-data module reviewed (none requires `CurrentRequestContext`). **Payroll Authorization is explicitly not introduced** — `payroll-authorization/decision.md` remains in force and unchanged; this plan does not add `RequestContext`, `AuthorizationRequest`, or any evaluator to this router.

## Schemas

Mirroring `EmploymentTypeCreate`/`Update`/`Response` exactly, minus `description` (§ Model):

```python
class PayrollRunCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)

class PayrollRunUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)

class PayrollRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    created_at: datetime
    updated_at: datetime
```

No validation beyond length/non-emptiness is specified for `code`'s format — the repository has no precedent anywhere for a structured/formatted code (every reviewed `code` field is a free-form unique string), and inventing a format (e.g., implying a period-derived naming convention) would reintroduce exactly the excluded "payroll period" concept through the back door. `code` is caller-assigned free text, nothing more.

---

# Database Migration

Create `payroll_runs` only, matching `create_employment_types_table`'s structure:

```python
def upgrade() -> None:
    op.create_table(
        "payroll_runs",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_payroll_runs_code"),
    )
    op.create_index("ix_payroll_runs_name", "payroll_runs", ["name"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_payroll_runs_name", table_name="payroll_runs")
    op.drop_table("payroll_runs")
```

`revision`/`down_revision`: implementation must set `down_revision` to the alembic head current at implementation time (confirmed at this plan-writing time to be `9c3d5f1a7b2e`, `add_user_id_to_hr_employees` — implementation must re-verify this has not advanced). No other table is created, altered, or dropped. No column is added to any existing table.

---

# Tests

Mirroring `test_employment_type_repository.py`/`test_employment_type_service.py`/`test_employment_types_api.py`'s shape:

## Repository (`test_payroll_run_repository.py`)
- `create` persists and returns a row with a generated `id`.
- `get_by_code` returns the matching row; `None` for a non-existent code.
- `get` returns the created row; `None` for a missing id.
- `list` returns all rows.
- `paginate` returns a `Page`; search against `code`/`name` narrows results.
- `update` mutates `updated_at` via `onupdate`; `None` for a missing id.
- `delete` removes the row (hard delete, per `BaseRepository.delete`'s existing, uniform behavior); `False` for a missing id.

## Service (`test_payroll_run_service.py`)
- `create`/`get`/`list`/`list_paginated`/`update`/`delete` round-trip.
- `create` with a duplicate `code` raises `DuplicatePayrollRunCodeError`.
- `update` changing `code` to one already in use by a different row raises `DuplicatePayrollRunCodeError`; updating a row's `code` to its own current value does not.
- Not-found handling for `get`/`update`/`delete`.

## API (`test_payroll_runs_api.py`)
- `201`/`200`/`404`/`204` status codes for each route.
- `409` on duplicate `code` for `create` and `update`.
- Authentication-required check (`401` without `CurrentUser`).
- No `403` test — no authorization exists to test.

## Migration
- `alembic upgrade head` succeeds and creates `payroll_runs` with exactly the ten columns specified (§ Database Migration), the `code` unique constraint, and the `name` index.
- `alembic downgrade -1` succeeds and drops `payroll_runs` cleanly, leaving no orphaned index or constraint.

No computation, lifecycle-transition, authorization, or cross-capability integration test is planned.

---

# Validation

Execute, once implementation is complete:

```
ruff check .
mypy src
alembic upgrade head
alembic downgrade -1
alembic upgrade head
pytest
```

Regression scope: `PayrollRun` only. No existing producer capability's file is modified (§ Files to Create), so a passing full-suite run should show zero change to any existing test's outcome.

---

# Explicitly Out of Scope

- `Payslip` (§ Aggregate) — re-evaluated, deferral confirmed, not expanded.
- Any business behavior, payroll calculation, salary computation, tax, allowance, or deduction logic.
- Authorization of any kind — `payroll-authorization/decision.md` remains blocked and unchanged.
- Approval workflow — no `ApprovalService` integration, no `status` field to transition.
- Batch execution — no iteration over multiple employees or multiple `PayrollRun`s; no use of `JobService`.
- Event publishing — no use of `EventService`.
- Integration with any producer capability (`LeaveRequest`, `OvertimeRequest`, `Timesheet`, `AttendanceEvent`/`ReconciliationService`, `LeaveBalance`, `Holiday`, `Shift`, `JobGrade`, `EmploymentType`, `EmploymentStatus`) — `PayrollRun` reads nothing from them; it exists as an isolated table.
- Posting, closing, export, import, reporting, notifications.
- Effective dating, historical payroll, retroactive adjustment.
- Currency handling.
- Policy engine.
- `PayrollRun.description` — deferred, not rejected (§ Model).

---

# Risks

1. **`code`'s format is entirely caller-defined.** No repository precedent constrains what a valid `code` looks like beyond length/non-emptiness (§ API, Schemas) — implementation must not infer or validate a period-derived format (e.g., `"2026-08"`), as that would reintroduce the excluded payroll-period concept through field validation rather than through a new column. `code` must remain an opaque string.
2. **`down_revision` drift.** This plan records the alembic head as of plan-writing time (`9c3d5f1a7b2e`); implementation must re-check the actual head, not trust this document's snapshot.
3. **Two-iteration sequencing risk, restated from v2, unchanged.** Deferring `Payslip` entirely means this iteration produces a `PayrollRun` with no consumer and no referencing table yet — by design, re-confirmed in § Aggregate, not an omission.
4. **`description`'s deferral (§ Model) may need revisiting once a real use case for administrator annotation appears** — this is not a risk to this iteration's correctness, only a note that the identity-only scope drawn here is deliberately narrower than "everything every master-data module happens to have."
5. **Hard-delete/unenforced-version inheritance**, uniform platform behavior (`domain-model-discovery.md` E4) — not a Payroll-specific gap, not addressed by this plan.

---

# Architecture Contract

The following documents collectively define this plan's contract:

- `docs/architecture/capabilities/payroll/discovery.md`
- `docs/architecture/capabilities/payroll/decision.md`
- `docs/architecture/capabilities/payroll/domain-model-discovery.md`

Implementation shall conform to these documents. If repository evidence contradicts any of them, implementation must stop and escalate to Architecture Governance. No architectural decision — including any decision about `Payslip`'s schema, `PayrollRun`'s eventual business fields, lifecycle, or batch processing — may be made during implementation of this plan.

---

# References

- `docs/architecture/capabilities/payroll/discovery.md`
- `docs/architecture/capabilities/payroll/decision.md`
- `docs/architecture/capabilities/payroll/domain-model-discovery.md`
- `docs/architecture/capabilities/payroll-authorization/decision.md` (unaffected)
- `docs/architecture/10-reference/ARCHITECTURE_INVENTORY.md` (source of the "standalone master-data module" grouping used to bound this iteration's complexity)
- `services/api/src/eop_api/models/employment_type.py`, `repositories/employment_type.py`, `schemas/employment_type.py`, `services/employment_type.py`, `api/employment_types.py` (primary structural precedent as of this refinement — closer field-shape match than `JobGrade`, this plan's v2 precedent)
