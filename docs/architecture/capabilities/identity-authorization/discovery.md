# Identity & Authorization Discovery

Status: **Discovery only. No code, no migrations, no tests. Repository Analyst role — findings, not decisions.**

Related roadmap item: `MASTER_ARCHITECTURE_ROADMAP.md` Phase 1, PR-051 ("Identity Context &
Authorization Architecture" — Discovery + Design).

---

## 1. Executive Summary

Authentication is mature; authorization is not. `User` (`models/user.py`) resolves from a bearer
token via `CurrentUser` (`dependencies/auth.py`) on every route in the codebase. A many-to-many
`Role` model exists and is enforced by exactly one dependency, `RequireRole` (`dependencies/rbac.py`),
which has exactly one call site: `RequireAdmin` in `api/roles.py`, gating role-management endpoints
themselves. No HR, Leave, Overtime, Timesheet, Attendance, or Reconciliation endpoint is role-gated
or ownership-checked — every one of them accepts any authenticated `User`.

The `User` ↔ `HrEmployee` link that earlier discovery documents (PR-039 through PR-049, all cited in
`PR-050_DISCOVERY.md`) repeatedly named as the blocking gap has since been built: `HrEmployee.user_id`
(nullable FK to `users.id`, `ON DELETE SET NULL`, indexed, **not unique**) shipped in migration
`9c3d5f1a7b2e` and is live on `main`/this branch. `HrEmployeeRepository.get_by_user_id(user_id) ->
Sequence[HrEmployee]` is the only lookup method, and it deliberately returns a sequence — not
`HrEmployee | None` — because cardinality (one `User` to how many `HrEmployee` rows) was left an
open business decision (`ADR-004`, `PR-050_DISCOVERY.md` Step 2) and is still open today. No
dependency anywhere in the codebase (`dependencies/`) calls this method — there is no
`CurrentEmployee`-shaped resolver yet.

`ApprovalService` (`services/approval.py`) — the component every leave/overtime/timesheet approve/
reject endpoint calls — performs no authorization check beyond authentication. Its own docstring and
`ADR-003` both state this explicitly as a known, current limitation, not an oversight.

This document inventories what exists, traces the `User → HrEmployee` resolution path and its edge
cases, catalogs every endpoint's current access-control state, and lists the decisions that must be
made — by someone other than this document — before an authorization boundary can be implemented.

---

## 2. Identity Inventory

### `User` (`models/user.py`)

```
id, email (unique), password_hash, full_name, is_active, roles (M2M via user_roles)
```

- No `organization_id` — `User` is not tenant/org-scoped in the current schema.
- No CRUD service exists for `User` (confirmed by grep: no `services/user.py`). The only ways a
  `User` row is created or read are `AuthService` (`services/auth.py`: `authenticate`, `login`,
  `get_current_user`) and the standalone `scripts/create_admin.py`.
- `UserRepository` (`repositories/user.py`) exposes only `get_by_email` plus inherited
  `BaseRepository` methods (`get`, `exists`, `create`, `update`, `delete`, `list`, `paginate`).

### Authentication flow

- `POST /auth/login` (`api/auth.py`) → `AuthService.login` → `AuthService.authenticate` (verifies
  password, checks `is_active`) → `create_access_token(subject=str(user.id))` (JWT).
- `GET /auth/me` returns the resolved `CurrentUser`.
- Every other route depends on `CurrentUser` (`dependencies/auth.py:47`), which:
  1. Extracts a bearer token via `HTTPBearer`.
  2. Calls `AuthService.get_current_user(token)` → decodes the JWT, loads the `User` by `sub`,
     rejects if missing/inactive.
  3. Binds `user.id` into `core/request_context.py`'s `ContextVar` (`bind_current_user`) — readable
     from anywhere in the call stack (services, repositories, logging) without threading `Request`.
  4. Raises `401` (`InvalidTokenError`) on any failure. No `403` path exists in this dependency —
     authorization is not this layer's concern by design (`ADR-002`: API layer is "not responsible"
     for business/authorization decisions; that boundary was written into the ADR, not into any
     enforcement code yet).

