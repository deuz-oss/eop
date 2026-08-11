# Field Attendance — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Field Execution Attendance / Check-In / Check-Out / GPS Validation / Selfie Verification (Product Scope §6 "Field Execution")

**Owner:** Engineering (Senior Engineer authority per standing mandate), CPO/CTO business/policy decision recorded below

---

# 1. Prior Discovery

The `# Attendance / Field Check-In Discovery Report` reached **Outcome B — Decision Required**, having resolved D1 (partial), D4, and D7 (partial) from evidence/precedent, but leaving business content (D2), cardinality (D3), GPS policy (D5), and selfie/privacy policy (D6) genuinely unresolved — explicitly not silently decided by engineering judgment. All four are now resolved by explicit CPO/CTO decision below.

---

# 2. Architectural Boundary (Not Reopened)

**HR/Payroll `AttendanceEvent` ≠ Field Execution `FieldAttendanceEvent`.**

`AttendanceEvent` (`services/api/src/eop_api/models/attendance_event.py`, implemented, merged, governed by `docs/architecture/capabilities/attendance-authorization/decision.md`) is a shift clock transaction (`CLOCK_IN`/`CLOCK_OUT`/`BREAK_IN`/`BREAK_OUT`, mandatory `shift_id`) feeding Payroll's attendance deduction (`services/payroll/attendance_leave_deduction_calculator.py`) and `ReconciliationService`. It is **not modified, not extended, not reused** by this capability.

`FieldAttendanceEvent` is a **separate standalone aggregate** with a separate business purpose (field-presence evidence: location + selfie at the moment of a field check-in/check-out), per explicit CPO/CTO decision. The two share only:

- The same identity-resolution infrastructure (`CurrentRequestContext`/`EmployeeContextResolver`, resolving the authenticated `User` to their `HrEmployee` via `HrEmployee.user_id`).
- The same Owner Only authorization *shape* (`resource.employee_id == context.employee_context.employee.id`) — and, per explicit CPO/CTO instruction, the existing `AttendanceAuthorizationEvaluator` class itself is reused completely unmodified (§6), since it is duck-typed on `resource.employee_id` and does not reference the `AttendanceEvent` model by type.

No FK, no shared table, no shared enum, no shared service or repository exists between the two.

---

# 3. Aggregate / Content Decision (D1/D2 — CPO/CTO)

`FieldAttendanceEvent`: a standalone aggregate. Not an extension of `AttendanceEvent`, not a child of `Visit`, not a daily summary, not a shift/payroll record.

One record represents **one field attendance event** — either `CHECK_IN` or `CHECK_OUT`. Event-stream model, structurally simple like `AttendanceEvent`, but a fully separate aggregate.

Fields, exactly these eight business fields (plus inherited `BaseEntity` columns):

| Field | Semantics |
|---|---|
| `employee_id` | FK → `hr_employees.id`; resolved from the authenticated user's `CurrentRequestContext`, must be the caller's own `HrEmployee` |
| `event_type` | `CHECK_IN` or `CHECK_OUT` |
| `event_time` | Timestamp of the field attendance event, supplied by the client — not replaced with server time, no timezone conversion |
| `latitude` | Required decimal coordinate |
| `longitude` | Required decimal coordinate |
| `gps_accuracy_meters` | Required, device-reported accuracy, stored as evidence only |
| `selfie_file_id` | **Not nullable** — FK → `file_objects.id`, mandatory for both `CHECK_IN` and `CHECK_OUT` |

No other fields.

---

# 4. Cardinality (D3 — CPO/CTO)

Multiple `FieldAttendanceEvent` rows are allowed for the same employee — no `(employee_id, date)` uniqueness, no one-check-in-or-check-out-per-day enforcement at the database level. No automatic pairing, sequencing, correction, or reconciliation logic in Iteration 1 — mirrors `AttendanceEvent`'s own established precedent of deferring sequencing/duplicate-detection to future work, now confirmed applicable here by explicit decision rather than assumed from precedent alone.

---

# 5. GPS Policy (D5 — CPO/CTO)

GPS is **mandatory**: `latitude`, `longitude`, `gps_accuracy_meters` all required (`NOT NULL`).

**Validation — structural only:**
- `latitude` ∈ [-90, 90]
- `longitude` ∈ [-180, 180]
- `gps_accuracy_meters` ≥ 0

