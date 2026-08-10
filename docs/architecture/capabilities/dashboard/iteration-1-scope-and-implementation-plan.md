# Dashboard — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Dashboard (Performance Management, Roadmap Phase 5)

**Owner:** Engineering (Senior Engineer authority per standing mandate)

---

# 1. Objective

Perform targeted discovery for the next Phase 5 capability after KPI/Target/Achievement, per the sequence `KPI → Target → Achievement → Dashboard → Reporting`, and determine the smallest coherent, implementation-ready **Dashboard** capability.

---

# 2. Candidate Evaluation — Dashboard vs. Reporting

Both remaining Phase 5 items were evaluated against product evidence, existing implementation, dependencies, and architectural precedent.

| | Dashboard | Reporting |
|---|---|---|
| **MVP Scope** | Named explicitly in *both* `02_PRODUCT_SCOPE.md` "MVP Scope" (line 287) and `06_PRODUCT_ROADMAP.md` "MVP" (line 142). | Named only as "Basic Reporting" in `02_PRODUCT_SCOPE.md`'s MVP Scope; **absent** from `06_PRODUCT_ROADMAP.md`'s own MVP list — the two MVP lists disagree on Reporting, not on Dashboard. |
| **Persona evidence** | `03_TARGET_CUSTOMER.md`: Executive needs *"Executive dashboard"*; Regional Manager needs *"Regional dashboard"* — two personas name it directly. | No persona lists "Reporting" or "Report" as a need anywhere. Only appears as a *problem statement* (`03_TARGET_CUSTOMER.md` "Customer Problems": *"Manual reporting"*) and a *success metric* (`04_SUCCESS_METRICS.md`: *"Reduce manual reporting"*) — evidence of a problem to solve, not a specified feature shape. |
| **Existing implementation** | A generic `/dashboard` endpoint already exists (`api/dashboard.py`, `services/dashboard.py`, `repositories/dashboard.py`) — see §3, a naming collision requiring disambiguation, not a blocker. | Zero existing implementation of any kind. |
| **Shape evidence** | Concrete: `02_PRODUCT_SCOPE.md` §8 "Analytics" lists Dashboard alongside Operational Report/Territory Analysis/Productivity Analysis/Heatmap/Forecast/Trend Analysis — Dashboard is the simplest of these (an aggregate summary view), the others are explicitly advanced/AI-adjacent and out of scope. | No format, mechanism, or content is named anywhere — CSV export? scheduled report? ad-hoc query? PDF? Nothing in product evidence answers this, a materially deeper ambiguity than anything Dashboard presents. |
| **Roadmap order** | Listed before Reporting in Phase 5's own module sequence. | Listed after Dashboard. |

**Conclusion:** Dashboard is the smallest coherent, most-evidenced next capability. Reporting's central question (what a "report" actually is) cannot be resolved from any repository or product evidence — selecting it now would require inventing a business decision, which this discovery does not do. Reporting is deferred, not rejected.

---

# 3. Critical Disambiguation — Existing `/dashboard` vs. Phase 5 "Dashboard"

**Repository evidence**: `GET /dashboard` already exists and returns `DashboardResponse(organizations, projects, employees, assignments, tasks, tasks_by_status)`, backed by `DashboardRepository.get_counts()`/`count_tasks_by_status()` reading `Organization`, `Project`, `Employee` (the generic scaffold entity, **not** `HrEmployee`), `Assignment`, `Task`. These are the Phase 1/2 "Core Platform" generic project-management entities — structurally and conceptually unrelated to the HR/Field Execution/Performance domain model this session has built (`HrEmployee`, `Store`, `Visit`, `Survey`, `Kpi`, `Target`, `Achievement`).

This is the same category of naming collision already resolved twice this session (Performance Review vs. Performance Management; HR `AttendanceEvent` vs. Field Execution "Attendance"): two concepts share a name but are not the same thing. The existing `/dashboard` is generic-entity scaffolding; Phase 5's "Dashboard" is a Performance Management summary over `Kpi`/`Target`/`Achievement`.

