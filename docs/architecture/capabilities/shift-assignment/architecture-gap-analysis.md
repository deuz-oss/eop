# Shift Assignment — Architecture Gap Analysis

**Status:** Complete

**Capability:** Shift Assignment

**Owner:** EOP Architecture Governance

**Based On:** `discovery.md`, `decision.md`, `domain-model-discovery.md`

---

# 1. Architectural Readiness

| Component | Classification | Repository Evidence |
|---|---|---|
| `BaseEntity` | **Sufficient** | Every persisted entity, including `Assignment` (`domain-model-discovery.md` §2), uses `UUIDMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin`/`VersionMixin` via `BaseEntity`. Both behaviorally-supported aggregate candidates (Aggregate Root, Association Aggregate — `domain-model-discovery.md` §1) are `BaseEntity`-shaped; only the still-`Unknown` Projection candidate would not need it. |
| `BaseRepository` | **Sufficient** | `AssignmentRepository` already extends `BaseRepository[Assignment]` with no overrides beyond a lookup helper — directly proven, working infrastructure for the same aggregate shape Shift Assignment would most plausibly take. |
| Repository pattern (concrete repository per aggregate) | **Sufficient** | Same evidence as above — `ShiftRepository`, `AssignmentRepository` both follow this pattern without exception. |
| `UnitOfWork` | **Sufficient** | `AssignmentService` and every other reviewed service use `SQLAlchemyUnitOfWork` uniformly — proven, working infrastructure with no exceptions found. |
| API layering (`API → Service → UoW → Repository → Model`) | **Sufficient** | `Assignment`'s own full stack (`api/assignments.py` → `AssignmentService` → `SQLAlchemyUnitOfWork` → `AssignmentRepository` → `Assignment`) already implements this exact layering for a structurally comparable aggregate. |
| Authorization Foundation | **Unknown** | `domain-model-discovery.md` §8 found genuine, unresolved ambiguity — Shift Assignment resembles both the unauthorized majority (`Shift`, `HrEmployee`, `Assignment` itself — 8 of 11 reviewed capabilities) and, less directly, the authorized minority (`LeaveRequest`, `AttendanceEvent`). Neither is confirmed. |
| `EventService` | **Not Applicable** | No document in this capability's own governance trail, nor any prior capability's, connects `EventService` to a shift-assignment concern. `EventService` remains dormant with zero callers repository-wide (established fact, restated). |
| `JobService` | **Not Applicable** | Same reasoning as `EventService` — no evidence of any background-execution need anywhere in this capability's governance. |

---

# 2. Missing Concepts

Each classified as exactly one category, per instruction.

**Repository Gap** (a technical capability the repository does not provide anywhere, independent of any pending decision):
- **Date-scoped/overlap-aware uniqueness enforcement** — no mechanism anywhere in the repository enforces "at most one active row for a given pair as of a given date." `Assignment`'s own `UniqueConstraint("employee_id", "project_id")` is not date-aware (`domain-model-discovery.md` §2, restated) — even if the relationship-shape decision (below) favored a date-scoped constraint, no existing pattern provides one.
- **Point-in-time / historical FK-value querying** — no mechanism anywhere answers "what was this relationship's value as of a past date" (`domain-model-discovery.md` §5, confirmed absence repository-wide). This is a genuine technical absence, separate from whether it is ever needed.

