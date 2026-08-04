# PR-051 — Authorization-Scoping Consumer of the User ↔ HrEmployee Link (Discovery)

Status: **Discovery only. No code, no migrations, no tests. Awaiting review.**

---

## 1. Executive Summary

**Repository evidence identifies the missing authorization/ownership-scoping layer on top of the
now-shipped `User` ↔ `HrEmployee` link as the next highest-priority architectural gap.** PR-050
resolved the schema-level blocker eight prior discovery documents had named in nearly identical
words: `hr_employees.user_id` exists (`models/hr_employee.py:91`, migration
`9c3d5f1a7b2e_add_user_id_to_hr_employees.py`), and `HrEmployeeRepository.get_by_user_id`
(`repositories/hr_employee.py:43-54`) resolves an authenticated `User` to its `HrEmployee` row(s).
That work is merged (`d82c8c2`, on `main`, confirmed by `git log`).

**But `get_by_user_id` has exactly one reference in the entire codebase: its own definition.**
Confirmed by a repository-wide grep — zero call sites anywhere in `services/`, `api/`, or
`dependencies/`. The link PR-050 built to make authorization *possible* is not yet consumed
*anywhere*. Every consequence PR-050's own discovery predicted would remain once the schema gap
closed is confirmed still open by direct read of the current code:

- `ApprovalService` (`services/approval.py:44-46`) still documents, verbatim, "Authorization
  beyond authentication... explicitly out of scope for this service" — and every one of its six
  public methods (`approve_leave_request`, `reject_leave_request`,
  `approve_overtime_request`/`reject_overtime_request`, `approve_timesheet`/`reject_timesheet`)
  still performs zero role or ownership check.
- Every router that exposes those methods (`api/leave_requests.py`, `api/overtime_requests.py`,
  `api/timesheets.py`) gates `.../approve` and `.../reject` with `CurrentUser` only — no
  `RequireRole`, no ownership check of any kind.
- `LeaveRequestCreate`, `OvertimeRequestCreate`, and `TimesheetCreate`
  (`schemas/leave_request.py:8`, `schemas/overtime_request.py:8`, `schemas/timesheet.py:8`) each
  accept a caller-supplied `employee_id: uuid.UUID` with no check that the authenticated `User`
  has any relationship to that employee — any authenticated user can create, list, or query a
  request "as" or "about" any `HrEmployee` in the system, and `GET /hr/reconciliation` accepts an
  arbitrary `employee_id` query parameter under the same `CurrentUser`-only gate
  (`api/reconciliation.py:22-30`).
- `RequireRole` (`dependencies/rbac.py`) still has exactly one call site in the whole codebase
  (`RequireAdmin` in `api/roles.py`), and no role named `approver` or `manager` (or any
  authorization-relevant role beyond `admin`) exists anywhere in the repository (confirmed by
  grep).

**Why this is the next gap, not a re-litigation of PR-050.** `APPROVAL_WORKFLOW_DESIGN.md` §6, §9,
§13, and §14 (Ambiguity 2 and 3) all frame this exact sequencing: the `User`↔`HrEmployee` link is a
*prerequisite*, not the *goal*; the stated goal is authorization scoped to "this employee's
manager can approve this employee's request" rather than "any authenticated user can call the
endpoint." PR-050 §7 says so explicitly: *"This discovery does not recommend building the
downstream consumer... those are separate, larger decisions."* That downstream consumer is now the
only remaining piece of the chain every prior discovery document has been building toward, and it
remains completely unbuilt.

**What repository evidence supports**: an authorization/scoping mechanism must be built that
consumes `HrEmployeeRepository.get_by_user_id`; the existing `RequireRole` dependency pattern is
directly reusable for a role-based version; `HrEmployee.manager_id` is available for an org-chart
version; and the codebase's own prior discovery (`APPROVAL_WORKFLOW_DESIGN.md` §9) already
identified role-based and org-chart-based as the two live candidates.

