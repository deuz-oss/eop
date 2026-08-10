# POSM Audit — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** POSM Audit (Field Operations, Product Scope §6 "Field Execution")

**Owner:** Engineering (Senior Engineer authority per standing mandate), CPO/CTO business decision recorded below

---

# 1. Prior Discovery

Candidate discovery (`# Next Workstream — Candidate Discovery & Targeted Discovery`) evaluated the full remaining capability landscape and selected POSM Audit as the strongest next workstream: smallest independent implementation scope, minimal new architectural surface, and — unlike `Stock Check` (which likely requires a not-yet-built Product/SKU master data prerequisite) or `Display Audit` (ambiguous between a flat observation and per-product compliance) — no risk of an entangled master-data dependency. That discovery reached **Outcome B — Decision Required**, with the single unresolved gap being business content (D2) and cardinality (D3). Both are resolved below by explicit CPO/CTO decision.

---

# 2. Decisions Already Made (Not Reopened)

- **D1 (aggregate identity):** Standalone child aggregate of `Visit` — confirmed by `Visit`'s own discovery document (`docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md`), which explicitly names `POSM Audit` as its own future child record referencing `Visit.id`, the same "owned child" shape `Interview`/`Offer` have to `Application`. Not already covered by `Survey` — `Survey`'s own discovery document explicitly excludes `POSM Audit` from its scope as a separate capability, despite `Survey.posm_available` capturing a coarse boolean version of a related question.

- **D2/D3 (business content and cardinality) — CPO/CTO decision:**

  POSM Audit is a **repeatable observation under a Visit**. Each record represents one POSM item/type observed during the Visit. A Visit may contain multiple `PosmAudit` records — `visit_id` is **not unique**.

  Fields (exactly these four, no others):

  | Field | Semantics |
  |---|---|
  | `visit_id` | Parent Visit |
  | `posm_type` | Free-text POSM type/name, e.g. banner, wobbler, standee |
  | `condition` | Free-text observation of the POSM condition/status — observation text only, **not** a workflow status |
  | `notes` | Optional additional observation |

  This mirrors `CompetitorActivity`'s just-resolved shape exactly (repeatable, free-text, no new master data) rather than `Survey`'s one-per-Visit shape.

Neither is revisited here. This document resolves only the remaining implementation-level questions.

---

# 3. PosmAudit → Visit Relationship

`PosmAudit` is a child of `Visit`, **many `PosmAudit` per `Visit`** — the same cardinality as `CompetitorActivity`, the deliberate opposite of `Survey`'s one-per-Visit shape. `PosmAudit.visit_id` is a required, **non-unique** FK to `visits.id`. No duplicate-rejection logic — repeated POSM observations for the same Visit are expected and permitted (a single Visit may observe multiple distinct POSM items: a banner, a wobbler, a standee, each its own row).

---

# 4. Minimum PosmAudit Schema

| Field | Type | Nullable |
|---|---|---|
| `visit_id` | UUID, FK `visits.id` (`ON DELETE RESTRICT`) | No |
| `posm_type` | `String(255)` | No |
| `condition` | `String(255)` | No |
| `notes` | `String(2000)` | Yes |

No dedicated audit timestamp — mirrors `CompetitorActivity`/`Survey` precedent, relying on the parent `Visit.visited_at` and `BaseEntity`'s inherited `created_at` for bookkeeping. No lifecycle/status field — `condition` is observation text only, explicitly not a workflow status per CPO/CTO decision (§0/§3 of the decision).

---

# 5. Authorization

Owner Only, evaluated against the resolved **parent `Visit`** — `PosmAudit` has no `employee_id` column of its own. Reuses the existing `VisitAuthorizationEvaluator` completely unmodified — the same child-of-Owner-Only-parent pattern established by `Survey` and repeated for `CompetitorActivity`. No new evaluator class, no new role.

---

# 6. API

`APIRouter(prefix="/posm-audits", tags=["Visit"])` — flat route, mirroring `Survey`/`CompetitorActivity`'s exact precedent (no nested-resource pattern exists anywhere in the codebase). Routes: `POST`, `GET` (plain list, scoped to the caller's own Visits), `GET /paginated` (optional `visit_id` query filter), `GET /{id}`, `PUT /{id}`, `DELETE /{id}`. No dedicated `GET /by-visit/{visit_id}` route — not requested by the CPO/CTO decision. Since Owner Only scoping already requires a hand-written join against `Visit` (`paginate_by_employee_id`, not the generic `FilterParams`/`filterable_fields` mechanism), the `visit_id` filter is layered directly onto that same join rather than routed through `FilterParams`. Same exception→HTTP mapping convention as every prior capability (404/403), via `PROBLEM_RESPONSES`.

---

# 7. Migration

One migration, `create_posm_audits_table`, chained onto the current head (`b0c1d2e3f4a5`, `create_competitor_activities_table`). Non-unique index on `visit_id`, no `UniqueConstraint`.

---

# 8. Tests

Repository/service/API tests mirroring `test_competitor_activity_*`'s exact structure: create/get, list-returns-multiple, multiple-per-visit-allowed (explicit non-duplicate-rejection), update, delete, pagination/filter by `visit_id`, Owner Only enforcement via the parent Visit's employee (including authorization-follows-current-visit-owner on reassignment), existence checks, CRUD happy path.

---

# Out of Scope

- POSM master data, `PosmMaterial` table, `PosmType` lookup table
- Product/SKU, Product relationship
- GPS, photo, selfie, `FileObject` attachment
- Scoring, approval workflow
- Territory/Region/Area, Route Planning
- Mission relationship
- Analytics, AI, automatic calculation
- Reporting, integration
- Dedicated audit timestamp
- Lifecycle/status workflow (`condition` is observation text only)

---

# Validation/Test Strategy (for when implementation is authorized)

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted tests then full suite.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §6 (Field Execution)
- `docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md` (parent aggregate, "owned child" precedent naming POSM Audit explicitly)
- `docs/architecture/capabilities/survey/iteration-1-scope-and-implementation-plan.md` (excludes POSM Audit from its own scope as a separate capability)
- `docs/architecture/capabilities/competitor-activity/competitor-activity-iteration-1-scope-and-implementation-plan.md` (direct structural precedent — repeatable, free-text, no new master data)
- `services/api/src/eop_api/models/visit.py`, `services/visit_authorization.py`, `models/survey.py`, `models/competitor_activity.py` (direct repository precedent)

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** D1–D10 are all resolved by the CPO/CTO's content/cardinality decision (§2) plus direct technical precedent (`Survey`, `CompetitorActivity`, `Visit`). No unresolved governance dependency remains — POSM master data, Product/SKU, GPS/photo/selfie, Territory/Region/Area, Route Planning, Mission, analytics, AI, and reporting are all explicitly out of scope and not referenced.
