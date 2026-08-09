# Target — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Target (Performance Management, Roadmap Phase 5)

**Owner:** Engineering (Senior Engineer authority per standing mandate), CPO/CTO ownership scope decision applied per this document's own §3

---

# 1. Objective

Determine the smallest coherent, implementation-ready **Target** capability from Roadmap Phase 5's `KPI → Target → Achievement → Dashboard → Reporting` sequence, continuing directly from the prior discovery turn (`OUTCOME B`, ownership unresolved) now that a CPO/CTO decision has resolved Target's ownership scope to **Employee**.

---

# 2. Product Evidence

- **`06_PRODUCT_ROADMAP.md`** and **`02_PRODUCT_SCOPE.md` §7 "Performance Management"** place `Target` as its own item, distinct from `KPI` and `Achievement` — a separable aggregate, not a field.
- **`02_PRODUCT_SCOPE.md` §5 "Planning"** lists `Target Assignment` alongside `Territory Assignment`, `Route Planning`, `Mission Planning`, `Schedule Planning` — an assignment activity, consistent with Target being *assigned to* an execution unit rather than merely defined.
- **`03_TARGET_CUSTOMER.md`**: Field Employees (Sales Representative, SPG, SPB, Merchandiser, Promoter) are the only personas performing the measurable operational work (Attendance, Visit, Survey) that a KPI like "Visit Compliance Rate" would track. Executive/National/Regional needs ("KPI overview", "National KPI", "Territory comparison", "Regional dashboard") are monitoring/rollup needs — Dashboard/Analytics concerns, already out of scope for Target itself.
- **`01_VISION.md` line 27**: *"Are we likely to achieve this month's target?"* — the only concrete period signal anywhere in product evidence, naming a **monthly** cadence.
- **`03_TARGET_CUSTOMER.md`, "Primary Target Customer"**: *"Performance targets"* listed as a characteristic of the target industries (FMCG/Retail/Distribution/Pharma), reinforcing that targets are a real, expected concept at the operational (field-employee) level these industries run on.

---

# 3. CPO/CTO Decision — Ownership Scope

**Target ownership = Employee**, resolved this turn as an ordinary product-scope decision (not an architecture gate), per the governing instruction. Recorded here so the decision travels with the capability, not only with the conversation that made it.

Conceptually:

```text
Target
├── kpi_id      -- which indicator
├── employee_id -- whose goal
├── period      -- which month
└── goal_value  -- the target number
```

**Rationale** (repository/product evidence + established precedent):

1. KPI is already global, definition-only reference data (§4 of `kpi-iteration-1-scope-and-implementation-plan.md`) — Target must attach a scope to it that KPI itself deliberately does not carry.
2. Field Employees are the only personas whose work product a KPI like "Visit Compliance Rate" actually measures — Executive/Regional-level needs are monitoring/rollup, not assignment.
3. `Store` is an operational object being visited (§7 of `store-iteration-1` precedent — `Store` has no "performance owner" role anywhere in product evidence), not a target-bearing actor.
4. Territory/Region/Area remains blocked by the pre-existing, unresolved Phase 3 / Organization Hierarchy collision (`ROADMAP_SEQUENCING_DECISION.md`-adjacent governance, `docs/architecture/00-governance/ARCHITECTURE_DECISION_INDEX.md` lines 498/621/773) — Employee scope introduces no new dependency on that gate, since `HrEmployee` already exists, unblocked, with established FK/query precedent (`Visit.employee_id`, `Compensation.employee_id`, `LeaveBalance.employee_id`).
5. Organization- or territory-level roll-up targets are a plausible *future* capability (a management/reporting view over many employee-level Targets), not a requirement for the smallest coherent Iteration 1.
6. Employee + KPI + period + goal value is sufficient for a future `Achievement` capability to compare an actual measured value against — without implementing `Achievement` now.

---

# 4. Aggregate / Entity Model

`Target(BaseEntity)`, table `targets`:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | via `UUIDMixin` |
| `kpi_id` | UUID, FK → `kpis.id`, `ON DELETE RESTRICT` | which indicator this goal is for |
| `employee_id` | UUID, FK → `hr_employees.id`, `ON DELETE RESTRICT` | whose goal this is |
| `period_year` | `Integer` | extends `LeaveBalance.period_year`'s existing convention (`models/leave_balance.py`) rather than inventing a new period representation |
| `period_month` | `Integer`, 1–12 | paired with `period_year` to express one calendar month; range validated at the Pydantic schema boundary (`Field(ge=1, le=12)`), matching this repository's existing convention of no `CheckConstraint` usage anywhere in `models/` (confirmed by repository search) |
| `goal_value` | `Numeric(18, 6)` | mirrors `PayrollStatutoryParameter.value`'s precedent for a generic, non-monetary numeric value — deliberately not `Numeric(14, 2)`/`Money` (`goal_value` is not currency; its unit is whatever `Kpi.unit` says, e.g. `"%"`, `"visits/day"`) |

