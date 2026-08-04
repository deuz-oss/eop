# PR-048 — Attendance Reconciliation Engine (Discovery)

Status: **Discovery only. No code, no migrations. Awaiting review.**

---

## 1. Executive Summary

**A prior draft of this document recommended a concrete `ReconciliationService` implementation.
That recommendation is withdrawn.** Repository evidence supports a set of architectural
*boundaries* for Attendance Reconciliation, but does not extend far enough to support a concrete
implementation choice. The two are kept separate throughout this revision (§7, §13).

**What repository evidence supports**: Attendance Reconciliation is a read-only computation,
combining `AttendanceEvent`, `Shift`, `LeaveRequest`, `Holiday`, and `OvertimeRequest`, that must
live **outside** repositories, **outside** aggregate CRUD services, and is **not** a persisted
aggregate or projection (§3, §5, §7). No code anywhere in this repository currently performs this
computation; every prior discovery document that touched the subject (`ATTENDANCE_DESIGN.md` §9,
`LEAVE_DESIGN.md` §10, `HOLIDAY_CALENDAR_DESIGN.md` §8, `TIMESHEET_DESIGN.md` §4/§7) anticipated
it as a future "read-time join, not a foreign key" and explicitly declined to build it. This PR
is the first discovery to examine that join directly rather than deferring it again.

**What repository evidence does *not* support**: the concrete shape or name of the component that
performs the computation. This codebase has exactly **one** precedent for a service that is not
scoped to a single entity's CRUD — `ApprovalService` (`services/approval.py`), built in PR-047 as
the resolution of `APPROVAL_ORCHESTRATION_DESIGN.md`'s previously-unresolved Option A/B question.
`ApprovalService` establishes two things a future orchestration component could build on: (a) a
service need not own a repository 1:1 — it can reach into
`LeaveRequestRepository`/`OvertimeRequestRepository`/`TimesheetRepository` directly, the same way
every CRUD service already reaches into `HrEmployeeRepository`/`ShiftRepository` for existence
checks; (b) a single `SQLAlchemyUnitOfWork` session can host multiple repositories side by side
without incident. **But `ApprovalService` only ever touches one repository per call** — it never
reads from two repositories and combines their results into a single computed value.
Reconciliation would need to read from *five* aggregates in one call and combine them. That
specific behavior — cross-aggregate **read composition** — has no precedent anywhere in this
codebase. `TIMESHEET_DESIGN.md` §7 identified exactly this gap for Timesheet's own (never-built)
period-total computation and left it an open architectural ambiguity; `TimesheetRepository`'s own
docstring (`repositories/timesheet.py:24-30`) now states explicitly that "no projection queries
and no joins... belong here," confirming Timesheet was ultimately built *without* solving this
problem, not with a different solution to it.

