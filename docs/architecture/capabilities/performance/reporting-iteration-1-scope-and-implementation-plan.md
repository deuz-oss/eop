# Reporting — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Reporting (Performance Management, Roadmap Phase 5)

**Owner:** Engineering (Senior Engineer authority per standing mandate), CPO/CTO decision applied per this document's own §3

---

# 1. Objective

Implement the smallest coherent, implementation-ready **Reporting** capability from Roadmap Phase 5's `KPI → Target → Achievement → Dashboard → Reporting` sequence — the last item in the sequence — continuing directly from the prior targeted discovery turn (`OUTCOME B`, content/shape unresolved) now that a CPO/CTO decision has resolved what Reporting Iteration 1 actually displays.

**Reporting Iteration 1 is a read-only operational report listing existing `Target` + `Achievement` data — employee, KPI, period, goal value, actual value — for `Achievement` rows that already exist. No new data, no export, no scheduling, no calculation.**

---

# 2. Prior Discovery Evidence (recap)

- Roadmap and Product Scope both list `Reporting` as its own item, separate from `Dashboard` (`02_PRODUCT_SCOPE.md` §8: `Dashboard`, `Operational Report` as sibling bullets).
- No persona, format, or mechanism evidence exists anywhere in product docs beyond the bare label — the content gap was genuine and correctly escalated rather than invented.
- "Reporting" is overloaded elsewhere in governance docs with two unrelated meanings: TD-003's "organizational reporting" (employee-manager hierarchy lines) and Phase 7's gated "Reporting Platform" (enterprise infrastructure, "Future ADRs required") — neither is this capability.
- No CSV/PDF/export precedent exists anywhere in this codebase.

---

# 3. CPO/CTO Decision — Content/Shape (D1, Final)

**Reporting Iteration 1 = a read-only list of existing `Achievement` rows, each resolved through its `Target` to `Kpi` and `HrEmployee`.**

Relation chain, as decided: `Achievement → Target → Kpi + HrEmployee`.

Fields displayed, minimum: employee, KPI, period (year/month), target goal value, achievement actual value.

**Row anchor resolved from the decision's own stated relation direction**: the chain begins at `Achievement`, not `Target` — read literally, this means one report row per existing `Achievement`, not one row per `Target` with a nullable Achievement column. This also matches the decision's own phrasing — *"data ... yang sudah ada"* ("data that already exists") — an `Achievement` row is exactly a record that already exists (unlike a `Target` with no recorded result yet, which is a goal, not yet an outcome). `Achievement.target_id` is `ON DELETE RESTRICT` and non-nullable, so every `Achievement` is guaranteed to resolve a `Target`, which is guaranteed to resolve a `Kpi` and an `HrEmployee` — no left-join/null-handling ambiguity, no invented business rule about how to display a Target without an Achievement.

---

# 4. Explicit Out of Scope (from D1, restated for completeness)

CSV export, PDF generation, scheduled reports, email delivery, persisted report definitions, report templates, report history/snapshots, arbitrary report builder, formula/calculation engine, scoring, achievement percentage, Territory/Region/Area, Organization Hierarchy, Visit/Survey aggregation, changes to `Kpi`/`Target`/`Achievement`, Phase 7 Reporting Platform.

---

# 5. Technical Shape — Resolved from Repository Precedent

## 5.1 API Response Shape

```text
ReportingLineResponse
├── achievement_id     -- Achievement.id
├── target_id          -- Achievement.target_id
├── kpi_id             -- Target.kpi_id
├── kpi_code           -- Kpi.code
├── kpi_name           -- Kpi.name
├── employee_id        -- Target.employee_id
├── employee_number     -- HrEmployee.employee_number
├── employee_full_name -- HrEmployee.full_name
├── period_year        -- Target.period_year
├── period_month        -- Target.period_month
├── goal_value          -- Target.goal_value
└── actual_value        -- Achievement.actual_value
```

Human-readable fields (`kpi_code`/`kpi_name`, `employee_number`/`employee_full_name`) are included, not just FK ids — a report is read by a person, unlike an ordinary CRUD index endpoint; this mirrors why every other schema in this repository that references a human (e.g., none currently denormalize a name, but every UI-facing precedent — `HrEmployeeResponse` itself — always exposes `full_name` directly) exposes readable identity, not opaque UUIDs, as the primary consumption surface. No other fields — matches the decision's explicit minimum field list exactly, nothing added.

