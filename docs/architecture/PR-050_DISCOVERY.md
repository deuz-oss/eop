# PR-050 — User ↔ HrEmployee Identity Linkage (Discovery)

Status: **Discovery only. No code, no migrations, no tests. Awaiting review.**

---

## 1. Executive Summary

**Repository evidence identifies the missing `User` ↔ `HrEmployee` identity link as the next
highest-priority architectural gap.** Every one of the eight prior discovery documents in this
repository — `ATTENDANCE_DESIGN.md` (PR-039), `LEAVE_DESIGN.md` (PR-040),
`HOLIDAY_CALENDAR_DESIGN.md` (PR-041), `TIMESHEET_DESIGN.md` (PR-045),
`APPROVAL_WORKFLOW_DESIGN.md` (PR-046), `APPROVAL_ORCHESTRATION_DESIGN.md` (PR-047),
`ATTENDANCE_RECONCILIATION_DESIGN.md` (PR-048), and `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`
(PR-049) — names this exact gap, in nearly identical words, as a blocker it declines to resolve.
No other gap in this codebase is named by more than a handful of these documents; this one is
named by all eight. `models/user.py:15-24` (`User`: `email`, `password_hash`, `full_name`,
`is_active`, `roles`) and `models/hr_employee.py:20-101` (`HrEmployee`: nine FKs to organizational
master data, plus a self-referential `manager_id`) confirm the relationship is absent in both
directions today — no `user_id` column on `hr_employees`, no `hr_employee_id`/`user_id` column on
`users`.

**Why this discovery does not continue Leave Balance Synchronization (PR-049).** Per instructions,
that continuation is not assumed by default, and repository evidence does not support it here.
PR-049's own discovery, and the "Implementation — Step 1: Architecture Decision" appended to it,
were carried out: `services/approval.py` (current state, confirmed by direct read) already shows
the chosen architecture built — `_apply_decision`/`_complete_decision` are split exactly as PR-049
specified (`services/approval.py:190-236`), and `approve_leave_request`'s own docstring
(`services/approval.py:73-90`) states explicitly that the actual `LeaveBalance` write is not
implemented **because every prerequisite is a business-rule ambiguity, not an architectural one**:
period-year derivation, row selection, and day-count semantics. These are not decidable from the
repository (PR-049 §12.2–§12.4) and remain undecided — the git history confirms no commit since
`e34b413` has touched this. Continuing Leave Balance Synchronization now would mean guessing at
product rules this discovery is instructed not to invent, not resolving an architectural question.
The User↔HrEmployee gap, by contrast, is not blocked on undiscoverable business rules — it is
blocked on a schema decision (which table gets the FK, in which direction) that the codebase's own
precedents can meaningfully constrain, and its absence is the stated reason (PR-046 §13, quoted
§3 below) that Approval — the feature most recently built — ships with a materially weaker
authorization boundary than "approval" ordinarily implies.

**What repository evidence supports**: some form of `User`↔`HrEmployee` linkage must eventually
exist for the authorization concerns already raised by name in the Approval discoveries; the
codebase has a strong, repeated precedent (five migrations) for adding a single nullable FK column
in its own standalone migration, chained off the current head; and no repository, service, or API
component reviewed can resolve "which `HrEmployee` is this authenticated `User`" today.

**What repository evidence does not support**: the direction of the FK (`hr_employees.user_id` vs.
`users.hr_employee_id`), its cardinality (one-to-one, or one-to-many via a join table), its
nullability/ownership semantics, or the authorization model it would ultimately feed
(role-based, org-chart/`manager_id`-based, or both). These are choices for the implementation PR,
not conclusions this discovery reaches (§7).

---

## 2. Repository Evidence

**The gap, named in the codebase's own prior discoveries — same words, eight separate times:**

| Document (PR) | Citation |
|---|---|
| `ATTENDANCE_DESIGN.md` (PR-039) | §11: *"`User` ↔ `HrEmployee` gap. Every API route authenticates a `User` (§0), but nothing links `User` to `HrEmployee`... no reliable way to answer 'this authenticated `User` is this `HrEmployee`.'"* (lines 317-320) |
| `LEAVE_DESIGN.md` (PR-040) | §1: *"The `User` ↔ `HrEmployee` gap still exists. No FK anywhere links the authenticated `User`... to an `HrEmployee` row."* (lines 32-33) |
| `HOLIDAY_CALENDAR_DESIGN.md` (PR-041) | §1: *"The `User` ↔ `HrEmployee` gap still exists (no FK anywhere links the authenticated `User`...)"* (line 49) |
| `TIMESHEET_DESIGN.md` (PR-045) | §2: confirms zero `HrEmployee`-referencing FK on `User`, "confirming the `User` ↔ `HrEmployee` gap first flagged in [PR-039]" (line 94) |
| `APPROVAL_WORKFLOW_DESIGN.md` (PR-046) | §6 (dedicated section): *"does the codebase provide any reliable way to map `User` → `HrEmployee`? ... the relationship is absent in both directions... This gap must be resolved... before [authorization stronger than flat role-gating is possible]."* (lines 270-303) |
| `APPROVAL_ORCHESTRATION_DESIGN.md` (PR-047) | §9 (dedicated section, "Gap 1"): re-verifies by direct file read, unchanged (lines 404-410) |
| `ATTENDANCE_RECONCILIATION_DESIGN.md` (PR-048) | §11: *"blocks any self-service or manager-scoped reconciliation view"* (line 566) |
| `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` (PR-049) | §2: notes `ApprovalService` passes `current_user.id` directly as `approver_id`, "no `HrEmployee` resolution is needed" — i.e., built around the gap, not through it (line 111) |