**This means Reconciliation is not filling a gap next to existing precedent — it is the first
attempt at the exact composition problem `TIMESHEET_DESIGN.md` §7 raised and never resolved.**
`ApprovalService` is an *analogy* — the closest available one — not a template repository evidence
confirms is correct for this different behavior (read-composition across five aggregates, versus
`ApprovalService`'s single-repository read-then-write). Evidence is sufficient to rule out placing
Reconciliation in a repository, in `AttendanceService`, or in a persisted aggregate (§7, Options
A/C) — each of those contradicts an explicit, still-honored boundary an existing design document
already drew. Evidence is **not** sufficient to compel a specific alternative among the remaining,
non-contradicted possibilities (a new dedicated service shaped like `ApprovalService`; a
differently-shaped orchestration component; some other read-oriented composition mechanism not
yet named in this codebase). Naming and designing that component is an architectural decision for
the implementation PR, informed by this discovery but not dictated by it (§13).

"Attendance Reconciliation" does not appear anywhere in `docs/product/06_PRODUCT_ROADMAP.md`
(only bare "Attendance" appears, twice, in Phase 4 and the MVP list) — continuing the pattern
already flagged by every Time Management discovery document since `LEAVE_DESIGN.md` §12.1.

---

## 2. Evidence Reviewed

**Aggregates** (`services/api/src/eop_api/models/`, full file reads): `AttendanceEvent`
(`attendance_event.py`, plus `core/attendance.py` for `EventType`/`EventSource`), `Shift`
(`shift.py`), `LeaveRequest` (`leave_request.py`), `Holiday` (`holiday.py`), `OvertimeRequest`
(`overtime_request.py`), `Timesheet` (`timesheet.py`), `HrEmployee` (`hr_employee.py`),
`LeaveBalance` (`leave_balance.py`), `User` (`user.py`).

**Services** (full file reads, all eight in the Time Management + Approval surface):
`services/attendance_event.py`, `services/leave_request.py`, `services/holiday.py`,
`services/overtime_request.py`, `services/timesheet.py`, `services/leave_balance.py`,
`services/approval.py`, `services/audit_log.py`. Confirmed via direct read that
`AttendanceEventService`, `LeaveRequestService`, `OvertimeRequestService`, `TimesheetService`,
`HolidayService`, `LeaveBalanceService` are all CRUD-only: each owns a `uow_factory`, performs at
most one or two narrow existence/structural checks against exactly one or two *other*
repositories, and never reads business data from a second repository to combine with its own.
`ApprovalService` (§1) is the sole exception — read in full, analyzed in §6.

**Infrastructure**: `repositories/base.py` (`BaseRepository[ModelT]`, generic over exactly one
model), `uow/base.py` (`AbstractUnitOfWork`), `uow/sqlalchemy.py` (`SQLAlchemyUnitOfWork`,
single shared `AsyncSession`), `schemas/search.py` (`SearchParams`/`FilterParams`),
`schemas/pagination.py` (`PaginationParams`/`Page`), `dependencies/search.py`,
`dependencies/pagination.py`, `models/audit_log.py` + `services/audit_log.py` + `core/audit.py`
(`AuditEntityType`/`AuditAction`), `events/base.py` + `events/memory_publisher.py`,
`notifications/base.py` + `notifications/memory_provider.py`, `dependencies/rbac.py` +
`api/roles.py` (`RequireRole` usage).

**Repositories** (full file reads): `repositories/attendance_event.py`,
`repositories/leave_request.py`, `repositories/holiday.py`, `repositories/overtime_request.py`,
`repositories/timesheet.py`, `repositories/hr_employee.py`. Confirmed every one subclasses
`BaseRepository[SingleModel]`, declares `SEARCHABLE_FIELDS`/`FILTERABLE_FIELDS` for its own table
only, and issues no query touching another model's table.

**API**: `api/leave_requests.py` (full file, representative of `api/overtime_requests.py`/
`api/timesheets.py`, confirmed structurally identical by the prior discovery docs and spot-checked
here) — confirms `POST .../approve`/`POST .../reject` are real, working endpoints (not stubs;
PR-046's `501` stubs were replaced by PR-047's `ApprovalService` wiring), and that no
`GET .../reconciliation`-shaped or cross-entity report endpoint exists anywhere in the API surface.

**Migrations**: every file in `alembic/versions/` (24 files, current head
`f4a1c9e6b2d7_add_approval_fields_to_leave_requests_overtime_requests_and_timesheets`), confirming
the incremental-FK/standalone-table precedent holds through the most recent migration, and that no
`attendance_reconciliations`/`attendance_daily_summaries`-shaped table exists.

**Previous discovery documents**, full files: `ATTENDANCE_DESIGN.md` (PR-039),
`LEAVE_DESIGN.md` (PR-040), `HOLIDAY_CALENDAR_DESIGN.md` (PR-041), `TIMESHEET_DESIGN.md`
(PR-045), `APPROVAL_WORKFLOW_DESIGN.md` (PR-046), `APPROVAL_ORCHESTRATION_DESIGN.md` (PR-047).
**Confirmed by `Glob` (no match): `OVERTIME_REQUEST_DESIGN.md` and `TIME_MANAGEMENT_DOMAIN.md`
do not exist anywhere in the repository** — `TIMESHEET_DESIGN.md` §2 and
`APPROVAL_WORKFLOW_DESIGN.md` §2 both already flagged this same gap; reconfirmed independently
here rather than re-derived, and still unresolved.

**Also reviewed**: `docs/product/06_PRODUCT_ROADMAP.md` (grepped for "reconcil" and "attendance" —
zero and two hits respectively, both bare "Attendance" in Phase 4 / MVP lists, no reconciliation
concept named anywhere).

**Not re-read in full** (already fully synthesized by the discovery docs above, no evidence
suggests re-deriving independently would change anything below): `services/holiday.py`,
`repositories/leave_balance.py`, `schemas/*` for the six aggregates, the full `alembic/versions/`
migration bodies beyond `f4a1c9e6b2d7`.

---

## 3. Aggregate Analysis

**Question: is Attendance Reconciliation an aggregate, a projection, an application service, an
orchestration service, a reporting layer, or something else?**

| Candidate | Verdict |
|---|---|
| A new persisted aggregate (e.g. `AttendanceReconciliation`, one row per employee-day) | Rejected |
| A projection/read-model materialized and stored in its own table | Rejected for this PR |
| A capability embedded in an existing service (`AttendanceService`) | Rejected |
| A read-only orchestration layer, outside repositories and CRUD services, that computes a result on demand, storing nothing | **Category supported by evidence** — concrete form not determined (§7, §13) |

**Why not a persisted aggregate.** `ATTENDANCE_DESIGN.md` §1 already evaluated and rejected
exactly this shape under the name `AttendanceDailySummary` — a mutable per-employee-day row —
specifically to avoid "read-modify-write races the moment there's more than one clock action per
day" and to avoid baking an unconfirmed business rule into a schema before the rule was known
(overnight-shift attribution, multiple-clock-ins-per-day, etc. — none of which are resolved even
now, three PRs later). `TIMESHEET_DESIGN.md` §4 independently reached the identical conclusion for
Timesheet's own hour totals: "compute, never store." Every aggregate reviewed in §2 that has a
computed-vs-stored choice to make has made the same choice: store the fact, compute the
derived view. A persisted `AttendanceReconciliation` row would be the first reversal of that
pattern in this codebase, with no new evidence to justify reversing it.

**Why not a projection materialized in its own table.** A repo-wide search for any `queries/`,
`read_models/`, or `projections/`-style module (already performed by `TIMESHEET_DESIGN.md` §2,
reconfirmed here) turns up nothing. There is no existing seam for a materialized read model to
plug into, and building the accompanying refresh/invalidation machinery (when does a materialized
row get recomputed after a late-arriving `AttendanceEvent` correction or a leave request that gets
approved after the fact?) would require resolving `TIMESHEET_DESIGN.md` §12's still-open
"frozen snapshot vs. live recompute" tension — this discovery does not resolve that tension either,
and building a projection table would force a premature answer to it.

**Why not embedded in `AttendanceService`.** `ATTENDANCE_DESIGN.md` §6 drew an explicit boundary
that is still in force, unmodified, in the current `AttendanceEventService`
(`services/attendance_event.py:22-30`, docstring): *"Sequencing... duplicate-event detection, and
shift-matching are explicitly out of scope for this module and belong to future business-workflow
PRs."* Reconciliation — combining `AttendanceEvent` with `LeaveRequest`/`Holiday`/`OvertimeRequest`
to produce a business judgment about a day — is precisely the class of cross-entity computation
that boundary was written to exclude. Extending `AttendanceEventService` to do it would directly
contradict a boundary its own design document drew and the current code still honors.

**Why a read-only orchestration layer, category only, not something heavier.** This is not a new
kind of component invented for this discovery — the *category* (a service with **no single
entity it owns**, that constructs repositories against a shared `uow.session` for a bounded
purpose, and returns a computed result rather than a row it created) is the same one
`ApprovalService` already established as viable in this codebase. The difference from
`ApprovalService` (read *multiple* repositories and *combine* their results, versus read/write
exactly one) is real and unprecedented (§6) — so while the general category is evidence-supported,
the concrete shape of a component that does cross-aggregate read composition specifically is not.
That distinction is carried through §6, §7, and §13 rather than resolved here.

**"Reporting layer" considered and rejected as a separate category.** The instructions ask
whether Reconciliation is a reporting layer; the evidence gives no basis to treat "reporting" as
architecturally distinct from "a read-only orchestration component that computes and returns a
value" in this codebase — there is no existing `reporting/` module, and `TIMESHEET_DESIGN.md`'s
own analysis of an analogous problem never introduced a "reporting" category as a candidate
either. Folding it into the orchestration-layer category above, rather than proposing it as a
fourth architectural option, reflects that the codebase draws no such distinction anywhere.

---

## 4. Input Analysis

**Question: which aggregates does reconciliation read?**

| Aggregate | Reads? | Why |
|---|---|---|
| `AttendanceEvent` | **Yes** | The raw fact stream reconciliation exists to interpret. `ATTENDANCE_DESIGN.md` §9 anticipated exactly this: "Leave... reconcile against approved leave days... Overtime: computed by a consumer that reads ordered events per employee-day." Filtered by `employee_id` + `event_time` within the target date (`attendance_event.py:44,53`). |
| `Shift` | **Yes, indirectly** | `AttendanceEvent.shift_id` (`attendance_event.py:47-49`) and `HrEmployee.shift_id` (`hr_employee.py:87-89`) both reference it. Needed to interpret *when* an employee was expected to work (`start_time`/`end_time`, `shift.py:30-31`) so "present" vs. "late" vs. "absent" can be judged against a schedule, not just against the presence of any event. |
| `LeaveRequest` | **Yes, filtered to `status == "approved"`** | Direct precedent: every prior doc anticipated this exact read (`ATTENDANCE_DESIGN.md` §9, `LEAVE_DESIGN.md` §10 — "an approved `LeaveRequest` suppressing an 'absent' read on an `AttendanceEvent` gap"). `status` is now a real, meaningful value post-`ApprovalService` (`"pending"`/`"approved"`/`"rejected"`, `services/approval.py:17-21`) — reconciliation is the first consumer with a concrete reason to filter on it. |
| `Holiday` | **Yes** | Filtered by `holiday_date` (`holiday.py:29`) matching the target date. `HOLIDAY_CALENDAR_DESIGN.md` §8 anticipated exactly this: "distinguishing 'absent' from 'non-working holiday' — a read-side join on `date`." No FK exists or is needed (§5). |
| `OvertimeRequest` | **Yes, filtered to `status == "approved"`** | Same status-filtering rationale as `LeaveRequest`. `overtime_date`/`start_time`/`end_time` (`overtime_request.py:46-48`) are needed to distinguish scheduled-shift hours from approved overtime hours on the same day. |
| `Timesheet` | **No** | `Timesheet` is a *downstream consumer* of reconciliation, not an input to it. `TIMESHEET_DESIGN.md` §4 already modeled `Timesheet` as storing only the ask-and-decision and computing "worked hours... projected from `AttendanceEvent`... leave days... projected from `LeaveRequest`... holiday days... projected from `Holiday`," i.e. `Timesheet`'s own unbuilt computation is a superset of what Reconciliation computes for one day, over a date span instead. Reading `Timesheet` as an *input* to Reconciliation would invert this dependency direction with no evidence supporting the inversion. |
| `LeaveBalance` | **No** | `LeaveBalance` holds entitlement bookkeeping (`allocated_days`/`used_days`/`remaining_days`, `leave_balance.py:35-37`), not a fact about what happened on a given date. Determining *whether* a day is a leave day only requires an approved `LeaveRequest` covering that date (§ above); `LeaveBalance` is relevant to Payroll/HR entitlement tracking, not to reconciling a single day's attendance result. |
| `HrEmployee` | **Yes, for existence/scope only** | Every reviewed service validates the referenced employee exists before proceeding (`HrEmployeeRepository(...).exists(...)`, uniform pattern across all six CRUD services). Reconciliation needs the same check — it is the scope key every other aggregate above is filtered by (`employee_id`) — but does not need to read `HrEmployee`'s own business fields (department, position, etc.) to compute a day's attendance result. |

**Not evaluated as inputs, no basis found**: `JobGrade`, `EmploymentType`, `EmploymentStatus`,
`Organization`, `Department`, `Position`, `Team`, `Location`, `User`, `Role`, `AuditLog` — none of
these carry any fact relevant to whether a given employee was present, late, absent, on leave, on
a holiday, or on approved overtime on a given date, and no prior discovery document has proposed
otherwise.

---

## 5. Repository Boundary

**Should repositories perform reconciliation, or join multiple aggregates? No — on two
independent, converging lines of evidence.**

**Structural**: `BaseRepository[ModelT]` (`repositories/base.py:14-19`) is generic over exactly
one model; every method (`get`, `get_by`, `list`, `create`, `update`, `delete`, `exists`, `count`,
`paginate`) issues `select(self.model)`-rooted queries. Every concrete repository reviewed (§2)
observes this without exception. A repository method joining `attendance_events`,
`leave_requests`, `holidays`, and `overtime_requests` would be the first repository in the
codebase to read outside its own model's table — not an extension of the pattern, a departure
from it.

**Direct, on-point precedent**: `TimesheetRepository`'s own docstring (`repositories/timesheet.py:24-30`)
states this exact conclusion for the structurally closest prior case: *"Persistence only, scoped
to the `timesheets` table -- per `docs/architecture/TIMESHEET_DESIGN.md` §6/§7, no projection
queries and no joins against `AttendanceEvent`/`LeaveRequest`/`OvertimeRequest`/`Holiday`/
`LeaveBalance` belong here."* This is not a hypothetical boundary — it is the recorded outcome of
the one prior discovery that asked almost this exact question and chose not to put the answer in
a repository. Reconciliation's repository-boundary question is answered by the same evidence,
without needing new reasoning.

**What repositories should gain, mechanically, if anything**: narrow, single-model range-query
helpers scoped to `employee_id` + a date column (e.g. `AttendanceEventRepository.list_by_employee_and_range`,
`LeaveRequestRepository.list_by_employee_and_range`, `HolidayRepository.list_between`,
`OvertimeRequestRepository.list_by_employee_and_range`) — each is a same-table query, consistent
with every existing `get_by_x`/`get_by_employee` helper already on these repositories
(`OvertimeRequestRepository.get_by_employee`, `repositories/overtime_request.py:28-31`;
`TimesheetRepository.get_by_employee`, `repositories/timesheet.py:35-38`). **Whether these are new
methods on the existing repositories, or whether `BaseRepository._apply_filters` should finally
gain generic `BETWEEN` support**, is the same open question every prior discovery document has
raised and explicitly declined to resolve on one consumer's evidence alone (`HOLIDAY_CALENDAR_DESIGN.md`
§4/§10.7, `LEAVE_DESIGN.md` §8, `TIMESHEET_DESIGN.md` §6/§13.9). This document does not resolve it
either — it is now the *fourth* module to need the same capability, which is closer to (but this
discovery does not declare it has reached) the "second concrete consumer" bar those documents set
for generalizing shared infrastructure.

