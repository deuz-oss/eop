# Display Audit — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Display Audit (Field Operations, Product Scope §6 "Field Execution")

**Owner:** Engineering (Senior Engineer authority per standing mandate), CPO/CTO business decision recorded below

---

# 1. Prior Discovery

The `# Next Workstream Discovery — CPO/CTO Discovery Gate` report selected Display Audit as the strongest remaining candidate — the last unresolved Field Execution item with a viable low-dependency shape (Stock Check, the other remaining item, is genuinely Blocked on the still-absent Product/SKU master data). That discovery reached **Outcome B — Decision Required**, with the single unresolved gap being business content (D2) and cardinality (D3). Both are resolved below by explicit CPO/CTO decision.

---

# 2. Decision — CPO/CTO (Not Reopened)

Display Audit is a **standalone child aggregate of `Visit`**, **repeatable / many-per-Visit**. No Product/SKU relationship. No FileObject/photo relationship. Owner Only authorization through the existing `VisitAuthorizationEvaluator`, unmodified. Flat CRUD lifecycle.

**Exact business fields:**

| Field | Semantics |
|---|---|
| `visit_id` | Required, FK → `visits.id` |
| `display_area` | Required, free-text (e.g. "endcap," "main shelf," "window display") |
| `observation` | Required, free-text compliance/condition observation |
| `notes` | Optional, free-text |

`visit_id` is **non-unique**.

This mirrors `CompetitorActivity`'s and `PosmAudit`'s just-resolved shape exactly (repeatable, free-text, no new master data) rather than `Survey`'s one-per-Visit shape.

---

# 3. Re-Review of Current Repository State (Not Assumed)

Verified directly against the current codebase before writing this document, not carried over from a prior report:

- `services/api/src/eop_api/models/visit.py` — `Visit` is confirmed "deliberately minimal... no GPS/photo/check-in-out, no Survey/Competitor Activity/Display Audit/Stock Check/POSM Audit" — Display Audit is *not* a field on `Visit` itself, consistent with the CPO/CTO decision.
- `services/api/src/eop_api/models/survey.py:42` — `Survey.display_compliant: Mapped[bool]` confirmed to still exist, untouched, not modified or repurposed by this discovery.
- `services/api/src/eop_api/models/` — confirmed no `Product`/`SKU` model exists anywhere, consistent with "no Product/SKU relationship."
- `services/api/src/eop_api/services/visit_authorization.py` — `VisitAuthorizationEvaluator` confirmed generic and duck-typed on `resource.employee_id`, evaluating no other rule — directly reusable unmodified, the same mechanism already reused by `Survey`, `CompetitorActivity`, `PosmAudit`, and `VisitPhoto`.

No contradiction found between the CPO/CTO decision and the current repository state.

---

# 4. DisplayAudit → Visit Relationship

`DisplayAudit` is a child of `Visit`, **many `DisplayAudit` per `Visit`** — the same cardinality as `CompetitorActivity`/`PosmAudit`/`VisitPhoto`, the deliberate opposite of `Survey`'s one-per-Visit shape. `DisplayAudit.visit_id` is a required, **non-unique** FK to `visits.id`. No duplicate-rejection logic — repeated display observations for the same Visit are expected and permitted (a single Visit may audit multiple distinct display areas).

---

# 5. Minimum DisplayAudit Schema

| Field | Type | Nullable |
|---|---|---|
| `visit_id` | UUID, FK `visits.id` (`ON DELETE RESTRICT`) | No |
| `display_area` | `String(255)` | No |
| `observation` | `String(255)` | No |
| `notes` | `String(2000)` | Yes |

Field lengths mirror the established Visit-child convention exactly — `PosmAudit.posm_type`/`condition` (`String(255)`) and `notes` (`String(2000)`), `CompetitorActivity.competitor_name`/`activity_type` (`String(255)`) and `notes` (`String(2000)`) — not invented.

No dedicated business timestamp — mirrors `CompetitorActivity`/`PosmAudit`/`VisitPhoto` precedent, relying on the parent `Visit` context and `BaseEntity`'s inherited `created_at`/`updated_at`. No lifecycle/status field — `observation` is free-text only, not a workflow status, mirroring `PosmAudit.condition`'s identical framing.

---

# 6. Authorization

Owner Only, evaluated against the resolved **parent `Visit`** — `DisplayAudit` has no `employee_id` column of its own. Reuses the existing `VisitAuthorizationEvaluator` completely unmodified — the same child-of-Owner-Only-parent pattern established by `Survey`, repeated by `CompetitorActivity`, `PosmAudit`, and `VisitPhoto`. No new evaluator class, no new role.

---

# 7. API

`APIRouter(prefix="/display-audits", tags=["Visit"])` — flat route, mirroring `Survey`/`CompetitorActivity`/`PosmAudit`/`VisitPhoto`'s exact precedent (no nested-resource pattern exists anywhere in the codebase). Routes: `POST`, `GET` (plain list, scoped to the caller's own Visits), `GET /paginated` (filterable by `visit_id`), `GET /{id}`, `PUT /{id}`, `DELETE /{id}`. Owner scoping via the existing Visit ownership mechanism (`VisitRepository`/`VisitAuthorizationEvaluator`) — no new authorization evaluator. Same exception→HTTP mapping convention as every prior capability (404/403), via `PROBLEM_RESPONSES`.

---

