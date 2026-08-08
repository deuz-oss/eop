# Shift Assignment — Implementation Plan

**Status:** Complete — Implementation Not Authorized

**Capability:** Shift Assignment

**Owner:** EOP Architecture Governance

**Based On:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`

---

# 1. Scope

**Implementation is not authorized.** This document's scope is limited to verifying, against the already-approved governance chain, whether implementation may legitimately begin — and, since it may not, to state precisely which prior findings block each implementation artifact and why. No architecture is introduced, no deferred decision is resolved, and no scaffold — minimal or otherwise — is proposed anywhere below.

This conclusion is not new: `architecture-gap-analysis.md` §7 already answered *"Can Iteration 1 Begin?"* with `No`, and `architecture-review.md` §6's Final Recommendation, reached after independently re-verifying the full governance chain, was `Additional Governance Required` — not `Ready for Implementation Planning`. This document does not overturn either conclusion; it applies them.

---

# 2. Dependencies

**Existing** (repository-evidenced, merged code):
- `HrEmployee` — confirmed merged (`decision.md` §1, `architecture-gap-analysis.md` §4).
- `Shift` — confirmed merged (`decision.md` §1, `architecture-gap-analysis.md` §4).

**Missing**: None. `architecture-gap-analysis.md` §4 found no prerequisite capability absent from the repository — both real upstream dependencies already exist.

**Unknown**: None, at the *dependency* level specifically. `AttendanceEvent` and `LeaveRequest` are not upstream dependencies of Shift Assignment — `architecture-gap-analysis.md` §4 classified both `Not Required` as prerequisites — they are, at most, unresolved *downstream* candidates (§10, §11 below), which is a different question from what this section covers.

---

# 3. Aggregate

**Cannot be written today.**

`decision.md` §4 leaves the aggregate classification split between two behaviorally-supported candidates (Aggregate Root, Association Aggregate — confirmed as "two descriptions of the same shape," not independently forced). `domain-model-discovery.md` §3 shows this abstract compatibility conceals a genuine, unresolved structural fork: a **peer-association shape** (pair-uniqueness enforced, at most one row per `employee_id`/`shift_id` pair) versus a **repeatable-fact-row shape** (no compound uniqueness, multiple rows per pair permitted). These produce different aggregates — one with an enforced uniqueness constraint, one without. `architecture-gap-analysis.md` §2 classifies this choice as an open Governance Gap ("Relationship shape") and §6 item 1 confirms it remains unresolved. Writing an aggregate definition today would require silently choosing between these two live, mutually-exclusive options, which no governance document authorizes.

---

# 4. Model

**Cannot be specified today.**

Blocked by the same unresolved relationship-shape question (§3), and additionally by the **delete rule**: `domain-model-discovery.md` §3 found `Assignment` — the only precedent for the peer-association shape — uses `ON DELETE CASCADE`, while every other entity relevant to this capability (`HrEmployee`, `Shift`'s other consumers, `AttendanceEvent`, `LeaveBalance`) uses `RESTRICT` without exception. `architecture-gap-analysis.md` §2/§6 item 2 confirms this is unresolved. A database model requires a decided uniqueness constraint and a decided `ondelete` rule; neither exists. `architecture-gap-analysis.md` §7 states this directly: *"any code written today would have to silently choose a uniqueness constraint (or its absence) and a delete rule, both of which are explicitly undecided."* No column, key, or relationship is invented here, per instruction.

---

# 5. Repository

**Cannot be specified today.**

`architecture-gap-analysis.md` §1 classifies `BaseRepository` and the repository pattern itself as `Sufficient` — proven, working infrastructure exists and would apply once a model exists. But no concrete repository behavior can be specified without a model to query against (§4), and any lookup method beyond generic CRUD (e.g., a pair-based lookup implying uniqueness, or a point-in-time lookup implying history) directly depends on the same unresolved relationship-shape and temporal-treatment questions (§3, §10 items 1 and 6). Nothing is specified here beyond noting that the underlying infrastructure is not the blocker — the missing model is.

---

# 6. Service

**Cannot be specified today.**

Per instruction, CRUD is not inferred and no lifecycle operation is invented. `decision.md` §6 leaves whether a dedicated lifecycle (reassignment/replacement/activation/deactivation as distinct operations) is needed at all as an open Business Gap (`architecture-gap-analysis.md` §2). Even ordinary CRUD cannot be safely assumed as the final service surface: whether "update" means in-place overwrite (the plain-FK/peer-association shape) or whether a new row must be appended instead (the repeatable-fact-row shape) depends entirely on the unresolved relationship-shape decision (§3). Service behavior cannot be specified until that decision is made.

---

# 7. API

**Cannot be specified today.**

No model (§4) and no service (§6) exist to expose. Additionally, `domain-model-discovery.md` §8 and `architecture-gap-analysis.md` §1/§6 item 3 leave the authorization posture `Unknown` — whether endpoints would be `CurrentUser`-only (the majority pattern, matching `Assignment` itself) or require a dedicated evaluator (matching `LeaveRequest`/`AttendanceEvent`) is unresolved, which determines the API layer's own dependency injection. No endpoint is specified here, per instruction.

---

# 8. Migration

**Cannot be written today.**

A migration requires a finalized table definition: columns, constraints, foreign keys, and `ondelete` rules. None of these is decided (§4). `architecture-gap-analysis.md` §7 explicitly states *"No minimum model is proposed here, per instruction"* — this document does not propose one either.

---

# 9. Tests

**Authorized**: None.

**Blocked**: All of the following, for the reasons already stated:
- Repository tests — blocked by §5 (no model to construct or query).
- Service tests — blocked by §6 (no service surface decided; even CRUD cannot be safely assumed).
- API tests — blocked by §7 (no endpoints, no authorization posture decided).
- Migration tests — blocked by §8 (no schema to migrate).

No meaningful test can be authored for Shift Assignment today without assuming an answer to at least one of the unresolved items in §10 — every such assumption would be an invented architectural decision, which this document does not make.

---

# 10. Deferred Decisions

Every unresolved governance item, carried forward without solving or removing any. Consolidated only where two items are literally identical; where a question was refined across phases (not literally identical, but the same underlying gap stated with more precision later), both framings are preserved with their full citation trail.

1. **Relationship shape / entity boundary** — originally framed in `decision.md` §2 as "part of `HrEmployee` (a field) or a separate entity"; refined in `domain-model-discovery.md` §3 to a three-way choice (plain FK, peer-association with pair-uniqueness, repeatable-fact-row). Not solved. (`decision.md` §2, §5; `domain-model-discovery.md` §3; `architecture-gap-analysis.md` §2, §6.1)
2. **Delete rule** — `CASCADE` (`Assignment`'s own precedent) vs. `RESTRICT` (every other relevant entity). Not solved. (`domain-model-discovery.md` §3; `architecture-gap-analysis.md` §2, §6.2)
3. **Authorization ownership and posture** — who owns authorization if not Shift Assignment (not decidable today), and which existing pattern (unauthorized-majority vs. dedicated-evaluator-minority) it more closely resembles. Not solved. (`decision.md` §9; `domain-model-discovery.md` §8; `architecture-gap-analysis.md` §1, §3, §6.3)
4. **`AttendanceEvent` cross-validation** — whether `AttendanceEvent.shift_id` should ever be validated against a Shift Assignment concept. Not solved. (`decision.md` §8; `domain-model-discovery.md` §6; `architecture-gap-analysis.md` §2, §6.4)
5. **Existing-FK sufficiency** — whether `HrEmployee.shift_id`/`AttendanceEvent.shift_id` as they exist today are adequate or merely transitional. Not solved. (`decision.md` §5; `architecture-gap-analysis.md` §2, §6.5)
6. **Effective dating / historical-treatment necessity** — whether the business needs point-in-time shift-assignment history at all. Not solved. (`decision.md` §7; `domain-model-discovery.md` §5-6; `architecture-gap-analysis.md` §2, §6.6)
7. **Dedicated lifecycle necessity** — whether reassignment/replacement/activation/deactivation need to exist as distinct, trackable operations. Not solved. (`decision.md` §6; `architecture-gap-analysis.md` §2, §6.7)
8. **`LeaveRequest` shift-hour consumption** — whether `LeaveRequest` needs shift-hour data for partial-day math; `LEAVE_DESIGN.md` itself labels this unconfirmed. Not solved. (`discovery.md` §8; `domain-model-discovery.md` §9; `architecture-gap-analysis.md` §2, §5, §6.8)
9. **Date-scoped uniqueness mechanism** — whether a pair-uniqueness constraint would need to be date-aware, and that no such mechanism exists anywhere in the repository regardless. Not solved. (`domain-model-discovery.md` §2; `architecture-gap-analysis.md` §2, §6.9)
10. **Capability naming** — whether "Shift Assignment" is the correct or final name; it originates from this governance trail's own task framing, not any pre-existing repository source. Not solved. (`decision.md` §11; `architecture-gap-analysis.md` §6.10)
11. **Whether "Aggregate Root" and "Association Aggregate" are meaningfully distinct categories** in this repository's own vocabulary, or two descriptions of one precedent. Recorded in `decision.md` §11; restated consistently (not re-opened) in `domain-model-discovery.md` §1; not explicitly carried into `architecture-gap-analysis.md` §6's consolidated list (`architecture-review.md` Finding 2). Restored here per this task's instruction not to remove any item. Not solved.
12. **Whether "Projection" is genuinely inapplicable to this domain, or merely unprecedented** in this repository. Left `Unknown`, not rejected, in `decision.md` §4 and restated identically in `domain-model-discovery.md` §1; not explicitly carried into `architecture-gap-analysis.md` §6. Restored here for the same reason as item 11. Not solved.
13. **Documentation discrepancy** (non-architectural) — whether the mismatch between this discovery's direct findings and `payroll/discovery.md`'s earlier claim that `Shift` is "not assigned to any employee" reflects staleness in that document or an oversight. (`discovery.md` §1, §10.) Not solved; not an architectural blocker, carried forward for completeness only.

---

# 11. Remaining Risks

Restated only from `architecture-gap-analysis.md` §8 and `architecture-review.md` §5, none invented:

- Building the wrong relationship shape — over-constraining with pair-uniqueness if a repeatable-fact-row shape was actually needed, or the reverse.
- A delete-rule mismatch with the rest of the HR domain if `CASCADE` is carried over from `Assignment` without reconciling with the `RESTRICT` convention used everywhere else this capability would touch.
- `AttendanceEvent`'s already-independent, unvalidated `shift_id` continuing to diverge from whatever "current" shift-assignment model is eventually built, with no reconciliation mechanism.
- Effective dating being needed later but not planned for now.
- Authorization being retrofitted later if Shift Assignment turns out to need Leave/Attendance-style dedicated-evaluator treatment rather than the CRUD-majority treatment it currently resembles.

---

# 12. Recommendation

```
Additional Governance Required
```

Not **Implementation may begin**: every implementation artifact evaluated above (§3-9) is blocked by at least one specific, cited, unresolved governance finding — none is a missing-evidence gap that more repository search would close (`architecture-gap-analysis.md` §6 already established this for each). Not **Waiting for Business Decision**: while several blockers are Business Gaps (effective dating, dedicated lifecycle, `LeaveRequest` consumption — `architecture-gap-analysis.md` §2), the two items that `architecture-gap-analysis.md` §7 identified as the specific reason Iteration 1 cannot begin — relationship shape and delete rule — are Governance Gaps, architecture decisions this repository's own precedent could resolve without new business input. Naming this "Waiting for Business Decision" would understate the architecture-level work still required. This matches `architecture-review.md` §6's own Final Recommendation exactly, reached independently after a full re-verification of the governance chain.

---

# References

- `docs/architecture/capabilities/shift-assignment/discovery.md`
- `docs/architecture/capabilities/shift-assignment/decision.md`
- `docs/architecture/capabilities/shift-assignment/domain-model-discovery.md`
- `docs/architecture/capabilities/shift-assignment/architecture-gap-analysis.md`
- `docs/architecture/capabilities/shift-assignment/architecture-review.md`