---

## 6. Service Boundary

**Question: where does the composition logic live?**

**The only existing precedent for a service that is not a single entity's CRUD owner is
`ApprovalService` (`services/approval.py`).** Reviewed in full (§2). Its shape:

- Constructor takes only a `uow_factory`, identical to every CRUD service (`services/approval.py:54-57`).
- Each public method (`approve_leave_request`, `reject_overtime_request`, etc.) opens **one**
  `uow`, constructs **one** repository against `uow.session` scoped to the target entity's own
  table (`LeaveRequestRepository`, `OvertimeRequestRepository`, or `TimesheetRepository` — never
  more than one per call), and delegates to a shared private `_decide` helper
  (`services/approval.py:143-179`).
- It reads the entity, checks one invariant (`status == "pending"`), writes new values via the
  existing generic `BaseRepository.update(**values)`, commits, refreshes, expunges — the same
  session-lifecycle contract every CRUD service already follows.

**What this precedent establishes, concretely, for Reconciliation:**

1. A service need not have a 1:1 relationship with a single repository/entity — `ApprovalService`
   already proves this is buildable and testable in this codebase (its own test suite,
   `tests/test_approval_service.py`, follows the same three-tier pattern as every other service
   test, just against a service with no "primary" entity of its own).
2. Multiple repositories can be constructed against one shared `uow.session` without incident —
   already proven by *every* CRUD service's own existence checks (`AttendanceEventService` alone
   uses `HrEmployeeRepository` **and** `ShiftRepository` in the same `uow` block,
   `services/attendance_event.py:54-58`), and by `ApprovalService`'s own choice of which
   repository to instantiate per call.

