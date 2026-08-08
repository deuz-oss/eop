# Shift Assignment — Final Governance Summary

**Status:** Complete — Closing Document

**Capability:** Shift Assignment

**Owner:** Engineering (CPO/CTO-directed closure)

**Reviews:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `implementation-plan.md` (all approved, none modified by this document)

---

# Purpose

This is the closing governance document for Shift Assignment. It performs no new discovery and reopens no prior phase. It reconciles the ten Blocking Unknowns left open by `implementation-plan.md` §10 against the capabilities that have since merged (Work Schedule, Effective Dating, Compensation's historical/correction pattern, Authorization Foundation's Owner-Only precedent), and records the CPO/CTO decision on the one item that could not be closed by precedent alone.

---

# 1. Governance Outcome

The five-document discovery-through-review chain (`discovery.md` → `decision.md` → `domain-model-discovery.md` → `architecture-gap-analysis.md` → `architecture-review.md` → `implementation-plan.md`) concluded `Additional Governance Required` at every stage, blocked principally on two structural questions — relationship shape (plain FK / peer-association-with-pair-uniqueness / repeatable-fact-row) and delete rule (`CASCADE` vs `RESTRICT`) — that the repository, at the time, had no precedent to resolve either way.

Since that chain was written, **Work Schedule** was designed and merged. Its `WorkSchedule` aggregate (`services/api/src/eop_api/models/work_schedule.py`) is, field for field, the effective-dated employee↔shift relationship this governance chain was searching for: `employee_id` (FK → `hr_employees.id`, `RESTRICT`), `shift_id` (FK → `shifts.id`, `RESTRICT`), `effective_from`/`effective_to` (`EffectiveDatingMixin`), `corrects_id` (correction lineage, mirroring `Compensation`), `is_active`. It resolves the relationship-shape question in favor of **repeatable-fact-row + effective dating** (not `Assignment`'s peer-association-with-pair-uniqueness), and the delete-rule question in favor of **`RESTRICT`** (not `Assignment`'s `CASCADE`) — consistent with every other entity touching `HrEmployee` or `Shift`.

---

# 2. Reconciliation of Blocking Unknowns

Each of `implementation-plan.md` §10's items, reconciled against current merged architecture:

| # | Item | Resolution |
|---|---|---|
| 1 | Relationship shape / entity boundary | **Resolved by precedent** — repeatable-fact-row + effective dating, as built for Work Schedule. The remaining half of this question (whether this is a *separate* entity from Work Schedule) is addressed in §3 below. |
| 2 | Delete rule (`CASCADE` vs `RESTRICT`) | **Resolved by precedent** — `RESTRICT`, matching Work Schedule and every other HR-domain FK into `HrEmployee`/`Shift`. |
| 3 | Authorization ownership/posture | **Resolved by precedent** — Owner-Only (`resource.employee_id == context.employee_context.employee.id`), matching Work Schedule/Compensation's posture for employee-scoped, attendance/payroll-adjacent data. |
| 4 | `AttendanceEvent` cross-validation | Genuine business/product question, but explicitly out of scope for this workstream — no Attendance changes were authorized. Remains deferred to Attendance's own future governance. |
| 5 | Existing-FK sufficiency | **Resolved by precedent** — `HrEmployee.shift_id` remains the plain current-value convenience field it always was; Work Schedule (not a new Shift Assignment table) is now the authoritative, effective-dated source of "what shift is this employee on as of date X." |
| 6 | Effective dating / historical-treatment necessity | **Resolved** — yes, and the mechanism (`EffectiveDatingMixin`/`EffectiveDatingEvaluator`) already exists and is already applied to exactly this relationship, by Work Schedule. |
| 7 | Dedicated lifecycle necessity | **Resolved by precedent** — no dedicated reassignment/activation/deactivation verbs; Work Schedule's create-new-row + `corrects_id` + narrow `is_active`-only `update()` pattern is the established mechanism for this exact relationship. |
| 8 | `LeaveRequest` shift-hour consumption | Business decision, out of scope for this workstream — unrelated to whether Shift Assignment exists as its own entity. |
| 9 | Date-scoped uniqueness mechanism | **Resolved by precedent** — service-layer overlap validation via `EffectiveDatingEvaluator` + a hand-written repository overlap query, exactly as Work Schedule (and Compensation before it) implements it. No `BaseRepository` change. |
| 10 | Capability naming | Moot — "Shift Assignment" was this governance trail's own working name for the employee↔shift relationship; that relationship is now a resolved part of Work Schedule, not a separately-named entity. |
| 11 | Aggregate Root vs. Association Aggregate distinctness | Moot — resolved in practice: Work Schedule is an Aggregate Root, effective-dated, employee-scoped; the distinction this item worried about does not affect any implementation. |
| 12 | Projection genuinely inapplicable vs. unprecedented | Moot — resolved in practice: the relationship is durable, correction-tracked business data (Aggregate Root), not a derived/transient Projection. |
| 13 | Documentation discrepancy (non-architectural) | Not a blocker; no action required. |

---

# 3. The One Genuine Decision: Relationship to Work Schedule

`decision.md` §3 and `work-schedule/decision.md` §3 both independently left the relationship between these two candidate capabilities **explicitly undecided** — neither capability's own governance names a direction (upstream/downstream/peer/unrelated), because Work Schedule did not exist yet when Shift Assignment's chain was written, and Work Schedule's own chain deliberately did not resolve it either.

This is the one item in this reconciliation that is a genuine capability-ownership decision, not a structural or technical one — building a second, separate `ShiftAssignment` table with the same `employee_id`/`shift_id`/`effective_from`/`effective_to`/`corrects_id` shape as `WorkSchedule` would duplicate an already-merged mechanism.

**CPO/CTO Decision (this document, 2026-08-09):** Shift Assignment's capability concern — the effective-dated employee↔shift relationship — is **subsumed by Work Schedule**. No separate `ShiftAssignment` aggregate, table, service, or API is built. `WorkSchedule.shift_id` + `WorkSchedule.effective_from`/`effective_to` + `WorkSchedule.corrects_id` is the system's one authoritative mechanism for "which shift is employee X assigned to, as of any date, with full historical/correction lineage." `WorkSchedule.get_by_employee(employee_id, as_of_date)` (`services/api/src/eop_api/services/work_schedule.py`) is the resolution method for this question.

This decision does not modify Work Schedule in any way — it recognizes Work Schedule's existing shape as already satisfying this capability's concern, per the explicit instruction not to duplicate or redesign it.

---

# 4. Deferred Decisions (Genuinely Remaining, Owned Elsewhere)

Carried forward, not solved here, and not blocking this closure:

- **`AttendanceEvent` cross-validation** (item 4) — whether `AttendanceEvent.shift_id` should ever be validated against `WorkSchedule`'s resolved shift — a future Attendance-capability decision.
- **`LeaveRequest` shift-hour consumption** (item 8) — a future Leave-capability decision.

Both are explicitly out of scope for this closure and require no action here.

---

# 5. Recommendation

```
Capability Closed — Subsumed by Work Schedule
```

No implementation artifact is produced under the name "Shift Assignment." The employee↔shift relationship this governance trail investigated is fully and correctly modeled by the already-merged Work Schedule capability. This closure requires no code, migration, or test changes to any existing capability.

---

# References

- `docs/architecture/capabilities/shift-assignment/discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `implementation-plan.md`
- `docs/architecture/capabilities/work-schedule/decision.md`, `iteration-1-implementation-plan.md`
- `services/api/src/eop_api/models/work_schedule.py`, `services/work_schedule.py`