**Explicitly excluded:** geofencing, store-radius validation, GPS spoof/mock-location detection, device integrity verification, route validation, automatic rejection based on accuracy threshold. `gps_accuracy_meters` is stored as device-reported evidence only — no business rejection threshold in Iteration 1.

---

# 6. Selfie Policy (D6 — CPO/CTO)

Selfie is **mandatory for both `CHECK_IN` and `CHECK_OUT`** — `selfie_file_id NOT NULL`. Evidence only, **not** an identity-verification mechanism. No face recognition, face matching, biometric processing, liveness detection, AI verification, or fraud detection.

**Storage:** reuses the existing `FileObject` (`services/api/src/eop_api/models/file_object.py`) unmodified — no new file entity, no file-ownership architecture beyond what `FileObject` already provides (infrastructure-only metadata record, no entity references of its own).

**Privacy/retention (explicit follow-up, not a blocker):** Iteration 1 does not define a new retention policy — uses the existing `FileObject` lifecycle as-is, no new retention period, no automatic deletion, no biometric metadata, no consent workflow, no privacy workflow. **Retention/privacy policy remains a governance/business-policy follow-up item**, explicitly documented here rather than silently decided, but does not block this technical implementation because the selfie is treated strictly as evidence, not biometric identity data.

---

# 7. Authorization (D7)

Owner Only. The authenticated user may access `FieldAttendanceEvent` rows belonging to their own `HrEmployee`, resolved via `CurrentRequestContext`/`EmployeeContextResolver` — the same identity infrastructure `AttendanceEvent`/`Visit`/`Survey`/`CompetitorActivity`/`PosmAudit` already use.

**Evaluator reuse:** the existing `AttendanceAuthorizationEvaluator` (`services/api/src/eop_api/services/attendance_authorization.py`) is reused **completely unmodified** — its `evaluate()` method only inspects `resource.employee_id == context.employee_context.employee.id` and does not reference the `AttendanceEvent` model by type, so passing a `FieldAttendanceEvent`/`FieldAttendanceEventCreate` as `resource` is sufficient. No new evaluator class, no new role, no new permission. `list`/`list_paginated` are scoped to the caller's own `employee_id`, mirroring `AttendanceEventService`'s exact pattern — not authorized per-item, since there is no single resource to evaluate a decision against for a collection read.

No manager/subordinate access — consistent with `attendance-authorization/decision.md`'s own explicit rejection of Manager Access for the sibling HR capability, citing `TD-003` (Employee Manager Hierarchy Limitation), which applies identically here.

---

# 8. Relationship to Visit (D1 confirmed)

No `visit_id`. No `store_id`, `mission_id`, `route_id`, `territory_id`, `region_id`, `area_id`. Field attendance represents field-presence evidence, independent of any particular `Visit`.

---

# 9. Lifecycle (D8)

Flat event records only. No status, approval, correction workflow, pairing, sequencing, reconciliation, or automatic duplicate detection. No business-operation endpoints (`/start`, `/end`, `/current-status`, `/close-open-attendance`) — standard CRUD only, mirroring `AttendanceEvent`'s own flat-CRUD precedent, now confirmed appropriate by explicit decision rather than assumed.

---

# 10. API (D8)

`APIRouter(prefix="/field-attendance", tags=["Field Attendance"])` — flat, dedicated route (distinct from `/hr/attendance-events`).