**What repository evidence does not support**: which of those two mechanisms (or a combination) is
correct, which endpoints it applies to first (approval only, vs. every `employee_id`-scoped
endpoint across Leave/Overtime/Timesheet/Reconciliation), or how the codebase should handle a
`User` that `get_by_user_id` resolves to zero or more than one `HrEmployee` — a case PR-050's own
Step 2 correction (§2.3 of that document) proved is possible by construction, since `user_id` on
`hr_employees` carries no uniqueness constraint.

---

## 2. Repository Evidence

**2.1 — The link exists and is unconsumed.**

- `models/hr_employee.py:91` — `user_id: Mapped[uuid.UUID | None]`, FK to `users.id`, `ON DELETE
  SET NULL`, indexed (`Index("ix_hr_employees_user_id", "user_id")`, line 51).
- `alembic/versions/20260804_0900-9c3d5f1a7b2e_add_user_id_to_hr_employees.py` — the migration
  that added it, confirmed present and the current head of the `hr_employees`-column-addition
  chain.
- `repositories/hr_employee.py:43-54` — `get_by_user_id(user_id) -> Sequence[HrEmployee]`, a
  direct `select(...)` (not the shared `get_by` helper), per PR-050 Step 2's correction for
  non-unique `user_id`.
- **Grep across `services/api/src` for `get_by_user_id`**: one match — the method's own
  definition. No service, dependency, or router calls it.

**2.2 — `ApprovalService` still has no authorization beyond authentication, confirmed by full
read (`services/approval.py`).**

- Class docstring, lines 44-46: *"Authorization beyond authentication, decision history, audit
  logging, and event/notification dispatch are explicitly out of scope for this service."*
- `_apply_decision` (lines 190-227) — fetches the entity, checks only `entity.status ==
  "pending"`, then writes `approved_by=approver_id` unconditionally. No role check, no ownership
  check, no call to `HrEmployeeRepository` anywhere in the file (confirmed: zero `HrEmployee`
  import in `services/approval.py`).
- All six public methods (`approve_leave_request`/`reject_leave_request` lines 70-120,
  `approve_overtime_request`/`reject_overtime_request` lines 122-154,
  `approve_timesheet`/`reject_timesheet` lines 156-188) take `approver_id: uuid.UUID` as a bare
  parameter and never validate the caller's relationship to the target entity's `employee_id`.

**2.3 — Every router endpoint that reaches `ApprovalService` gates on `CurrentUser` only.**

- `api/leave_requests.py:148-164`, `api/overtime_requests.py:150-168`,
  `api/timesheets.py:150-164` — each `.../approve` and `.../reject` route depends on
  `current_user: CurrentUser` and passes `current_user.id` straight through as `approver_id`.
  Confirmed by grep: no `RequireRole`, no other authorization dependency, imported or used in any
  of these three router modules.

**2.4 — The same caller-supplied-`employee_id`-with-no-scoping shape recurs across every HR
transactional schema, not just Approval.**

| Schema | Evidence |
|---|---|
| `LeaveRequestCreate` | `schemas/leave_request.py:8` — `employee_id: uuid.UUID`, required, caller-supplied |
| `OvertimeRequestCreate` | `schemas/overtime_request.py:8` — same shape |
| `TimesheetCreate` | `schemas/timesheet.py:8` — same shape |
| `GET /hr/leave-requests` (and overtime/timesheet equivalents) | `api/leave_requests.py:42-51` — `employee_id` is an optional query filter, gated by `CurrentUser` only |
| `GET /hr/reconciliation` | `api/reconciliation.py:22-30` — `employee_id: Annotated[uuid.UUID, Query()]`, required, gated by `CurrentUser` only |

None of these five call sites checks that the authenticated `User` corresponds to (or manages)
the `HrEmployee` named by `employee_id`. This is the same root cause named for Approval
specifically, but it is not unique to Approval — it is the uniform shape of every HR-domain
write and read that takes an `employee_id`.

**2.5 — `RequireRole` exists, is reusable, and has exactly one caller in the whole codebase.**

- `dependencies/rbac.py:18-33` — `RequireRole(role_name)` is a generic dependency factory: checks
  `service.user_has_role(current_user.id, role_name)`, 403s otherwise. Fully general — no
  HR-specific coupling.