No `unit` field on `Target` — it is read from the referenced `Kpi.unit` at presentation time by the caller, never duplicated (per instruction).

---

# 5. Relationships

```text
Target.kpi_id      → Kpi.id        ON DELETE RESTRICT
Target.employee_id → HrEmployee.id ON DELETE RESTRICT
```

No other relationships. No department, organization hierarchy, territory, region, area, or manager-hierarchy reference — consistent with the CPO/CTO decision (§3) and the standing Phase 3/6 gates.

---

# 6. Constraints

- **Uniqueness**: at most one `Target` per `(employee_id, kpi_id, period_year, period_month)`, enforced via a database-level `UniqueConstraint("employee_id", "kpi_id", "period_year", "period_month", name="uq_targets_employee_kpi_period")` — the same DB-level enforcement pattern already used for `Survey.visit_id` (`uq_surveys_visit_id`). No alternative versioning/history semantics introduced.
- **Referential existence**: `kpi_id` must reference an existing `Kpi`; `employee_id` must reference an existing `HrEmployee` — both checked in the service layer before insert (mirrors `CompensationService.create`'s `HrEmployeeRepository(...).exists(...)` pattern, using the already-generic `BaseRepository.exists(id)`), surfaced as typed application errors (`KpiNotFoundError`, `EmployeeNotFoundError`) rather than raw FK `IntegrityError`s.
- **Duplicate application error**: a pre-insert existence check for the same `(employee_id, kpi_id, period_year, period_month)` tuple raises `DuplicateTargetError` (mirrors `DuplicateSurveyError`'s check-then-insert shape), with the DB constraint as the final guarantee.

---

# 7. Monthly Period Semantics

Target Iteration 1 represents exactly **one KPI target for one employee for one calendar month** — `period_year` + `period_month` as two plain integer columns, not a `period_start`/`period_end` date-range pair (the heavier shape `PayrollRun` uses for its own service-validated "exactly one calendar month" rule) and not a generic recurrence/period engine. This is the most direct extension of `LeaveBalance.period_year`'s existing single-integer-field convention to month granularity, and avoids introducing `PayrollRun`-style range-validation logic for a period that is, for Target, always a single discrete month by construction — there is nothing to validate beyond `period_month ∈ [1, 12]`, already handled at the schema boundary.

---

# 8. Authorization

**Role Based (`RequireRole("admin")`)** — direct reuse, no new mechanism, per the CPO/CTO decision (§3, D8): a Target is assigned *to* an employee by an administrator/manager, not self-authored by the employee. `employee_id` is the Target's business scope (whose goal it is), not its authorization boundary (who may write it) — this is a real distinction from every existing Owner Only capability in this repository (`Visit`, `Survey`, `Compensation`, `AttendanceEvent`), where the resource's owning employee is also the actor authorized to act on it. No `TargetAuthorizationEvaluator` is created; no existing evaluator is reused, since none fits an admin-assigns/employee-does-not-self-write shape. Employee-facing read access to one's own assigned Targets is a plausible future extension, not evidenced or required for Iteration 1.

---

# 9. Lifecycle

**Flat CRUD, no status field.** No product evidence describes a draft/approval/effective-dating/versioning lifecycle specific to Target — mirrors `Kpi`/`StoreType`/`JobGrade`'s identical resolution, and is not introduced speculatively for a future `Achievement` capability that does not yet exist.

---

# 10. Explicit Out of Scope

- **Achievement** — the measured/actual value compared against a Target; a separate future capability.
- `actual_value`, achievement percentage, KPI calculation, scoring — no computation of any kind on `Target` itself.
- Dashboard, Reporting — presentation/aggregation layers over Target(+Achievement) data.
- Team, organization, store, territory, region, or area-scoped targets — Employee scope only, per §3; roll-up views over employee-level Targets are a future concern, not this iteration's.
- Target approval, target versioning, target history, target-assignment workflow, automatic target generation — no lifecycle beyond flat CRUD (§9).
- Formula engine, unit taxonomy on `Target` itself — unit is read from `Kpi.unit`, never duplicated (§4).
- Modifying `Kpi` in any way — untouched.
- Territory/Region/Area, Organization Hierarchy — not referenced; zero relationship to either (§5).

---

# 11. Proposed Files (not yet created — discovery only)

- `docs/architecture/capabilities/performance/target-iteration-1-scope-and-implementation-plan.md` — this document
- `services/api/src/eop_api/models/target.py`
- `services/api/src/eop_api/repositories/target.py`
- `services/api/src/eop_api/schemas/target.py`
- `services/api/src/eop_api/services/target.py`
- `services/api/src/eop_api/api/targets.py`
- `services/api/src/eop_api/main.py` (router registration)
- `services/api/src/eop_api/models/__init__.py` (model registration)
- One Alembic migration: `create_targets_table`
- `services/api/tests/test_target_repository.py`, `test_target_service.py`, `test_targets_api.py`

---

# 12. Test Strategy

Mirrors `Kpi`'s three-layer coverage, plus the two-FK existence checks and composite uniqueness `Survey`'s precedent already established:

- **Repository**: create/get, list, update (`goal_value` only), delete, uniqueness violation → `IntegrityError` on duplicate `(employee_id, kpi_id, period_year, period_month)`, pagination, filter by `employee_id`/`kpi_id`.
- **Service**: CRUD; `KpiNotFoundError` on missing `kpi_id`; `EmployeeNotFoundError` on missing `employee_id`; `DuplicateTargetError` on a repeat `(employee_id, kpi_id, period_year, period_month)`; pagination/filter passthrough.
- **API**: 401 unauthenticated matrix, 403 non-admin matrix (mirrors `test_kpis_api.py` exactly), 201/200/204 happy paths, 404 (KPI missing, Employee missing, Target missing), 409 (duplicate).

---

# 13. Validation Strategy

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted Target tests then full suite (`run_in_background: true`, awaited via task notification, never polled).

---

# 14. Remaining Risks

- **Admin-assigns-employee-does-not-self-write is a new authorization shape** (§8) — not wrong, but the first capability in this repository where the "scope" field and the "authorization" mechanism diverge. Future capabilities with the same shape should reuse this reasoning rather than reaching for Owner Only by default.
- **`goal_value`'s unit is implicit** (read from `Kpi.unit`, itself free-text with no fixed taxonomy) — an accepted, low-stakes risk already priced into `Kpi`'s own design (`kpi-iteration-1-scope-and-implementation-plan.md` §11).
- **Monthly-only period model** is evidenced by exactly one product sentence (`01_VISION.md` line 27). If quarterly/annual targets are later required, this will need a genuine schema extension (not merely a new enum value), since `period_year`/`period_month` has no slot for a different grain — acceptable for Iteration 1, flagged for awareness.
- **`TargetUpdate` restricted to `goal_value` only** — `kpi_id`/`employee_id`/`period_year`/`period_month` collectively form the row's identity and uniqueness key; allowing them to change via `PUT` would make an update indistinguishable from a delete-and-recreate. Mirrors `Survey`'s `visit_id` and `Compensation`'s narrow-`update()` precedents. Not stated explicitly in the assigning instruction, resolved here from established precedent rather than escalated, since it is a routine implementation detail, not a business-policy question.

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** Ownership (§3), KPI/Employee relationships (§5), uniqueness (§6), period model (§7), authorization (§8), and lifecycle (§9) are all resolved. No unresolved governance dependency remains — Territory/Region/Area and Organization Hierarchy are not referenced (§10).

---

# References

- `docs/product/01_VISION.md`, `02_PRODUCT_SCOPE.md` §5/§7, `03_TARGET_CUSTOMER.md`
- `docs/architecture/capabilities/performance/kpi-iteration-1-scope-and-implementation-plan.md`
- `services/api/src/eop_api/models/kpi.py`, `leave_balance.py`, `payroll_run.py`, `payroll_statutory_parameter.py` (structural precedent)
- `services/api/src/eop_api/services/compensation.py` (`EmployeeNotFoundError`/`exists()` pattern), `services/survey.py` (`DuplicateSurveyError` check-then-insert pattern)
- `docs/architecture/00-governance/ARCHITECTURE_DECISION_INDEX.md` (Organization Hierarchy gate, referenced not reopened)
