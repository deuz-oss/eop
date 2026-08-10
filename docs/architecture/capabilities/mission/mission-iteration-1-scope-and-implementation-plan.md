# Mission — Iteration 1 Scope and Implementation Plan

**Status:** Discovery Complete — Implementation-Ready

**Capability:** Mission (Field Operations, Roadmap Phase 4 / Product Scope §5 Planning)

**Owner:** Engineering (Senior Engineer authority per standing mandate), CPO/CTO decision applied per this document's own §3

---

# 1. Objective

Finalize the targeted discovery for **Mission** into an implementation-ready scope, now that the CPO/CTO has resolved the one genuine content gap the prior discovery turn escalated (what a Mission targets).

**Mission Iteration 1 is a single-store employee assignment: a planning/assignment record created by an administrator to assign one employee to one store on one date.**

---

# 2. Prior Discovery Evidence (recap)

- Six bare mentions across product docs, no elaboration: `02_PRODUCT_SCOPE.md` §5 Planning (*"Mission Planning"*, grouped with Route Planning/Territory Assignment/Target Assignment/Schedule Planning) and MVP Scope (*"Mission"*); `03_TARGET_CUSTOMER.md` Area Manager (*"Mission assignment"*) and Field Employee (*"Mission"*, listed before Visit) needs; `06_PRODUCT_ROADMAP.md` Phase 4 modules and MVP.
- `visit/iteration-1-scope-and-implementation-plan.md` §3 already resolved that `Visit` does not reference Mission — re-verified, not reversed, no new evidence found that would justify reopening it.
- No existing Mission-related governance/decision document existed prior to this discovery.
- The one genuine gap — what a Mission targets (single Store, multi-stop Route, or store-independent task) — could not be resolved from evidence and was correctly escalated rather than invented.

---

# 3. CPO/CTO Decision — Content/Shape (D1–D2, Final)

**Final business shape: `Employee → Mission → Store`.**

Mission is a planning/assignment record, created by an administrator/manager, assigning one employee to one store on one date. Minimum fields: `employee_id`, `store_id`, `scheduled_date`.

Route Planning remains a separate, not-yet-discovered capability and is **not** a dependency of Mission Iteration 1 — no `route_id`, no multi-stop structure.

---

# 4. D1–D10 Final Decisions

**D1 — Aggregate identity.** Standalone aggregate. Purpose: an assignment/planning record created ahead of execution — the "who goes where, when" plan a manager sets, distinct from `Visit` (the executed act). Not a field on any existing entity.

**D2 — Relationships.** `employee_id` → `hr_employees.id`, `ON DELETE RESTRICT` (required — the assignee). `store_id` → `stores.id`, `ON DELETE RESTRICT` (required — the assignment target, per §3). No other relationship — no Territory/Region/Area, no `route_id`, no `visit_id` (Visit's own discovery already established the FK, if ever needed, would live on Mission's side in a *future* iteration, not required now — nothing in this iteration adds it speculatively).

**D3 — Mission semantics.** A planning/assignment record, created in advance by a manager. Distinct from `Visit`: Mission is the *plan* ("employee X is assigned to store Y on date Z"), `Visit` is the *executed record* of a field employee actually being at a store. No structural or FK link between them in Iteration 1.

**D4 — Fields.** `employee_id`, `store_id`, `scheduled_date`. Nothing else. Explicitly excluded, per instruction, since no evidence supports any of them: `description`, `status`, `priority`, `notes`, `start_time`, `end_time`, `route_id`, `territory_id`, GPS coordinates, completion fields.

**D5 — Date/time.** `scheduled_date: Date` (not `DateTime`) — Mission Planning is day-granular (paired with "Schedule Planning" in Product Scope §5), distinct from `Visit.visited_at`'s point-in-time `DateTime` shape, which records when execution actually happened. No start/end time — not evidenced, and a single date is sufficient for "assigned to store Y on date Z."

**D6 — Lifecycle.** Flat CRUD. No status, approval, completion, or cancellation workflow — no evidence supports any of it; matches the established default for every capability without explicit lifecycle evidence (`Kpi`, `Store`, `Visit`, `Target`, `Achievement`).

**D7 — Authorization.** Role Based (`RequireRole("admin")`) — *"Mission assignment"* is an Area Manager action, not something the Field Employee self-authors, the same structural distinction that placed `Target` in `RequireRole("admin")` rather than Owner Only. `employee_id` is Mission's business scope (whose assignment this is), not its authorization boundary — mirrors `Target`'s/`Achievement`'s identical reasoning exactly. No dedicated "Area Manager" role exists in this codebase's RBAC (only "admin" is ever seeded anywhere); reusing `RequireRole("admin")` introduces no new mechanism. No new evaluator, no new role.

**D8 — API.** See §6.

**D9 — Database.** See §7.