## 5.2 Repository

**A new repository is required** — no existing single-model repository can answer a 4-table join (`Achievement` × `Target` × `Kpi` × `HrEmployee`), and `BaseRepository[ModelT]` is generically tied to exactly one model.

The precedent to follow is **`DashboardRepository`**, not `AchievementRepository`/`TargetRepository`: `DashboardRepository`'s own docstring already establishes this exact exception — *"Unlike the other repositories, this one is not tied to a single model, so it does not subclass `BaseRepository`."* A cross-cutting, read-only, multi-table reporting query is architecturally identical to that shape, not a persistence concern of any single aggregate (`Achievement` owns its own row, not a join view across four tables). Bolting this query onto `AchievementRepository` would conflate Achievement's own persistence-only responsibility with a cross-cutting reporting concern — the same reasoning that kept `SurveyRepository.paginate_by_employee_id` a narrow, hand-written query specific to its own repository rather than a `BaseRepository` change, extended one level further here since the join spans capabilities, not just a parent/child pair within one capability.

`ReportingRepository.paginate(...)`: one hand-written SQL join (`Achievement` → `Target` → `Kpi`, `Target` → `HrEmployee`), filterable by `employee_id`/`kpi_id`/`period_year`/`period_month` (§5.3), returning `Page[ReportingLineResponse]` directly (rows are already the final shape — no intermediate ORM entity to wrap, mirroring `DashboardRepository.get_counts()` returning a plain dataclass rather than a model instance).

## 5.3 Filtering / Pagination — Minimum Defensible

**Pagination is mandatory**, not optional — this report's row count grows with every `Achievement` ever recorded, unbounded, across the whole organization; every other list endpoint in this codebase paginates for exactly this reason. Unlike `Kpi`/`Target`/`Achievement` (which each also expose an unpaginated `GET ""`), Reporting exposes **only the paginated form** — a single `GET /performance/reporting` route returning `Page[ReportingLineResponse]` directly, no separate unbounded list variant. This is a deliberate, minimal deviation from the dual-endpoint convention, justified specifically by this capability's own nature (an operational report, consumed page by page, not a small reference/assignment list) — not a new convention, a narrower one.