Routes: `POST`, `GET` (plain list, scoped to caller's own `employee_id`), `GET /paginated` (filterable by `event_type`/`event_time`), `GET /{id}`, `PUT /{id}`, `DELETE /{id}`.

Filtering mechanism mirrors `AttendanceEventService.list_paginated` exactly: `employee_id` is force-set to the caller's own resolved employee id at the service layer, overriding any client-supplied value — the caller cannot widen scope via a filter parameter. No manager/admin cross-employee access. `event_time` filtering uses the same equality-only mechanism `BaseRepository._apply_filters` already provides throughout this codebase (no new range-filter capability introduced) — an exact-timestamp match, the same limitation already inherent to every other equality-filterable timestamp-adjacent field in this repository, not a gap specific to this capability.

---

# 11. Database (D9)

One table, `field_attendance_events`, chained onto the current alembic head.

| Field | Type | Nullable |
|---|---|---|
| `employee_id` | UUID, FK `hr_employees.id` (`ON DELETE RESTRICT`) | No |
| `event_type` | `String` enum (`CHECK_IN`/`CHECK_OUT`, `native_enum=False`, mirroring `core/attendance.py`'s established enum-as-VARCHAR convention) | No |
| `event_time` | `DateTime(timezone=True)` | No |
| `latitude` | `Numeric(9, 6)` (mirrors `Store.latitude`'s exact precedent) | No |
| `longitude` | `Numeric(9, 6)` (mirrors `Store.longitude`'s exact precedent) | No |
| `gps_accuracy_meters` | `Numeric(8, 2)` | No |
| `selfie_file_id` | UUID, FK `file_objects.id` (`ON DELETE RESTRICT`) | No |

`selfie_file_id` uses `ON DELETE RESTRICT`, not `SET NULL` — an engineering-precedent resolution, not a business-policy one: every mandatory FK in this codebase (including `employee_id` here) uses `RESTRICT` to preserve history; the one existing `SET NULL` precedent (`HrEmployee.user_id`) is for a genuinely optional, later-nullifiable link, a materially different case from a mandatory evidence attachment that should not silently lose its reference. This is the first FK into `file_objects.id` anywhere in the codebase.

No uniqueness constraint. Indexes limited to normal retrieval/filtering needs: `employee_id`, `event_type`, `event_time` — mirroring `AttendanceEvent`'s own index set exactly.

No relationship to `Visit`, `Store`, `Mission`, `Route`, `Territory`, `Region`, `Area`, `Shift`, `Payroll`, or `Holiday`.

---

# 12. Schema Validation

`FieldAttendanceEventCreate`: `latitude: Decimal = Field(ge=-90, le=90)`, `longitude: Decimal = Field(ge=-180, le=180)`, `gps_accuracy_meters: Decimal = Field(ge=0)`, `selfie_file_id: uuid.UUID` (required), `event_type: FieldAttendanceEventType`, `event_time: datetime`, `employee_id: uuid.UUID`. Structural range validation only, per §5 — no business-threshold rejection.

---

# 13. Explicit Iteration 1 Exclusions (D10)

HR/Payroll `AttendanceEvent` changes, payroll calculation, overtime, shift assignment, work schedule, holiday calculation, leave, timesheet, Visit linkage, Mission linkage, Route Planning, Territory/Region/Area, geofencing, store-radius validation, GPS spoof detection, mock-location detection, face recognition, biometric processing, liveness detection, fraud detection, AI verification, automatic attendance pairing, correction workflow, approval workflow, manager/subordinate visibility, cross-employee access, attendance reconciliation, analytics, reporting, dashboard changes, webhook/integration.

---

# 14. Tests (for when implementation is authorized)

Mirrors `test_posm_audit_*`/`test_attendance_event_*`'s established structure: create/get, list-scoped-to-owner, update, delete, pagination/filter by `event_type`, Owner Only enforcement (denied for a different employee's event), GPS range validation (rejects out-of-range latitude/longitude, rejects negative accuracy), missing-employee/missing-selfie-file existence checks.

---

# Validation/Test Strategy (for when implementation is authorized)

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted tests then full suite.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §6 (Field Execution)
- `docs/architecture/ATTENDANCE_DESIGN.md` (PR-039, prior HR AttendanceEvent discovery — re-verified, not assumed)
- `docs/architecture/capabilities/attendance-authorization/decision.md` (Owner Only precedent, Manager Access rejection via TD-003)
- `services/api/src/eop_api/models/attendance_event.py`, `services/attendance_event.py`, `services/attendance_authorization.py` (direct structural and authorization-reuse precedent)
- `services/api/src/eop_api/models/store.py` (`latitude`/`longitude` `Numeric(9, 6)` precedent)
- `services/api/src/eop_api/models/hr_employee.py` (`user_id` identity link), `dependencies/employee_context.py` (`CurrentRequestContext`/`EmployeeContextResolver`)
- `services/api/src/eop_api/models/file_object.py` (selfie storage, reused unmodified)

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** D1–D10 are all resolved by the CPO/CTO's content/cardinality/GPS/selfie/privacy decision (§3–§9) plus direct technical precedent (`AttendanceEvent`, `Store`, `Visit`/`Survey`/`CompetitorActivity`/`PosmAudit`'s Owner Only lineage). No unresolved governance dependency remains — Visit/Mission/Route Planning/Territory/Region/Area, geofencing, biometrics, and manager access are all explicitly out of scope and not referenced. The HR/Payroll `AttendanceEvent` boundary is preserved and unmodified.