**What this precedent does *not* establish — the gap this document does not paper over:**
`ApprovalService` never reads from **two or more** repositories and **combines** their results
into one computed value. Every method reads and writes exactly one entity's table. Reconciliation
needs to read from **five** (`AttendanceEvent`, `Shift`, `LeaveRequest`, `Holiday`,
`OvertimeRequest`) and produce one combined result. This is categorically the same problem
`TIMESHEET_DESIGN.md` §7 raised for Timesheet's own (never-built) period-total computation and
explicitly left as an "open architectural ambiguity, not a resolved design" — restated verbatim in
that document's §13.5 and never subsequently resolved by any later PR (`Timesheet` shipped without
solving it — its repository docstring, quoted in §5 above, confirms the computation was never
attempted).

**What repository evidence supports, stated at the boundary level only**: whatever component ends
up performing this composition should have no owned entity of its own, should follow the
`uow_factory`-constructor / one-`uow`-per-call shape every service in this codebase already uses,
and should construct the five repositories it needs (`AttendanceEventRepository`,
`ShiftRepository`, `LeaveRequestRepository`, `HolidayRepository`, `OvertimeRequestRepository`)
against a single shared `uow.session` — each of these is a direct, evidenced continuation of
`ApprovalService`'s proven shape (§2) or of the multi-repository-per-session pattern already used
by every CRUD service's existence checks. **What repository evidence does not support is naming
or finalizing this as a specific class** (e.g. a `ReconciliationService`). Evidence confirms the
*boundary conditions* the component must satisfy (no owned entity, read-only, reads five
repositories, returns a computed non-persisted result — §9); it does not confirm that a single new
service class, as opposed to some other read-oriented composition mechanism consistent with those
same boundary conditions, is the only or correct way to satisfy them. This mirrors
`APPROVAL_ORCHESTRATION_DESIGN.md` §5/§14's own posture before Option B was adopted for Approval in
a later implementation PR, not this discovery: the boundary conditions were established by
discovery, the concrete class was an implementation-PR decision. §7 and §13 carry this distinction
forward explicitly rather than collapsing it.

**Must NOT belong in whichever component ends up performing this composition**, mirroring the
boundary every prior service in this codebase draws around its own downstream consumers:
- Writing anything. This is a pure read (§8) — no repository's `create`/`update`/`delete` should
  ever be called as part of this computation.
- Leave/overtime *approval* logic — `ApprovalService` already owns that; Reconciliation only reads
  the resulting `status`.
- Payroll rate/deduction computation, Timesheet period-total computation, or Analytics
  aggregation — each is a distinct future consumer of Reconciliation's output (§10), not a
  responsibility Reconciliation should absorb.

---

## 7. Candidate Architectures

Evaluated per the instructions, with supporting evidence, contradicting evidence, advantages, and
disadvantages for each. No precedent is invented; where evidence is genuinely absent, that is
stated rather than resolved by assumption.

### Option A — `AttendanceService`

**Supporting evidence**: `AttendanceEvent` is the primary raw-fact input (§4); it is plausible on
its face that "interpreting" attendance facts belongs next to the service that owns them.

**Contradicting evidence**: `ATTENDANCE_DESIGN.md` §6 explicitly excludes this class of
computation from `AttendanceService`'s responsibilities (quoted in full, §3) — a boundary the
current `AttendanceEventService` code still honors verbatim (§3). Extending it now would reverse
an existing, still-in-force design decision without new evidence to justify the reversal. It would
also require `AttendanceEventService` — currently dependent on exactly two other repositories
(`HrEmployeeRepository`, `ShiftRepository`, both for existence checks only) — to newly depend on
`LeaveRequestRepository`, `HolidayRepository`, and `OvertimeRequestRepository` as well, a much
larger dependency surface than any CRUD service in this codebase currently carries.

**Advantages**: no new class; reuses `AttendanceEventService`'s existing DI wiring and test
scaffolding.

**Disadvantages**: directly contradicts an explicit, documented, still-honored boundary; conflates
a CRUD service with an orchestration service in one class, the exact "concentration of
unprecedented responsibilities into a narrowly-scoped class" risk `APPROVAL_WORKFLOW_DESIGN.md`
§10 flagged for its own Option A.

### Option B — A dedicated read-only orchestration component (concrete form undetermined)