### Role model

- `Role` (`models/role.py`): `id`, `name` (unique), `description`. Many-to-many with `User` via
  `user_roles` (`models/user_role.py`, composite PK `(user_id, role_id)`).
- `RoleRepository` (`repositories/role.py`): `get_by_name`, `is_assigned`, `assign_user`,
  `unassign_user`, `get_role_names_for_user`.
- `RoleService` (`services/role.py`): full CRUD plus `assign_role`/`remove_role`/`user_has_role`.
- `RequireRole(role_name)` (`dependencies/rbac.py:18`): a dependency factory — 403s if
  `RoleService.user_has_role(current_user.id, role_name)` is false. Runs after `CurrentUser`, so a
  missing/invalid token already 401s before this check.
- **No permission model exists.** `Role` carries only a `name`/`description`; there is no
  `Permission` table, no role→permission mapping, and no policy/rule structure anywhere in
  `models/`, `services/`, or `dependencies/`.
- **`RequireRole` has exactly one call site**: `RequireAdmin = Depends(RequireRole("admin"))` in
  `api/roles.py`, gating `POST/PATCH/DELETE /roles` and the role-assignment endpoints. No other
  router imports `RequireRole` or `RequireAdmin` — confirmed by grep across `api/`.
- `main.py:87-89` carries a `TODO`: *"Locations (and location types) are authenticated-only for
  now. Once the platform defines administrative roles for master data, gate these routes with
  `RequireRole(...)`..."* — direct evidence the platform has no working
  authorization-beyond-authentication story anywhere outside `api/roles.py`, and that this is a
  known, named gap rather than an unnoticed one.

### CurrentUser implementation

`Annotated[User, Depends(get_current_user)]` (`dependencies/auth.py:47`). Used as a required
dependency (typically bound to `_`, discarding the value, just to force the `401` check) on every
route reviewed in `api/`. No equivalent `CurrentEmployee`/`CurrentHrEmployee` dependency exists.

**What represents identity today**: `User`, resolved from a JWT, is the sole identity primitive
every route authenticates against. Nothing beyond `Role` membership (checked in exactly one place)
distinguishes one authenticated `User` from another for access-control purposes.

---

## 3. Employee Context Resolution

### The link

`HrEmployee.user_id` (`models/hr_employee.py:91-93`): nullable FK to `users.id`,
`ON DELETE SET NULL`, indexed (`ix_hr_employees_user_id`), **no unique constraint**. Shipped via
migration `9c3d5f1a7b2e` (chained off `f4a1c9e6b2d7`), per the architecture decision recorded in
`PR-050_DISCOVERY.md` (Steps 1–2) and `ADR-004`. `EmployeeCreate`/`EmployeeUpdate`/`EmployeeResponse`
(`schemas/hr_employee.py`) all carry `user_id: uuid.UUID | None`. Linking is **explicit** — a caller
sets `user_id` through the ordinary `POST /hr/employees` / `PUT /hr/employees/{id}` surface; there
is no auto-matching (e.g. by email) and no dedicated linking endpoint.

### Lookup pattern

`HrEmployeeRepository.get_by_user_id(user_id: uuid.UUID) -> Sequence[HrEmployee]`
(`repositories/hr_employee.py:43-55`): a hand-written `select(...)`, deliberately **not** built on
the shared `BaseRepository.get_by()` helper, because that helper's `scalar_one_or_none()` raises
`MultipleResultsFound` whenever more than one row matches — reachable here since `user_id` carries
no DB-level uniqueness constraint. The repository docstring cites this exact reasoning. Test
coverage (`tests/test_hr_employee_repository.py:557-611`) exercises all three shapes: one match,
zero matches, and two `HrEmployee` rows sharing one `user_id` (returns both, not an error).

### How current authenticated user resolves to employee — today