**Decision (architecture-shape, not business policy)**: Do **not** extend or modify the existing `Dashboard`/`DashboardService`/`DashboardRepository`/`DashboardResponse` — mixing an unrelated generic-entity capability with Performance Management data under one response schema would conflate two bounded contexts, the same reasoning that kept `AttendanceEvent` and `Visit` separate. A new, separately named capability is introduced instead, following the same "don't touch/reinterpret an existing, unrelated capability" precedent applied throughout this session.

---

# 4. Scope Decision — Smallest Coherent Iteration 1

**Dashboard Iteration 1 = a read-only Performance Management summary: counts of `Kpi`, `Target`, and `Achievement` rows, organization-wide (no Territory/Region scoping).**

Rationale:

- `03_TARGET_CUSTOMER.md`'s Executive need lists *"Executive dashboard"*, *"Forecast"*, and *"KPI overview"* as three **separate** needs — this iteration addresses only the first, most general one. "KPI overview" (a richer, KPI-specific view) and "Forecast" (an AI Intelligence-phase item, `06_PRODUCT_ROADMAP.md` §9) are not required here and are not implemented.
- Regional Manager's need is specifically *"Regional dashboard"* — a **territory-scoped** view. This directly collides with the still-open Phase 3 Territory/Region/Area vs. Organization Hierarchy gate (same gate already deferring Territory Analysis, Territory comparison, and store-level territory assignment throughout this session). Iteration 1 delivers only the organization-wide (unscoped) view, explicitly deferring the territory-scoped "Regional dashboard" until that gate is resolved — the identical reasoning already used to scope `Target` to Employee rather than Territory.
- Counts only, no computed ratios (e.g., "% of targets achieved", "targets on track") — computing a ratio requires comparing `Target.goal_value` against `Achievement.actual_value`, which is exactly the scoring/percentage-calculation behavior the Achievement discovery explicitly excluded (`achievement-iteration-1-scope-and-implementation-plan.md` §11: *"no `actual <= target` rule... achievement scoring, achievement percentage calculation"*). A dashboard cannot compute what the underlying capability was explicitly barred from computing; introducing it here would silently reopen that decision through a side door.
- Mirrors the existing `Dashboard`'s own established shape (a stateless, read-only orchestration returning simple counts) — not a new architectural pattern.

---

# 5. Proposed Implementation Shape

**No new repository is required.** `BaseRepository.count()` (`repositories/base.py:73`) already provides a generic row-count method, inherited unmodified by `KpiRepository`, `TargetRepository`, and `AchievementRepository` — smaller than the existing `Dashboard`'s own custom scalar-subquery `DashboardRepository`, which predates this generic method's establishment as a repository-wide convention.

```text
PerformanceDashboardService.get_summary()
  → KpiRepository(session).count()
  → TargetRepository(session).count()
  → AchievementRepository(session).count()
  → PerformanceDashboardResponse(kpi_count, target_count, achievement_count)
```

