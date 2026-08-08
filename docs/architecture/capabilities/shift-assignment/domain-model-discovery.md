# Shift Assignment — Domain Model Discovery

**Status:** Complete

**Capability:** Shift Assignment

**Owner:** EOP Architecture Governance

**Depends On:** `docs/architecture/capabilities/shift-assignment/discovery.md`, `docs/architecture/capabilities/shift-assignment/decision.md`

---

# Purpose

This document discovers the domain model shape for Shift Assignment using repository precedent only. Ownership, the relationship with `Shift`, the relationship with `HrEmployee`, and the Unknowns already recorded in `decision.md` are not reopened here. Every conclusion is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**.

---

# 1. Aggregate Candidates — Behavioral Evaluation

Not a repeat of `decision.md` §4's classification vote — this evaluates how each candidate would *behave* as a domain model, rejecting only where repository evidence supports rejection.

- **Aggregate Root** — **Repository Evidence**: `Assignment` behaves as one — independently created/read/updated/deleted through its own service, queryable by its own `id`, listable without going through `Employee`'s or `Project`'s own repository. **Not rejected**: if Shift Assignment followed this shape, it would behave identically — independently addressable, not reachable only via `HrEmployee` or `Shift`.
- **Association Aggregate** — **Repository Evidence**: `Assignment` enforces a pair-based `UniqueConstraint("employee_id", "project_id")` and a cross-aggregate consistency check (`OrganizationMismatchError`) at creation and update. **Not rejected**: the same behavioral shape — enforcing at most one row per referenced pair, validating both referenced aggregates exist and are mutually consistent — is directly reusable behavior, not merely a label.
- **Child Entity** — **Repository Evidence**: no entity anywhere in the repository is created, read, or updated only through another aggregate's own service/repository. Even `Assignment`, conceptually "between" two aggregates, is independently addressable. **Rejected**: no repository precedent behaves this way for any relationship-type entity.
- **Transactional Aggregate** — **Repository Evidence**: `AttendanceEvent`/`LeaveRequest`/`OvertimeRequest` behave as append-heavy discrete-fact records — each row represents one occurrence, not a queryable "current state" of a standing relationship. **Rejected behaviorally**: a standing employee↔shift relationship needs a "what shift is this employee on right now" query, which a discrete-event log does not directly answer without additional aggregation logic this repository does not have precedent for.
- **Domain Service** — **Repository Evidence**: `ApprovalService`/`ReconciliationService` behave as stateless orchestrators — no owned table, they read/mutate other aggregates' rows per invocation. **Rejected behaviorally**: Shift Assignment inherently needs to persist "employee X is assigned shift Y" as its own durable fact, which a stateless orchestrator does not do.
- **Value Object** — **Repository Evidence**: `LeaveBalance.period_year` behaves as an inline scalar — no independent identity, no independent repository, created/updated only as part of its parent row. **Rejected behaviorally**: a Shift↔Employee relationship needs independent identity and independent queryability (§2), which no Value Object in this repository has ever exhibited.
- **Projection** — **Repository Evidence**: no read-model, projection, or materialized-view pattern exists anywhere. The closest available comparison, `ReconciliationService`, computes a transient, non-persisted classification across multiple repositories per request rather than persisting a derived row. **Unknown, not rejected**: there is no positive or negative repository evidence to compare a Projection's specific behavior (a persisted or cached *derived* view) against.

**Result**: Four candidates rejected on direct behavioral mismatch (Child Entity, Transactional Aggregate, Domain Service, Value Object); Aggregate Root and Association Aggregate both behaviorally supported by the one available precedent (`Assignment`); Projection remains `Unknown`.

---

# 2. Identity

**Repository Evidence**: Every persisted entity in the repository, including `Assignment`, uses `UUIDMixin` — a generated UUID primary key via `BaseEntity`, retrieved through `BaseRepository.get(id)`. `Assignment` additionally enforces a natural-key-shaped constraint, `UniqueConstraint("employee_id", "project_id")`, but its actual identity for lookup purposes remains the UUID; the constraint only prevents a second row for the same pair, it is not itself used as a lookup key anywhere in `AssignmentRepository`.

**Logical Consequence**: If Shift Assignment becomes its own aggregate, identity would most plausibly follow this same uniform pattern: a UUID primary key via `BaseEntity`, with a plausible pair-based uniqueness constraint (`employee_id` + `shift_id`) mirroring `Assignment`'s own constraint shape exactly. No identifier scheme is invented here — this restates the one pattern already used for every persisted entity in the repository.

**Unknown**: Whether a pair-uniqueness constraint would need to account for time is not decidable — `Assignment`'s own constraint is not date-scoped (a second row for the same pair cannot exist even after `end_date` has passed, per `discovery.md` §3), so mirroring it exactly would carry the same limitation forward. Whether that limitation is acceptable for Shift Assignment is not addressed here.

---

# 3. Relationship Model — Structural Comparison Only

No pattern is chosen; comparison only, per instruction.