**D10 — Iteration 1 boundary.** See §8.

---

# 5. Aggregate / Entity Model

`Mission(BaseEntity)`, table `missions`:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | via `UUIDMixin` |
| `employee_id` | UUID, FK → `hr_employees.id`, `ON DELETE RESTRICT` | the assignee |
| `store_id` | UUID, FK → `stores.id`, `ON DELETE RESTRICT` | the assignment target |
| `scheduled_date` | `Date` | the planned date |

No other fields. Mirrors `Visit`'s exact structural shape (two required FKs + one temporal field), substituting a planning-granularity `Date` for Visit's execution-granularity `DateTime`.

---

# 6. Relationships

```text
Mission.employee_id → HrEmployee.id  ON DELETE RESTRICT
Mission.store_id    → Store.id       ON DELETE RESTRICT
```

Both `RESTRICT`, matching every other FK into `HrEmployee`/`Store` in this repository (`Visit`, `Target`) — planning history must be preserved, not silently cascaded away.

---

# 7. Constraints

- **No uniqueness constraint.** Considered and rejected: unlike `Target` (which enforces one goal value per employee/kpi/period, since two conflicting goal values would be a genuine data-integrity problem), a Mission has no "authoritative value" property — two assignments for the same employee/store/date are not contradictory, they are simply two assignments (e.g., a legitimate re-visit or split task). This mirrors `Visit`'s own identical, already-accepted precedent: *"No uniqueness constraint — multiple visits per employee/store over time are expected and normal."* Applying a stricter rule to the mere *plan* (Mission) than to the *executed act* (Visit) it precedes would be inconsistent and unevidenced.
- **Referential existence**: `employee_id` must reference an existing `HrEmployee`; `store_id` must reference an existing `Store` — checked in the service layer before insert (mirrors `TargetService.create`'s `HrEmployeeRepository(...).exists(...)` pattern), surfaced as typed application errors (`EmployeeNotFoundError`, `StoreNotFoundError`) rather than raw FK `IntegrityError`.

---

# 8. Explicit Out of Scope

Visit, Route, Route Stop, Territory assignment, Attendance, GPS tracking, Photo/selfie evidence, Completion tracking, KPI/Target/Achievement, any workflow/status entity, `description`/`status`/`priority`/`notes`/`start_time`/`end_time`/`route_id`/`territory_id`/GPS coordinates/completion fields, any new authorization evaluator or role, Route Planning as a dependency.

---

# 9. Proposed Files

- `docs/architecture/capabilities/mission/mission-iteration-1-scope-and-implementation-plan.md` — this document
- `services/api/src/eop_api/models/mission.py`
- `services/api/src/eop_api/repositories/mission.py`
- `services/api/src/eop_api/schemas/mission.py`
- `services/api/src/eop_api/services/mission.py`
- `services/api/src/eop_api/api/missions.py`
- `services/api/src/eop_api/main.py` (router registration only)
- `services/api/src/eop_api/models/__init__.py` (model registration only)
- One Alembic migration: `create_missions_table`
- `services/api/tests/test_mission_repository.py`, `test_mission_service.py`, `test_missions_api.py`

---

# 10. Repository / Service / API Architecture

**Repository**: `MissionRepository(BaseRepository[Mission])`, mirroring `TargetRepository`/`VisitRepository` exactly — persistence only, no business validation. `FILTERABLE_FIELDS = {"employee_id": Mission.employee_id, "store_id": Mission.store_id, "scheduled_date": Mission.scheduled_date}` — the same three fields Mission carries, mirroring `TargetRepository`'s identical "filter on the fields you have" convention. No text-searchable field exists (no `description`/`notes`), so no `search_fields` — mirrors `Achievement`'s identical reasoning.

**Service**: `MissionService` — `create`/`get`/`list`/`list_paginated`/`update`/`delete`. `create` validates `employee_id` and `store_id` both exist (`EmployeeNotFoundError`, `StoreNotFoundError`), mirroring `TargetService.create`'s existence-check pattern (using `BaseRepository.exists()`, already generic). `update` allows changing **all three** fields (`employee_id`, `store_id`, `scheduled_date`), each optional for partial update — mirrors `VisitUpdate`'s own precedent exactly (`schemas/visit.py`: `employee_id`, `store_id`, `visited_at` are all independently nullable/updatable), not `Target`'s narrower value-only update — Mission has no separate "identity vs. value" split the way `Target`/`Achievement` do (`employee_id`/`store_id`/`scheduled_date` collectively *are* Mission's entire content, and reassigning/rescheduling an unexecuted plan is a natural planning-record operation, exactly as reassigning a `Visit`'s `employee_id` already is in this repository).

**API**: `services/api/src/eop_api/api/missions.py`, `router = APIRouter(prefix="/missions", tags=["Mission"])` — its own dedicated tag, mirroring `Visit`'s own dedicated `"Visit"` tag (Mission has no natural existing tag to join). Routes: `POST`, `GET ""` (plain list), `GET /paginated`, `GET /{mission_id}`, `PUT /{mission_id}`, `DELETE /{mission_id}` — mirrors `Target`'s exact CRUD + dual-list-endpoint shape (both a plain list and a paginated list, the majority convention in this codebase; not `Reporting`'s paginated-only deviation, since Mission has no unbounded-growth justification for departing from the default).

Filters wired via query params exactly as `departments.py`/`reporting.py` already establish: `employee_id`, `store_id`, `scheduled_date` as optional `Query()` params building a `FilterParams`.

---

# 11. Authorization

`RequireRole("admin")` on every route — reused unmodified via `RequireMissionAdmin` (mirrors `RequireTargetAdmin`'s naming/shape exactly). No `MissionAuthorizationEvaluator`, no Owner Only, no new role.

---

# 12. Migration

One Alembic migration, `create_missions_table`: `missions` table with standard `BaseEntity` columns, `employee_id`/`store_id` FKs (`ON DELETE RESTRICT`), `scheduled_date` (`Date`, not null), indexes on `employee_id` and `store_id` (mirrors `Visit`'s exact index set), no unique constraint (§7). Downgrade drops the indexes then the table, mirroring `Visit`'s/`Target`'s migration shape exactly.

---

# 13. Test Strategy

- **Repository**: create/get, list, update (all three fields independently), delete, pagination, filter by each of `employee_id`/`store_id`/`scheduled_date`.
- **Service**: CRUD; `EmployeeNotFoundError` on missing `employee_id`; `StoreNotFoundError` on missing `store_id`; update reassigning `employee_id`/`store_id`/rescheduling `scheduled_date`.
- **API**: 401 unauthenticated matrix, 403 non-admin matrix (mirrors `test_targets_api.py` exactly), 201/200/204 happy paths, 404 (Employee missing, Store missing, Mission missing), pagination, filter query params.

---

# 14. Validation Strategy

Mirrors this session's established convention: `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted Mission tests then full suite.

---

# 15. Remaining Risks

- **No uniqueness constraint** means an administrator can create duplicate/overlapping assignments (same employee, same store, same date) with no system-level prevention — deliberately accepted, mirroring `Visit`'s identical precedent, not a defect.
- **Full update mutability** (reassigning employee/store/date after creation) has no audit trail beyond `AuditLog`'s generic action logging — same accepted limitation every other mutable capability in this repository already has (`Visit`, `Kpi`).
- **Route Planning remains fully unaddressed** — if a future Route-level Mission concept is ever needed, it may require a schema extension (e.g., a `MissionStop` child table) rather than a clean drop-in, since this iteration's `Mission` is single-store by design (§3 CPO/CTO decision).

---

# Outcome

**OUTCOME A — IMPLEMENTATION-READY.** D1–D10 are all resolved by the CPO/CTO's content decision (§3) plus direct technical precedent (`Visit`, `Target`, `Achievement`). No unresolved governance dependency remains — Territory/Region/Area, Route Planning, and Organization Hierarchy are all explicitly out of scope and not referenced.

---

# Implementation Checklist (for the next authorized turn)

- [ ] `models/mission.py` — `Mission(BaseEntity)`
- [ ] `models/__init__.py` — register `Mission`
- [ ] `repositories/mission.py` — `MissionRepository(BaseRepository[Mission])`
- [ ] `schemas/mission.py` — `MissionCreate`/`MissionUpdate`/`MissionResponse`
- [ ] `services/mission.py` — `MissionService`, `EmployeeNotFoundError`, `StoreNotFoundError`
- [ ] `api/missions.py` — router, `RequireMissionAdmin`
- [ ] `main.py` — register router
- [ ] Alembic migration — `create_missions_table`
- [ ] `tests/test_mission_repository.py`, `test_mission_service.py`, `test_missions_api.py`
- [ ] `ruff`/`mypy`/Alembic reversibility/targeted tests/full suite — all clean
- [ ] Branch, commit, push, manual PR link — no merge

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §5 (Planning), MVP Scope; `docs/product/06_PRODUCT_ROADMAP.md` Phase 4, MVP; `docs/product/03_TARGET_CUSTOMER.md` (Area Manager/Field Employee needs)
- `docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md` (structural precedent, Mission/Visit non-relationship, uniqueness precedent)
- `docs/architecture/capabilities/performance/target-iteration-1-scope-and-implementation-plan.md` (admin-assignment authorization precedent)
- `services/api/src/eop_api/models/visit.py`, `schemas/visit.py` (exact field/update-mutability precedent)
- `services/api/src/eop_api/repositories/target.py`, `services/target.py` (existence-check, filterable-fields precedent)
