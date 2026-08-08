# Shift Assignment — Capability Decision

**Capability:** Shift Assignment

**Status:** Approved — Boundary Decision Only (no schema, history, or lifecycle decided)

**Version:** 1

**Owner:** Architecture

---

# 1. Capability Ownership

**Does Shift Assignment own the employee ↔ shift relationship?**

- **Repository Evidence**: `discovery.md` §5 found no existing capability owns this relationship — `Shift`'s own docstring explicitly disclaims it (*"assigning a shift to an employee... out of scope"*), `HrEmployeeService` only validates `shift_id`'s existence, and `AttendanceEvent.shift_id` is independently validated with no cross-check against `HrEmployee.shift_id`.
- **Logical Consequence**: By elimination, if this relationship is owned by any capability, it is not owned by any that currently exists. This is the exact relationship in question for this candidate capability.
- **Decision: Yes** — Shift Assignment, as a candidate capability, is the only evidenced candidate owner of this relationship.

**Does it own `Shift`?**

- **Repository Evidence**: `Shift` already has its own service, repository, and API (`ShiftService`/`ShiftRepository`/`api/shifts.py`), predating this discovery, owning its own template fields (`start_time`, `end_time`, `break_duration_minutes`, `grace_period_minutes`).
- **Decision: No.** Shift Assignment would depend on `Shift` existing, not own it — the same non-ownership relationship `Assignment` (Project Tracking) already has to `Project`.

**Does it own `HrEmployee`?**

- **Repository Evidence**: `HrEmployee` already has its own service, repository, and API, owning its own fields independent of any shift concern.
- **Decision: No.** Shift Assignment would depend on `HrEmployee` existing, not own it — mirroring `Assignment`'s existing non-ownership relationship to `Employee`.

**Does it own Attendance?**

- **Repository Evidence**: `AttendanceEvent` already has its own service, repository, and API, independent of Shift Assignment.
- **Decision: No.** See §8 for the relationship direction.

**Ownership vs. dependency, stated explicitly**: Shift Assignment would *depend on* `Shift` and `HrEmployee` (both must exist for it to reference), without *owning* either — the same dependency-without-ownership shape `Assignment` already has toward `Employee` and `Project`.

---

# 2. Relationship with `HrEmployee`

- **Repository Evidence**: `HrEmployee.shift_id` already exists as a plain FK column directly on `HrEmployee` (`discovery.md` §2). Separately, `Assignment` — the repository's one precedent for modeling a relationship between two aggregates — exists as its own entity, not as a column on either `Employee` or `Project` (`discovery.md` §3).
- **Logical Consequence**: The repository already contains evidence for both shapes simultaneously: a relationship expressed as a plain FK column on one side (`HrEmployee.shift_id`, alongside `job_grade_id`/`employment_type_id`/`employment_status_id`) and a relationship expressed as its own separate entity (`Assignment`). Nothing in the repository establishes which shape applies when — both coexist for different relationships, and no document or code comment explains the choice between them for either case.
- **Decision: Undecidable from repository evidence alone.** Choosing between "part of `HrEmployee`" and "separate from `HrEmployee`" here would require either a normalization argument (explicitly prohibited by this task) or new repository evidence that does not exist. Not resolved here.

---

# 3. Relationship with `Shift`

- **Repository Evidence**: `Shift`'s own docstring states directly, in the codebase itself: *"assigning a shift to an employee, a work calendar, and rostering are all out of scope and belong to future modules."* This is an explicit, authored exclusion — not an absence inferred from silence.
- **Logical Consequence**: This is direct, first-party repository evidence that `Shift` itself does not intend to own assignment. This is stronger evidence than the by-elimination reasoning used for most other topics in this document.
- **Decision: Assignment belongs to Shift Assignment, not inside `Shift`.** This is the one topic in this document decidable from an explicit, authored statement rather than an absence.

---

# 4. Aggregate Classification

Each candidate evaluated independently; rejected only where repository evidence supports rejection, per instruction.