| Entity | FKs | Delete Rule | Own Payload | Pair Uniqueness | Recurs Over Time |
|---|---|---|---|---|---|
| `Assignment` | `employee_id` → `employees`, `project_id` → `projects` | `CASCADE` (both) | `role`, `start_date`, `end_date` | Yes — one row per pair | No — blocked by the uniqueness constraint |
| `LeaveBalance` | `employee_id` → `hr_employees` | `RESTRICT` | `period_year`, `allocated_days`, `used_days`, `remaining_days` | Not found — no compound constraint on `(employee_id, period_year)` | Yes — nothing prevents multiple rows |
| `AttendanceEvent` | `employee_id` → `hr_employees`, `shift_id` → `shifts` | `RESTRICT` (both) | `event_type`, `event_time`, `remarks` | None | Yes — many events expected per employee/shift |
| `HrEmployee` | Many single FKs to master data (`organization_id`, `department_id`, `shift_id`, etc.) | `RESTRICT` (all) | N/A — each FK is a plain current-value column | N/A | No — one current value per column, overwritten |
| `Shift` | None (referenced, not referencing) | N/A | N/A | N/A | N/A |

**Repository Evidence**: Two structurally distinct, both-reusable relationship shapes coexist in the repository today:
- **Peer association with pair-uniqueness** (`Assignment`) — enforces at most one standing row per referenced pair, carries its own payload, uses `CASCADE`.
- **Repeatable fact row** (`AttendanceEvent`, `LeaveBalance`) — allows multiple rows referencing the same pair over time, no compound uniqueness, uses `RESTRICT`.