- `api/roles.py:25` — `RequireAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]` — the
  only instantiation anywhere, gating role-management endpoints on themselves.
- **No role named `approver`, `manager`, or any HR-authorization-relevant name exists anywhere**
  (grep across all `.py` files for `"approver"`/`"manager"` as string literals: zero matches
  outside comments/docs already quoted in §2.6 below). `RoleService` (`services/role.py`) is fully
  generic — `create`/`get`/`list`/`update`/`delete`/`assign_role`/`remove_role`/`user_has_role` —
  with no seeded role vocabulary anywhere in the reviewed codebase or its migrations.
- `main.py:87-89` — the same `TODO` PR-050 already cited, unchanged: *"Locations... are
  authenticated-only for now. Once the platform defines administrative roles for master data, gate
  these routes with `RequireRole(...)`..."* — confirms the platform-wide authorization story is
  still only "authenticated," not "authorized," everywhere it has come up, not only in HR.

**2.6 — This exact sequencing is the codebase's own stated plan, not an invented one.**

`APPROVAL_WORKFLOW_DESIGN.md` §6 (lines 268-305, quoted at length in `PR-050_DISCOVERY.md` §2):
*"This gap must be resolved (i.e., some `User`↔`HrEmployee` linkage must exist) before role-scoped
or manager-scoped approval authorization can be implemented at all."* §9 lists, as Ambiguity 3
(still unresolved, restated verbatim below in §8): *"Authorization model: role-based, org-chart-based
(manager-of-requester), or both? ... no precedent for either shape exists in the codebase today."*
§13 (Risks): *"the best available authorization is 'any `User` holding the `approver` role can
approve *any* employee's request' — a flat, unscoped permission, not 'this employee's manager can
approve this employee's request.'"* PR-050's own "Authorization impact" section (its Step 1, final
bullet): *"a future `dependencies/auth.py`-style `CurrentEmployee` dependency could resolve
`CurrentUser.id → HrEmployeeRepository.get_by_user_id(...)` without any further schema change. No
such dependency is built here."* Every one of these forward references is now the only undone
piece.

**2.7 — `HrEmployee.manager_id` is available for an org-chart-based mechanism, confirmed by
direct read.**

- `models/hr_employee.py:76` — `manager_id: Mapped[uuid.UUID | None]`, nullable self-reference FK
  to `hr_employees.id`, `RESTRICT`, indexed (line 44). Populated today by `HrEmployeeService`'s
  existing existence-check pattern (mirrors the nine other FK checks).
- Every request-shaped entity (`LeaveRequest`, `OvertimeRequest`, `Timesheet`) carries
  `employee_id → hr_employees.id` (confirmed §2.4 evidence table's schemas map 1:1 to these
  models' own `employee_id` columns). An org-chart check ("is the approver's `HrEmployee` the
  `manager_id` of the target request's `HrEmployee`") is mechanically composable today from
  `get_by_user_id` (approver side) plus a `get(entity_id).employee_id` lookup (target side) plus a
  read of that employee's `manager_id` — no new column or migration required.

**2.8 — Roadmap and product-scope grounding, checked directly.** `docs/product/02_PRODUCT_SCOPE.md`
§1 names `Authorization`, `Role & Permission` as in-scope Platform Foundation modules (same
citation PR-050 used); `03_TARGET_CUSTOMER.md` names `Supervisor`/`Area Manager`/`Regional
Manager` personas by role title, implying a real manager hierarchy the product expects
authorization to respect. No product document names "approval authorization" or "manager-scoped
access" as a literal roadmap line item — this is the same weaker-than-a-named-feature grounding
every prior discovery (including PR-050) already found and disclosed for its own subject, not new
weakness introduced here.

---

## 3. Architectural Analysis

**What kind of gap is this?** Unlike PR-050 (a missing *relationship* between two complete
aggregates), this is a missing *cross-cutting concern* — authorization/ownership-scoping — that
every HR-domain write and read implicitly assumes will eventually exist (`ApprovalService`'s own
docstring says so by declaring it explicitly out of scope, not by omission) but that no component
in the codebase currently implements beyond bare authentication. It is architecturally analogous
to PR-047's "orchestration service" gap in shape (a capability multiple existing aggregates need,
that none of them owns individually) but the *consequence* is different: PR-047 identified a
missing orchestration boundary before anything shipped without it; this gap is a missing control on
code that has already shipped and is currently reachable with no meaningful access restriction.