**Governance Gap** (an architecture decision not yet made, not blocked on new evidence):
- **Relationship shape** — plain FK (current state), peer-association entity, or repeatable-fact-row entity (`domain-model-discovery.md` §3) — three shapes coexist as repository precedent with nothing distinguishing which applies.
- **Delete rule** — `CASCADE` (`Assignment`'s own precedent) vs. `RESTRICT` (every other entity relevant to this context) (`domain-model-discovery.md` §3).
- **`AttendanceEvent` cross-validation** — whether `AttendanceEvent.shift_id` should ever be validated against a Shift Assignment concept (`decision.md` §8, `domain-model-discovery.md` §6; already flagged unconfirmed in `ATTENDANCE_DESIGN.md`).
- **Existing-FK sufficiency** — whether `HrEmployee.shift_id`/`AttendanceEvent.shift_id` as they exist today are adequate or merely transitional (`decision.md` §5).
- **Authorization mechanism applicability** — whether Shift Assignment needs a dedicated evaluator at all (`domain-model-discovery.md` §8) — distinct from the policy content itself, listed below.

**Business Gap** (depends on product/business requirements this repository does not contain):
- **Effective dating / historical-treatment necessity** — whether the business needs to know a shift assignment's value as of a past date at all (`decision.md` §7; `domain-model-discovery.md` §5-6).
- **Dedicated lifecycle necessity** — whether reassignment/replacement/activation/deactivation need to exist as distinct, trackable operations, or whether plain field overwrite (the only pattern that exists anywhere today) remains sufficient (`decision.md` §6).
- **`LeaveRequest` shift-hour consumption** — whether `LeaveRequest` needs shift-hour data for partial-day math; `LEAVE_DESIGN.md` itself labels this unconfirmed (`discovery.md` §8, `domain-model-discovery.md` §9).
- **Authorization policy content** — *if* a dedicated evaluator is ever built (Governance Gap above), who specifically may reassign a shift is a business-process question, not an architecture one.

**External Dependency**: **None found.** No third-party system, external data source, or capability outside this repository's own control is evidenced anywhere across `discovery.md`, `decision.md`, or `domain-model-discovery.md` — confirmed absent, not omitted.

---

# 3. Existing Infrastructure

Applicability only — no reuse recommendation, per instruction.

| Component | Classification | Repository Evidence |
|---|---|---|
| `Assignment` | **Applicable as structural precedent, not as reusable code** | `domain-model-discovery.md` §1/§3 found this the closest behavioral and structural match anywhere in the repository (Aggregate Root + Association Aggregate shape). It is Project Tracking's own aggregate, tied to `Employee`/`Project` — not directly reusable, but its shape is the most applicable comparison available. |
| `AuditLog` | **Not Applicable** | A fresh grep confirms `AuditLog` is referenced only within its own service file (`services/audit_log.py`) — no other reviewed service (`Shift`, `HrEmployee`, `AttendanceEvent`, `Assignment`) populates or reads it. No working audit trail exists to extend. |
| `AuditMixin` | **Not Applicable** | Composed into every `BaseEntity` mechanically, including `Assignment`, but `created_by`/`updated_by` are populated by nothing anywhere in the repository — an established, repeated finding across this governance trail. Present on paper, functionally inert. |
| `EventService` | **Not Applicable** | Dormant, zero callers repository-wide; no document anywhere connects it to a shift-assignment concern (§1, restated). |
| `JobService` | **Not Applicable** | Same reasoning as `EventService`. |
| Authorization Foundation | **Unknown** | Same genuine ambiguity as §1 — cannot be confirmed applicable or ruled out from repository evidence. |

---

# 4. Upstream Dependencies

| Capability | Classification | Reasoning |
|---|---|---|
| `HrEmployee` | **Already Exists** | Merged, implemented code (`decision.md` §1) — Shift Assignment would depend on it without owning it. |
| `Shift` | **Already Exists** | Merged, implemented code (`decision.md` §1) — same dependency-without-ownership relationship. |
| `AttendanceEvent` | **Not Required** | Already exists, but `decision.md` §8/`domain-model-discovery.md` §6 establish it as, at most, a *future consumer* (§5 below) — not a prerequisite for Shift Assignment to be built. |
| `LeaveRequest` | **Not Required** | Same reasoning — a documented, unconfirmed candidate *consumer* (`discovery.md` §8), not a prerequisite. |

**Logical Consequence**: Both real prerequisites (`HrEmployee`, `Shift`) already exist and are merged. Shift Assignment does not wait on any capability to be built first — mirroring the same finding already reached for Monetary Representation's own upstream-dependency analysis, though for a different underlying reason (there, the candidate was evidenced as upstream of its consumers; here, both actual dependencies simply already exist in code).

---

# 5. Downstream Dependencies

Restated from `domain-model-discovery.md` §9, not re-derived:

- **Confirmed**: None. Nothing in code currently consumes a Shift Assignment concept, since it does not yet exist.
- **Documented**: `LeaveRequest` — `LEAVE_DESIGN.md`'s own "Shift changes" section names "shift reassignment mid-request" as an unconfirmed open question.
- **Unknown**: `AttendanceEvent` — structurally plausible as a future consumer (`decision.md` §8), but this is this governance trail's own logical inference, not a statement authored anywhere in repository documentation.

---

# 6. Blocking Unknowns

Consolidated only from `discovery.md`, `decision.md`, and `domain-model-discovery.md`. Nothing new added.

1. **Relationship shape / entity boundary** (`decision.md` §2, §5; `domain-model-discovery.md` §3) — *Why unresolved*: the repository contains working precedent for three different shapes (plain FK, peer-association, repeatable-fact-row) with nothing distinguishing which applies to this relationship. *Why more repository search would not help*: this ambiguity has been checked across three separate phases of this capability's own governance and has not narrowed; it is a design choice, not an undiscovered fact.

2. **Delete rule** (`domain-model-discovery.md` §3) — *Why unresolved*: `Assignment`, the only "association" precedent, uses `CASCADE`; every other entity relevant to this context uses `RESTRICT` without exception. The repository itself is internally split. *Why more search would not help*: this is the complete set of `ondelete` conventions found anywhere touching `HrEmployee`/`Shift`; nothing further exists to find.

3. **Authorization posture** (`decision.md` §9; `domain-model-discovery.md` §8) — *Why unresolved*: Shift Assignment structurally resembles both the unauthorized majority and, less directly, the authorized minority, and no repository fact breaks the tie. *Why more search would not help*: this is the same structural gap already found identically for every other capability in this governance trail — no resource or Service exists yet for `AuthorizationRequest.resource` to resolve against.

4. **`AttendanceEvent` cross-validation** (`decision.md` §8; `domain-model-discovery.md` §6) — *Why unresolved*: `ATTENDANCE_DESIGN.md` itself already flags whether `AttendanceEvent.shift_id` must match the employee's currently-assigned shift as unconfirmed, and no later document resolves it. *Why more search would not help*: this has been an open, explicitly-flagged question since before this capability's governance began; three fresh phases of dedicated discovery have not changed it.

5. **Existing-FK sufficiency** (`decision.md` §5) — *Why unresolved*: no requirements document states what "sufficient" would mean for this relationship, and no code comment frames either existing FK as permanent or transitional. *Why more search would not help*: this is an absence of stated intent, not an undiscovered fact — nothing in the codebase could resolve it either way.

6. **Effective dating / historical-treatment necessity** (`decision.md` §7; `domain-model-discovery.md` §5-6) — *Why unresolved*: no repository evidence establishes whether the business needs point-in-time shift-assignment history, and `AttendanceEvent`'s own independent, potentially point-in-time-historical `shift_id` raises an unresolved consistency question. *Why more search would not help*: confirmed absent at every phase (`discovery.md` §4, `domain-model-discovery.md` §5) — this is a business-requirements question the repository's code cannot answer.

7. **Dedicated lifecycle necessity** (`decision.md` §6) — *Why unresolved*: no capability anywhere in the repository models reassignment/activation/deactivation as distinct operations; whether Shift Assignment should be the first is unevidenced either way. *Why more search would not help*: absence confirmed exhaustively in `discovery.md` §6.

8. **`LeaveRequest` consumption** (`discovery.md` §8; `domain-model-discovery.md` §9) — *Why unresolved*: `LEAVE_DESIGN.md` itself labels this unconfirmed, and it depends on `LeaveRequest`'s own governance, not Shift Assignment's. *Why more search would not help*: the source document already states this is undecided.

9. **Date-scoped uniqueness mechanism** (`domain-model-discovery.md` §2) — *Why unresolved*: depends on both the relationship-shape and effective-dating decisions above, and no existing repository pattern (date-aware or otherwise) provides a model to follow. *Why more search would not help*: confirmed exhaustively absent repository-wide (§2 above).

10. **Capability naming** (`decision.md` §11) — *Why unresolved*: "Shift Assignment" originates from this governance trail's own task framing, not any pre-existing repository source, and no competing or confirming terminology exists anywhere in `docs/`. *Why more search would not help*: already searched exhaustively in `discovery.md`.

---

# 7. Can Iteration 1 Begin?

```
No
```

Two of the Blocking Unknowns (§6.1, §6.2 — relationship shape and delete rule) are not content-level gaps but structural ones: any code written today would have to silently choose a uniqueness constraint (or its absence) and a delete rule, both of which are explicitly undecided and both of which the hard constraints of this document (and of any implementation task) forbid inventing. Unlike Payroll's or Payslip's own Iteration 1, where a single confirmed shape existed to scaffold minimally, Shift Assignment has two live, evidenced, mutually-exclusive shapes and no basis in repository evidence to pick between them. No minimum model is proposed here, per instruction.

---

# 8. Remaining Risks

Restated only from prior documents, none invented:

- Building the wrong relationship shape — over-constraining with pair-uniqueness if a repeatable-fact-row shape was actually needed, or under-constraining the reverse (`domain-model-discovery.md` §3).
- A delete-rule mismatch with the rest of the HR domain if `CASCADE` is carried over from `Assignment` without reconciling with the `RESTRICT` convention used everywhere else this capability would touch (`domain-model-discovery.md` §3).
- `AttendanceEvent`'s already-independent, unvalidated `shift_id` continuing to diverge from whatever "current" shift-assignment model is eventually built, with no reconciliation mechanism (`domain-model-discovery.md` §6).
- Effective dating being needed later but not planned for now — the same "future synchronization" gap already flagged for `LeaveBalance`'s own `period_year` shape (`discovery.md` §4, `domain-model-discovery.md` §5).
- Authorization being retrofitted later if Shift Assignment turns out to need Leave/Attendance-style dedicated-evaluator treatment rather than the CRUD-majority treatment it currently resembles (`domain-model-discovery.md` §8).

---

# 9. Recommendation

```
Additional Governance Required
```

Not **Waiting for New Capability**: §4 found both real upstream dependencies (`HrEmployee`, `Shift`) already exist and are merged — nothing needs to be built first. Not **Capability Rejected**: substantial, consistent evidence across three governance phases supports this being a genuine gap (`Shift`'s own explicit docstring exclusion, `decision.md` §3; two independently-usable relationship shapes already proven in the repository, §3 above). Not **Architecture Review may begin**: two structural, non-content decisions (relationship shape, delete rule — §6.1-2) remain genuinely open, with no repository evidence to resolve either, leaving no stable target for a consistency review. The blocking items in §6 are architecture and business decisions the same way Monetary Representation's own blockers were at this stage — not missing repository evidence and not a missing capability — making Additional Governance Required the precise fit.

---

# References

- `docs/architecture/capabilities/shift-assignment/discovery.md`
- `docs/architecture/capabilities/shift-assignment/decision.md`
- `docs/architecture/capabilities/shift-assignment/domain-model-discovery.md`
- `docs/architecture/capabilities/monetary-representation/architecture-gap-analysis.md` (classification taxonomy and recommendation precedent)
