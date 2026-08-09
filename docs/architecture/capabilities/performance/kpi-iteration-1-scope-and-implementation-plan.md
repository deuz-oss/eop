# KPI — Iteration 1 Scope and Discovery

**Status:** Discovery Complete — Implementation-Ready

**Capability:** KPI (Performance Management, Roadmap Phase 5)

**Owner:** Engineering (Senior Engineer authority per standing mandate), reviewed by CPO/CTO

---

# 1. Objective

Determine the smallest coherent, implementation-ready **KPI** capability from Roadmap Phase 5's `KPI → Target → Achievement → Dashboard → Reporting` sequence, without collapsing later stages into this iteration.

---

# 2. Product Evidence

- **`02_PRODUCT_SCOPE.md` §7 "Performance Management"** (already in-scope, unrelated to the already-implemented "Performance Review" — same disambiguation this repository's own governance has stated three times: `ARCHITECTURE_CHANGELOG.md`, `ARCHITECTURE_STATUS.md`, `CAPABILITY_CATALOG.md`): *"KPI, Target, Achievement, Productivity, Scorecard, Leaderboard, Incentive Calculation."*
- **§8 "Analytics"** separately lists `Dashboard, Operational Report, ...` — the Roadmap's Phase 5 module list (`06_PRODUCT_ROADMAP.md`: `KPI, Target, Achievement, Dashboard, Reporting`) groups Dashboard/Reporting alongside KPI/Target/Achievement for *sequencing* purposes even though Product Scope itself places them in a separate topical section (§8, not §7) — noted, not a blocker; it doesn't change what KPI itself needs to contain.
- **`03_TARGET_CUSTOMER.md`** consistently frames KPI as something **monitored/viewed**, not authored by field employees: Executive's needs include *"KPI overview"*; National Sales Manager's needs include *"National KPI"*/*"Territory comparison"*; Customer Problems includes *"Difficult KPI monitoring"* as a problem the platform should solve. No persona need describes defining, editing, or calculating a KPI value themselves — that reads as an admin/management activity, not a field-employee one.
- **`04_SUCCESS_METRICS.md`**: *"Improved KPI achievement"* — again framing KPI as something tracked against, not the record of a specific measurement itself (that's `Achievement`'s job, per the Roadmap's own separate naming).
- No document anywhere names a specific KPI, its unit, its formula, or how it is calculated.

---

# 3. Scope Decision

**Iteration 1 = KPI definition only** — a named, admin-managed indicator (e.g. "Visit Compliance Rate"), analogous to `JobGrade`/`EmploymentType`/`StoreType`'s exact shape: reference data describing *what indicator exists*, not a value, not an assignment, not a calculation.

This directly follows the evidence in §2: nothing describes field employees interacting with KPI directly (rules out an employee-owned record), nothing names a formula or calculation (rules out a calculation engine), and the Roadmap's own explicit ordering (`KPI` before `Target` before `Achievement`) is the strongest signal that these are three separable stages, not one. Collapsing `Target` (a goal value assigned to someone/something for a period) or `Achievement` (a measured actual value) into this iteration would require inventing exactly the ownership/period/formula decisions product evidence does not supply — the same reasoning that kept `Interview`/`Offer` decoupled from `Application`'s lifecycle, and `Visit`/`Survey` decoupled from `Mission`.

---

# 4. Aggregate / Entity Model

`Kpi(BaseEntity)`, table `kpis`:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | via `UUIDMixin` |
| `code` | `String(50)`, unique | mirrors `JobGrade`/`EmploymentType`/`StoreType`'s identity convention |
| `name` | `String(255)` | required |
| `unit` | `String(50)`, nullable | free text (e.g. `"%"`, `"visits/day"`, `"IDR"`) — a label only, not a fixed enum and not a computed value; no closed unit taxonomy is named anywhere in product evidence, so a free-form field avoids inventing one (mirrors `StoreType`'s own free-form-over-fixed-enum resolution for the same reason) |
| `description` | `String(1000)`, nullable | mirrors every other master-data entity's optional description field |

**No relationships, no foreign keys.** See §7.

---

# 5. Authorization

**Role Based (`RequireRole("admin")`)** — direct reuse, no new mechanism. `Kpi` is admin-managed reference data with no natural owner-employee field, the same shape as `JobGrade`/`EmploymentType`/`StoreType`/`PayrollRun`, all of which resolved identically. Product evidence (§2) supports this directly: every persona need describing KPI is a *monitoring* need (Executive, National Sales Manager), never a field-employee self-service need, so Owner Only has no basis here — there is no "owning employee" of a KPI *definition* the way there is of a `Visit`.

---

# 6. Lifecycle

**Flat CRUD, no status field.** Mirrors `JobGrade`/`EmploymentType`/`StoreType` exactly — none of this repository's simple reference-data entities carry an `is_active`/status field, and nothing in product evidence describes a KPI definition lifecycle (draft/approved/retired). Not introduced merely because a future `Target`/`Achievement` capability might one day want to reference only "active" KPIs — that would be designing for a hypothetical future requirement, which this session's standing conventions explicitly avoid.

---

# 7. Explicit Out of Scope

- **Target** — the next Phase 5 stage; would need an owner (employee/store/department — undecided), a period, and a goal value, none of which product evidence defines yet.
- **Achievement** — the measured/actual value against a Target; further downstream, needs Target to exist first.
- **Dashboard, Reporting** — aggregation/presentation layers over KPI+Target+Achievement data that doesn't exist yet.
- **KPI calculation engine / formula engine** — no formula, computation rule, or data source is named anywhere; `Kpi` in this iteration carries no computed value at all, only a definition.
- **Productivity, Scorecard, Leaderboard, Incentive Calculation** — named in §7 alongside KPI but each is its own further-downstream concept (a Scorecard/Leaderboard presumably aggregates multiple KPI+Achievement records; Incentive Calculation presumably feeds Payroll) — none is KPI itself.
- **Territory / Region / Area, Organization Hierarchy** — not referenced; `Kpi` has no relationship to either (§4 — zero foreign keys).
- **Mission, Visit, Survey, Payroll, Attendance** — no relationship; KPI Iteration 1 is fully independent of every Phase 3/4 capability.

---

# 8. Phase 5 Sequencing

`KPI → Target → Achievement → Dashboard → Reporting` is confirmed the correct order, and KPI is independently implementable first: it is pure definition data with zero dependents required to exist and zero dependencies on anything else in the repository. `Target` is *not* separable from KPI in the reverse direction (a Target must reference a `Kpi` by definition), but KPI has no such reverse dependency — it is meaningful and complete on its own, the same relationship `StoreType` has to `Store` or `JobGrade` has to `HrEmployee`. Target is deliberately not started in this discovery; its own ownership question (§D2 in the assigning task — employee/store/department/organization) is a genuine open product decision, not resolvable from current evidence, and belongs to a separate future discovery.

---

# 9. Proposed Files (not yet created — discovery only)

- `docs/architecture/capabilities/performance/kpi-iteration-1-scope-and-implementation-plan.md` — this document
- `services/api/src/eop_api/models/kpi.py`
- `services/api/src/eop_api/repositories/kpi.py`
- `services/api/src/eop_api/schemas/kpi.py`
- `services/api/src/eop_api/services/kpi.py`
- `services/api/src/eop_api/api/kpis.py`
- `services/api/src/eop_api/main.py` (router registration)
- `services/api/src/eop_api/models/__init__.py` (model registration)
- One Alembic migration: `create_kpis_table`
- `services/api/tests/test_kpi_repository.py`, `test_kpi_service.py`, `test_kpis_api.py`

---

# 10. Validation Strategy (for when implementation is authorized)

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted tests then full suite.

---

# 11. Risks

- The `unit` field's free-text shape means nothing prevents inconsistent unit labels across KPIs (e.g. `"%"` vs `"percent"`) — an acceptable, low-stakes risk at this scope, consistent with `StoreType`'s identical free-form precedent; not a blocker.
- The Roadmap's placement of `Dashboard`/`Reporting` in the Phase 5 module list, despite Product Scope's own §8 "Analytics" categorization, is a minor cross-document inconsistency — noted in §2, does not affect KPI's own scope or block this iteration.

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** No material business decision remains unresolved for KPI itself; every open question in this document (unit taxonomy, calculation formulas, ownership model) belongs to `Target`/`Achievement`/later stages, not to the KPI definition.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §7 (Performance Management), §8 (Analytics)
- `docs/product/06_PRODUCT_ROADMAP.md` Phase 5
- `docs/product/03_TARGET_CUSTOMER.md` (Executive/National Sales Manager KPI-monitoring needs)
- `docs/product/04_SUCCESS_METRICS.md`
- `services/api/src/eop_api/models/job_grade.py`, `employment_type.py`, `store_type.py` (structural precedent)
- `docs/architecture/00-governance/ARCHITECTURE_CHANGELOG.md`/`ARCHITECTURE_STATUS.md`/`CAPABILITY_CATALOG.md` (existing Performance Review vs. Performance Management disambiguation, referenced not reopened)
