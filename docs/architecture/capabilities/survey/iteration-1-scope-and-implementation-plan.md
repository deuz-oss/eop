# Survey — Iteration 1 Scope and Discovery

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Survey (Field Operations, Roadmap Phase 4)

**Owner:** Engineering (Senior Engineer authority per standing mandate), reviewed by CPO/CTO

---

# 1. Decisions Already Made (Not Reopened)

- **D1 (shape):** Fixed Question Set (Option A) — no generic questionnaire engine, no runtime configuration, no question-type registry.
- **D2 (content):** Exactly three fixed boolean questions, CPO/CTO-specified:
  1. *"Apakah kondisi display produk di toko sesuai standar?"* — Boolean
  2. *"Apakah stok produk utama tersedia?"* — Boolean
  3. *"Apakah materi promosi/POSM tersedia dan terpasang dengan baik?"* — Boolean

Neither is revisited here. This document resolves only the remaining implementation-level questions explicitly delegated to Engineering.

---

# 2. Survey → Visit Relationship

**Survey is a child of `Visit`, one Survey per Visit.** Product intent is explicit and singular: *"Survey is a minimal operational survey attached to a Visit... to capture a small set of structured observations during a store visit"* — one survey, one visit, not a repeatable sub-collection (unlike `Interview`/`Offer`'s deliberately-unconstrained multiplicity against `Application`, which had no such singular framing). `Survey.visit_id` is therefore a required, **unique** FK to `visits.id` — a second `POST` for the same `visit_id` is rejected, mirroring `JobRequisition`/`Store`'s `code`-uniqueness pattern in spirit (one distinguished row per parent), not a `UniqueConstraint` this repository has used for a FK before, but the smallest correct expression of "one Survey per Visit."

---

# 3. Minimum Survey Schema

Three dedicated `Boolean` columns — one per fixed question, not a generic answer table (explicitly forbidden):

| Field | Maps to question | Type | Nullable |
|---|---|---|---|
| `visit_id` | — | UUID, FK `visits.id` | No (also unique) |
| `display_compliant` | Q1 — display sesuai standar | `Boolean` | No |
| `stock_available` | Q2 — stok produk utama tersedia | `Boolean` | No |
| `posm_available` | Q3 — materi promosi/POSM tersedia dan terpasang | `Boolean` | No |

All three answer columns are required (`NOT NULL`) — a `Survey` without all three answers isn't a completed survey, and nothing in the product decision describes a partial/draft state (§6). No `default` value is set for any of them: defaulting an unanswered question to `False` would silently invent an answer, which the CPO/CTO decision does not authorize.

No `notes`/free-text field is added — not one of the three fixed questions, and adding one would be exactly the kind of "additional question" the decision forbids.

---

# 4. One Survey Per Visit

Confirmed sufficient (§2) — enforced via a unique constraint on `Survey.visit_id`, not a business-layer convention alone, so a second create attempt for the same `Visit` fails deterministically (409, mirroring every other duplicate-rejection precedent in this repository — `DuplicateStoreCodeError`, `DuplicateJobRequisitionCodeError`, etc.).

---

# 5. Authorization

**Owner Only, reusing `VisitAuthorizationEvaluator` literally unmodified — no new evaluator class, no denormalized field.**

`Survey` does **not** carry its own `employee_id` column. Reasoning: `VisitUpdate` already permits reassigning `Visit.employee_id` (mirrors `AttendanceEventUpdate`'s identical precedent) — if `Survey` denormalized a copy of the owning employee at creation time, that copy could silently go stale relative to the Visit's current owner after a reassignment, a real data-integrity risk with no product justification. Instead, `SurveyService` resolves the parent `Visit` (already required, to validate `visit_id` exists) and authorizes against **that Visit object directly**, passing it as `AuthorizationRequest.resource` to the existing, unmodified `VisitAuthorizationEvaluator` — which only ever inspects `resource.employee_id`. This is the literal existing mechanism, reused exactly, always reflecting the Visit's current owner, zero new authorization code of any kind.

`SurveyAuthorizationDeniedError` (a new exception, not a new evaluator) is raised by `SurveyService`, mirroring `VisitAuthorizationDeniedError`'s/`AttendanceAuthorizationDeniedError`'s own precedent of one exception class per consuming service.

---

# 6. Independent CRUD vs. Visit-Constrained

**Independent CRUD**, scoped by re-checking the parent Visit's ownership on every call — mirrors `Interview`/`Offer`'s relationship to `Application` (their own resource, own repository, own service, own API, FK-linked, not embedded in the parent's schema). `create`/`get`/`update`/`delete` all resolve and authorize against the parent `Visit` (§5). A `get_by_visit_id` repository/service convenience method is included (mirrors `ApplicationRepository.get_by_candidate_and_requisition`'s pair-lookup precedent) so a caller can find "the survey for this visit" without knowing the Survey's own id first.

`update` allows changing any of the three answers (correcting a mis-entered response) but not `visit_id` — reassigning a Survey to a different Visit is not a scenario any product evidence describes, and `visit_id` uniqueness would make it a meaningless operation in practice (the target Visit either already has a Survey, blocking it, or doesn't, in which case it should be a new Survey). `SurveyUpdate` therefore excludes `visit_id`.

---

# 7. Lifecycle

**None — flat CRUD.** No status field, no draft/submitted/verified states. Nothing in the CPO/CTO decision or any product document describes a Survey lifecycle; matches the "ship flat first" precedent used by every capability this session (`PayrollRun`, `JobRequisition`, `PerformanceReview`, `Visit` itself).

---

# 8. Database / Architecture Shape

## Aggregate / Model

`Survey(BaseEntity)`, table `surveys`:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | via `UUIDMixin` |
| `visit_id` | UUID, FK `visits.id`, `ON DELETE RESTRICT` | required, unique |
| `display_compliant` | `Boolean` | required |
| `stock_available` | `Boolean` | required |
| `posm_available` | `Boolean` | required |

Indexes: unique index on `visit_id` (doubles as the FK index and the one-per-visit enforcement).

## Repository

`SurveyRepository(BaseRepository[Survey])` — persistence-only. `get_by_visit_id(visit_id)`, mirroring `ApplicationRepository`'s pair-lookup shape. `paginate(...)`, filterable by `visit_id`.

## Service

`SurveyService` — mirrors `VisitService`'s structure: `create` validates `visit_id` exists (`VisitNotFoundError`) and is not already surveyed (`DuplicateSurveyError`), then authorizes against the resolved `Visit` (§5) before creating. `get`/`update`/`delete` load the `Survey`, resolve its parent `Visit`, and authorize against that `Visit` the same way.

## Authorization

Owner Only, via the existing unmodified `VisitAuthorizationEvaluator`, authorized against the parent `Visit` object (§5). `SurveyAuthorizationDeniedError` raised on denial.

## API

`APIRouter(prefix="/surveys", tags=["Visit"])` — `POST`, `GET` (own, scoped the same way `Visit.list` scopes to the caller's own `employee_id` via the parent Visit), `GET /paginated`, `GET /{id}`, `GET /by-visit/{visit_id}`, `PUT /{id}`, `DELETE /{id}`. Same exception→HTTP mapping convention as every prior capability (404/409/403).

## Migration

One migration, `create_surveys_table`, chained onto the current head.

## Tests

Repository/service/API tests mirroring `test_visit_*`'s exact structure (owner-only enforcement via the parent Visit's employee, one-per-visit duplicate rejection, existence checks, CRUD happy path).

---

# Out of Scope

- Additional questions, scoring, rating scales, question configuration, question tables, answer-type registries (§1/§3)
- Versioning, branching, approval workflow, audit workflow (§7)
- Product/SKU entities, Display Audit, Stock Check, POSM Audit (as separate capabilities)
- Mission, Check In/Check Out, GPS, Selfie, Photo Evidence
- Territory/Region/Area, Organization Hierarchy, Enterprise Authorization

---

# Validation/Test Strategy (for when implementation is authorized)

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted tests then full suite.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §6 (Field Execution)
- `docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md` (parent aggregate, Owner Only precedent)
- `services/api/src/eop_api/models/visit.py`, `services/visit.py`, `services/visit_authorization.py` (direct precedent)
- `services/api/src/eop_api/models/interview.py`, `offer.py` (independent-CRUD-child-of-parent precedent)