**There is no standard dependency that performs this resolution.** No file under `dependencies/`
references `HrEmployeeRepository` or `get_by_user_id`. Grep across the full `services/api/src`
tree finds `get_by_user_id` called only inside its own repository module and its test file — zero
production call sites. Any caller wanting "the `HrEmployee` record(s) for the current `User`" would
today have to construct the call manually: `HrEmployeeRepository(session).get_by_user_id(current_user.id)`,
using the `Sequence[HrEmployee]` return type, and must have already decided how to handle zero or
multiple results.

### Edge cases (structural, not resolved by any code reviewed)

- **Zero employees.** A `User` with no linked `HrEmployee` is valid and current
  (`scripts/create_admin.py` creates such `User` rows; nothing requires a link). No code path
  reviewed defines what "current employee" means for such a user.
- **Multiple employees.** `user_id` is deliberately non-unique (§ above). Two or more `HrEmployee`
  rows can share one `user_id` today with no constraint violation and no service-layer check
  preventing it (`HrEmployeeService.create`/`update` only verify the referenced `User` *exists*,
  never that it is not already linked elsewhere — confirmed by reading `services/hr_employee.py`
  in full). Which row (if any) should be treated as "the" employee for a given request is
  unresolved.
- **Stale/orphaned links.** `ON DELETE SET NULL` means deleting a `User` silently clears `user_id`
  on any linked `HrEmployee` rows, with no audit trail (`AuditLog` is not wired to this FK or to
  `HrEmployeeService` at all — confirmed by grep, no `AuditLog` import in `services/hr_employee.py`).
- **Project-tracking `Employee` is a distinct model.** `models/employee.py`'s `Employee` (used by
  `Assignment`/`Task`, `organization_id`-scoped, `ON DELETE CASCADE`) shares no FK relationship with
  `HrEmployee` and has no link to `User` at all. The two "Employee" concepts are independent; this
  discovery's employee-context findings apply only to `HrEmployee` (the HR/Leave/Attendance/
  Overtime/Timesheet domain), not to `Employee` (the Project domain).

---

## 4. Existing Authorization Mechanisms

| Component | File | What it does | Where it's used |
|---|---|---|---|
| `CurrentUser` | `dependencies/auth.py` | Authenticates a bearer token → `User`; 401 on failure | Every route in `api/` |
| `RequireRole(name)` | `dependencies/rbac.py` | 403 unless `user_has_role(user.id, name)` | Only `api/roles.py` (`RequireAdmin`) |
| `RoleService.user_has_role` | `services/role.py` | Flat name-in-set check against `user_roles` | Called only by `RequireRole` |
| `bind_current_user` / request context | `core/request_context.py` | Propagates `user_id` (string) via `ContextVar` for logging/tracing | Bound in `dependencies/auth.py`; read wherever request-scoped identity is logged |

**Missing, confirmed by grep across `services/api/src/eop_api` for `permission`, `Permission`,
`policy`, `Policy`, `authorize`, `Authoriz*`, `access` (beyond `HTTPBearer`/DB access), and
`CurrentEmployee`:**

- No `Permission` model, table, or vocabulary.
- No policy/rule evaluation component.
- No ownership-check helper (e.g. "does this `HrEmployee` belong to the requester").
- No manager/org-chart-aware check anywhere.
- No `CurrentEmployee`-shaped dependency built on `get_by_user_id`.

---

## 5. Authorization Gaps — Endpoint Analysis

Pattern observed across every endpoint file reviewed (`api/leave_requests.py`,
`api/overtime_requests.py`, `api/timesheets.py`, `api/reconciliation.py`, `api/hr_employees.py`):
every handler's only access-control dependency is `CurrentUser` (bound to `_`, value discarded).
None reference `RequireRole`, `RequireAdmin`, or any ownership/ scoping check.

### Leave (`api/leave_requests.py`, prefix `/hr/leave-requests`)

