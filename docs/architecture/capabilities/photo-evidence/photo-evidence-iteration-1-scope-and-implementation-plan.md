# Photo Evidence — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Photo Evidence (Field Operations, Product Scope §6 "Field Execution")

**Owner:** Engineering (Senior Engineer authority per standing mandate), CPO/CTO business decision recorded below

---

# 1. Prior Discovery

The `# Next Workstream Discovery — Post Field Attendance` report selected Photo Evidence as the strongest next candidate — the highest evidence density of any remaining Field Execution item (independently named in both `02_PRODUCT_SCOPE.md` §6 and `03_TARGET_CUSTOMER.md`'s Field Employee "Needs"), explicitly anticipated by name in `Visit`'s and `Survey`'s own already-merged discovery documents, and technically de-risked by Field Attendance's just-proven `FileObject` FK pattern. That discovery reached **Outcome B — Decision Required**, with the single unresolved gap being aggregate identity/parent scope (D1) and cardinality (D3). Both are resolved below by explicit CPO/CTO decision.

---

# 2. Decision — CPO/CTO (Not Reopened)

**Option A — Visit-only, many-per-Visit child aggregate.**

`VisitPhoto` is a standalone child aggregate of `Visit`. Not a field on `Visit` itself (Visit's own discovery document is not reopened — `Visit` remains "deliberately minimal, no GPS/photo"). One `Visit` may have many `VisitPhoto` records — `visit_id` is **not unique**. Each `VisitPhoto` row represents one uploaded photo attached to one Visit.

No relationship to `Survey`, `CompetitorActivity`, `PosmAudit`, `Mission`, `Store`, or `HrEmployee` directly — ownership is resolved entirely through the parent `Visit`, mirroring the established child-of-Owner-Only-parent pattern.

---

# 3. Exact Scope

Minimum data required to represent "one photo attached to one Visit" — exactly two FK columns, nothing else:

| Field | Type | Nullable |
|---|---|---|
| `visit_id` | UUID, FK `visits.id` (`ON DELETE RESTRICT`) | No |
| `file_object_id` | UUID, FK `file_objects.id` (`ON DELETE RESTRICT`) | No |

No caption, description, category, photo_type, tags, coordinates, captured_at, device metadata, checksum, AI metadata, OCR data, face data, classification, approval status, or lifecycle status — all explicitly excluded per CPO/CTO decision. `FileObject` remains the sole source of file metadata (filename, content type, size, storage key, bucket).

No dedicated timestamp beyond inherited `BaseEntity` columns (`created_at`/`updated_at`) — mirrors `CompetitorActivity`/`PosmAudit` precedent.

---

# 4. Authorization

Owner Only, evaluated against the resolved **parent `Visit`** — `VisitPhoto` has no `employee_id` column of its own. Reuses the existing `VisitAuthorizationEvaluator` completely unmodified — the same child-of-Owner-Only-parent pattern established by `Survey`, `CompetitorActivity`, and `PosmAudit`. No new evaluator, no manager/subordinate access, no new role or permission.

---

# 5. File Upload / FileObject

Reuses the existing `FileObject` infrastructure unmodified — no new file entity, no new storage abstraction. Follows the established `upload → obtain file_object_id → create` flow, proven by Field Attendance's `selfie_file_id` pattern: existence-check via `FileRepository(uow.session).exists(data.file_object_id)` before insert, `ON DELETE RESTRICT` to preserve the reference. Tests use the same `FakeStorageProvider`/`get_file_service` dependency-override convention already established in `test_files_api.py` and `test_field_attendance_events_api.py` — no live MinIO required.

---

# 6. API

`APIRouter(prefix="/visit-photos", tags=["Visit"])` — flat route, mirroring `Survey`/`CompetitorActivity`/`PosmAudit`'s exact precedent (no nested-resource pattern exists anywhere in the codebase). Routes: `POST`, `GET` (plain list, scoped to the caller's own Visits), `GET /paginated` (filterable by `visit_id`), `GET /{id}`, `PUT /{id}`, `DELETE /{id}`. No workflow endpoints. Same exception→HTTP mapping convention as every prior capability (404/403), via `PROBLEM_RESPONSES`.

---

# 7. Database

One table, `visit_photos`, chained onto the current alembic head. `visit_id` and `file_object_id` both `ON DELETE RESTRICT`, non-unique index on `visit_id`. No `UniqueConstraint`. No additional FK.

---

# 8. Tests

Repository/service/API tests mirroring `test_posm_audit_*`'s/`test_field_attendance_event_*`'s exact structure: create/get, multiple-per-visit-allowed (explicit non-uniqueness), update, delete, pagination/filter by `visit_id`, Owner Only enforcement via the parent Visit's employee (including authorization-follows-current-visit-owner), missing-Visit/missing-FileObject existence checks, file upload/reference flow via `FakeStorageProvider`.

---

# Out of Scope

Survey/CompetitorActivity/PosmAudit/Mission relationship, direct Store/Employee relationship, Territory/Region/Area, Product/SKU, GPS, geofencing, spoof detection, selfie verification, biometric processing, face recognition, liveness detection, fraud detection, AI classification, OCR, automatic tagging, analytics, reporting, dashboard integration, approval/moderation workflow, photo scoring, captions, categories, lifecycle/status, retention-policy implementation, generic/polymorphic attachment framework.

---

# Validation/Test Strategy (for when implementation is authorized)

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted tests then full suite.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §6 (Field Execution), `03_TARGET_CUSTOMER.md` (Field Employee "Photo upload" need)
- `docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md` (parent aggregate, explicit Photo Evidence anticipation)
- `docs/architecture/capabilities/survey/iteration-1-scope-and-implementation-plan.md` (Photo Evidence named as its own separate, unbuilt item)
- `docs/architecture/capabilities/field-attendance/field-attendance-iteration-1-scope-and-implementation-plan.md` (direct `FileObject` FK precedent)
- `services/api/src/eop_api/models/visit.py`, `services/visit_authorization.py`, `models/posm_audit.py`, `models/field_attendance_event.py`, `models/file_object.py` (direct repository precedent)

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** D1–D10 are all resolved by the CPO/CTO's parent/cardinality decision (§2) plus direct technical precedent (`PosmAudit`, `CompetitorActivity`, `FieldAttendanceEvent`, `Visit`). No unresolved governance dependency remains — Survey/CompetitorActivity/PosmAudit/Mission relationships, Territory/Region/Area, Product/SKU, GPS, biometrics, workflow, and a generic attachment framework are all explicitly out of scope and not referenced.