- **Aggregate Root** — **Repository Evidence**: `Assignment`, the one precedent for this kind of relationship, is a full `BaseEntity` subclass — independent identity (own `id`), own repository (`AssignmentRepository`), own complete CRUD lifecycle (`create`/`get`/`list`/`update`/`delete`), own service. **Not rejected** — directly supported by the one available precedent.
- **Child Entity** — **Repository Evidence**: no entity anywhere in the repository is accessed only through another aggregate's own repository/service (composed-but-not-independently-addressable). Even `Assignment`, which conceptually sits "between" two aggregates, has its own independent repository and service rather than being reachable only via `Employee`'s or `Project`'s own repository. **Rejected** — no repository precedent for this shape exists for a relationship-type entity.
- **Association Aggregate** — **Repository Evidence**: `discovery.md` §9 already identified this as the closest structural match to `Assignment`'s shape (two FKs to independent aggregates, its own payload, pair-uniqueness constraint). **Not rejected** — this and "Aggregate Root" above describe the same one precedent from two angles (persistence shape vs. conceptual role), not two independent findings.
- **Transactional Aggregate** — **Repository Evidence**: `discovery.md` §9 compared this directly against `AttendanceEvent`/`LeaveRequest`/`OvertimeRequest`/`Timesheet`/`Payslip` — each records a discrete fact or event scoped to one employee, not a standing relationship between two aggregates. **Rejected** — direct structural mismatch, not merely unprecedented.
- **Domain Service** — **Repository Evidence**: `discovery.md` §9 compared this directly against `ApprovalService`/`ReconciliationService` — both orchestrate reads/writes across other capabilities' repositories with no owned table. A standing employee↔shift relationship is not an orchestration invoked per request. **Rejected** — direct structural mismatch.
- **Value Object** — **Repository Evidence**: this repository's one established Value Object precedent, `LeaveBalance.period_year`, is a bare `Integer` column with no independent identity, scoped to a single entity. A Shift↔Employee relationship, per §3, concerns two independent aggregates (`Shift`, `HrEmployee`), not a scalar field on one entity. **Rejected** — direct structural mismatch.
- **Projection** — **Repository Evidence**: `discovery.md` §9 found zero read-model, projection, or materialized-view pattern anywhere in the repository to compare against. **Unknown, not rejected** — there is no positive or negative evidence either way, the same treatment this governance trail has given other candidates with zero precedent to compare against (e.g., "Library"/"Utility" in Monetary Representation's own decision).

**Result**: Three candidates rejected on direct structural mismatch (Child Entity, Transactional Aggregate, Domain Service, Value Object — four, not three); Aggregate Root and Association Aggregate both supported by the one available precedent (two descriptions of the same shape); Projection remains `Unknown`. No single winner is forced.

---

# 5. Existing FK Model

- **Repository Evidence**: `discovery.md` found `HrEmployee.shift_id` and `AttendanceEvent.shift_id` are both plain, current-value-only FK columns — no history, no effective dating, no dedicated entity, and (per `ATTENDANCE_DESIGN.md`, cited in `discovery.md` §5) explicitly unvalidated against each other.
- **Logical Consequence**: These FKs capture only the current state of each relationship at read time, are silently overwritten on update with no record of the prior value, and the two independent references to "an employee's shift" are never reconciled with each other. This is the same plain-FK shape used for every other current-value master-data reference on `HrEmployee` (`job_grade_id`, `employment_type_id`, `employment_status_id`).
- **Are they sufficient, transitional, unrelated, or undecidable?** **Not unrelated** — they are the exact mechanism this capability concerns. Whether they are **sufficient** (adequate for whatever this capability's eventual scope turns out to be) or merely **transitional** (a stand-in ahead of a dedicated mechanism) is **Undecidable** from repository evidence: no requirements document states what "sufficient" would mean, and no code comment or docstring frames either FK as temporary or provisional. `Shift`'s own docstring excludes assignment from *`Shift`* (§3) but says nothing about the *permanence* of `HrEmployee.shift_id` itself.

---

# 6. Lifecycle Ownership

- **Repository Evidence**: `discovery.md` §6 found zero dedicated mechanism anywhere in the repository for assignment, reassignment, replacement, activation, or deactivation as distinct operations — every "reassignment" found in the repository is ordinary field overwrite via `update()`.
- **Logical Consequence**: Today, by strict current-code fact, `HrEmployeeService.update()` is the only code path that can change `HrEmployee.shift_id` — this makes it the incidental current owner of the *mechanism*, in the same way it incidentally owns changing `organization_id`/`department_id`. This is evidence of where the current plain-overwrite mechanism happens to live, not evidence that `HrEmployeeService` conceptually owns "shift reassignment" as a distinct lifecycle concept.
- **Unknown**: Whether a dedicated lifecycle (assignment/reassignment/replacement/activation/deactivation as distinct, trackable operations, each conceptually separate from the others) should exist at all, and if so whether Shift Assignment or `HrEmployeeService` would own it — not decidable, since no such lifecycle concept currently exists anywhere to assign ownership of. No lifecycle rule is invented here, per instruction.

---

# 7. Effective Dating

- **Repository Evidence**: `discovery.md` §4 found zero effective-dating mechanism anywhere in the repository. The one relevant precedent, `Assignment`, carries its own `start_date`/`end_date` as part of its own payload — owned by the association entity itself, not by either `Employee` or `Project`.
- **Logical Consequence**: By direct structural analogy to the one available precedent, *if* effective dating is ever introduced for the employee↔shift relationship, the repository's own established pattern places that concern on the association entity itself, not on `Shift` or `HrEmployee` individually.
- **Decision (conceptual ownership only, not existence)**: If effective dating for this relationship is ever built, it would conceptually belong to Shift Assignment, mirroring `Assignment`'s own already-existing shape. **Whether it should exist at all is not addressed here**, per instruction.

---

# 8. Attendance Relationship

- **Repository Evidence**: `AttendanceEvent.shift_id` is independent of and unvalidated against `HrEmployee.shift_id` (`discovery.md` §5). `discovery.md` §9 classified `AttendanceEvent` as a Transactional Aggregate (a discrete recorded fact), structurally distinct from an Association Aggregate (§4 above).
- **Logical Consequence**: A Transactional Aggregate, by the shape already rejected for it in §4, does not itself hold a standing relationship — it would, at most, reference one. `AttendanceEvent` today does not own an assignment concept (none exists) and does not consume one either (nothing exists yet to consume).
- **Decision: Neither, today** — stated as current repository fact. **If Shift Assignment comes to exist**, the only structurally consistent direction (by the same Transactional-Aggregate-vs-Association-Aggregate distinction already drawn in §4) would be for `AttendanceEvent` to *consume* it, not own it — this is a logical implication of the existing classification, not a decision that `AttendanceEvent` will be changed.

---

# 9. Authorization

- **Repository Evidence**: `discovery.md` §7 found zero references to "shift" anywhere in any authorization-related service file. No authorization policy anywhere addresses `Shift`, shift assignment, or any related concept.
- **Decision**: Shift Assignment does not own authorization today — there is nothing to own, since no resource or Service exists for it yet.
- **Who does, if not Shift Assignment?** **Not decidable today.** This mirrors the identical structural finding already reached independently for every other capability in this governance trail (Payroll, Payslip, Payroll Calculation, Compensation, Monetary Representation): no resource or Service exists yet for `AuthorizationRequest.resource` to resolve against. No other capability is evidenced as already owning shift-related authorization — the zero-match grep covered every authorization file in the repository, not only this candidate's own scope.

---

# 10. Producer / Consumer Direction

**Producers** (repository-evidenced, pre-existing):
- `Shift` — produces the shift template a Shift Assignment would reference.
- `HrEmployee` — produces the employee record a Shift Assignment would reference.

**Consumers**:
- No capability currently consumes a "Shift Assignment" concept, since none exists in code today.
- `LeaveRequest` is a documented, evidenced **candidate**: `LEAVE_DESIGN.md` (cited in `discovery.md` §8) explicitly names "shift reassignment mid-request" as an unconfirmed open question for `LeaveRequest`. This is repository-evidenced as a *documented, unconfirmed* interest — not a confirmed consumer.
- `AttendanceEvent` is not currently a consumer (§8) — its own `shift_id` is independent and unvalidated against anything today. If Shift Assignment comes to exist, `AttendanceEvent` is the structurally consistent candidate consumer (§8), not confirmed.

No other capability in this governance trail's documents names Shift Assignment as a producer, consumer, or dependency anywhere.

---

# 11. Deferred Decisions

Not solved here:

- Whether Shift Assignment should be part of `HrEmployee` (a field) or a separate entity (§2).
- Whether the existing `HrEmployee.shift_id`/`AttendanceEvent.shift_id` FKs are sufficient as-is or merely transitional scaffolding (§5).
- Whether a dedicated lifecycle (assignment/reassignment/replacement/activation/deactivation) should exist, and who would own it if so (§6).
- Whether effective dating should exist at all for this relationship (§7 — only conceptual ownership-if-it-exists was addressed).
- Whether `AttendanceEvent.shift_id` should ever be validated against or derived from a Shift Assignment concept (§8).
- Whether `LeaveRequest` becomes a real consumer (§8, §10).
- Authorization ownership (§9) — deferred, consistent with every other capability in this trail.
- Whether "Aggregate Root" and "Association Aggregate" are meaningfully distinct categories in this repository's own vocabulary, or two descriptions of one precedent (§4).
- Whether "Projection" is genuinely inapplicable or merely unprecedented (§4) — left `Unknown`, not rejected.
- Whether "Shift Assignment" is the correct or final capability name — it originates from this governance trail's own task framing, not from any pre-existing repository source.

---

# 12. Recommendation

```
Domain Model Discovery may begin.
```

Ownership is decided by elimination (§1), the relationship with `Shift` is decided on direct, first-party repository evidence — an authored exclusion, not an absence (§3) — and aggregate classification meaningfully narrowed four candidates on direct structural grounds while leaving only one genuinely `Unknown` (§4). This is a comparable or greater degree of resolution than Monetary Representation's own `decision.md` reached at the same stage, which also recommended proceeding to Domain Model Discovery with several structural classifications and all content-level questions still open. The unresolved items (§11) are appropriately left to a Domain Model Discovery pass, not to another Discovery round — no new repository search is expected to change any of them (each was already checked exhaustively in `discovery.md`).

---

# References

- `docs/architecture/capabilities/shift-assignment/discovery.md`
- `docs/architecture/capabilities/compensation/capability-boundary-analysis.md`, `docs/architecture/capabilities/monetary-representation/decision.md` (methodology and terminology precedent for aggregate-classification reasoning and Unknown-vs-Rejected treatment)
- `services/api/src/eop_api/models/shift.py`, `hr_employee.py`, `assignment.py`, `attendance_event.py`, `leave_balance.py`