| Route | Who can call | What is checked | What is missing |
|---|---|---|---|
| `POST ""` (create) | Any authenticated `User` | `EmployeeNotFoundError`, date-range validity | No check that the caller is/represents `employee_id`, or is authorized to submit on that employee's behalf |
| `GET ""`, `GET /paginated`, `GET /{id}` | Any authenticated `User` | Nothing beyond auth | Any user can read any employee's leave requests; no scoping by employee/org/manager |
| `PUT /{id}` (update) | Any authenticated `User` | `EmployeeNotFoundError`, date-range validity | No ownership check; any authenticated user can edit any pending or non-pending leave request's fields |
| `DELETE /{id}` | Any authenticated `User` | Existence only | No ownership check |
| `POST /{id}/approve`, `POST /{id}/reject` | Any authenticated `User` | `InvalidApprovalStateError` (must be `pending`) via `ApprovalService` | No check the caller is an approver, a manager of the employee, or holds any role — see §6 |

### Overtime (`api/overtime_requests.py`) and Timesheet (`api/timesheets.py`)

Structurally identical to Leave — same CRUD/approve/reject pattern, same absence of ownership or
role checks on every route.

### Attendance Reconciliation (`api/reconciliation.py`, prefix `/hr/reconciliation`)

`GET ""` takes `employee_id` and `date` as query parameters and returns that employee's
reconciliation for that date to **any** authenticated `User` — there is no check that the caller is
the named employee, that employee's manager, or holds any role. Any authenticated account can query
any employee's attendance reconciliation by supplying their id.

### HR Employees (`api/hr_employees.py`, prefix `/hr/employees`)

Full CRUD (`create`, `list`, `paginated list`, `get`, `update`, `delete`) is available to any
authenticated `User`. This includes writing `user_id` itself (§3 "linking is explicit") — meaning
any authenticated user can currently link or relink any `HrEmployee` row to any `User` id via
`PUT /hr/employees/{id}`, with only existence validation, no ownership or admin check.

### Roles (`api/roles.py`) — the one exception

`POST/PATCH/DELETE /roles` and the assign/remove-role endpoints require `RequireAdmin`
(`RequireRole("admin")`). `GET` endpoints require only `CurrentUser`. This is the only router in
the codebase with any role-gating at all.

---

## 6. Approval Authorization Analysis

`ApprovalService` (`services/approval.py`) is called by all six approve/reject endpoints across
Leave, Overtime, and Timesheet (§5). Per its own docstring and `ADR-003` ("Current Limitation":
*"Approval authorization belum diimplementasikan... Current: Authentication only"*):

**Current boundary**: `_apply_decision` validates only that the target entity's `status == "pending"`
(raising `InvalidApprovalStateError` otherwise) and that the entity exists. `approver_id` — the
value written to `approved_by` — is `current_user.id`, supplied directly by each API handler with
no validation of *who* that user is. Any authenticated `User`, regardless of role, regardless of
any relationship to the target employee, can approve or reject any pending leave request, overtime
request, or timesheet in the system.

**Missing boundary** (per `ADR-003` and `APPROVAL_WORKFLOW_DESIGN.md` §13, quoted in
`PR-050_DISCOVERY.md` §2): *"the best available authorization is 'any `User` holding the `approver`
role can approve any employee's request' — a flat, unscoped permission, not 'this employee's
manager can approve this employee's request.'"* Neither the role-scoped nor the manager-scoped
version is implemented; today it is weaker than either — no role check exists at all on these
routes.

This document does not propose where or how to close this gap (§10).

---

## 7. Authorization Boundary Location — Evidence for Each Option

Per instructions, no option is chosen here. Evidence for each:

**API dependency** (e.g. extending the `RequireRole`/`CurrentUser` pattern):
- Precedent exists and is proven: `RequireRole` is exactly this shape today, already composable
  with `CurrentUser` (`RequireAdmin = Depends(RequireRole("admin"))`).
- `ADR-002` assigns the API layer "authentication dependency" as a named responsibility, and FastAPI
  `Depends()` chains are the codebase's established mechanism for cross-cutting request concerns
  (`CurrentUser`, `Pagination`, `Search` are all built this way).
