# Achievement — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Achievement (Performance Management, Roadmap Phase 5)

**Owner:** Engineering (Senior Engineer authority per standing mandate), CPO/CTO decisions applied per this document's own §3

---

# 1. Objective

Implement the smallest coherent, implementation-ready **Achievement** capability from Roadmap Phase 5's `KPI → Target → Achievement → Dashboard → Reporting` sequence, continuing directly from the targeted discovery turn that identified two genuine, unresolved architectural forks (D2: relationship to Target; D3: source of the actual value) and stopped for CPO/CTO decision rather than inventing either.

**Achievement Iteration 1 is a manually entered actual value against exactly one Target. Automatic/computed achievement is deferred.**

---

# 2. Discovery Evidence (from the preceding targeted discovery)

- **`06_PRODUCT_ROADMAP.md`** and **`02_PRODUCT_SCOPE.md` §7 "Performance Management"** list `KPI`, `Target`, `Achievement` as three separate items — the same explicit-separation signal already used twice (KPI, Target) to justify a standalone aggregate rather than a field.
- **`04_SUCCESS_METRICS.md`**: *"Improved KPI achievement"* is the only sentence anywhere in product evidence that touches Achievement's concept — aspirational language, not a shape or computation specification.
- No product document names a formula, a computation rule, a data source, or who records the actual value.
- **Repository evidence**: `Kpi.unit` is free-text with no formula/data-source binding to any other capability (`kpi-iteration-1-scope-and-implementation-plan.md` §7, explicitly out of scope). `VisitRepository`/`SurveyRepository` have no count/aggregate query methods — no existing infrastructure a computed Achievement could read from without first building it. `ReconciliationService` is the only "computed/derived value" precedent in the repository, and it depends on a fixed, hand-coded rule set (holiday/leave/attendance precedence) — there is no analogous per-KPI rule anywhere for Achievement to reuse, and building one would require inventing a formula taxonomy that does not exist in product evidence.

This confirmed D2 and D3 could not be resolved from repository evidence alone — both were genuine product/architecture decisions, correctly escalated rather than guessed.

---

# 3. CPO/CTO Decisions — Final (applied verbatim)

| # | Decision |
|---|---|
| D1 | Achievement is a **standalone aggregate** — not merged into `Kpi` or `Target`. |
| D2 | Achievement **must** reference exactly one `Target` via `target_id` (`ON DELETE RESTRICT`). No independent `employee_id`/`kpi_id`/`period_year`/`period_month` identity — those are inherited through `Target`. |
| D3 | **Manual entry only.** `actual_value` is entered by an authorized administrative user. No automatic calculation, Visit/Survey aggregation, Attendance/Payroll integration, formula engine, or KPI formula binding — computed/derived Achievement is explicitly deferred to a future capability/decision. |
| D4 | **No period fields.** Period is read from `Achievement.target.period_year`/`Achievement.target.period_month` — never duplicated on `Achievement` itself. |
| D5 | **No scope fields** (`employee_id`, `organization_id`, `store_id`, `territory_id`, `region_id`, `area_id`). Employee scope is inherited from `Target`. No new dependency on Territory/Region/Area or Organization Hierarchy. |
| D6 | Authorization: **`RequireRole("admin")`**, reused unmodified. No `AchievementAuthorizationEvaluator`, no Owner Only, no new RBAC/permission/policy infrastructure. `Target.employee_id` is business scope, not an authorization boundary — same reasoning already established for `Target` itself. |
| D7 | **Flat CRUD.** No draft/submitted/approved/finalized/locked/status/revision-history/workflow. |
| D8 | **At most one Achievement per Target**, enforced at the database level via `UniqueConstraint("target_id")` — not service-layer validation alone. |
| D9 | `actual_value: Numeric(18, 6)` — mirrors `Target.goal_value`'s precedent exactly. No `unit`/`formula`/`percentage_type`/`value_type`/`currency`/`measurement_type` field — unit is inherited conceptually through `Target → Kpi.unit`, never duplicated. |

---

# 4. Aggregate / Entity Model

`Achievement(BaseEntity)`, table `achievements`:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | via `UUIDMixin` |
| `target_id` | UUID, FK → `targets.id`, `ON DELETE RESTRICT`, unique | which Target this is the actual result for |
| `actual_value` | `Numeric(18, 6)` | mirrors `Target.goal_value`'s precedent exactly — a generic, non-monetary numeric value |

No `employee_id`, `kpi_id`, `period_year`, `period_month`, or `unit` — all read through `target_id` (§4/§5/§9 above).

---

# 5. Relationships

```text
Achievement.target_id → Target.id   ON DELETE RESTRICT
```

No other relationships. `Target` deletion is restricted while an `Achievement` references it — mirrors every other FK in this repository into a row that must be preserved as history (`Visit.employee_id`, `Survey.visit_id`, `Target.kpi_id`/`Target.employee_id`).

---

# 6. Constraints