# 8. Database

One table, `display_audits`, chained onto the current alembic head. `visit_id` FK `ON DELETE RESTRICT`, non-unique index on `visit_id`. No `UniqueConstraint`. No additional FK.

---

# 9. Validation Rules

Only validation directly justified by the decision:

- `visit_id` required, must reference an existing `Visit` (service-layer existence check, `VisitNotFoundError` → 404)
- `display_area` required, `min_length=1, max_length=255` (mirrors `PosmAuditCreate.posm_type`'s exact `Field` constraint)
- `observation` required, `min_length=1, max_length=255` (mirrors `PosmAuditCreate.condition`'s exact `Field` constraint)
- `notes` optional, `max_length=2000`
- Owner Only authorization via the resolved parent `Visit`

No minimum/maximum semantic length beyond the mirrored convention, no scoring, no compliance interpretation, no enum values, no normalization, no uniqueness — none of these are invented.

---

# 10. Architecture

```text
API → Service → UnitOfWork → Repository → SQLAlchemy Model
```

Repository remains persistence-only — no validation, no authorization. Service owns validation (Visit/field existence) and authorization invocation. API only translates service exceptions into HTTP responses. Follows the established Visit-child architecture exactly (`CompetitorActivityService`/`PosmAuditService`/`VisitPhotoService`'s identical shape).

---

# 11. Implementation Plan

**New files:**

1. `services/api/src/eop_api/models/display_audit.py` — `DisplayAudit(BaseEntity)`
2. `services/api/src/eop_api/repositories/display_audit.py` — `DisplayAuditRepository(BaseRepository[DisplayAudit])`, hand-written `paginate_by_employee_id` (Owner Only join against `Visit`, mirroring `PosmAuditRepository` exactly, with an optional `visit_id` filter layered onto the same join)
3. `services/api/src/eop_api/services/display_audit.py` — `DisplayAuditService`, exceptions `VisitNotFoundError`/`DisplayAuditAuthorizationDeniedError`
4. `services/api/src/eop_api/schemas/display_audit.py` — `DisplayAuditCreate`/`Update`/`Response`
5. `services/api/src/eop_api/api/display_audits.py` — `APIRouter(prefix="/display-audits", tags=["Visit"])`
6. `services/api/alembic/versions/<revision>_create_display_audits_table.py`
7. `services/api/tests/test_display_audit_repository.py`
8. `services/api/tests/test_display_audit_service.py`
9. `services/api/tests/test_display_audits_api.py`

**Modified files (registration only):**

- `services/api/src/eop_api/models/__init__.py` — register `DisplayAudit`
- `services/api/src/eop_api/main.py` — register `display_audits_router`

No existing capability implementation or test is modified — no proven architectural dependency requires it (unlike Field Attendance's `test_file_service.py` fix, which was required because it was the *first* FK into `file_objects`; `DisplayAudit` introduces no new FK target).

**Tests, mirroring `test_posm_audit_*`'s exact structure:**

- *Repository:* create/get, list-returns-multiple-per-visit (explicit non-uniqueness), update, delete, pagination, filter by `visit_id`.
- *Service:* CRUD, Visit existence check (`VisitNotFoundError`), Owner Only authorization (denied for a different employee's Visit, including authorization-follows-current-visit-owner on reassignment), required-field validation via schema, multiple Display Audits allowed for one Visit.
- *API:* CRUD, authentication required, Owner Only (403 for a different owner's Visit), cannot access another user's Visit's Display Audit, pagination, `visit_id` filtering, 422 on missing required fields, 404 on missing Visit.

---

# 12. Out of Scope (Explicit Non-Goals)

Product/SKU master data, product-level display auditing, planogram, display scoring, compliance percentage calculation, photo evidence (already its own separate capability — not duplicated here), GPS/location (Field Attendance's domain — not duplicated here), geofencing, Mission relationship, Survey relationship (Survey's `display_compliant` is not modified or repurposed), POSM Audit relationship, Competitor Activity relationship, approval/moderation workflow, manager/subordinate visibility, analytics, AI, reporting, integration/webhooks.

---

# Validation/Test Strategy (for when implementation is authorized)

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted tests then full suite.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §6 (Field Execution)
- `docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md` (parent aggregate, explicit Display Audit anticipation)
- `docs/architecture/capabilities/survey/iteration-1-scope-and-implementation-plan.md` (Display Audit named as its own separate, unbuilt item)
- `docs/architecture/capabilities/competitor-activity/competitor-activity-iteration-1-scope-and-implementation-plan.md`, `posm-audit/posm-audit-iteration-1-scope-and-implementation-plan.md`, `photo-evidence/photo-evidence-iteration-1-scope-and-implementation-plan.md` (direct structural precedent)
- `services/api/src/eop_api/models/visit.py`, `services/visit_authorization.py`, `models/posm_audit.py`, `models/competitor_activity.py` (direct repository precedent)

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** D1–D10 are all resolved by the CPO/CTO's content/cardinality decision (§2) plus direct technical precedent (`Survey`, `CompetitorActivity`, `PosmAudit`, `VisitPhoto`, `Visit`). No unresolved governance dependency remains — Product/SKU, FileObject/photo, GPS/location, Territory/Region/Area, Mission, Survey, POSM Audit, and Competitor Activity relationships are all explicitly out of scope and not referenced. No contradiction found between this decision and the current repository state.