- Limitation: a dependency alone cannot easily express per-resource ownership checks (e.g. "is this
  `HrEmployee` the caller's own record") without fetching the target resource first — something
  `RequireRole` does not currently do (it checks only the caller's roles, never a target entity).

**Service layer**:
- `ADR-002` assigns "business validation," "business decision," and (implicitly, per
  `ARCHITECTURE_INVENTORY.md` §3 Service responsibilities) authorization-adjacent decisions to this
  layer — the inventory explicitly lists "Ownership validation" and "Approval authorization" under
  "Missing" security components, alongside "Permission" and "Policy," without assigning them to a
  layer.
- `ApprovalService` already centralizes the one cross-cutting workflow operation (approve/reject)
  that spans three domains (`ADR-003`) — a natural place to add a check that needs the target
  entity's `employee_id` already loaded, which the service has and a route-level dependency would
  not without an extra query.
- Every other service (`HrEmployeeService`, `LeaveRequestService`, etc.) already performs its own
  business validation inline (existence checks, date-range checks) — adding authorization here would
  match that existing per-service validation style rather than introducing a new one.

**Dedicated authorization component**:
- `MASTER_ARCHITECTURE_BLUEPRINT.md` §5 ("Authorization Architecture") explicitly targets this shape:
  *"Authorization menjadi capability tersendiri... Permission, Policy, Resource ownership, Role
  mapping... `CurrentUser` → `Authorization Context` → `Policy Evaluation` → `Allow/Deny`."*
  `CAPABILITY_DEPENDENCY_GRAPH.md` likewise places "Authorization Context" as a first-class node
  between "Authentication" and "Employee Context"/"Permission Model."
- No such component exists yet anywhere in the codebase — this option has target-architecture
  backing but zero implementation precedent, unlike the other two.
- Would be the first cross-domain component in the codebase that is neither a `Service` (owns
  business rules per `ADR-002`) nor a `Repository` (owns persistence) — a new architectural
  category, which `ADR-001`/`ADR-002` do not currently define a boundary for.

---

## 8. Role Model Analysis

**Existing (confirmed, §2, §4):**
- Database structure: `roles` table (`id`, `name` unique, `description`), `user_roles` join table
  (composite PK `user_id`, `role_id`, both `ON DELETE CASCADE`).
- Assignment mechanism: `RoleService.assign_role`/`remove_role`, exposed via
  `POST/DELETE /roles/{role_id}/users/{user_id}`, both gated by `RequireAdmin`.
- Usage: `RequireRole(role_name)` — a single flat "does this user hold a role with this exact name"
  check. No role hierarchy, no role composition, no wildcard/scope matching.
- Only one role name is referenced anywhere in code: `"admin"` (in `api/roles.py`). No seed data,
  migration, or fixture reviewed defines any other role name as a system convention — role names
  beyond `"admin"` would be freely-chosen strings created via `POST /roles`, not a fixed vocabulary.

**Missing:**
- An `approver` role (named as a hypothetical in `APPROVAL_WORKFLOW_DESIGN.md` §13, quoted §6) does
  not exist in any migration, seed, or fixture.
- A `manager` role, or any role tied to `HrEmployee.manager_id` standing, does not exist.
- A permission vocabulary (discrete, composable grants below the level of a whole role) — none
  exists; `Role` has no child/related table besides the `user_roles` membership join.
- Role scoping (e.g. org-scoped or department-scoped role assignment) — `user_roles` has no
  `organization_id`/`department_id` column; a role assignment today is global to the user, not
  scoped to any organizational unit.

---

## 9. Organization Hierarchy Analysis

`HrEmployee.manager_id` (`models/hr_employee.py:76-78`): nullable, self-referential FK to
`hr_employees.id`, `ON DELETE RESTRICT`, indexed. `HrEmployeeService` (`services/hr_employee.py`)
validates exactly one rule on it: `SelfManagerError` — an employee cannot be its own direct manager
(checked in both `create` and `update`, lines ~175-177, ~300-304). The service docstring/comments
confirm this explicitly: *"only a direct self-manager is rejected... no recursive validation or
cycle detection across the tree"* (`models/hr_employee.py:31-32`).

**Is manager-based authorization possible today?** Not directly, and not yet through the identity
link either:

- `HrEmployee.manager` is a working ORM relationship (`relationship(remote_side="HrEmployee.id")`),
  so "who is `employee_x`'s manager" is answerable once an `HrEmployee` row is in hand.
- But reaching "is the *current authenticated User* the manager of *this employee*" requires
  chaining through `user_id` first (`CurrentUser.id` → `HrEmployeeRepository.get_by_user_id(...)`
  → pick a resulting `HrEmployee` → compare its `id` to `target_employee.manager_id`), and:
  - No dependency performs the first hop today (§3).
  - The second hop ("pick a resulting `HrEmployee`") is unresolved whenever `get_by_user_id` returns
    more than one row (§3 edge cases) — there is no rule for which one represents "the" manager.
  - No cycle/tree traversal exists beyond one level — `manager_id` only exposes an employee's
    *direct* manager, not an arbitrary-depth "is this employee anywhere in my reporting chain"
    check. Any multi-level manager-authorization scheme would need new traversal logic that does
    not exist in `HrEmployeeRepository`, `HrEmployeeService`, or anywhere else reviewed.
- Department/team/location hierarchy: `Department`, `Team`, `Location`, `Organization` models exist
  and are FK'd from `HrEmployee`, but no code reviewed in `services/` or `dependencies/` derives an
  authorization decision from department/team membership. `Organization`/`Department`/`Team` were
  out of scope for direct inspection in this discovery (not listed under the repository areas to
  inspect) beyond their role as `HrEmployee` FK targets.

**Conclusion**: the data needed for single-level manager-based authorization exists on `HrEmployee`
(`manager_id`) and is now reachable in principle from `CurrentUser` via `user_id`, but no code path
performs this resolution today, and multi-level/tree-aware authorization is not supported by any
existing traversal logic.

---

## 10. Capability Impact Analysis

| Capability | Current authorization state | Future dependency (per `CAPABILITY_DEPENDENCY_GRAPH.md`) |
|---|---|---|
| Leave | `CurrentUser` only, no ownership/role check on any route (§5) | Depends on Authorization Context → Employee Context / Permission Model, per the graph's "Operational Capability" tier |
| Attendance (Reconciliation) | `CurrentUser` only; any user can query any `employee_id` (§5) | Same dependency; graph also notes prior discovery (`ATTENDANCE_RECONCILIATION_DESIGN.md` §11) named the `User`↔`HrEmployee` gap as the specific blocker on self-service/manager-scoped views — that schema gap is now closed (§3), but the consuming authorization logic is not built |
| Timesheet | `CurrentUser` only, no ownership/role check on any route (§5) | Same dependency tier as Leave |
| Overtime | `CurrentUser` only, no ownership/role check on any route (§5) | Same dependency tier as Leave |
| Approval | `CurrentUser` only; no role, no ownership, no employee-relationship check (§6) | Graph's "Approval Authorization" node sits directly above "Authorization Context" — marked `Missing` in the graph's Capability Status table (row: `Approval Authorization | Missing`) |
| Reconciliation | See Attendance, above | Same |
| Project | Out of scope for this discovery's endpoint review (uses the separate `Employee` model, §3); not part of the `HrEmployee`/approval chain this document traces | Not on the Identity & Authorization critical path per the dependency graph (Project sits outside the Authentication → Authorization Context → Approval Authorization chain) |

`CAPABILITY_DEPENDENCY_GRAPH.md`'s own architectural rule applies directly here: *"Capability tidak
boleh dibangun sebelum dependency-nya tersedia"* — Approval Authorization (currently `Missing`)
sits downstream of Authorization Context (also `Missing`) in the documented graph, and this
discovery finds that ordering matches the code: `ApprovalService` is fully built and wired, but the
authorization layer it would need to enforce anything is not.

---

## 11. Open Decisions

Listed, not resolved, per role constraints:

1. **RBAC vs. policy-based authorization.** `RequireRole` today is flat RBAC (name-in-set). The
   blueprint's target (`MASTER_ARCHITECTURE_BLUEPRINT.md` §5) names "Policy" and "Policy Evaluation"
   generically, without committing to a specific model (RBAC extension, ABAC, or a hybrid).
2. **Whether/how manager-hierarchy (`HrEmployee.manager_id`) participates in authorization**, and at
   what depth (direct-manager-only vs. arbitrary-depth reporting chain) — §9 found the data exists
   but no traversal or authorization logic is built.
3. **Ownership model** — what "this employee's request" means for authorization purposes (the
   requester = the `HrEmployee` whose `employee_id` matches, via `user_id`? their manager? a role
   holder? some combination), and how it differs across Leave/Overtime/Timesheet/Reconciliation
   versus Approval.
4. **Authorization enforcement location** — API dependency, service layer, or a dedicated
   authorization component (§7 lists evidence for each; none is chosen).
5. **Multiple-`HrEmployee`-per-`User` handling** — `get_by_user_id` returns a `Sequence` by design
   (§3); no rule exists for which row (if any) is authoritative when more than one is returned, and
   whether authorization logic should treat multiplicity as an error, a first-match, or a
   union-of-permissions case.
6. **Role vocabulary** — only `"admin"` exists as a de facto convention today (§8); whether
   `approver`, `manager`, or other role names should be introduced, and whether roles should be
   scoped (e.g. per-organization) rather than global as they are now.
7. **Provisioning process for `HrEmployee.user_id`** — linking is mechanically possible via the
   existing `PUT /hr/employees/{id}` endpoint (§3), but whether that is the intended provisioning
   path, versus a dedicated onboarding flow, remains open (carried over unresolved from
   `PR-050_DISCOVERY.md` §7 item 3 — still unresolved as of this document).
8. **Whether `user_id` should become unique** — deferred at the schema level (§3, `ADR-004`); still
   undecided, and every downstream authorization design that assumes "the" employee for a user
   depends on this being resolved one way or the other.
9. **Scope of the authorization boundary's first increment** — whether Approval Authorization (the
   capability the dependency graph places immediately downstream) is the correct first consumer, or
   whether ownership-scoping on Leave/Overtime/Timesheet/Reconciliation reads should come first —
   not decided by this document.

---

## 12. Evidence References

- Models: `models/user.py`, `models/role.py`, `models/user_role.py`, `models/hr_employee.py`,
  `models/employee.py`, `models/leave_request.py`, `models/overtime_request.py`,
  `models/timesheet.py`, `models/leave_balance.py`
- Repositories: `repositories/user.py`, `repositories/role.py`, `repositories/hr_employee.py`
- Services: `services/auth.py`, `services/role.py`, `services/hr_employee.py`,
  `services/approval.py`
- Dependencies: `dependencies/auth.py`, `dependencies/rbac.py`
- API: `api/auth.py`, `api/roles.py`, `api/leave_requests.py`, `api/overtime_requests.py`,
  `api/timesheets.py`, `api/reconciliation.py`, `api/hr_employees.py`, `main.py` (TODO comment,
  lines 87-89)
- Core: `core/request_context.py`
- Migration: `alembic/versions/20260804_0900-9c3d5f1a7b2e_add_user_id_to_hr_employees.py`
- Tests: `tests/test_hr_employee_repository.py` (lines 557-611, `get_by_user_id` cardinality
  coverage)
- Architecture docs: `ARCHITECTURE_INVENTORY.md`, `CAPABILITY_DEPENDENCY_GRAPH.md`,
  `MASTER_ARCHITECTURE_BLUEPRINT.md`, `MASTER_ARCHITECTURE_ROADMAP.md`,
  `ARCHITECTURE_DECISION_RECORDS/ADR-001` through `ADR-004`, `PR-050_DISCOVERY.md` (Steps 1–2),
  `APPROVAL_WORKFLOW_DESIGN.md` (cited via `PR-050_DISCOVERY.md` §2 for its §13 quotation),
  `docs/product/02_PRODUCT_SCOPE.md`, `docs/product/03_TARGET_CUSTOMER.md` (cited via
  `PR-050_DISCOVERY.md` §2 for named manager personas)

**Not resolved by this document**: any of the items in §11. No model, migration, repository method,
service, dependency, or API route has been added or modified in producing this discovery.