No other architectural gap in this codebase is named across more than three of these documents.
The closest competitors — generic `BaseRepository` date-range support (named in
`HOLIDAY_CALENDAR_DESIGN.md`, `LEAVE_DESIGN.md`, `TIMESHEET_DESIGN.md`,
`ATTENDANCE_RECONCILIATION_DESIGN.md` — four documents) and dormant `AuditLog`/`EventPublisher`/
`NotificationProvider` infrastructure (named in most of the same set) — are each narrower in
consequence: the range-query gap is a query-ergonomics question with a manual workaround already
in use everywhere (§6), and the dormant-infrastructure gap is explicitly *optional*, not blocking,
per every document that raises it (`APPROVAL_WORKFLOW_DESIGN.md` §14.3: *"not recommended as part
of a first implementation... no consumer exists"*).

**Direct model evidence, confirmed by full read:**

- `models/user.py:15-24` — `User` columns: `email`, `password_hash`, `full_name`, `is_active`,
  `roles` (many-to-many via `user_roles`). No FK to `hr_employees`, no `hr_employee_id` column of
  any kind.
- `models/hr_employee.py:20-101` — `HrEmployee` columns include nine FKs (`organization_id`,
  `department_id`, `position_id`, `team_id`, `location_id`, `manager_id`, `job_grade_id`,
  `employment_type_id`, `employment_status_id`, `shift_id` — ten, including the self-referential
  one) and a docstring (lines 20-33) documenting the deliberate ownership boundary of every other
  reference this entity holds. No `user_id` column, and no mention of `User` anywhere in the class
  or its docstring.
- `alembic/versions/` (30 files, confirmed by directory listing) — grepped for `user_id` and
  `hr_employee_id`: two matches, both unrelated (`create_audit_logs_table` — `AuditLog.user_id`,
  the generic actor column; `create_roles_table` — the `user_roles` join table for RBAC). **No
  migration anywhere adds a column linking `users` and `hr_employees`.**

**Authentication and authorization infrastructure, confirmed by full read — solid up to the exact
point this gap blocks:**

- `dependencies/auth.py:27-47` — `get_current_user`/`CurrentUser` resolves a bearer token to a
  `User` row via `AuthService`, binds `user.id` into `core/request_context.py`'s request-scoped
  identity. This chain is complete and used by every router in the codebase (`CurrentUser` is a
  required dependency on every route, per every prior discovery's confirmation).
- `dependencies/rbac.py:18-33` — `RequireRole(role_name)` checks `service.user_has_role(current_user.id,
  role_name)` and 403s otherwise. This is *role*-based only — it has no concept of "is this `User`
  the requester's manager" or any other org-chart-derived relationship, because nothing links
  `User` to a position in the org chart (`HrEmployee.manager_id`) at all.
- **`RequireRole` has exactly one call site in the entire codebase**: `RequireAdmin` in
  `api/roles.py`, gating role-management endpoints themselves (confirmed by fresh grep, matching
  every prior discovery's identical finding). No HR, Attendance, Leave, Overtime, Timesheet, or
  Reconciliation endpoint is role-gated.
- `main.py:87-89` — a `TODO` comment: *"Locations (and location types) are authenticated-only for
  now. Once the platform defines administrative roles for master data, gate these routes with
  `RequireRole(...)`..."* — direct evidence that role-gating beyond authentication is a known,
  explicitly deferred intention elsewhere in the codebase too, not unique to this gap, but
  confirming the platform has no working authorization-beyond-authentication story anywhere yet.
- `HrEmployeeService` (`services/hr_employee.py`, full read) validates nine cross-entity references
  per `create`/`update` call (organization/department/position/team/location/manager/job_grade/
  employment_type/employment_status — lines 122-178, 209-308) but has and needs no concept of
  `User` anywhere in its logic — confirming the absence is total, not partial.

**Concrete, already-shipped consequence of the gap, quoted directly:** `APPROVAL_WORKFLOW_DESIGN.md`
§13 (Risks): *"Even if `RequireRole`/a new `approver` role is wired up, without resolving [the
`User`↔`HrEmployee` gap], the best available authorization is 'any `User` holding the `approver`
role can approve *any* employee's request' — a flat, unscoped permission, not 'this employee's
manager can approve this employee's request.'"* `ApprovalService` — built in PR-047, the component
every reviewed router now calls for leave/overtime/timesheet approval — ships today with **no
authorization check beyond authentication at all** (confirmed: `services/approval.py`, full read,
contains no role or ownership check anywhere in `_apply_decision`/`_complete_decision` or any of
the six public methods). This is not a hypothetical future risk; it is the current, shipped state
of the most recently built HR feature in this repository.

**Roadmap grounding, checked directly**: `docs/product/06_PRODUCT_ROADMAP.md` names no `User`/
`HrEmployee` linkage explicitly, but `docs/product/02_PRODUCT_SCOPE.md` §1 ("Platform Foundation")
lists `Authentication`, `Authorization`, `Role & Permission`, and `User Management` as in-scope
foundation modules, and §3 ("Workforce Management") lists a role hierarchy — `Supervisor`, `Area
Manager`, `Regional Manager` — implying manager-scoped authorization is a real, named product
concept (`03_TARGET_CUSTOMER.md` describes `National Sales Manager`/`Regional Manager`/`Area
Manager` personas by name), even though no product document spells out the specific `User`↔
`HrEmployee` mechanism. This is weaker grounding than a literal roadmap line item, on par with
every prior discovery's own roadmap-silence finding for its subject, but it does establish that
role-scoped, manager-aware authorization is a named product concern, not an invented one.

---

## 3. Architectural Analysis

**What kind of gap is this?** Unlike PR-048 (Attendance Reconciliation) and PR-049 (Leave Balance
Synchronization), this is not a missing *behavior* spanning existing aggregates — it is a missing
*relationship* between two existing, independently complete aggregates (`User`, the
authentication/authorization root, and `HrEmployee`, the HR master-data root). Both aggregates are
fully built: `User` has a working repository, service, schemas, and API surface
(`repositories/user.py`, `services/auth.py`, `api/auth.py`); `HrEmployee` likewise
(`repositories/hr_employee.py`, `services/hr_employee.py`, `schemas/hr_employee.py`,
`api/hr_employees.py`). Neither is incomplete on its own terms. The gap is structural: nothing
connects the identity a request authenticates as (`User`) to the identity the HR domain reasons
about (`HrEmployee`).

**Why this is architecturally prior to (not competing with) Leave Balance Synchronization and
further Reconciliation work.** Both of those features already have a concrete, evidenced
next-question — a **business-rule** question (day-count semantics, row selection, day-result
vocabulary) that this discovery is explicitly instructed not to invent an answer to. The
User↔HrEmployee gap has no such block: the question it raises ("which table gets the FK, in which
direction") is answerable by the same kind of repository-evidence reasoning this discovery
methodology already uses successfully (§4, §5) — it does not require guessing a business rule, only
applying this codebase's own established schema-evolution precedent (§4). Resolving it also does
not compete with either feature: it does not touch `LeaveBalance`, `LeaveRequest`,
`AttendanceEvent`, or `ReconciliationService` at all (§6, Future Compatibility) — it is additive to
`User` and/or `HrEmployee` only.

**Why this is the same evidentiary shape the prior three discoveries used to select their own
topics.** PR-048 §1 and PR-049 §1 both justified their topic choice on "a gap named, in the same
words, by every module whose boundary excludes it." This gap meets that bar more strongly than
either of those did at the time they were chosen: PR-048 found the reconciliation gap named in four
documents before building its case; PR-049 found its gap named in five places. This document finds
the `User`↔`HrEmployee` gap named in **eight** — every discovery document that exists in this
repository, without exception, including PR-048 and PR-049 themselves.

**Consequence already realized, not merely anticipated.** Every previous discovery treated this gap
as a *future* blocker on a *future* feature (self-service attendance clock-in, self-service leave
submission). PR-047 changed that: `ApprovalService` is built and wired into three live endpoints per
entity (`POST .../approve`, `POST .../reject` on `leave_requests`, `overtime_requests`,
`timesheets`), and it authorizes nothing beyond "is this a valid token" (§2). The gap is no longer
only blocking hypothetical self-service reads — it is the reason a shipped, callable write endpoint
has no meaningful access control today.

---

## 4. Candidate Implementations

Enumerated for cost/precedent analysis, per the same method prior discovery documents used —
**not a narrowing of the design space by this section alone** (see §7 for what evidence actually
resolves).

### Option A — `hr_employees.user_id` (nullable FK to `users.id`)

**Supporting evidence**: matches this codebase's strongest, most literal precedent exactly. Five
existing migrations (`b3f7a1c9d2e4_add_job_grade_id...`, `2b2c0e23e9bc_add_employment_type_id...`,
`2fe575272108_add_employment_status_id...`, plus the shift/overtime-adjacent columns) each add a
single FK column to `hr_employees` in its own standalone migration, chained off the prior head —
confirmed by direct read of `2b2c0e23e9bc_add_employment_type_id_to_hr_employees.py` (lines 22-35):
`op.add_column` + `op.create_foreign_key(..., ondelete="RESTRICT")` + `op.create_index`, nothing
else. `hr_employees` is also the table every other cross-entity reference in the HR domain already
points *at* (`LeaveRequest.employee_id`, `AttendanceEvent.employee_id`,
`OvertimeRequest.employee_id`, `Timesheet.employee_id`, `LeaveBalance.employee_id` — all FK into
`hr_employees`, none into `users`), so a consumer already holding an `HrEmployee` id can resolve to
a `User` without an extra join through a different table.

**Contradicting evidence**: `HrEmployee` already carries ten FK/relationship columns (§2); adding
an eleventh continues, rather than introduces, an existing pattern, so this is not itself
contradicting evidence — no repository evidence weighs against this option specifically, beyond the
general observation (§7) that evidence does not select between this and Option B.

### Option B — `users.hr_employee_id` (nullable FK to `hr_employees.id`)

**Supporting evidence**: `User` is the row every request already resolves to first
(`CurrentUser`, §2) — placing the FK here means every authenticated request can resolve its
`HrEmployee` with zero extra lookups beyond what `CurrentUser` already performs, rather than
requiring a reverse query (`HrEmployeeRepository.get_by(user_id=...)`, a method that does not exist
today on any repository — `get_by` is a generic `BaseRepository` method (`repositories/base.py`)
that would work unmodified, but no existing service calls it this way for a 1:1 identity lookup).

**Contradicting evidence**: no existing precedent for adding a column to `users` at all —
`models/user.py` has never been touched by a migration beyond its `create_table`
(`a8cea7343ee6_create_users_table.py`, confirmed by the alembic file listing: no
`..._add_..._to_users.py`-shaped migration exists anywhere), whereas `hr_employees` has five such
precedents (Option A). This does not rule the option out — it means Option A has direct precedent
this option does not.

### Option C — A separate join/mapping table (`user_hr_employee_links` or similar)

**Supporting evidence**: would support one-`User`-to-many-`HrEmployee` or
many-`User`-to-one-`HrEmployee` cardinalities without a uniqueness constraint on either base table,
if that flexibility is ever needed (§8, Ambiguity 3).

**Contradicting evidence**: no join-table precedent exists anywhere in this codebase for a
1:1-or-near-1:1 relationship — the one existing join table, `user_roles`
(`models/user_role.py`), models a genuine many-to-many (`Role` is reusable across many `User`s,
and vice versa), a structurally different cardinality question than "which single employee record
does this single login correspond to." Introducing a new table shape for a relationship every other
signal in this codebase (single active account per employee, standard HR-identity modeling) suggests
is 1:1 or nullable-1:1 would be the first table in this codebase modeling a relationship more
loosely than the data plausibly requires, with no second concrete use case (multiple accounts per
employee, or one account spanning employees) to justify the extra structure — the same
premature-generalization argument every prior discovery has used to reject over-general shapes
(`LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` §8 Option D, `ATTENDANCE_RECONCILIATION_DESIGN.md` §7
Option C).

### Option D — No schema change; resolve identity at the application layer only (e.g. matching on `email`)

**Supporting evidence**: `HrEmployee.email` (`models/hr_employee.py:57`) and `User.email`
(`models/user.py:19`) are both unique, populated `String` columns already
(`UniqueConstraint("email", ...)` on both tables, confirmed §2) — an application-layer lookup
(`HrEmployeeRepository.get_by_email(current_user.email)`) is mechanically possible today with zero
migration.

**Contradicting evidence**: this is an implicit, unenforced coupling — nothing prevents a `User`
and an `HrEmployee` from having different emails, or either email from changing independently, and
no FK/constraint would ever catch a mismatch. It also does not match how every other identity
relationship in this codebase is modeled: every other cross-entity reference in the HR domain is an
explicit FK, never an implicit match on a non-key field. This option would be the first
identity-resolution mechanism in the codebase not backed by a foreign key.

**No option above is selected by this section.** Each is evaluated on its own merits in §7, where
repository evidence is applied to narrow, but not fully resolve, the field.

---

## 5. Architectural Constraints

What current repository evidence establishes about *any* eventual implementation, regardless of
which option (§4) is ultimately chosen:

- **Must be a single, additive schema change** (a new nullable column, or new nullable-FK-bearing
  table), never a retroactive edit to `create_users_table` or `create_hr_employees_table` — every
  migration in this codebase, without exception, is additive (confirmed by full `alembic/versions/`
  listing; no migration edits a prior migration's `create_table` body).
- **Must be nullable, or must tolerate rows on both sides having no counterpart.** `User` rows exist
  today (e.g. any created via `scripts/create_admin.py`, confirmed by file listing) with no
  corresponding `HrEmployee` — an administrative account is a legitimate `User` with no HR master
  data. Symmetrically, `HrEmployee` rows can exist with no corresponding `User` — HR master data can
  be created (`HrEmployeeService.create`, `services/hr_employee.py:122-178`) with no dependency on
  any `User` row at all, and nothing in the reviewed codebase suggests every `HrEmployee` needs a
  login. A `NOT NULL` FK either direction would be a data-integrity requirement contradicted by how
  both aggregates are actually created today.
- **Whichever table gains the column, the pattern is `ForeignKey(..., ondelete=...)` plus an index**,
  matching every one of the five precedented `hr_employees` column-addition migrations (§4, Option
  A) — no repository evidence supports a different mechanical shape (e.g. a nullable UUID with no FK
  constraint) for a reference this codebase would otherwise always enforce at the database level.
- **The `ondelete` behavior is not determined by this discovery.** Every existing FK *from*
  `hr_employees` uses `RESTRICT` (§2, `models/hr_employee.py` docstring: *"this is master data, so
  deleting any of those while an HrEmployee still references it must fail at the database level"*).
  Whether a `User`↔`HrEmployee` link should behave the same way, or should tolerate one side being
  deleted (e.g. deactivating a `User` account without deleting HR history, or vice versa), is not
  settled by precedent — `RESTRICT` is what every analogous FK in this codebase already does, but
  none of those FKs represents an identity link the way this one would, so the analogy is partial
  (§8, Ambiguity 5).
- **Resolving the `User` → `HrEmployee` lookup belongs in a repository method, not a new
  orchestration service.** Unlike PR-048/PR-049's gaps, this is a same-table, single-FK read once
  the column exists — squarely inside the existing `BaseRepository[ModelT]` single-model contract
  (`repositories/base.py:14-19`), via a narrow `get_by(...)`-shaped method, exactly like every other
  `get_by_x` helper already on these repositories (`HrEmployeeRepository.get_by_email`,
  `get_by_employee_number`, confirmed in `services/hr_employee.py:170-172, 294-301` call sites).
  No repository evidence supports building a new service category for this, unlike Reconciliation
  or Leave Balance Synchronization, both of which needed cross-repository composition this does
  not.
- **No repository evidence determines what consumes the link once it exists** (an
  authorization dependency gating `ApprovalService`; a self-service filter on Attendance/Leave/
  Timesheet submission; a manager-scoped Reconciliation view) — those are downstream features this
  discovery does not scope or recommend building (§8).

---

## 6. Alternatives Considered

**Continuing Leave Balance Synchronization (PR-049) into its next step.** Rejected as this
discovery's topic. PR-049's own architecture decision is already built (`services/approval.py`,
confirmed §1); its only remaining open items are business-rule ambiguities (period-year derivation,
row selection, day-count semantics, overlap handling, reversal semantics — PR-049 §12.2–§12.7) that
no repository evidence resolves and that this discovery is explicitly instructed not to invent
answers to. There is no *architectural* question left in that thread for a discovery document to
usefully analyze; what remains is a product-input request, not a code-evidence question.

**Continuing Attendance Reconciliation (PR-048) — e.g., adding a self-service or manager-scoped
view.** Considered and rejected as redundant with this document's own topic: PR-048 §11 itself
names the `User`↔`HrEmployee` gap as the specific blocker on exactly this extension (§2, citation
table). Pursuing it as a separate topic would mean re-discovering the same root cause this document
already establishes as the higher-priority, more-consistently-evidenced gap.

**Wiring `AuditLog`/`EventPublisher`/`NotificationProvider` into the HR domain.** Real, confirmed
infrastructure (`services/audit_log.py`, `events/base.py`, `notifications/base.py`), confirmed
unused by any HR service in every discovery through PR-049. Rejected as this document's topic
because every document that raises it also explicitly marks it *optional*, not blocking
(`APPROVAL_WORKFLOW_DESIGN.md` §14.3, quoted §2) — unlike the `User`↔`HrEmployee` gap, no shipped
feature is currently *broken* or *unauthorized* for lack of it. Consequence, not just count of
mentions, is the deciding factor between these two candidates.

**Generalizing `BaseRepository` date-range (`BETWEEN`) query support.** Named in four discovery
documents (`HOLIDAY_CALENDAR_DESIGN.md`, `LEAVE_DESIGN.md`, `TIMESHEET_DESIGN.md`,
`ATTENDANCE_RECONCILIATION_DESIGN.md`) as a repeated, unresolved capability gap. Rejected as this
document's topic: every one of those four documents found a same-table, per-repository workaround
sufficient for its own needs (each repository grows its own narrow range helper), so this gap is a
query-ergonomics improvement with a working substitute already in place everywhere it has come up —
a smaller-consequence gap than one that leaves a shipped write endpoint with no authorization model.

**Optimistic concurrency (`VersionMixin`) and soft-delete enforcement.** Both confirmed
codebase-wide infrastructure gaps (`VersionMixin.version`/`SoftDeleteMixin.is_deleted` exist on
every `BaseEntity` per `db/mixins.py` but are never read by `BaseRepository.update()`/`delete()`),
flagged in PR-048 §7/§11 and PR-049 §7/§11. Rejected as this document's topic: both are real, but
narrower in *how many* discovery documents independently converge on them (two, not eight) and
neither currently blocks a shipped feature's basic correctness the way the authorization gap blocks
`ApprovalService`'s access control today.

**Roadmap Phase 3/4 modules** (`Territory`, `Region`, `Area`, `Store`, `Customer`, `Mission`,
`Visit`, `Survey`, `GPS`, `Photo`, per `docs/product/06_PRODUCT_ROADMAP.md`). Considered and set
aside for the same reason `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` §1 already set them aside: none
has any existing model, repository, service, schema, or prior discovery document to build evidence
from. Choosing one would require inventing an aggregate shape from a one-line roadmap module name,
which repository-evidence-only discovery cannot do.

---

## 7. Recommendation

**Repository evidence supports treating the `User`↔`HrEmployee` identity linkage as the
next-highest-priority architectural gap**, on the strength of being named by every prior discovery
document in this repository (eight of eight) and being the confirmed, current cause of a shipped
feature (`ApprovalService`) having no authorization model beyond authentication. As with every
recommendation in this codebase's discovery methodology, the statements below describe what current
evidence supports building toward, not a claim that any excluded shape is impossible:

- Current repository evidence supports the eventual link being a **single nullable FK column**, not
  a new join/mapping table (§4 Option C) — no relationship in this codebase's HR domain is modeled
  via a join table except the genuinely many-to-many `user_roles`, and no second concrete use case
  motivates that structure here (§4).
- Current repository evidence supports the eventual link being **schema-backed (a real FK
  constraint)**, not an implicit application-layer match on `email` (§4 Option D) — every other
  identity/reference relationship in this codebase's HR domain is FK-backed, and an unenforced
  email-match would be a first, weaker exception to that pattern.
- Current repository evidence supports resolving the lookup via a **narrow repository method**
  (`get_by(user_id=...)` or `get_by(hr_employee_id=...)`, depending on direction), consistent with
  every existing `get_by_x` helper already on these repositories — not a new orchestration service,
  unlike PR-048/PR-049's gaps.
- Current repository evidence supports adding the column via a **standalone migration chained off
  the current head**, matching the five-migration precedent for incremental `hr_employees` columns.

**Repository evidence is insufficient to determine the FK's direction, cardinality, or
`ondelete` behavior.** Option A (`hr_employees.user_id`) has direct, five-times-repeated migration
precedent; Option B (`users.hr_employee_id`) has no migration precedent for touching `users` at
all, but a stronger fit with how `CurrentUser` resolution already works. Neither is selected here —
`APPROVAL_WORKFLOW_DESIGN.md` §11 already reached the identical conclusion on this same question
(*"which of the three schema shapes... is correct cannot be determined from the codebase,"* lines
599-607) and no evidence has appeared since to break that tie. **Choosing the direction, the
`ondelete` behavior, and the authorization model the link ultimately feeds (role-based,
`manager_id`-based, or both) are implementation-PR decisions**, to be made with the benefit of the
constraints in §5, not conclusions this discovery reaches.

**This discovery does not recommend building the downstream consumer** (wiring the resulting link
into `ApprovalService`'s authorization, or into a self-service Attendance/Leave/Timesheet endpoint,
or into a manager-scoped Reconciliation view) — those are separate, larger decisions that
presuppose the schema question this document addresses, and each carries its own unresolved
business-rule questions (§8) beyond what this document's schema-level scope covers.

---

## 8. Remaining Ambiguities

Per instructions, listed, not guessed at:

1. **FK direction.** `hr_employees.user_id` (precedented migration shape, §4 Option A) vs.
   `users.hr_employee_id` (matches `CurrentUser` resolution order, §4 Option B). Not decidable from
   the codebase (§7, restating `APPROVAL_WORKFLOW_DESIGN.md` §11's identical unresolved finding).
2. **`ondelete` behavior.** Every existing FK from `hr_employees` is `RESTRICT`, but none of them
   represents an identity link the way this one would — whether deactivating a `User` account
   should be allowed to happen independently of the `HrEmployee` record's lifecycle (and vice versa)
   is a product/security decision, not a schema-precedent one (§5).
3. **Cardinality.** Whether the relationship is strictly 1:1, or whether a scenario exists (e.g. a
   contractor with no `HrEmployee` record but a `User` login, or a shared/service account) that
   would require a looser cardinality — not addressed by any product document reviewed.
4. **Authorization model built on top of the link.** Role-based (`RequireRole`, extended with a new
   role vocabulary), org-chart-based (`HrEmployee.manager_id`-aware, "is this `User`'s `HrEmployee`
   the manager of the target `HrEmployee`"), or both — inherited unresolved from
   `APPROVAL_WORKFLOW_DESIGN.md` §9 Ambiguity 3, still open.
5. **Who is responsible for populating the link.** Whether `HrEmployeeService.create` should gain an
   optional `user_id`/account-provisioning step, whether it is a separate manual admin action, or
   whether user accounts are created *from* an `HrEmployee` record (reversing today's
   `scripts/create_admin.py`-only account-creation path) — not decidable from the repository.
6. **Whether this unblocks a specific next feature** (self-service submission, manager-scoped
   approval, self-service reconciliation) as an immediate follow-on, or is scoped as pure schema/
   infrastructure work with consumers deferred to later, separate PRs — a product-sequencing
   decision, not an architectural one.
7. **Product intent.** No product document names "`User`↔`HrEmployee` linkage," "account
   provisioning," or an equivalent term explicitly; support is inferred from
   `02_PRODUCT_SCOPE.md`'s named `Authorization`/`Role & Permission` foundation modules and named
   manager personas (§2), not from a literal roadmap line item — weaker grounding than a named
   feature, consistent with every prior discovery's own roadmap-silence finding for its own subject.

**Stopping here per instructions.** No model, migration, repository method, service, or API route
has been added or modified. Awaiting direction on the items above — particularly the FK-direction
and authorization-model questions (Ambiguities 1 and 4), without which no implementation can begin
— before proceeding.

---

# PR-050 (Implementation) — Step 1: Architecture Decision

Status: **Architecture decision only. No code, no migrations, no tests. Awaiting review.**

This section resolves §8's Ambiguity 1 (FK direction) and the mechanical questions in §5/§7 that
the discovery left to an implementation PR. It does not reopen the discovery: the four conclusions
already established there — a single nullable foreign key, schema-backed identity linkage, a
standalone migration, repository-owned persistence with service-owned interpretation — are treated
as fixed inputs, not re-derived. It does not resolve any business-rule ambiguity (Ambiguities 2–7);
those remain open regardless of this decision.

## 1. Executive Summary

**Chosen direction: `hr_employees.user_id`** (nullable FK to `users.id`, `ON DELETE SET NULL`,
indexed), added in one standalone migration chained off the current head
(`f4a1c9e6b2d7`). Persistence lives entirely in `HrEmployeeRepository`/`models/hr_employee.py`; a
single new same-table repository method (`get_by_user_id`) provides the User→HrEmployee lookup
direction. Interpretation (existence-check validation on write) is added to the existing
`HrEmployeeService.create`/`update` methods, mirroring the nine FK-existence checks already there —
no new service, no new service method, no dedicated "linking" endpoint. Linking is **explicit**,
via the existing `POST /hr/employees` / `PUT /hr/employees/{id}` surface, once `user_id` is added
to `EmployeeCreate`/`EmployeeUpdate`. No DI change. No authorization is implemented; the column and
lookup method are the only hook left for future authorization work.

## 2. Chosen Architecture

**Foreign key direction: Option A — `hr_employees.user_id`.**

- `models/hr_employee.py` gains `user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)`, plus a matching `Index("ix_hr_employees_user_id", "user_id")` in `__table_args__` and a `user: Mapped[User | None] = relationship()` attribute, mirroring the existing `manager`/`organization`/`department`/`position`/`team`/`location` relationship attributes already on the class.
- `models/user.py` is **not** modified.

**Migration strategy:**

- **Nullable**: yes (already established by the discovery, §5). `HrEmployee` rows are created today with zero dependency on any `User` row (`HrEmployeeService.create`, confirmed by full read), and `User` rows are created today with zero dependency on any `HrEmployee` row (`scripts/create_admin.py`) — a `NOT NULL` constraint either direction would contradict both existing creation paths.
- **`ON DELETE SET NULL`**, not `RESTRICT`. Every existing FK *within* the HR master-data domain (`organization_id`, `department_id`, `position_id`, `team_id`, `location_id`, `manager_id`, `job_grade_id`, `employment_type_id`, `employment_status_id`, `shift_id`, and every other domain table's `employee_id → hr_employees.id`) uses `RESTRICT` — but this codebase already draws a separate, distinct line for FKs that reference `users.id` specifically to record an *associated actor*, not *structural master data*: `AuditLog.user_id → users.id` uses `SET NULL` (`create_audit_logs_table.py:51`), and `Task.assignee_id → employees.id` (a structurally identical "optional associative reference," not a structural dependency) also uses `SET NULL` (`92b9eb08becc:168`). `hr_employees.user_id` is the same shape as `AuditLog.user_id` — a reference *to* `users.id` recording an association, not a piece of the referencing row's own structural identity — so it follows that precedent, not the `RESTRICT` precedent, which is reserved for references *within* HR master data.
- **No unique constraint on `user_id`.** The discovery (Ambiguity 3) left cardinality open — whether one `User` could ever legitimately be associated with more than one `HrEmployee` row (e.g. a rehire, a multi-entity assignment) is a business question this decision does not answer. A plain (non-unique) index is added for lookup performance; a unique constraint is deferred rather than assumed, since it is easy to add later and hard to remove without a product decision to justify relaxing it. **Superseded in part by Step 2 below**: this bullet is correct that cardinality is not decided here, but the repository-method consequence of leaving it undecided (§ Repository impact, next) was not fully worked through at the time this bullet was written — see Step 2, §2.3.
- **Backfill: none.** No existing data anywhere in this codebase establishes a `User`↔`HrEmployee` correspondence (no shared identifier, no prior mapping table, confirmed absent in the discovery §2) — there is nothing to backfill from. The column is added and every existing row simply gets `NULL`.
- **Upgrade path**: one standalone migration, chained off `f4a1c9e6b2d7` (current head, unchanged since PR-047; PR-048 and PR-049 added no migrations), following the exact three-step shape of the five precedent `hr_employees` column-addition migrations (e.g. `2b2c0e23e9bc_add_employment_type_id_to_hr_employees.py:22-35`): `op.add_column("hr_employees", sa.Column("user_id", sa.Uuid(), nullable=True))`, `op.create_foreign_key("fk_hr_employees_user_id_users", "hr_employees", "users", ["user_id"], ["id"], ondelete="SET NULL")`, `op.create_index("ix_hr_employees_user_id", "hr_employees", ["user_id"], unique=False)`.
- **Downgrade path**: the mirror-image of every precedent downgrade (e.g. `2b2c0e23e9bc:38-44`): `op.drop_index`, `op.drop_constraint` (the FK), `op.drop_column` — no data-loss concern beyond the `user_id` values themselves, since nothing else in the schema references this column.

**Repository impact:**

- **New method**: `HrEmployeeRepository.get_by_user_id(user_id: uuid.UUID) -> HrEmployee | None`, a one-line call to the existing generic `self.get_by(HrEmployee.user_id, user_id)` — identical in shape to `get_by_email`/`get_by_employee_number` already on the same class (`repositories/hr_employee.py:35-39`). No new query logic, no filtering/business logic — pure persistence-layer symmetry with what already exists. **Correction, Step 2 below**: this method signature is only safe if `user_id` is unique; see Step 2, §2.3/§3 — this bullet is retained for the historical record but is no longer the final shape.
- **Ownership**: `HrEmployeeRepository` owns the column and the lookup, because the column lives on `hr_employees` — consistent with `BaseRepository[ModelT]`'s single-model-per-repository contract (`repositories/base.py:14-19`), which this decision does not touch.
- **`UserRepository` is unmodified.** No new method is needed there: `UserRepository`/`BaseRepository` already expose a generic `exists(id)` (used identically by every other FK-existence check in `HrEmployeeService`, e.g. `OrganizationRepository(uow.session).exists(...)`, `services/hr_employee.py:126`), which is sufficient for validating a supplied `user_id` refers to a real `User` row.
- **Lookup directions**: User → HrEmployee is served by the new `get_by_user_id` method. HrEmployee → User needs no repository method at all — once an `HrEmployee` row is loaded, `employee.user_id` (and, if the relationship is eager/lazy-loaded, `employee.user`) is already on the row, the same way `employee.manager_id`/`employee.department_id` are read directly today with no dedicated `get_manager`-shaped method anywhere in the codebase.

**Service impact:**

- **`HrEmployeeService` owns interpretation of the linkage** — it is the service that already owns every other FK on this entity, and it already generically applies whatever fields the `EmployeeCreate`/`EmployeeUpdate` schema exposes via `**data.model_dump()`/`**values` (`services/hr_employee.py:175, 303`). No new method is required: `create`/`update` need exactly one addition each, an existence check on `user_id` when supplied, structurally identical to (and inserted alongside) the nine existence checks these methods already perform for `organization_id`/`department_id`/`position_id`/`team_id`/`location_id`/`job_grade_id`/`employment_type_id`/`employment_status_id`/`shift_id`/`manager_id`. A new `UserNotFoundError` exception is added to the module's existing flat list of local, per-reference not-found exceptions (`services/hr_employee.py:22-91`), matching the existing naming/placement convention exactly.
- **No dedicated service.** Unlike PR-048/PR-049's gaps (which needed multi-repository read or write composition with no existing precedent), this is a single-table column addition consumed through the same single-repository, single-entity CRUD shape `HrEmployeeService` already has. There is nothing here that resembles the "no owned entity, multi-repository" orchestration category `ApprovalService`/`ReconciliationService` established — introducing a new service for it would be inventing structure repository evidence does not call for.
- **`AuthService`/`UserService` do not change**, and no `UserService` needs to be created. Confirmed by grep: no `services/user.py` exists anywhere in the codebase today — `User` has no CRUD service at all, only `AuthService.authenticate`/`login`/`get_current_user` (`services/auth.py:32-53`) and the standalone `scripts/create_admin.py`. Placing the FK on `users` (Option B) would have required inventing a `UserService` from nothing just to expose the link mutation — a materially larger new-precedent cost than the one addition `HrEmployeeService` needs. This is additional, direct evidence supporting Option A beyond the migration-precedent argument.

**API impact:**

- **No new endpoint.** `POST /hr/employees` and `PUT /hr/employees/{id}` already exist and already accept/return every other field on `HrEmployee` via `EmployeeCreate`/`EmployeeUpdate`/`EmployeeResponse` (`schemas/hr_employee.py`). Adding `user_id: uuid.UUID | None = None` to all three schemas is the only change needed for the existing CRUD surface to carry the new column, matching the reasoning the discovery's own precedents (`LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` §6, `ATTENDANCE_RECONCILIATION_DESIGN.md` §9) already used: no new route when an existing CRUD surface already covers the mutation.
- **Existing CRUD endpoints change** only in schema shape (one additional optional field, in and out) — no new route, no new HTTP method, no change to any other router.
- **Linking is explicit, not automatic.** Setting `user_id` is a caller-supplied value on an existing write, exactly like every other FK on this entity — there is no auto-matching (e.g. on `email`, which the discovery's §4 Option D already found unsupported by any existing precedent) and no auto-provisioning. This is a deliberate implementation choice consistent with "do not invent product behavior": the mechanism does not decide *who* should be linked to *what*, it only provides the field through which an already-existing write path can record that decision once made elsewhere (by whatever process — admin action, a future onboarding flow — the product eventually specifies).

**Dependency Injection**: **no changes required.** `get_hr_employee_service()` (existing factory,
unchanged signature) continues to construct `HrEmployeeService` exactly as today; no new
`Depends()`, no new router, no new factory function, no change to `main.py`'s router registration
list. This follows directly from "no dedicated service" above — DI changes only when a new
injectable component is introduced, and none is here.

**Authorization impact**: **not implemented, as instructed.** The column
(`HrEmployee.user_id`) and the lookup method (`HrEmployeeRepository.get_by_user_id`) are the
entirety of what this decision exposes as a hook for future authorization work — e.g., a future
`dependencies/auth.py`-style `CurrentEmployee` dependency could resolve `CurrentUser.id →
HrEmployeeRepository.get_by_user_id(...)` without any further schema change. No such dependency is
built here. No change is made to `dependencies/rbac.py`, `RequireRole`, `ApprovalService`, or any
route's authorization surface. This decision only makes the *lookup* possible; it does not decide
*what* consumes it or *when*.

## 3. Alternatives Considered

1. **`users.hr_employee_id`** (§4 Option B of the discovery). Rejected. No migration in this
   codebase has ever added a column to `users` (confirmed by the discovery's full `alembic/`
   grep) — this would be a first, against five direct precedents for the chosen option. It would
   also require inventing a `UserService` to own the mutation, since none exists today (`Service
   impact`, above) — a materially larger new-precedent cost for the same outcome. Its one advantage
   (resolving `HrEmployee` from `CurrentUser` without an extra query) is not a decisive advantage in
   this codebase: no service anywhere avoids an extra repository call for a single-row lookup by
   denormalizing (no caching, no eager-join optimization exists anywhere in the reviewed codebase),
   so the "saves a query" argument is not grounded in an existing pattern the way the migration and
   service-ownership arguments are.
2. **A join/mapping table** (§4 Option C of the discovery). Rejected on the same grounds the
   discovery already found: the only existing join table in this codebase (`user_roles`) models a
   genuine many-to-many, a different cardinality question than this one, and no second concrete use
   case justifies the extra structure now.
3. **Implicit email matching, no schema change** (§4 Option D of the discovery). Rejected: would be
   the first identity-resolution mechanism in the codebase not backed by an FK, and both `email`
   columns can diverge over time with nothing to catch it.
4. **`RESTRICT` instead of `SET NULL`.** Considered because it is the majority pattern for FKs on
   `hr_employees`. Rejected once the FK's *target* is examined rather than its *source table*: every
   `RESTRICT` FK on `hr_employees` references another piece of HR master data (a `Department`,
   `Position`, another `HrEmployee`, etc.) whose loss would leave the referencing row structurally
   incomplete. `user_id` instead references `users.id` — and the one other FK in this codebase that
   also targets `users.id` from a non-`users` table (`AuditLog.user_id`) already uses `SET NULL`,
   confirming that the deciding factor in this codebase's own precedent is the FK's target, not its
   source table. `RESTRICT` would also mean a `User` could never be removed while any `HrEmployee`
   remains linked to it — a stronger constraint than any product document reviewed calls for, and
   inconsistent with the "optional association, not structural dependency" framing the discovery
   itself used for this relationship (discovery §5: *"an `HrEmployee` rows can exist with no
   corresponding `User`"*).
5. **A unique constraint on `user_id` now.** Considered, to enforce a clean 1:1 mapping from the
   start. Rejected: the discovery (Ambiguity 3) explicitly left cardinality open, and adding a
   constraint now would decide a business rule ("no two employee records may ever share one login")
   this decision has no product basis for. Deferred, not rejected outright — see §7.
6. **A dedicated "link account" endpoint** (e.g. `POST /hr/employees/{id}/link-user`). Considered as
   a way to make linking a distinct, auditable action rather than a generic field update. Rejected
   for this decision: it would be the first single-purpose "mutate one field" action-style endpoint
   on `HrEmployee` (every existing mutation on this entity goes through generic `create`/`update`),
   and nothing in the discovery or this decision's scope establishes that linking needs to be a
   distinct business event rather than an ordinary field edit — that framing itself is closer to
   authorization/workflow design than to the schema-and-plumbing question this document answers.

## 4. Reasons

**The deciding factor across every sub-decision above is "fewest new precedents," the same
standard `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` §C used to choose its own implementation.**
Option A (`hr_employees.user_id`, `SET NULL`, generic `create`/`update` field, no new service)
introduces exactly one new precedent: a `hr_employees` FK that targets `users.id` instead of
another HR master-data table. Every other piece of its shape — the migration mechanics, the
existence-check style, the repository method style, the schema field style — is a direct,
literal continuation of a pattern already used five, nine, or more times elsewhere in this
codebase. Option B would have introduced at least two new precedents (a `users`-table migration,
and a `UserService` where none exists) for no offsetting benefit the codebase's own patterns
value. The join-table and implicit-matching alternatives were rejected in the discovery itself on
identical no-second-use-case and no-FK-precedent grounds, restated rather than re-litigated here.

**`SET NULL` is not a deviation from precedent — `RESTRICT` would have been.** The
apparent majority (`RESTRICT` on nine of `hr_employees`'s existing ten FKs) is not evidence for
`RESTRICT` here once precedent is read at the right grain: this codebase already conditions
`ondelete` behavior on what a FK's *target* represents (structural master data → `RESTRICT`;
`users.id` specifically → `SET NULL`, per `AuditLog.user_id`), not on which table happens to hold
the FK. Applying `RESTRICT` here would have been the actual departure from precedent, not `SET
NULL`.

**Nothing here presupposes the authorization model, manager approval, or self-service submission
the discovery flagged as separately open (Ambiguities 4 and 6).** The column and the
`get_by_user_id` lookup are consumable by any of those future directions equally — role-based
authorization, org-chart-based authorization, self-service Attendance/Leave/Timesheet submission,
or a manager-scoped Reconciliation view would each start from the same `CurrentUser.id →
HrEmployeeRepository.get_by_user_id(...)` call. This decision deliberately stops at making that
call possible, not at deciding which future feature makes it first.

## 5. Files That Would Be Created

- `alembic/versions/<new_revision>_add_user_id_to_hr_employees.py` — the standalone migration
  described above, chained off `f4a1c9e6b2d7`.

No other new files. No new service module, no new router module, no new schema module — every
other change is an addition to a file that already exists.

## 6. Files That Would Be Modified

- `services/api/src/eop_api/models/hr_employee.py` — add `user_id` column, its index in
  `__table_args__`, and a `user` relationship attribute.
- `services/api/src/eop_api/repositories/hr_employee.py` — add `get_by_user_id`.
- `services/api/src/eop_api/schemas/hr_employee.py` — add `user_id: uuid.UUID | None = None` to
  `EmployeeCreate`, `EmployeeUpdate`, `EmployeeResponse`.
- `services/api/src/eop_api/services/hr_employee.py` — add `UserNotFoundError`; add a `user_id`
  existence check (against `UserRepository`) in `create` and `update`, alongside the nine existing
  checks.

Not modified: `models/user.py`, `repositories/user.py`, `services/auth.py`,
`dependencies/auth.py`, `dependencies/rbac.py`, `api/hr_employees.py` (schema shape changes only,
no route/handler logic changes), `main.py`, any `services/approval.py`/`services/reconciliation.py`
file, and every test file (no tests are written by this decision, per instructions).

## 7. Remaining Business Decisions

Unchanged from, and not narrowed beyond, the discovery's own §8 — restated here only to confirm
this decision does not silently resolve any of them:

1. **Whether `user_id` should eventually become unique** (one `User` to at most one `HrEmployee`) —
   deferred, not decided (§2, §3.5). A future migration could add the constraint once product
   confirms the cardinality rule; nothing in this decision blocks that.
2. **Authorization model built on the link** (role-based, org-chart/`manager_id`-based, or both) —
   entirely unaddressed; this decision provides only the lookup primitive.
3. **Who is responsible for populating `user_id`** — a manual admin action through the existing
   `PUT /hr/employees/{id}` endpoint is mechanically possible the moment this ships, but whether
   that is the intended provisioning process, versus some future dedicated onboarding flow, is a
   product decision.
4. **Whether this unblocks a specific next feature immediately** (self-service submission,
   manager-scoped approval, self-service reconciliation) or is purely infrastructure for now — a
   sequencing decision for a future PR, not this one.
5. **`ondelete=SET NULL`'s downstream consequence** — once a linked `User` is deleted, the
   `HrEmployee` row silently loses its account association with no record of what the association
   was. Whether that silent loss is acceptable, or whether it should instead be captured somewhere
   (e.g. an audit entry, once `AuditLog` is ever wired to HR entities — still unaddressed, per every
   prior discovery), is not decided here.

**Stopping here per instructions.** No production code, migrations, models, repositories,
services, schemas, or tests have been written. Awaiting review before any file listed in §5/§6 is
actually touched.

---

# PR-050 (Implementation) — Step 2: Uniqueness Re-Examination

Status: **Architecture decision only. No code, no migrations, no tests. Awaiting review.**

Scope: this section reviews exactly one question left open by Step 1 — whether repository
evidence determines `user_id`'s uniqueness — per instruction. It does not reopen FK direction,
`ON DELETE` behavior, backfill, DI, API shape, or any other Step 1 decision.

## 1. Conclusion

**Repository evidence does not determine uniqueness either way. Cardinality remains an
unresolved business decision — Step 1's own characterization of this as deferred (§2, "No unique
constraint on `user_id`") was correct on the business question, but incomplete: it did not surface
a real, evidenced *technical* consequence of leaving it undecided, which this section corrects.**

Neither "UNIQUE" nor "NOT UNIQUE" is proven by repository evidence. What repository evidence *does*
prove is narrower and more concrete: **whichever cardinality is eventually chosen, the repository
method built on top of `user_id` must match it** — and Step 1's proposed method
(`get_by_user_id(user_id) -> HrEmployee | None`, built on the shared `get_by` helper) silently
assumed uniqueness without the constraint that would make that assumption safe. That mismatch is
corrected in §3, without resolving the underlying business question.

## 2. Evidence

**2.1 — Every existing FK.** A full grep of every `UniqueConstraint`/`unique=True` in the codebase
(all models and all migrations) finds none that constrains a bare foreign-key column to enforce a
1:1 relationship between two independent aggregate roots. Every existing `UniqueConstraint` is one
of two shapes: (a) a business key on a non-FK field — `code` (`employment_types`, `job_grades`,
`holidays`, `shifts`, `employment_statuses`, `location_types`, `locations`), `email`
(`users.email` — `uq_users_email`, `hr_employees.email` — `uq_hr_employees_email`,
`employees.email`), `employee_number` (`uq_hr_employees_employee_number`), `level`
(`job_grades.level`), `holiday_date`, `storage_key` — or (b) a composite constraint scoping an FK
within a tenant or pairing, never the FK alone — `UniqueConstraint("organization_id", "code")` on
`departments`/`positions`/`teams`/`projects`, `UniqueConstraint("employee_id", "project_id")` on
`assignments`. The one join table in the codebase, `user_roles` (`models/user_role.py:5-10`), uses
a **composite primary key** (`user_id`, `role_id` together), not a unique constraint on either
column alone — a many-to-many shape, not a 1:1 one. **No precedent exists anywhere in this
codebase for a unique constraint enforcing 1:1 cardinality on a single FK column.** This means the
absence of a unique constraint on `hr_employees.user_id` cannot be read as "following precedent"
(there is no precedent either way for this exact situation — an identity-linking FK between two
independent aggregate roots has never existed in this codebase before), and neither can its
presence.

**2.2 — Identity semantics.** `users.email` is unique (`uq_users_email`) and
`hr_employees.email` is unique (`uq_hr_employees_email`) — but these are two independently-unique
keys *within* two separate identity spaces (login identity; HR-master-data identity), and this PR's
entire purpose is to bridge those two spaces for the first time. Two independently-unique-keyed
sets can still map to each other as 1:1, 1:many, or many:1 — uniqueness *within* each space says
nothing about the cardinality *between* them. Separately, `hr_employees.organization_id`
(`models/hr_employee.py:60-62`) confirms `HrEmployee` is organization-scoped (multi-tenant, per
`docs/product/02_PRODUCT_SCOPE.md` §1's "Multi-Tenant Organization" foundation module), while
`models/user.py` (full read, confirmed by grep) has **no `organization_id` column at all** — `User`
is not tenant-scoped in the current schema. This is a genuine structural fact: nothing in the
schema rules out a single login someday needing to resolve to employee records in more than one
organization, and nothing rules it in either. It demonstrates only that the schema does not
currently supply a reason uniqueness must hold — it is not evidence that multiplicity is needed.

**2.3 — Repository contracts (the decisive new evidence, not examined in Step 1).**
`BaseRepository.get_by` (`repositories/base.py:28-36`) is implemented as:

```python
async def get_by(self, column: InstrumentedAttribute[Any], value: Any) -> ModelT | None:
    stmt = select(self.model).where(column == value)
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()
```

`scalar_one_or_none()` raises `MultipleResultsFound` if more than one row matches. Every existing
call site of this method — `HrEmployeeRepository.get_by_email`, `get_by_employee_number`
(`repositories/hr_employee.py:35-39`) — is on a column already backed by a database-level
`UniqueConstraint` (§2.1). `UserRepository.get_by_email` (`repositories/user.py:14-17`) hand-writes
the same `scalar_one_or_none()` pattern directly against `User.email`, also unique. **Every
single-result lookup in this codebase, without exception, is performed against a column the
database already guarantees is unique.** There is no precedent anywhere for using this
method-shape against a column that is not database-unique. Step 1's proposed
`get_by_user_id(user_id) -> HrEmployee | None`, built on this same `get_by` helper, would be the
first exception — and, absent a unique constraint, a real correctness defect: if `user_id` is ever
non-unique in the data (which nothing prevents under the Step 1 schema), the call raises an
unhandled `MultipleResultsFound` at runtime instead of returning a value. This is evidence about a
method-contract mismatch, not about the underlying business cardinality — but it is evidence, and
it was absent from Step 1's analysis.

**2.4 — Service behavior.** `HrEmployeeService.create`/`update`, as scoped in Step 1, only checks
"does the referenced `User` exist" (mirroring the other nine FK-existence checks). Nothing in that
design checks "is this `User` already linked to a different `HrEmployee`." This is neutral: it
neither assumes nor precludes either cardinality, and adding such a check would itself be encoding
a business rule (uniqueness) this section finds unresolved — so no such check is proposed here
either.

**2.5 — Discovery documents.** `PR-050_DISCOVERY.md` §8, Ambiguity 3 already states cardinality is
"not addressed by any product document reviewed." No document reviewed for either the discovery or
Step 1 — `docs/product/*`, or any of the eight prior architecture discoveries — states or implies
whether one `User` may correspond to more than one `HrEmployee`. Nothing new has appeared to
resolve it.

## 3. Whether the implementation decision changes

**The business decision does not change: uniqueness remains unresolved, exactly as Step 1 already
said.** No repository evidence reviewed here overturns that — §2.1, §2.2, §2.4, and §2.5 all
independently confirm the codebase supplies no basis for choosing UNIQUE over NOT UNIQUE, or vice
versa, as a statement about real-world cardinality.

**One concrete piece of Step 1 does change, as a direct, evidenced consequence of §2.3, not as a
new business guess:**

- `HrEmployeeRepository.get_by_user_id` **must not** be built on `BaseRepository.get_by`
  (`scalar_one_or_none()`) while `user_id` remains non-unique — doing so carries a latent
  `MultipleResultsFound` failure mode with no precedent anywhere else in this codebase (§2.3). The
  method must instead return a collection, mirroring the codebase's own precedent for a
  legitimately-unconstrained one-to-many lookup — `LeaveBalanceRepository.get_by_employee(employee_id) -> Sequence[LeaveBalance]`
  (`repositories/leave_balance.py:27-30`), which queries a non-unique-by-schema FK
  (`leave_balances.employee_id` has no uniqueness constraint either, confirmed by direct read of
  `models/leave_balance.py` and its migration) and returns a `Sequence`, not a single optional row.
  The corrected signature is therefore `get_by_user_id(user_id: uuid.UUID) -> Sequence[HrEmployee]`,
  implemented as a direct `select(HrEmployee).where(HrEmployee.user_id == user_id)` (the same
  hand-written shape `LeaveBalanceRepository.get_by_employee` already uses), not a call to the
  shared `get_by` helper.
- This is a **repository-layer correction only**. It does not change FK direction, `ON DELETE
  SET NULL`, the migration's nullable/no-backfill shape, the absence of a DB-level unique
  constraint, the service-layer existence check, the API/schema changes, or the "no DI change"
  conclusion — none of those are touched by this section, per scope.
- If a future PR resolves the business question in favor of UNIQUE (via a follow-up migration
  adding the constraint, per Step 1 §7 item 1), `get_by_user_id` could then be safely simplified
  back to the single-result `get_by`-based form — but that simplification is contingent on the
  constraint existing, not assumed now.

**Files That Would Be Modified (Step 1, §6) is amended by exactly one clarifying detail**: the
`repositories/hr_employee.py` entry now specifies `get_by_user_id` returns `Sequence[HrEmployee]`
via a hand-written query, not a `get_by(...)`-based single-result method. No file is added to or
removed from the Step 1 list.

**Stopping here per instructions.** No production code, migrations, models, repositories,
services, schemas, or tests have been written. This section only corrects Step 1's repository
method contract and confirms uniqueness itself remains an open business decision.