**Filtering**: `employee_id`, `kpi_id`, `period_year`, `period_month` — the exact same fields `TargetRepository.FILTERABLE_FIELDS` and `AchievementRepository.FILTERABLE_FIELDS` already expose one layer down. Extending identical filters onto their join view is a direct, low-risk continuation of established precedent, not a new capability — a caller who could already filter Targets by employee/KPI/period can filter this report by the same dimensions. No text search (no free-text field exists on any of the four joined tables' relevant columns beyond `Kpi.name`/`code`, and search was not requested by the CPO/CTO decision — not added speculatively).

## 5.4 Service / API Architecture

`ReportingService.list_paginated(pagination, filters)` — a single read-only method delegating to `ReportingRepository.paginate(...)`, mirroring `PerformanceDashboardService`'s and `TargetService.list_paginated`'s identical shape (no `create`/`update`/`delete`: this capability creates no data, per D1). No UnitOfWork commit ever occurs — pure read, same as `PerformanceDashboardService`.

API: `services/api/src/eop_api/api/reporting.py`, `router = APIRouter(prefix="/performance/reporting", tags=["Performance Management"])`, one route: `GET ""` → `Page[ReportingLineResponse]`.

## 5.5 Authorization

**Role Based (`RequireRole("admin")`)** — not `CurrentUser` (Dashboard's own precedent does not transfer here). Dashboard exposes only aggregate *counts*, a low-sensitivity signal already precedented as ungated. Reporting exposes **row-level detail**: specific employees' individual goal and actual values, organization-wide, not scoped to the caller — the same exposure category as `Kpi`/`Target`/`Achievement`'s own list/get endpoints, all of which are `RequireRole("admin")`. This is the correct precedent to extend, not Dashboard's — a report that reveals "Ada Lovelace's Visit Compliance Rate goal was 95.5, actual was 90.25" is materially different from a report that reveals only "12 Achievements exist total."

## 5.6 Route Naming

`GET /performance/reporting`, tag `"Performance Management"` — consistent with `Kpi`/`Target`/`Achievement`/Dashboard's shared tag and `/performance/...` prefix convention (Dashboard already established `/performance/dashboard`; `/performance/reporting` is the direct sibling).

---

# 6. Proposed Files

- `docs/architecture/capabilities/performance/reporting-iteration-1-scope-and-implementation-plan.md` — this document
- `services/api/src/eop_api/schemas/reporting.py`
- `services/api/src/eop_api/repositories/reporting.py`
- `services/api/src/eop_api/services/reporting.py`
- `services/api/src/eop_api/api/reporting.py`
- `services/api/src/eop_api/main.py` (router registration only)
- `services/api/tests/test_reporting_repository.py`, `test_reporting_service.py`, `test_reporting_api.py`

No model, no migration — this capability owns no persisted state of its own (reads `Achievement`/`Target`/`Kpi`/`HrEmployee`, creates nothing, per D1/§4).

---

# 7. Test Strategy

- **Repository**: empty state (zero rows); one Achievement resolves the full joined row correctly; filtering by each of `employee_id`/`kpi_id`/`period_year`/`period_month`; pagination total/offset/limit slicing; a `Target` with no `Achievement` does **not** appear (confirms `Achievement`-anchored, not `Target`-anchored).
- **Service**: pagination/filter passthrough.
- **API**: 401 unauthenticated; 403 non-admin; 200 admin happy path with correct field shape; pagination.

---

# 8. Validation Strategy

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; no Alembic migration exists for this iteration (no persisted state), so no reversibility check applies; targeted tests then full suite.

---

# 9. Remaining Risks

- **Achievement-anchored (not Target-anchored) means Targets without a recorded Achievement never appear in this report** — an administrator cannot use this report alone to see "which targets are still missing a result." Deliberately resolved this way from the CPO/CTO decision's own literal relation direction and "data that already exists" framing (§3); if a future need for a Target-inclusive (left-joined) view emerges, it is a distinct, separately-decided capability, not an extension of this one.
- **Paginated-only (no plain `GET ""`)** is a deliberate, narrower deviation from the `Kpi`/`Target`/`Achievement` dual-endpoint convention — flagged for awareness, not a defect; justified by this report's unbounded growth (§5.3).
- **`RequireRole("admin")` diverges from Dashboard's `CurrentUser`** — both are precedent-consistent for their own exposure level (§5.5), but a reader of this session's history might expect all `/performance/*` routes to share one authorization posture; they do not, by design, because they expose materially different sensitivity levels.

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** Content/shape (D1, CPO/CTO-decided), API response shape, repository shape, filtering/pagination, service/API architecture, authorization, and route naming are all resolved — the shape questions from precedent, the content question from the CPO/CTO decision. No unresolved governance dependency remains — Territory/Region/Area, Organization Hierarchy, and Phase 7 Reporting Platform are all explicitly out of scope and not referenced.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §8 (Analytics); `docs/product/06_PRODUCT_ROADMAP.md` Phase 5
- `docs/architecture/capabilities/performance/kpi-iteration-1-scope-and-implementation-plan.md`, `target-iteration-1-scope-and-implementation-plan.md`, `achievement-iteration-1-scope-and-implementation-plan.md`
- `docs/architecture/capabilities/dashboard/iteration-1-scope-and-implementation-plan.md` (authorization-posture contrast, §5.5; `/performance/...` route precedent, §5.6)
- `services/api/src/eop_api/repositories/dashboard.py` (`DashboardRepository`'s not-tied-to-one-model precedent, §5.2)
- `services/api/src/eop_api/repositories/survey.py` (`paginate_by_employee_id`'s hand-written-join precedent, §5.2)
- `services/api/src/eop_api/repositories/target.py`, `achievement.py` (`FILTERABLE_FIELDS` precedent, §5.3)
- `services/api/src/eop_api/models/hr_employee.py` (`employee_number`/`full_name` field names, §5.1)