**Supporting evidence**: `ApprovalService` is direct, working precedent for a service with no
owned entity that reaches into other entities' repositories for a bounded purpose (§6). This
category violates neither the repository single-model contract (§5) nor the explicit
`AttendanceService` boundary (Option A's problem) nor the "no persisted projection" precedent
(Option C's problem, below) — it is the only evaluated category that violates none of the three
established boundaries this discovery has found. **Repository evidence supports this category as
the location for Reconciliation's logic.**

**Contradicting evidence, scoped to the concrete implementation, not the category**: no service in
this codebase reads from more than one *other* repository's business data and combines the results
(§6) — `ApprovalService` reads/writes exactly one repository per call. Cross-aggregate read
composition — reading five repositories and combining them into one value — has no precedent
anywhere in this codebase, only the adjacent "service reaches into another entity's repository"
pattern. **This is why repository evidence, while sufficient to support the category, is not
sufficient to determine the category's concrete implementation.** A single new service class
shaped exactly like `ApprovalService` is the closest analogy available, but it is an analogy, not
a confirmed instance of the specific behavior (multi-repository read composition) Reconciliation
needs. Other concrete forms consistent with the same category — e.g. a differently-structured
orchestration component, or a composition mechanism not otherwise named in this discovery — are
neither confirmed nor ruled out by the evidence reviewed.

**Advantages** (of the category): does not contradict any existing documented boundary; the
category's outer shape (no owned entity, `uow_factory`-based, reads via existing repositories)
matches the one available orchestration-service precedent as closely as any option can; keeps
every existing CRUD service's responsibility surface unchanged; naturally read-only in a way that
maps directly onto §8's UnitOfWork analysis.

**Disadvantages** (of the category, and of committing to a concrete form prematurely): introduces
a new component category (cross-aggregate read composition) with only partial precedent; the
query itself (five tables, filtered by employee + date, no shared FK to join on — see §5) has to
be hand-written per repository and combined in Python, since no cross-model join capability exists
at the ORM/repository layer; and picking a specific class/shape now, without a second concrete use
case to validate it against, risks the same premature-generalization this codebase's discovery
methodology has otherwise consistently avoided (`TIMESHEET_DESIGN.md` §7,
`APPROVAL_WORKFLOW_DESIGN.md` §3).

### Option C — `AttendanceProjection` (a persisted or purely computed aggregate)

**Supporting evidence**: none found for the *persisted* variant — see §3's rejection of a
persisted aggregate. For a purely in-memory, non-persisted "projection" (a DTO, not a `BaseEntity`
subclass), this is not architecturally distinct from Option B's return type (§9) — it would only
be a different name for the same shape, not a different placement for the computation itself.

**Contradicting evidence**: `ATTENDANCE_DESIGN.md` §1 already rejected the persisted variant of
this exact idea (`AttendanceDailySummary`) for the reasons restated in §3. No `projections/` or
`read_models/` module exists to anchor a "Projection" as a distinct architectural category from
"a service method's return value" in this codebase (§2, confirmed by `TIMESHEET_DESIGN.md` §2's
identical prior search).

**Advantages**: if persisted, would allow cheap repeated reads without recomputation — but this
advantage requires solving the unresolved "frozen snapshot vs. live recompute" question (§3, §12)
first, which this discovery does not do.

**Disadvantages**: the persisted variant reintroduces exactly the read-modify-write and
stale-data risks `ATTENDANCE_DESIGN.md` §1 rejected `AttendanceDailySummary` to avoid; the
non-persisted variant is not a genuinely different option from Option B, only different
terminology for its output shape.

### Option D — Another architecture

No fourth placement is justified by evidence beyond what Options A–C already cover. A
generic cross-aggregate "query object" or "CQRS read-side" layer (raised and rejected on identical
"zero precedent, would require inventing an unprecedented layer" grounds by
`APPROVAL_ORCHESTRATION_DESIGN.md` §5's own Option C) was considered and rejected here for the
same reason: nothing in `services/api/src/eop_api` resembles such a layer, and introducing one now,
for a single consumer, would repeat the exact premature-generalization this codebase's discovery
methodology has consistently declined to commit to (`TIMESHEET_DESIGN.md` §7,
`APPROVAL_WORKFLOW_DESIGN.md` §3).

**Verdict**: Option A and Option C are each ruled out by a specific, on-point, still-current
design decision already in the repository (§3, §7A). Option D has no precedent in either
direction. **Repository evidence supports Option B's category — a dedicated read-only
orchestration component, outside repositories and aggregate CRUD services — as the only evaluated
category that does not contradict an existing, explicit architectural boundary this discovery
found.** Repository evidence does **not** extend to determining Option B's concrete architectural
form or naming (a specific `ReconciliationService` class, or any other named component) — that is
an architectural decision for the implementation PR, informed by the boundary conditions
established here (§6), not a conclusion this discovery reaches on its own. This mirrors, rather
than repeats, `APPROVAL_ORCHESTRATION_DESIGN.md`'s own posture: that document found the evidence
evenly insufficient between two named options and declined to pick either; this document finds the
evidence sufficient to narrow the *category* to one of four, while remaining insufficient to name
or finalize a concrete component within that category.

---

## 8. UnitOfWork

**Transaction requirement: read-only.** Reconciliation writes nothing to any table — it reads five
aggregates and returns a computed value. Concretely:

- One `SQLAlchemyUnitOfWork` per call (matching every service's existing per-call `uow_factory()`
  pattern), used to construct `AttendanceEventRepository`, `ShiftRepository`,
  `LeaveRequestRepository`, `HolidayRepository`, and `OvertimeRequestRepository` against the
  **same** `uow.session` — directly following the multi-repository-per-session pattern already
  proven safe by `AttendanceEventService` (`HrEmployeeRepository` + `ShiftRepository`) and
  `ApprovalService`.
- **`uow.commit()` should never be called.** This mirrors every existing read-only service method
  in the codebase exactly: `get`, `list`, and `list_paginated` on every CRUD service reviewed
  (§2) never call `commit()` — only `create`/`update`/`delete` do. `AbstractUnitOfWork`'s own
  contract (`uow/base.py:6-14`) makes this safe by construction: *"exiting the context without an
  explicit commit rolls the transaction back."* A read-only method relying on rollback-on-exit is
  the existing, established pattern, not a new one.
- **`expunge_all()` before the `uow` context closes**, matching every `list`/`list_paginated`
  method reviewed (§2), so returned data survives session closure without triggering
  `DetachedInstanceError`.
- **Not mixed.** No evidence anywhere in this discovery suggests Reconciliation ever needs to
  write (§3, §6) — there is no scenario identified in which computing a reconciliation result
  should itself mutate `AttendanceEvent`/`LeaveRequest`/`Holiday`/`OvertimeRequest`. If a future
  PR decides reconciliation results should be cached/persisted (§3's rejected Option C, revisited
  with new evidence), that would change this section's conclusion — but no such evidence exists
  today.

---

## 9. API Boundary

**Recommendation: `GET` only.** No `POST`/`PUT`/`DELETE` is proposed, because reconciliation
creates, updates, or deletes nothing (§8) — there is no resource lifecycle to expose beyond
reading a computed value. This is a different shape from every other reviewed entity's six-route
CRUD set (`POST ""`, `GET ""`, `GET "/paginated"`, `GET "/{id}"`, `PUT "/{id}"`,
`DELETE "/{id}"`), and deliberately so: Reconciliation has no `{id}` — its identity is
`(employee_id, date)` or `(employee_id, date_range)`, not a UUID primary key, because it is not a
stored row (§3).

Proposed, following the existing `APIRouter(prefix="/hr/...", tags=[...])` /
`CurrentUser`-on-every-route / `Depends`-injected-service shape every reviewed router uses:

| Method | Path | Why |
|---|---|---|
| `GET` | `/hr/attendance/reconciliation?employee_id=&date=` | Single-day reconciliation for one employee — the atomic unit of computation (§4). |
| `GET` | `/hr/attendance/reconciliation?employee_id=&start_date=&end_date=` | Range form, likely the more useful shape for a real caller (matches every other date-range consumer flagged across all prior discoveries — Timesheet periods, Leave spans). Whether this is the *same* route as the single-day form (optional `end_date`) or a separate route is an implementation-time decision, not resolved here. |

**Explicitly not proposed**, because each presupposes a decision this document does not make:

- Any endpoint that *writes* a reconciliation result (e.g. "lock"/"finalize" a day) — presupposes
  the still-unresolved frozen-snapshot-vs-live-recompute question (§3, §12), inherited unresolved
  from `TIMESHEET_DESIGN.md` §12/§13.6.
- A bulk/all-employees reconciliation report endpoint — no precedent for bulk operations exists
  anywhere in the reviewed codebase (`HOLIDAY_CALENDAR_DESIGN.md` §6 already made this same
  observation for Holiday), and performance implications of a many-employee, many-day query are
  entirely unaddressed by this discovery (§12).
- Any role-gated or manager-scoped variant — `RequireRole` exists but is used by exactly one
  endpoint in the entire codebase (`RequireAdmin` in `api/roles.py`, confirmed by fresh grep, §2);
  no HR/Time-Management endpoint is role-gated, and Reconciliation would have no basis to be the
  first without a product decision this discovery cannot make.
- A self-service "my reconciliation" endpoint resolved from the authenticated `User` — blocked by
  the same `User` ↔ `HrEmployee` gap every prior discovery has flagged unresolved (confirmed still
  absent in both directions by direct read of `models/user.py`, §2).

---

## 10. Future Compatibility

- **Timesheet**: this is the most consequential compatibility finding in this discovery.
  `TIMESHEET_DESIGN.md` §4 already specified that `Timesheet`'s worked/overtime/leave/holiday
  totals should be "computed, never stored," projected from exactly the same five aggregates
  Reconciliation reads (§4) — and §7 of that same document left *how* to compute them an
  unresolved architectural ambiguity, one `Timesheet` ultimately shipped without resolving
  (`repositories/timesheet.py`'s docstring, quoted §5). **If a dedicated read-only reconciliation
  component is built (§7, category only — concrete form not decided here), it would directly
  supply the missing computation `TIMESHEET_DESIGN.md` §7/§13.5 left as Timesheet's own central,
  still-open blocker** — a future `TimesheetService` could call it once per date in a submitted
  period and sum the results, rather than independently solving the same cross-aggregate read
  problem a second time. This is not proposed as an implementation here (out of scope for this
  discovery), only noted as the clearest, strongest compatibility signal found.
- **Payroll**: no `Payroll`/`PayPeriod` concept exists anywhere in the codebase or roadmap (same
  gap `TIMESHEET_DESIGN.md` §1/§13.12 already flagged). If it materializes, it would consume
  Reconciliation's per-day result the same way Timesheet would — a read, not a schema dependency.
- **Analytics/Dashboards**: would aggregate reconciliation results across employees/departments —
  reachable via the same `HrEmployee` relationship graph (`department_id`/`location_id`/`team_id`)
  every prior discovery has already established as sufficient for this purpose, provided
  Reconciliation's output is well-typed enough to aggregate over (§9's response shape, not
  resolved to field level here).
- **Leave/Overtime**: unaffected structurally — Reconciliation reads their `status` column as a
  consumer; nothing about Reconciliation existing requires any change to either aggregate's own
  schema or service.

**The common thread, consistent with every prior discovery's own future-compatibility reasoning**:
Reconciliation is itself a *consumer* of five existing aggregates and would become a *producer*
for at least one already-identified future consumer (Timesheet) — it changes no existing schema,
requires no FK from any reviewed table, and is additive by construction (§3, §5).

---

## 11. Risks

Identified, not solved:

- **Cross-aggregate read composition is unprecedented.** This is the central, load-bearing risk
  of this entire discovery (§6, §7): no service in this codebase has ever combined data from more
  than one other repository into a single computed value. Whatever concrete component the
  implementation PR chooses to perform this composition, it would be new, unreviewed-in-practice
  territory, not a mechanical extension of `ApprovalService` — the category is evidence-supported
  (§7), the specific behavior is not (§1, §6).
- **Overnight-shift day attribution is still unresolved.** `ATTENDANCE_DESIGN.md` §10 flagged this
  for `AttendanceEvent` itself (a clock-in at 22:00, clock-out at 06:00 the next day — which
  calendar date does the event belong to?) and it remains unresolved three PRs later. Reconciliation
  cannot correctly bucket events into "the day's result" without an answer.
- **Timezone attribution is still unresolved.** `Location` has no timezone column (confirmed
  unresolved in `ATTENDANCE_DESIGN.md` §10, `LEAVE_DESIGN.md` §11, never since addressed);
  Reconciliation's date-boundary semantics inherit this gap directly.
- **No day-result vocabulary exists.** No enum or business term anywhere in the codebase defines
  what a reconciled day's outcome even *is* ("present," "absent," "late," "half-day," "on leave,"
  "holiday," "overtime," or some combination) — `EventType`/`EventSource` (`core/attendance.py`)
  describe individual clock events, not a day's aggregate outcome. This discovery does not invent
  one; see §13.1.
- **Precedence rules for conflicting facts are undefined.** If an employee has both an approved
  `LeaveRequest` covering a date *and* one or more `AttendanceEvent` rows on that same date, no
  rule anywhere determines which fact wins, or whether both are surfaced. Same open question for
  an approved `Holiday` coinciding with actual clock events.
- **No overlap/duplicate prevention on the source data.** `LEAVE_DESIGN.md` §12.8 and
  `TIMESHEET_DESIGN.md` §13.8 both flagged, unresolved, that overlapping `LeaveRequest`/`Timesheet`
  spans for the same employee are not prevented at write time. Reconciliation would need to decide
  how to handle two approved, overlapping `LeaveRequest`s covering the same date — a scenario the
  write-side has never guarded against.
- **Performance is entirely unaddressed.** A per-day, five-repository, in-Python-combined read has
  no caching, batching, or range-query optimization proposed here (§5's range-helper question is
  explicitly left open). A range or multi-employee variant (§9, explicitly not proposed) would
  compound this immediately.
- **`User` ↔ `HrEmployee` gap** (confirmed still absent in both directions, §2) blocks any
  self-service or manager-scoped reconciliation view, though it does not block the base
  `employee_id`-parameterized `GET` form proposed in §9.
- **Systemic soft-delete/version gaps** (flagged unresolved in every prior discovery) apply here
  too: a hard-deleted `LeaveRequest`/`AttendanceEvent` (`BaseRepository.delete()` performs a real
  `session.delete()`, `repositories/base.py:59-66`) leaves no trace for reconciliation to explain
  a gap in the record, should one ever have existed and been removed.
- **No roadmap grounding**, consistent with every Time Management module since Leave (§1, §2).

---

## 12. Ambiguities

Per instructions, these are listed, not guessed at. Implementation should not proceed until they
are resolved:

1. **Day-result vocabulary.** What are the valid outcomes of reconciling one employee-day
   (`present`, `absent`, `late`, `half_day`, `on_leave`, `holiday`, `overtime`, some combination)?
   No precedent anywhere in the codebase defines this (§11).
2. **Precedence rules.** When an approved `LeaveRequest`, a `Holiday`, and one or more
   `AttendanceEvent` rows coexist for the same employee-date, what wins, and is more than one fact
   surfaced at once? Not decidable from the codebase.
3. **Overnight-shift day attribution.** Inherited unresolved from `ATTENDANCE_DESIGN.md` §10/§11.3
   — still unresolved after three subsequent PRs; directly load-bearing for Reconciliation.
4. **Timezone attribution.** Inherited unresolved from `ATTENDANCE_DESIGN.md` §10,
   `LEAVE_DESIGN.md` §11 — `Location` still has no timezone column.
5. **Frozen snapshot vs. live recompute.** Should a reconciliation result, once computed for a
   past date, ever be cached/persisted so a later correction to `AttendanceEvent`/`LeaveRequest`
   doesn't silently change history? Inherited unresolved from `TIMESHEET_DESIGN.md` §12/§13.6 —
   directly determines whether §3's "no persisted aggregate" recommendation holds under all future
   requirements or only for a first version.
6. **Range-query capability.** Should `BaseRepository` gain generic date-range (`BETWEEN`) support,
   or should each of `AttendanceEventRepository`/`LeaveRequestRepository`/`HolidayRepository`/
   `OvertimeRequestRepository` grow its own local range helper? Restated, not resolved, from
   `HOLIDAY_CALENDAR_DESIGN.md` §10.7/`TIMESHEET_DESIGN.md` §13.9 — this is now the fourth module
   to need it.
7. **Multi-employee / bulk reconciliation.** Explicitly not proposed in §9 — is a bulk report ever
   in scope, and if so, what are the performance implications of a five-repository read
   multiplied across many employees and dates?
8. **Whether Timesheet should be refactored to consume the reconciliation component** once it
   exists (§10) — a real, evidence-supported future direction, but a decision for a later PR, not
   this discovery.
9. **Product intent.** "Attendance Reconciliation" appears nowhere in
   `docs/product/06_PRODUCT_ROADMAP.md` (only bare "Attendance" appears, twice) — the same
   roadmap-silence gap already raised, unresolved, for Leave, Holiday, Timesheet, and Approval
   before it.
10. **Overlapping approved records.** Two approved `LeaveRequest`s (or an approved `LeaveRequest`
    and an approved `OvertimeRequest`) covering the same date for the same employee — is this
    possible today (§11 says yes, nothing prevents it at write time), and if so, how should
    Reconciliation resolve it?
11. **Concrete architectural form of the orchestration component.** Repository evidence supports
    the *category* (a dedicated, read-only, no-owned-entity component reading five repositories
    against a shared `uow.session`, §6/§7) but not a specific class, name, or internal structure.
    Whether this is a single new service shaped like `ApprovalService`, some other composition
    mechanism consistent with the same boundary conditions, or a shape not yet named in this
    discovery is explicitly **not resolved here** and is an architectural decision for the
    implementation PR (§13, §14).

---

## 13. Recommendation

**Repository evidence supports a dedicated read-only orchestration layer outside repositories and
aggregate CRUD services** (§3, §5, §6, §7 — the category shared by Option B). Concretely, this
means:

- No repository gains reconciliation logic (§5) — `TimesheetRepository`'s own precedent settles
  this directly.
- `AttendanceService` gains no reconciliation responsibility (§3, §7 Option A) — this would
  reverse an explicit, still-honored boundary `ATTENDANCE_DESIGN.md` §6 already drew.
- No new table, no new aggregate, no persisted projection (§3, §7 Option C) — `ATTENDANCE_DESIGN.md`
  §1 already rejected this shape for the identical reason (read-modify-write races, unconfirmed
  day-attribution rules), and nothing in this discovery supplies new evidence to reopen that
  rejection.
- Whatever component performs the composition should have no owned entity, follow the
  `uow_factory` / one-`uow`-per-call shape, read `AttendanceEventRepository`, `ShiftRepository`,
  `LeaveRequestRepository`, `HolidayRepository`, and `OvertimeRequestRepository` against a shared
  `uow.session` scoped to `employee_id` + a date/date-range (§4), and never write or call
  `uow.commit()` (§8).
- API surface is `GET`-only, parameterized by `employee_id` + date/date-range, not by a resource
  `{id}` (§9) — Reconciliation has no persisted identity to key a route on.

**However, repository evidence is insufficient to determine the final architectural shape or
naming of that component.** A prior draft of this document recommended a specific
`ReconciliationService` class, modeled on `ApprovalService`. That recommendation is withdrawn: the
`ApprovalService` analogy establishes that a non-CRUD, multi-repository-capable service *can* be
built in this codebase, but it does not establish that a single new service class of that exact
shape is the correct or only way to perform cross-aggregate *read composition* — a behavior
`ApprovalService` itself never performs (§1, §6). No service anywhere in this codebase combines
reads from more than one other repository into a single computed value; this specific composition
behavior is unprecedented regardless of which concrete component ends up implementing it (§11).

**The implementation PR should make that architectural decision explicitly — this discovery does
not.** What this document concludes, independent of that decision: the composition logic must sit
outside repositories, outside `AttendanceService`, and outside any persisted aggregate (§7,
Options A/C ruled out); it must be read-only (§8); and its public surface is `GET`-only (§9).
What component performs it — a service shaped like `ApprovalService`, a differently-structured
orchestration component, or some other mechanism consistent with those same boundaries — is left
open (§12.11), to be decided by whoever implements this feature, informed by this discovery's
boundary conclusions rather than by a name this discovery does not have the evidence to assign.

---

## 14. Implementation Readiness

**Not ready — and readiness here spans two distinct kinds of open item, which should not be
blurred.** Repository evidence in this discovery **defines the architectural boundaries**:
Reconciliation must not be a repository responsibility, must not be embedded in
`AttendanceService`, must not be a persisted aggregate, must be read-only, and must expose a
`GET`-only API (§3, §5, §7, §8, §9). That much is settled by evidence, not left open. What
repository evidence does **not** do is settle the concrete component that will satisfy those
boundaries. **The implementation PR will establish this repository's first precedent for
read-oriented, cross-aggregate orchestration** — there is nothing to extend, because nothing like
it exists yet (§1, §6, §11). That decision belongs to the implementation PR, made with the benefit
of this discovery's boundary conclusions, not to this discovery.

Separately, and regardless of how the implementation-PR architectural decision above is resolved,
at least six of the ambiguities in §12 are substantive, unresolved *business rules* (day-result
vocabulary, precedence, overnight-shift attribution, timezone, frozen-vs-live, overlap handling)
that determine what the computation actually produces, not just which component produces it. None
of these can be inferred from the repository as it stands — several have been open, unresolved,
since `ATTENDANCE_DESIGN.md` §11 (PR-039) and remain open after three subsequent PRs (Leave,
Holiday, Timesheet, Approval) that each could have — but did not — resolved them.

Concrete decisions required before implementation can begin, separated by kind:

**Architectural decision (implementation PR's to make, informed by §6/§7/§13, not by this
document)**:
1. **Concrete form of the orchestration component (§12.11)** — a service shaped like
   `ApprovalService`, a differently-structured component, or another mechanism consistent with the
   boundary conditions in §13. Repository evidence supports the boundary conditions; it does not
   support one specific answer to this question.

**Business-rule decisions (product/architecture input needed; not resolvable from the repository
by either this discovery or the implementation PR alone)**:
2. **Day-result vocabulary (§12.1)** — blocks the response shape of whatever component is chosen;
   nothing can be implemented without it.
3. **Precedence rules for conflicting facts (§12.2, §12.10)** — blocks the core combination logic.
4. **Overnight-shift day attribution and timezone attribution (§12.3, §12.4)** — inherited,
   still-unresolved blockers from `ATTENDANCE_DESIGN.md` §11, now directly load-bearing rather
   than a background risk.
5. **Frozen snapshot vs. live recompute (§12.5)** — determines whether §3/§13's "no persisted
   aggregate" conclusion is final or provisional.
6. **Range-query capability placement (§12.6)** — an implementation-time decision, not a hard
   blocker, but affects whether the eventual component's repository reads are efficient or require
   follow-up work.
7. **Confirmation that no roadmap/product decision supersedes this discovery (§12.9)**, given
   "Attendance Reconciliation" is named nowhere in `docs/product/06_PRODUCT_ROADMAP.md`.

**Stopping here per instructions.** No aggregate has been implemented, no migration has been
written, no code has been changed. Awaiting direction on the items above — particularly the
business-rule ambiguities (§12.1/§12.2), without which no implementation can begin regardless of
how the architectural-form decision (§12.11) is ultimately made — before proceeding.

---

# PR-048 (Implementation) — Step 1: Architecture Decision

Status: **Architecture decision only. No code, no migrations, no tests. Awaiting review.**

This section resolves §12.11/§14's "concrete architectural form" open item left by the discovery
above. It is an **implementation decision**, made with the benefit of the discovery's boundary
conclusions — it does not revise or re-litigate the discovery itself.

## A. Chosen implementation

**`ReconciliationService`**, in `services/reconciliation.py`: a class with a `uow_factory`-only
constructor, no owned entity, one `SQLAlchemyUnitOfWork` per call, repositories constructed
against the shared `uow.session`, wired into a router via a `get_reconciliation_service()` factory
+ `Depends()` — the same DI shape every router in this codebase already uses.

## B. Alternatives considered

- `AttendanceQueryService`
- `AttendanceReadService`
- Another orchestration component (a standalone function, a command/query object, or a new
  architectural layer distinct from "service")

## C. Justification

**Repository evidence supports implementing reconciliation as a dedicated capability-oriented
service because the repository already contains one capability-oriented orchestration service
(`ApprovalService`).** `ApprovalService` is named after the business capability it performs
(approval), not after any entity it owns — because it owns none, exactly the shape the discovery
establishes Reconciliation also needs (§6/§13 of the discovery). Every entity-owning service in
this codebase is instead named after its entity (`LeaveRequestService`, `TimesheetService`,
`HrEmployeeService`). `ReconciliationService` follows the one precedented naming convention for a
service in this position; `AttendanceQueryService`/`AttendanceReadService` do not — both prefix
the name with `Attendance`, a prefix the codebase already uses for an entity-owning service
(`AttendanceEventService`, scoped to the `attendance_events` table alone), and neither `*Query*`
nor `*Read*` appears anywhere else in this codebase as a naming pattern.

**This precedent is scoped narrowly, and should not be read more broadly than the evidence
supports.** `ApprovalService` is a precedent for the **service category** (a service with no
owned entity), the **dependency-injection pattern** (`uow_factory` constructor +
`get_x_service()`/`Depends()` wiring), **UnitOfWork usage** (one `uow` per call, repositories
built against a shared `uow.session`), and **repository coordination** (multiple repositories
instantiated side by side within one unit of work). It is **not** a precedent for:

- combining reads from multiple repositories,
- computing derived state,
- reconciliation algorithms, or
- precedence resolution.

Every `ApprovalService` method reads and writes exactly **one** repository per call
(`LeaveRequestRepository`, `OvertimeRequestRepository`, or `TimesheetRepository` — never more than
one, per the discovery's §6). Reconciliation must read **five** repositories and combine their
results into one computed value — a behavior with no precedent anywhere in this codebase,
regardless of which class performs it. Choosing `ReconciliationService` as the *name and shell* is
justified by the evidence above; it is not a claim that the *composition logic inside it* is
precedented. That logic — how facts from five aggregates resolve into a day's outcome — remains
new, unbuilt, and gated on the discovery's still-open business-rule ambiguities (§12.1, §12.2, and
related).

**Why the alternatives are less suitable, restated against this narrower justification:**

- `AttendanceQueryService`/`AttendanceReadService` do not misrepresent the *precedent* (neither
  claims more than `ReconciliationService` does about `ApprovalService`'s coverage) — they
  misrepresent *scope*, by prefixing the class with an entity name (`Attendance`) the codebase
  already uses for a narrower, entity-owning service. Adopting either risks a reader assuming this
  new component is scoped to `AttendanceEvent` alone, when the discovery's Input Analysis (§4)
  established it is not.
- A non-class, non-`uow_factory`-shaped component (standalone function, command/query object, new
  layer) is rejected on the same DI-practicality grounds as before: every injected component in
  this codebase is a class instance resolved via `Depends()`; adopting a different shape would
  introduce a second, parallel DI mechanism with no repository evidence supporting it, and the
  discovery's own §7 Option D already ruled out inventing a new architectural layer for lack of
  precedent.

## D. File impact

### Guaranteed

Required regardless of how the unresolved business-rule ambiguities (§12 of the discovery) are
eventually settled — these files exist because of the architecture decision made in this section,
not because of any business-rule decision:

- `services/reconciliation.py` — `ReconciliationService` class shell (constructor, DI-compatible
  shape). Method bodies performing the actual composition are gated on Section E below.
- `api/attendance_reconciliation.py` (or equivalently-named new router module) — `GET`-only
  router, `get_reconciliation_service()` factory, per the discovery's §9 API Boundary.
- `main.py` — router registration.

### Possible

Will probably exist, but final shape depends on business-rule decisions the discovery left open
(§12.1 day-result vocabulary, §12.2 precedence rules) — not yet designable:

- `schemas/reconciliation.py` — response DTO(s); field set blocked on §12.1/§12.2.
- `tests/test_reconciliation_service.py` — three-tier test coverage, matching the existing pattern;
  concrete test cases blocked on the same business rules as the schema.

### Blocked by unresolved architecture

Listed because the discovery **intentionally left the range-query architecture unresolved**
(§12.6) — whether `BaseRepository` gains generic range support or each repository grows its own
local helper. Do not imply these files will definitely change; whether they change, and how,
depends on a decision this document does not make:

- `repositories/attendance_event.py`
- `repositories/leave_request.py`
- `repositories/holiday.py`
- `repositories/overtime_request.py`
- `BaseRepository` (`repositories/base.py`)

**Stopping here per instructions.** No production code, migrations, models, repositories,
services, APIs, or tests have been written. Awaiting review before proceeding.