- **Route**: `GET /performance/dashboard`, tag `"Performance Management"` (matching `Kpi`/`Target`/`Achievement`'s existing tag) — deliberately distinct from the existing `/dashboard` route and its `"Dashboard"` tag (§3).
- **Response**: `PerformanceDashboardResponse(kpi_count: int, target_count: int, achievement_count: int)`.
- **Authorization**: `CurrentUser` only (any authenticated user), **no** `RequireRole("admin")` gate. This mirrors the existing `/dashboard` endpoint's own established precedent exactly: aggregate counts are not gated the same way as the underlying resource's own CRUD endpoints in this codebase (the existing `/dashboard` exposes `Organization`/`Employee` counts to any authenticated user despite those resources having their own more restrictive CRUD authorization elsewhere). Not a new decision — a direct continuation of the one precedent already established for exactly this kind of endpoint.
- **Service layer only** (no repository file): `PerformanceDashboardService` is a stateless, read-only orchestration service with no owned table, mirroring `DashboardService`'s and `ReconciliationService`'s identical shape.

---

# 6. Explicit Out of Scope

- Modifying, extending, or reinterpreting the existing `/dashboard`, `DashboardService`, `DashboardRepository`, or `DashboardResponse` (§3).
- Territory/Region-scoped views ("Regional dashboard"), Organization Hierarchy — blocked by the pre-existing, unresolved Phase 3 gate.
- Computed ratios, percentages, "on track"/"achieved" scoring of any kind (§4).
- "KPI overview" (a richer, KPI-specific detail view), Forecast, Trend Analysis, Heatmap, Productivity Analysis — later/AI Intelligence-phase items, not this iteration's.
- Reporting (export, scheduled reports, PDF/CSV generation) — a separate, still-undiscovered Phase 5 item (§2).
- Any new authorization mechanism, role, or permission model — `CurrentUser` reused unmodified (§5).

---

# 7. Proposed Files

- `docs/architecture/capabilities/dashboard/iteration-1-scope-and-implementation-plan.md` — this document
- `services/api/src/eop_api/schemas/performance_dashboard.py`
- `services/api/src/eop_api/services/performance_dashboard.py`
- `services/api/src/eop_api/api/performance_dashboard.py`
- `services/api/src/eop_api/main.py` (router registration only)
- `services/api/tests/test_performance_dashboard_service.py`, `test_performance_dashboard_api.py`

No model, no repository, no migration — this capability owns no persisted state.

---

# 8. Test Strategy

- **Service**: empty-state counts (all zero); counts reflect actual `Kpi`/`Target`/`Achievement` row counts after creating a mix of each.
- **API**: 401 unauthenticated; 200 for any authenticated user (no admin requirement, explicitly verified with a non-admin user); response shape.

---

# 9. Validation Strategy

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; no Alembic migration exists for this iteration (no persisted state), so no reversibility check applies; targeted tests then full suite.

---

# 10. Remaining Risks

- **Naming**: the coexistence of `/dashboard` (generic, Phase 1/2 legacy) and `/performance/dashboard` (Phase 5, Performance Management) may read as inconsistent to an API consumer unfamiliar with this session's disambiguation history. Documented here and in the route's own tag separation (§5); not fixed by renaming the legacy endpoint, which is out of this capability's scope.
- **`CurrentUser`-only authorization** exposes aggregate counts of admin-managed resources to any authenticated user. Accepted as consistent with the pre-existing `/dashboard` precedent (§5), not a new exposure introduced by this capability — flagged for awareness, not a defect.
- **Counts-only scope** may under-deliver against the full "Executive dashboard"/"Regional dashboard" vision described in product evidence; explicitly incremental by design (§4), with "KPI overview," territory-scoped views, and computed ratios each requiring their own future decision.

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** Scope, disambiguation from the existing `/dashboard`, data source, authorization, and boundaries are all resolved from repository/product evidence and established architectural precedent. No unresolved governance dependency blocks this iteration — the one genuine dependency found (Territory/Region-scoped "Regional dashboard") is explicitly deferred, not required for this scope.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §8 (Analytics), MVP Scope; `docs/product/06_PRODUCT_ROADMAP.md` Phase 5, MVP; `docs/product/03_TARGET_CUSTOMER.md` (Executive/Regional Manager needs); `docs/product/04_SUCCESS_METRICS.md`
- `services/api/src/eop_api/api/dashboard.py`, `services/dashboard.py`, `repositories/dashboard.py`, `schemas/dashboard.py` (existing, unrelated capability — examined, not modified)
- `services/api/src/eop_api/repositories/base.py` (`BaseRepository.count()`)
- `docs/architecture/capabilities/performance/achievement-iteration-1-scope-and-implementation-plan.md` §11 (scoring/percentage exclusion, applied identically here)
- `docs/architecture/capabilities/performance/target-iteration-1-scope-and-implementation-plan.md` §3 (Employee-over-Territory scoping precedent, applied identically here)