**Logical Consequence**: These two shapes differ specifically on whether a referenced pair can recur, and on delete rule. Notably, `Assignment` — the only precedent for a "peer association" shape — is also the only entity among all five compared here that uses `CASCADE` rather than `RESTRICT`; every other entity that touches `HrEmployee` or `Shift` (`LeaveBalance`, `AttendanceEvent`, `HrEmployee`'s own FKs) uses `RESTRICT` without exception. This is a real, evidenced divergence between the one available "association" precedent and the delete-rule convention used everywhere else Shift Assignment would need to relate.

**Unknown**: Which of these two reusable shapes fits Shift Assignment's eventual needs, and how the `CASCADE`/`RESTRICT` divergence would be resolved if the "peer association" shape were followed — not decided, comparison only.

---

# 4. Lifecycle Model

**Repository Evidence**: Exactly two lifecycle-adjacent patterns exist anywhere in the repository:
1. **Plain FK overwrite** — used for every current-value FK column (`HrEmployee.shift_id`, `department_id`, etc.) via ordinary `update()`. No record of the prior value, no event, a single in-place mutation.
2. **`Assignment.start_date`/`end_date`** — set at creation and mutable via the same generic `update()` path as any other field (confirmed in `AssignmentService.update`). No automatic transition logic exists — `end_date` is not populated by any distinct "close out"/terminate operation; it is set the same way `role` or any other field is set.

**Logical Consequence**: Neither pattern constitutes a lifecycle in the sense of distinct, named state-transition operations — both are variations of "set a field via ordinary `update()`." No two-step create-then-terminate operation exists anywhere in the repository for any entity.

**Unknown**: Whether Shift Assignment would need lifecycle behavior beyond these two existing patterns — not addressed; no new lifecycle behavior is invented here, per instruction.

---

# 5. Temporal Modeling

**Repository Evidence**: `discovery.md` §4 confirmed zero `effective_from`/`effective_to`/`valid_from`/`valid_to` field anywhere, and zero `*History`/`*Snapshot`/`*Revision` entity class anywhere (fresh, repository-wide search). The only date-range field anywhere in the repository is `Assignment.start_date`/`end_date` (§3, §4). The only non-date temporal partition anywhere is `LeaveBalance.period_year`, a bare `Integer` year, not a true date range. `VersionMixin` exists on `BaseEntity` but — consistent with every other capability's own domain-model-discovery in this governance trail — is never read or incremented by any application code found anywhere.

**Logical Consequence**: No versioning mechanism and no historical-record pattern exists anywhere in the repository, for any entity, without exception.

**Unknown**: Whether Shift Assignment would need temporal treatment beyond `Assignment`'s own plain `start_date`/`end_date` shape — not decided here. `decision.md` §7 already established, as a Deferred Decision, that *if* effective dating for this relationship is ever built, it would conceptually belong to Shift Assignment itself, not to `Shift` or `HrEmployee` — that conclusion is restated as context, not reopened.

---

# 6. Attendance Relationship

**Repository Evidence**: `AttendanceEvent.shift_id` is a required, independent FK, unvalidated against `HrEmployee.shift_id` (`discovery.md` §5, `decision.md` §8, both restated).

**Logical Consequence**: This existing FK is itself evidence that the repository already tolerates two independent sources for "an employee's shift" at any given moment — `HrEmployee.shift_id` (the assumed current shift) and each `AttendanceEvent.shift_id` (the shift recorded at the moment of a specific clock event, which may not match today's `HrEmployee.shift_id` if a reassignment happened since). This has a direct domain-model implication: a Shift Assignment model that only tracks *current* state (mirroring `HrEmployee.shift_id`) would not, by itself, explain or reconcile `AttendanceEvent`'s own independent, potentially point-in-time-historical `shift_id` values.

**Unknown**: Whether this means Shift Assignment's domain model needs a historical component to stay consistent with `AttendanceEvent`'s existing shape, or whether the two are intended to remain permanently independent — not decided. No redesign of `AttendanceEvent` is proposed, per instruction.

---

# 7. Invariants

Only what is directly supported by `decision.md` or unambiguous structural fact — restated, not re-derived:

- Shift Assignment does not own `Shift` or `HrEmployee` (`decision.md` §1).
- Shift Assignment would depend on both `Shift` and `HrEmployee` existing (`decision.md` §1).
- `AttendanceEvent` does not own assignment and does not currently consume it (`decision.md` §8).
- No authorization currently applies to anything shift-related (`decision.md` §9).
- Whatever aggregate boundary is eventually chosen excludes the Child Entity, Transactional Aggregate, Domain Service, and Value Object shapes (§1).

No delete-rule invariant is stated here: §3 found a real, unresolved divergence (`Assignment`'s `CASCADE` vs. every other relevant entity's `RESTRICT`) — this is a comparison finding, not a decided invariant, and is not asserted as one.

---

# 8. Authorization Relationship

**Repository Evidence**: Of the eleven currently-implemented capabilities reviewed across this governance trail, eight use `CurrentUser`-only dependency injection with no dedicated authorization evaluator (`Shift`, `HrEmployee`, `JobGrade`, `EmploymentType`, `EmploymentStatus`, `Holiday`, `PayrollRun`, `Payslip`); exactly three have a dedicated `AuthorizationEvaluator` (`ApprovalAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`, `AttendanceAuthorizationEvaluator`). `Assignment` (Project Tracking), the repository's one structural precedent for Shift Assignment's likely shape (§1), also has no dedicated evaluator. Payroll Authorization exists as its own, separately-foldered capability specifically because its own governance work began before a `Payroll` resource existed to authorize against (established in this trail's own prior governance) — no analogous circumstance is evidenced for Shift Assignment.

**Logical Consequence**: By direct count, "ordinary CRUD capability" (`CurrentUser`-only, no evaluator) is the majority pattern among implemented capabilities, and is also the pattern exhibited by `Assignment` — the one structural precedent already identified for Shift Assignment's likely aggregate shape (§1). Neither the Payroll Authorization precedent (a separate-capability-folder pattern tied to a specific historical sequencing not evidenced here) nor the Authorization Foundation precedent (a shared mechanism evidenced as needed by three or more consumer capabilities, which is not evidenced for Shift Assignment) has any repository connection to Shift Assignment specifically.

**Unknown**: Whether Shift Assignment's specific semantics — an employee-relevant assignment, potentially self-service-adjacent the way `LeaveRequest`/`AttendanceEvent` are — would eventually warrant a dedicated evaluator like those three, despite resembling the unauthorized majority structurally today. Not decided; no authorization policy is invented here.

---

# 9. Future Consumers

**Confirmed** (code-level, currently consuming a Shift Assignment concept): **None.** Nothing exists in code today to consume, since Shift Assignment does not yet exist as an entity.

**Documented** (named in a repository governance/design document as a candidate, explicitly marked unconfirmed by that source):
- `LeaveRequest` — `LEAVE_DESIGN.md`'s own "Shift changes" section names "shift reassignment mid-request" as an unconfirmed open question (cited in `discovery.md` §8, `decision.md` §10).

**Unknown** (structurally plausible by logical inference, but not stated in any repository document):
- `AttendanceEvent` — `decision.md` §8 concluded it would be the structurally consistent candidate consumer *if* Shift Assignment is built, but this is this governance trail's own logical inference (§6 above), not a statement authored anywhere in the repository itself. Kept distinct from `LeaveRequest`, whose candidacy is directly documented, not inferred.

No fourth candidate is found anywhere in repository code or governance documents.

---

# 10. Recommendation

```
Architecture Gap Analysis may begin.
```

This domain-model pass narrowed aggregate candidates to one genuine `Unknown` out of seven (Projection), established a clear, uniform identity pattern (§2), and surfaced two distinct, comparably-reusable relationship shapes (§3) along with a real, evidenced delete-rule divergence between them — more structural resolution than `monetary-representation/domain-model-discovery.md` reached at the same stage (four of seven candidates left `Unknown` there), which still proceeded to its own Architecture Gap Analysis. The remaining Unknowns here (relationship shape choice, delete-rule resolution, temporal/lifecycle treatment, authorization posture, `AttendanceEvent` consistency) are consolidation-and-classification questions, not evidence gaps — no further repository search is expected to change them, matching the precedent already established for proceeding to Architecture Gap Analysis rather than another Domain Discovery round.

---

# References

- `docs/architecture/capabilities/shift-assignment/discovery.md`
- `docs/architecture/capabilities/shift-assignment/decision.md`
- `docs/architecture/capabilities/monetary-representation/domain-model-discovery.md` (methodology and recommendation-threshold precedent)
- `services/api/src/eop_api/models/assignment.py`, `leave_balance.py`, `attendance_event.py`, `hr_employee.py`, `shift.py`
