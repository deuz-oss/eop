# Work Schedule — Domain Model Discovery

**Status:** Complete

**Capability:** Work Schedule

**Owner:** EOP Architecture Governance

**Depends On:** `docs/architecture/capabilities/work-schedule/discovery.md`, `docs/architecture/capabilities/work-schedule/decision.md`

---

# Purpose

This document refines the structural model for Work Schedule using repository evidence only. It does not reopen `discovery.md`'s findings or `decision.md`'s conclusions (ownership, the relationship with `Shift`, the boundary with Attendance, the four rejected aggregate candidates) — it evaluates only what remains genuinely open. Every conclusion is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**.

---

# 1. Aggregate Candidates

Only the three candidates `decision.md` §5 left `Unknown` (Aggregate Root, Association Aggregate, Projection) are re-evaluated. The four already-rejected candidates (Child Entity, Transactional Aggregate, Domain Service, Value Object) are not reopened.

- **Aggregate Root** — **Repository Evidence**: the `BaseEntity`/`UUIDMixin` persistence shape is universal across every entity in the repository and does not inherently conflict with a recurring concept. **Not narrowed**: nothing found beyond what `decision.md` §5 already established — the general persistence shape doesn't confirm the specific recurring behavior Work Schedule would need. **Remains `Unknown`.**
- **Association Aggregate** — **Repository Evidence**: `Assignment`, the one association precedent, enforces `UniqueConstraint("employee_id", "project_id")` — a rule that actively *prevents* a second row for the same pair, even after the first's `end_date` has passed (`discovery.md` §4, `decision.md` §5, restated). **Logical Consequence — a genuine narrowing**: this specific enforced behavior is structurally incompatible with recurrence — a schedule that repeats needs *multiple* rows for the same employee/shift pair over time, which `Assignment`'s exact constraint shape forbids. The "linking two aggregates" aspect of Association Aggregate remains structurally plausible; the "pair-uniqueness" aspect, as the one repository precedent implements it, would need to be dropped, not mirrored. **Remains `Unknown` overall, but narrower than before**: if this shape is followed, it could not reuse `Assignment`'s uniqueness rule as-is.
- **Projection** — **Repository Evidence**: `discovery.md` found zero projection/read-model precedent anywhere. `ReconciliationService` computes a transient, non-persisted classification ("present"/"late"/"absent") from multiple repositories at read time, and — more directly relevant to Work Schedule specifically than it was for Shift Assignment — already does so by comparing `Holiday.holiday_date` against a target date with *no FK*, described in `ATTENDANCE_RECONCILIATION_DESIGN.md` as *"a read-side join on `date`. No FK exists or is needed."* **Logical Consequence**: this is a real, existing precedent for computing a derived answer at read time without persisting a new row — closer to what a Projection-shaped Work Schedule concept would need than the comparison available for Shift Assignment. It does not confirm Projection is the right shape — `ReconciliationService` is a Domain Service (already rejected in `decision.md` §5), not a true persisted-or-cached Projection. **Remains `Unknown`**, with a more directly relevant comparison point than before.

**Result**: All three candidates remain `Unknown`, per instruction — none is forced. Two (Association Aggregate, Projection) now have a more precisely characterized reason for remaining `Unknown` than a flat absence of evidence.

---

# 2. Identity

**Repository Evidence**: All four compared entities use `UUIDMixin`/`BaseEntity` as their primary identity. Beyond that, three distinct secondary-identity conventions coexist in the repository:
- `AttendanceEvent` — UUID only, no natural key, no compound uniqueness — used where multiplicity/recurrence of rows for the same employee/shift pair is expected and must not be blocked.
- `Shift`, `PayrollRun` — UUID plus a unique `code` (`String`) — used for master/reference data meant to be looked up by a stable business key.
- `Assignment` — UUID plus a compound pair-uniqueness constraint (`employee_id`, `project_id`) — used to prevent a duplicate relationship row.

**Logical Consequence**: If Work Schedule becomes its own aggregate, identity would follow the universal UUID pattern at minimum. Whether it also needs a `code`-style natural key or a compound uniqueness constraint depends entirely on the still-open aggregate-shape question (§1) — a schedule needing recurrence would structurally resemble `AttendanceEvent`'s "no compound uniqueness" convention more than `Assignment`'s, per §1's finding.

**Unknown**: Which of these three secondary-identity conventions, if any, would apply — not decided; mirrors the still-open aggregate-shape question.

---

# 3. Relationship Model