**Why this is architecturally prior to continuing Leave Balance Synchronization (PR-049) or
extending Reconciliation.** Both of those remain blocked on the same undiscoverable business-rule
ambiguities PR-050 already found and declined to guess at (period-year derivation, row selection,
day-count semantics — `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` §12.2-§12.7; unchanged, confirmed
by direct read of `services/leave_balance.py`/`repositories/leave_balance.py` — no `period_year`
handling exists anywhere in either file, and no commit since `e34b413` has touched
`services/approval.py`'s LeaveBalance-synchronization docstring). This gap has no equivalent block:
the question it raises ("role-based, org-chart-based, or both, and which endpoints first") is the
exact ambiguity `APPROVAL_WORKFLOW_DESIGN.md` §9 already named as the *only* remaining open
question once `User`↔`HrEmployee` resolved — and that resolution is now done.

**Why this is not merely "finish PR-050."** PR-050's own scope was explicitly the schema and
lookup primitive only (§7 of that document: *"This discovery does not recommend building the
downstream consumer... those are separate, larger decisions that presuppose the schema question
this document addresses"*). This document is not reopening that scope — it is identifying that the
presupposed downstream decision is now the only thing standing between the codebase and the
authorization boundary eight consecutive discovery documents have flagged as missing.

**Consequence already realized, not merely anticipated — restated and now broader than PR-050
found it.** PR-050 focused on `ApprovalService`'s six methods. Direct re-read confirms the same
shape recurs at the *creation* and *read* boundary of the same three entities plus Reconciliation
(§2.4) — a caller-supplied `employee_id` with a `CurrentUser`-only gate is not a peculiarity of
approval; it is the uniform current state of the entire Time Management API surface's ownership
model.

---

## 4. Candidate Implementations

Enumerated for cost/precedent analysis, per the same method PR-048/PR-049/PR-050 used — **not a
narrowing of the design space by this section alone** (see §7 for what evidence actually resolves).

### Option A — Role-based only: a new `approver` (or similar) role, gated via existing `RequireRole`

**Supporting evidence**: `RequireRole` (`dependencies/rbac.py`) already exists, is fully generic,
and needs zero new code to apply — only a new seeded role name and its use as a dependency on the
six approve/reject routes (mirroring `RequireAdmin`'s exact shape in `api/roles.py:25`). This is
the smallest-new-precedent option: it introduces one new role name, using machinery that already
exists and has one working precedent.

**Contradicting evidence**: `APPROVAL_WORKFLOW_DESIGN.md` §13 (quoted §2.6) already characterizes
this alone as "a flat, unscoped permission" — it would not answer the question this gap's own
name in eight prior documents attaches to it ("is this `User` this employee's manager"), only "is
this `User` allowed to approve *something*." It does not touch the caller-supplied-`employee_id`
problem on create/read endpoints (§2.4) at all — a role check on `.../approve` says nothing about
who may create a request "as" an arbitrary employee or query another employee's Reconciliation
report.

### Option B — Org-chart-based: a `CurrentEmployee`-shaped dependency using `manager_id`

**Supporting evidence**: consumes the exact primitive PR-050 built for this purpose
(`get_by_user_id`) and `HrEmployee.manager_id` (§2.7), which already exists and is already
populated by ordinary HR-employee CRUD. Matches the specific phrase every prior discovery used
("this employee's manager can approve this employee's request") more literally than Option A.

**Contradicting evidence**: no precedent anywhere in the codebase for a dependency that resolves a
non-unique lookup (`get_by_user_id` returns `Sequence[HrEmployee]`, not a single row — PR-050 Step
2, §2.3 of that document) into a single "current employee" identity; this option requires a new
decision this repository does not currently make anywhere — what happens when a `User` maps to
zero `HrEmployee`s (an admin-only account) or more than one (a case the schema permits by
construction, cardinality unresolved per PR-050 §8 Ambiguity 3, still open). It also does not, by
itself, cover the case where "any user with the right role, not necessarily this employee's direct
manager" is the intended model (e.g. an HR administrator who is not in the org chart at all) —
`APPROVAL_WORKFLOW_DESIGN.md` §9's own ambiguity 3 raises "or both" for exactly this reason.

### Option C — Both, combined (role gates "may this `User` ever decide," org-chart scopes "may this
`User` decide *this* request")

**Supporting evidence**: `APPROVAL_WORKFLOW_DESIGN.md` §9 names this combination explicitly as a
live candidate, not invented here. It would resolve Option A's "unscoped" weakness and Option B's
"no path for a non-org-chart approver (e.g. HR admin)" weakness simultaneously.

**Contradicting evidence**: composes two mechanisms neither of which has a single working example
in this codebase yet (§2.5, §2.7) — this is the largest-new-precedent option of the three, and no
repository evidence establishes that both are needed versus either alone being sufficient for a
first version.

### Option D — No new authorization; leave the current `CurrentUser`-only gate as the shipped state

**Supporting evidence**: mechanically, this is what the codebase already does — zero-cost,
zero-risk to any other component.

**Contradicting evidence**: this is the exact state `APPROVAL_WORKFLOW_DESIGN.md` §13 already
named as a real risk, not a hypothetical one, for a feature that is live and callable today. Every
prior discovery that named the `User`↔`HrEmployee` gap did so specifically because it blocked
*eventually* closing this option out — declining to build it now, with the blocker gone, would
leave the platform's newest and most sensitive write surface (approve/reject on
leave/overtime/timesheet) permanently in the state every prior document flagged as provisional.

**No option above is selected by this section.** Each is evaluated on its own merits in §7, where
repository evidence is applied to narrow, but not fully resolve, the field.

---

## 5. Architectural Constraints

What current repository evidence establishes about *any* eventual implementation, regardless of
which option (§4) is ultimately chosen:

- **Must tolerate a `User` with zero linked `HrEmployee` rows.** `get_by_user_id` returns
  `Sequence[HrEmployee]`, and nothing in the codebase guarantees every `User` has at least one
  linked row — `scripts/create_admin.py`-created accounts have none by construction (PR-050 §5).
  Any authorization mechanism built on this lookup must define (or explicitly leave undefined) what
  happens for such a `User` — it cannot assume a non-empty result.
- **Must tolerate a `User` with more than one linked `HrEmployee` row**, since `hr_employees.user_id`
  carries no uniqueness constraint (PR-050 Step 2, confirmed unchanged: no migration since
  `9c3d5f1a7b2e` adds one). Whichever mechanism is chosen must state how it picks among multiple
  rows, or must be evidenced as unnecessary — not silently assume uniqueness the way an earlier,
  since-corrected version of PR-050's own repository method briefly did.
- **`RequireRole`'s existing shape is the only precedented FastAPI-dependency-based authorization
  pattern in this codebase** (`dependencies/rbac.py:18-33`) — any role-based component of a
  solution should extend this pattern rather than introduce a second, differently-shaped one,
  absent evidence a new shape is required.
- **No `Permission` model, and no per-endpoint permission granularity, exists anywhere.**
  `RoleService` operates on role *names* only (`user_has_role(user_id, role_name)` — a string
  match); there is no finer-grained permission concept to compose with. Any design assuming
  permission-level (not just role-level) granularity is not supported by anything in the current
  codebase.
- **Whichever service ends up performing the check, `ApprovalService`'s own documented invariant
  ("Authorization beyond authentication... explicitly out of scope for this service") would have
  to change**, either by removing that invariant (moving the check inside the service) or by
  confirming it stays true and the check lives entirely at the router/dependency layer instead
  (matching where `RequireRole`/`RequireAdmin` already live today, outside every service they
  gate). No repository evidence currently picks between these two placements.
- **The same gap recurs on `employee_id`-scoped create/list endpoints outside Approval** (§2.4) —
  any design that treats this as "an Approval-only fix" would leave the identical shape open on
  Leave/Overtime/Timesheet creation and listing and on Reconciliation, which repository evidence
  does not distinguish as lower-priority than Approval itself (all five call sites share the same
  `CurrentUser`-only gate and the same caller-supplied `employee_id`).

---

## 6. Alternatives Considered

**Continuing Leave Balance Synchronization (PR-049) into its next step.** Rejected, for the same
reason PR-050 already rejected it: its remaining open items (period-year derivation, row selection,
day-count semantics) are business-rule ambiguities, unchanged since PR-049, that no repository
evidence resolves and that this discovery is instructed not to invent answers to. Directly
re-confirmed here: no commit since `e34b413` has touched the relevant code, and
`services/approval.py`'s docstring still states the same unresolved reasons verbatim.

**Extending Attendance Reconciliation with a self-service or manager-scoped view.**
`ATTENDANCE_RECONCILIATION_DESIGN.md` §11 names this as blocked by the `User`↔`HrEmployee` gap,
which is now resolved — making this a plausible alternative topic. Considered and folded into this
document's scope rather than treated as a separate, competing topic: a "manager-scoped
reconciliation view" is not a new architectural question distinct from "manager-scoped
authorization" — it is one more consumer of the exact same missing mechanism this document already
identifies (§2.4 explicitly includes `GET /hr/reconciliation` in the caller-supplied-`employee_id`
evidence table). Treating it as a separate PR topic would re-discover the same root cause this
document already establishes.

**Building a dedicated `Permission`/RBAC model beyond simple role names.** Considered because
`RoleService`'s current shape (flat role-name string match) is coarse. Rejected as this document's
topic: no repository evidence anywhere calls for finer-grained permissions than role names — no
service, schema, or product document references a `Permission` concept, and introducing one now
would be inventing structure ahead of a concrete need, the same premature-generalization argument
PR-049/PR-050 already used to reject over-general shapes elsewhere.

**Wiring `AuditLog` to record approval decisions.** Real, confirmed-unused infrastructure
(`services/audit_log.py`), named as optional (not blocking) by every document that raises it
(`APPROVAL_WORKFLOW_DESIGN.md` §14.3). Rejected as this document's topic for the same reason
PR-050 rejected it: no shipped feature is currently broken or unauthorized for lack of it — this
gap (authorization itself) is the more consequential, more-consistently-evidenced one.

**Generalizing `BaseRepository` date-range query support, `VersionMixin`/`SoftDeleteMixin`
enforcement.** Both remain real, confirmed gaps (unchanged since PR-048/PR-049), and both remain
narrower in consequence — neither currently leaves a shipped write endpoint without meaningful
access control the way this gap does.

**Roadmap Phase 3/4/5 modules** (`Territory`, `Region`, `Area`, `Store`, `Customer`, `Mission`,
`Visit`, `Survey`, `GPS`, `Photo`, `KPI`, `Target`, per `docs/product/06_PRODUCT_ROADMAP.md`).
Considered and set aside for the same reason every prior discovery has set them aside: none has any
existing model, repository, service, schema, or prior discovery to build repository evidence from.

---

## 7. Recommendation

**Repository evidence supports treating authorization/ownership-scoping on top of the `User` ↔
`HrEmployee` link as the next-highest-priority architectural gap.** It is the explicit, named
successor to PR-050 in the codebase's own prior discoveries (§2.6), and it is the confirmed,
current reason the platform's most recently completed schema work (`get_by_user_id`) has zero
consumers and the platform's most recently shipped write surface (`ApprovalService`) has no access
control beyond authentication.

- Current repository evidence supports building on the **existing `RequireRole` dependency
  pattern** for any role-based component — it is the only precedented authorization-dependency
  shape in the codebase (§5), and extending it (new role name, new dependency instantiation) is a
  smaller-new-precedent step than introducing a differently-shaped mechanism.
- Current repository evidence supports that **`HrEmployeeRepository.get_by_user_id` is the correct
  and only existing primitive** for any org-chart-based component — no other lookup path exists,
  and none should be built, since this one already exists for exactly this purpose (PR-050
  "Authorization impact," quoted §2.6).
- Current repository evidence supports that **any implementation must explicitly define its
  behavior for zero-result and multiple-result `get_by_user_id` calls** — this is not optional
  hardening; it is a structural possibility the schema itself permits (§5), unlike a hypothetical
  where uniqueness could simply be assumed.
- Current repository evidence supports that **the gap is not Approval-specific** — a scoped
  solution should be evaluated against, at minimum, the same five call sites enumerated in §2.4,
  not designed against `ApprovalService` alone and left silent on Leave/Overtime/Timesheet
  create/list and Reconciliation.

**Repository evidence is insufficient to determine the authorization model.** `RequireRole` (role,
Option A), `manager_id`-based org-chart scoping (Option B), and their combination (Option C) are
each named and partially supported by different pieces of evidence (§4), and
`APPROVAL_WORKFLOW_DESIGN.md` §9 Ambiguity 3 already reached the identical conclusion on this exact
question — *"no precedent for either shape exists in the codebase today"* — and no evidence has
appeared since PR-046 to break that tie; PR-050 closed the *prerequisite* question, not this one.
**Choosing the authorization model, its placement (service-internal vs. dependency-layer), its
behavior under zero/multiple `HrEmployee` results, and its exact endpoint scope (Approval only,
vs. every `employee_id`-scoped endpoint) are implementation-PR decisions**, to be made with the
benefit of the constraints in §5, not conclusions this discovery reaches.

**This discovery does not recommend a specific role vocabulary, a specific dependency
implementation, or a specific rollout order across the five affected call sites** — those
presuppose the model-selection question above and are not decidable from repository evidence
alone.

---

## 8. Remaining Ambiguities

Per instructions, listed, not guessed at:

1. **Authorization model.** Role-based (`RequireRole`, new role vocabulary), org-chart-based
   (`HrEmployee.manager_id`-aware via `get_by_user_id`), or both — inherited unresolved, verbatim,
   from `APPROVAL_WORKFLOW_DESIGN.md` §9 Ambiguity 3; still open, no evidence has appeared since to
   resolve it.
2. **Behavior for a `User` with zero linked `HrEmployee` rows.** Whether such a `User` is denied
   outright, granted a role-based fallback, or something else — not addressed by any reviewed
   document.
3. **Behavior for a `User` with more than one linked `HrEmployee` row.** Whether the mechanism
   picks the first, requires all, requires an explicit selector, or this case is treated as
   unsupported/an error — the schema permits it (PR-050 §8 Ambiguity 3, still open), but no
   consumer-side behavior has ever been defined for it.
4. **Placement of the check.** Inside `ApprovalService` (removing its current documented
   authorization-out-of-scope invariant) versus entirely at the router/dependency layer (matching
   where `RequireRole` already lives) — not decidable from the codebase; both are structurally
   possible today.
5. **Scope: Approval only, or every `employee_id`-scoped endpoint.** Whether this gap should be
   closed for the six approve/reject routes first, or treated as one fix across all five call
   sites in §2.4 simultaneously — a sequencing decision, not an architectural one this discovery
   resolves.
6. **Whether "manager" for authorization purposes means `HrEmployee.manager_id` specifically**, or
   some broader/different org-chart concept (e.g. `department_id`/`team_id`-based scoping instead
   of or in addition to direct-manager scoping) — no product document reviewed defines "manager"
   for approval purposes beyond the persona names in `03_TARGET_CUSTOMER.md` (§2.8).
7. **Role vocabulary, if role-based.** What role name(s) to introduce (`approver`, `manager`, one
   per module, or a single platform-wide role) — not decidable from the codebase; `RoleService`
   itself is fully generic and takes no position on naming.
8. **Product intent.** No product document names "approval authorization," "manager-scoped
   access," or an equivalent term explicitly; support is inferred from `02_PRODUCT_SCOPE.md`'s
   named `Authorization`/`Role & Permission` foundation modules and named manager personas — the
   same strength of grounding (not weaker, not stronger) that PR-050 already disclosed for its own
   subject.

**Stopping here per instructions.** No model, migration, repository method, service, dependency,
or API route has been added or modified. Awaiting direction on the items above — particularly the
authorization-model question (Ambiguity 1), without which no implementation can begin — before
proceeding.