- **Cardinality (D8)**: at most one `Achievement` per `Target`, enforced via `UniqueConstraint("target_id", name="uq_achievements_target_id")` — the same DB-level, one-per-parent shape already used by `Survey.visit_id` (`uq_surveys_visit_id`).
- **Referential existence**: `target_id` must reference an existing `Target`, checked in the service layer before insert (mirrors `TargetService.create`'s `KpiRepository(...).exists(...)`/`HrEmployeeRepository(...).exists(...)` pattern), surfaced as a typed application error (`TargetNotFoundError`) rather than a raw FK `IntegrityError`.
- **Duplicate application error**: a pre-insert existence check for the same `target_id` raises `DuplicateAchievementError` (mirrors `DuplicateTargetError`/`DuplicateSurveyError`'s check-then-insert shape), with the DB constraint as the final guarantee.

---

# 7. Period and Scope Inheritance

Achievement carries no period or scope fields of its own (D4/D5). Any caller needing an Achievement's period or employee must resolve it through `Achievement.target_id → Target.period_year`/`period_month`/`employee_id` — a one-hop lookup, not a duplicated column. This mirrors `Survey`'s own resolved-parent pattern (`Survey.visit_id → Visit.employee_id`), extended here to a `Numeric` value instead of Owner Only authorization: the *shape* of "read the parent for what this child doesn't carry" repeats, even though *why* it's needed differs (authorization for Survey; period/scope display for Achievement).

---

# 8. Authorization

**Role Based (`RequireRole("admin")`)** — direct reuse, no new mechanism (D6). Achievement is admin-managed: an administrator manually records the actual result, mirroring exactly how an administrator manually assigns the `Target` goal in the first place. `Target.employee_id` remains business scope only (whose result this is), never an authorization boundary — the same distinction already established for `Target` itself (`target-iteration-1-scope-and-implementation-plan.md` §8), now extended consistently to `Achievement`.

---

# 9. Lifecycle

**Flat CRUD, no status field** (D7). No product evidence describes an approval/submission/locking workflow for Achievement, and none is introduced speculatively.

---

# 10. Explicit Integration Boundaries

Achievement Iteration 1 does **not** calculate from `Visit`, `Survey`, `Attendance`, or `Payroll`. There is no automatic synchronization, no KPI formula engine, no calculation service. A future computed Achievement capability can be designed separately, once product requirements define a formula, source data, aggregation rules, period-calculation semantics, and recalculation semantics — none of which exist in product evidence today. This iteration does not pre-commit to any of those.

---

# 11. Explicit Out of Scope

- Automatic/computed Achievement (Visit/Survey/Attendance/Payroll aggregation, formula engine, KPI formula/data-source binding, hardcoded per-KPI calculation).
- `employee_id`, `organization_id`, `store_id`, `territory_id`, `region_id`, `area_id`, `period_year`, `period_month`, `unit`, `formula`, `percentage_type`, `value_type`, `currency`, `measurement_type` fields on `Achievement`.
- Lifecycle/workflow of any kind (draft/submitted/approved/finalized/locked/revision history).
- Speculative validation: `actual_value >= 0`, `actual_value <= goal_value`, percentage/scoring rules — none required by product evidence or existing repository convention.
- Modifying `Kpi` or `Target` in any way.
- Territory/Region/Area, Organization Hierarchy — not referenced; zero relationship to either.
- Dashboard, Reporting — presentation/aggregation layers over Target+Achievement data that don't exist yet.

---

# 12. Proposed Files

- `docs/architecture/capabilities/performance/achievement-iteration-1-scope-and-implementation-plan.md` — this document
- `services/api/src/eop_api/models/achievement.py`
- `services/api/src/eop_api/repositories/achievement.py`
- `services/api/src/eop_api/schemas/achievement.py`
- `services/api/src/eop_api/services/achievement.py`
- `services/api/src/eop_api/api/achievements.py`
- `services/api/src/eop_api/main.py` (router registration)
- `services/api/src/eop_api/models/__init__.py` (model registration)
- One Alembic migration: `create_achievements_table`
- `services/api/tests/test_achievement_repository.py`, `test_achievement_service.py`, `test_achievements_api.py`

---

# 13. Validation Strategy

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted Achievement tests then full suite.

---

# 14. Remaining Risks

- **Manual entry has no cross-check against `goal_value`** — an administrator can record any `actual_value`, including one that would be nonsensical relative to the Target's goal (e.g., negative, or absurdly large for the KPI's implied unit). Deliberately not validated (D9/§11: no `actual >= 0`, no `actual <= target` rule) since no product evidence defines acceptable bounds and inventing one would be guessing at unconfirmed business policy. Accepted, low-stakes risk consistent with `Target.goal_value`'s identical unvalidated-numeric precedent.
- **One-Achievement-per-Target is a hard ceiling** — if the business later wants to *revise* a recorded actual value (e.g., correcting a data-entry error after the fact), Iteration 1's `update()` (mutating `actual_value` in place) is the only path; there is no history/correction mechanism (mirrors `Target.goal_value`'s own mutable-in-place shape, not `Compensation`'s effective-dated correction pattern). Acceptable for Iteration 1, flagged for awareness if audit-trail requirements emerge later.
- **Computed Achievement remains fully unscoped** — this iteration deliberately leaves the entire computed/derived path undesigned (§10). When product requirements eventually define a formula/source-data model, it may require a schema change to `Achievement` (e.g., a `source`/`is_computed` discriminator) rather than a clean drop-in extension — not a defect now, but a known future migration cost.

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** D1–D9 are all resolved by explicit CPO/CTO decision (§3). No unresolved governance dependency remains — Territory/Region/Area and Organization Hierarchy are not referenced (§5/§11).

---

# References

- `docs/product/04_SUCCESS_METRICS.md`, `02_PRODUCT_SCOPE.md` §7, `06_PRODUCT_ROADMAP.md` Phase 5
- `docs/architecture/capabilities/performance/kpi-iteration-1-scope-and-implementation-plan.md`, `target-iteration-1-scope-and-implementation-plan.md`
- `services/api/src/eop_api/models/target.py`, `survey.py` (structural precedent for FK + `UniqueConstraint` one-per-parent shape)
- `services/api/src/eop_api/services/target.py` (`TargetNotFoundError`-equivalent existence-check pattern), `services/survey.py` (`DuplicateSurveyError` check-then-insert pattern)