**Repository Evidence — employee relationships**: Every employee-scoped entity in the repository (`AttendanceEvent`, `LeaveRequest`, `LeaveBalance`, `OvertimeRequest`, `Timesheet`, `Payslip`, and `HrEmployee`'s own `manager_id` self-reference) uses an `employee_id`-shaped FK, `ON DELETE RESTRICT`, without exception.

**Repository Evidence — recurring ownership**: Zero precedent, confirmed exhaustively in `discovery.md` §1/§4 and re-confirmed here — no pattern exists anywhere for representing "this fact repeats," so there is nothing to compare structurally.

**Repository Evidence — temporal planning**: Zero precedent as a general pattern. `decision.md` §6 already established, by elimination rather than by following an existing pattern, that temporal ownership would fall to Work Schedule.

**Logical Consequence**: If Work Schedule turns out to be employee-scoped (plausible, per `decision.md` §8, but not confirmed there either), it would very likely use the uniform `employee_id`/`RESTRICT` convention — the one aspect of a relationship model with strong, essentially unanimous repository precedent. Recurring ownership and temporal planning have no comparable precedent of any kind to draw on.

**Unknown**: Whether Work Schedule is employee-scoped at all (inferred in `decision.md` §8, not confirmed); how recurring ownership or temporal planning would be structurally represented — no precedent exists for either.

---

# 4. Temporal Modeling

**Repository Evidence**: Beyond the confirmed absence of any recurring mechanism (`discovery.md` §1, §4, restated, not reopened), three weaker temporal precedents exist at different granularities:
- `Assignment.start_date`/`end_date` — a single, continuous date range.
- `LeaveBalance.period_year` — a coarse, bare-`Integer` year partition, not a true date.
- `Holiday.holiday_date` — a single, flat date, no range.
- `PayrollRun` — zero date field of any kind (confirmed by direct model read: only `code`/`name`).

**Logical Consequence**: These four form a rough spectrum from "continuous range" through "coarse partition" and "single flat date" down to "no temporal dimension at all." None represents recurrence — each is a single, bounded, one-time temporal fact. This confirms `discovery.md`'s finding (no recurring precedent) while showing the repository has some experience with bounded temporal facts at multiple granularities — a slightly richer picture than "zero temporal precedent of any kind," though still no precedent for the specific shape (repetition) Work Schedule's own ownership decision (`decision.md` §1, §6) concerns.

**Unknown**: Whether any of these three weaker shapes is structurally closer to what Work Schedule needs than a genuinely unprecedented recurring shape — not decided.

---

# 5. Lifecycle

**Repository Evidence**: `create` is universal (`BaseRepository.create`, every entity). "Overwrite" (mutating a field in place via `update()`) is the only mutation pattern found anywhere for "current value" fields. No entity anywhere has a "replace" operation distinct from ordinary `update()` — the two are the same thing in this repository. No `*History`/`*Snapshot`/`*Revision` entity exists anywhere (confirmed absent repeatedly across this governance trail, re-confirmed applicable here per `discovery.md` §4's own zero-match search). `VersionMixin` exists on `BaseEntity` but is never read or incremented by any application code found anywhere — the same established, repository-wide fact restated, not re-derived.

**Logical Consequence**: Every lifecycle-adjacent behavior in the repository reduces to "create once, then overwrite fields in place." There is no precedent anywhere for "replace" as a operation distinct from "overwrite," and no working historical-preservation or versioning mechanism exists for any entity — including entities that plausibly would benefit from one (e.g., `LeaveBalance`). `Payslip`'s own decided immutability (omitting `update`/`delete` entirely, per its own governance) is a deliberate scope restriction, not a historical-preservation mechanism, and does not provide a precedent for preserving *prior* values.

**Unknown**: Whether Work Schedule, which plausibly needs both to change over time (a pattern being modified) and to preserve what was true in the past (for consistency with Attendance's own point-in-time facts, echoing the same tension already flagged for Shift Assignment), would need something beyond this universal create-then-overwrite pattern — not decided; `decision.md` §6 already flagged this as unresolved and it is restated, not reopened, here.

---

# 6. Relationship with Shift Assignment

**Repository Evidence**: Nothing new found. No code and no additional governance document connects Work Schedule and Shift Assignment. Both remain entirely unimplemented candidate capabilities.

**Logical Consequence**: Domain Model Discovery's own method — structural and behavioral comparison against existing repository code — cannot narrow a relationship between two capabilities when neither side has any implementation to compare. This differs from §1's aggregate-candidate narrowing, which could at least compare against `Assignment`'s real, existing code; here, both sides of the relationship in question are equally hypothetical.

**Unknown**: **Not narrowed.** Remains exactly as `decision.md` §3 left it — upstream, downstream, peer, and unrelated all remain possible; none is forced here either.

---

# 7. Attendance Relationship

**Repository Evidence**: `decision.md` §4 already decided Attendance owns recorded (past) facts and Work Schedule would own planned (future) facts, by elimination and by Attendance's own self-exclusion — not reopened here. One additional structural fact, not explicitly present in `decision.md`, is directly relevant: `ReconciliationService` already consults `Holiday` — a planned/reference-shaped concept — via *"a read-side join on `date`. No FK exists or is needed"* (`ATTENDANCE_RECONCILIATION_DESIGN.md`, cited via `discovery.md` §3).

**Logical Consequence**: This is a real, existing precedent for *how* a planned concept gets consulted by Attendance — a read-time, no-FK, cross-repository comparison — directly relevant if Work Schedule is ever consulted by Attendance/Reconciliation the same way `Holiday` already is. This narrows the *mechanism* question slightly (a plausible pattern exists to compare against) without touching the *ownership* question `decision.md` §4 already settled.

**Unknown**: Whether Work Schedule would actually be consulted this way — not decided; only a mechanism precedent is noted, not adopted.

---

# 8. Authorization

**Repository Evidence**: `Assignment` has no dedicated authorization evaluator (`CurrentUser`-only). The majority "ordinary CRUD capability" pattern (8 of 11 implemented capabilities, per `shift-assignment/domain-model-discovery.md` §8, cited for direct comparison) likewise has none. Payroll Authorization is its own separately-foldered capability, created specifically because its own governance began before a `Payroll` resource existed — no analogous circumstance is evidenced for Work Schedule.

**Logical Consequence**: By the same reasoning already applied to Shift Assignment, Work Schedule structurally resembles the majority "ordinary CRUD" pattern (including `Assignment` itself) far more than the Payroll Authorization precedent, which is tied to a specific historical sequencing not evidenced here. Resemblance to the smaller Leave/Attendance-style dedicated-evaluator minority is less clear — if Work Schedule turns out to be employee-scoped (§3's `Unknown`), it would share some self-service-adjacent characteristics with those two.

**Unknown**: The same genuine ambiguity already found for Shift Assignment — whether Work Schedule's specific semantics would eventually warrant a dedicated evaluator despite structurally resembling the unauthorized majority today. Not decided; no authorization policy is invented here.

---

# 9. Invariants

Only what is directly supported by `decision.md` or unambiguous structural fact — restated, not re-derived:

- Work Schedule does not own `Shift` (`decision.md` §2).
- Work Schedule would depend on/consume `Shift` (`decision.md` §2).
- Attendance owns recorded (past) facts; Work Schedule would own planned (future) facts (`decision.md` §4).
- Whatever aggregate shape is eventually chosen excludes Child Entity, Transactional Aggregate, Domain Service, and Value Object (`decision.md` §5).
- No versioning or historical-preservation mechanism exists for any entity in the repository today; any future Work Schedule aggregate would inherit this absence by default unless something new is built (§5 above).

No recurring-behavior invariant is stated — none is evidenced anywhere, confirmed repeatedly (`discovery.md` §1, §4; `decision.md` §5-6).

---

# 10. Recommendation

```
Architecture Gap Analysis may begin.
```

This pass narrowed less in absolute terms than Shift Assignment's own domain-model-discovery did (three aggregate candidates remain `Unknown` here, versus one there) — but every one of the nine topics evaluated either confirmed an already-established absence with added structural precision (§1, §3, §4, §5) or explicitly found nothing further to narrow (§6, the Shift Assignment relationship). No topic surfaced a new, undiscovered repository fact — each conclusion traces to evidence already present in `discovery.md` or `decision.md`, reasoned about more precisely. This matches the "evidence exhausted" threshold this governance trail has used elsewhere to proceed to Architecture Gap Analysis rather than repeat Domain Model Discovery (`monetary-representation/domain-model-discovery.md`, which also proceeded with a comparable number of `Unknown` candidates), not a specific resolution count.

---

# References

- `docs/architecture/capabilities/work-schedule/discovery.md`
- `docs/architecture/capabilities/work-schedule/decision.md`
- `docs/architecture/capabilities/shift-assignment/domain-model-discovery.md` (methodology and authorization-comparison precedent)
- `services/api/src/eop_api/models/assignment.py`, `shift.py`, `attendance_event.py`, `payroll_run.py`, `leave_balance.py`, `holiday.py`
