# Work Schedule — Implementation Plan

**Status:** Complete — Implementation Not Authorized

**Capability:** Work Schedule

**Owner:** EOP Architecture Governance

**Based On:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`

---

# 1. Executive Summary

The governance chain for Work Schedule reached: ownership decided by elimination for four core concepts (`decision.md` §1), a clean, decided relationship with `Shift` (`decision.md` §2) and boundary with Attendance (`decision.md` §4), and four of seven aggregate candidates rejected (`decision.md` §5) — but three aggregate candidates (Aggregate Root, Association Aggregate, Projection) remain genuinely `Unknown`, wider than any other capability's comparable stage in this trail. `architecture-gap-analysis.md` §7 answered *"Can Iteration 1 Begin?"* with `No`. `architecture-review.md` §6, after independently re-verifying the entire chain fresh from disk and finding zero Blocking contradictions, reached the same Final Recommendation: `Additional Governance Required`, not `Ready for Implementation Planning`.

**Implementation is not currently authorized.** This document applies that conclusion; it does not reargue it.

---

# 2. Implementation Readiness

```
Not Authorized
```

Justified entirely by prior governance: `architecture-gap-analysis.md` §7 (`No`) and `architecture-review.md` §6 (`Additional Governance Required`), reached independently at two different review stages, agree without contradiction.

---

# 3. Aggregate

**Cannot be written today.**

`decision.md` §5 leaves three of seven aggregate candidates `Unknown` — Aggregate Root, Association Aggregate, and Projection. `domain-model-discovery.md` §1 narrowed the *reasoning* behind two of these (Association Aggregate cannot mirror `Assignment`'s exact pair-uniqueness rule, which is structurally incompatible with recurrence; Projection has a more directly relevant comparison point in `ReconciliationService`'s read-time `Holiday` join than it did for Shift Assignment) without resolving which, if any, applies. Writing an aggregate definition today would require silently choosing among three live, structurally distinct candidates — exactly what `architecture-gap-analysis.md` §7 identified as the reason Iteration 1 cannot begin. No aggregate is invented here, per instruction.

---

# 4. Model

**Cannot be defined today.**

Blocked by the unresolved aggregate shape (§3), and compounded by four further unresolved prerequisites, each identified precisely:
- **Identity convention** — `domain-model-discovery.md` §2 found three distinct secondary-identity conventions in the repository (UUID-only, UUID+code, UUID+pair-uniqueness); which applies depends entirely on the unresolved aggregate shape (§3).
- **Whether Work Schedule is employee-scoped at all** — only inferred by analogy, never confirmed (`decision.md` §8, `domain-model-discovery.md` §3). No `employee_id` FK can be specified without this.
- **Which weaker temporal shape (if any) fits** — `domain-model-discovery.md` §4 found three weaker precedents (`Assignment`'s range, `LeaveBalance`'s partition, `Holiday`'s flat date) with nothing distinguishing which, if any, is the better analogy.
- **Recurrence identity and temporal uniqueness** — `architecture-gap-analysis.md` §2 classifies both as **Repository Gaps**: no mechanism anywhere in the repository represents "one template, many recurring instances," and no date-scoped/overlap-aware uniqueness constraint exists anywhere to model against.

No field, foreign key, constraint, or index is invented here, per instruction.

---

# 5. Repository

**Cannot be specified today.**

`architecture-gap-analysis.md` §1 classifies `BaseRepository` and the repository pattern as `Sufficient` — proven, working infrastructure exists and would apply once a model exists. But no concrete repository behavior can be specified without a model to query against (§4). Additionally, `architecture-gap-analysis.md` §2 classifies **Overlap validation** as a **Repository Gap**: `BaseRepository._apply_filters` has no `BETWEEN`/range-query support, a gap independently named in four prior design documents (`HOLIDAY_CALENDAR_DESIGN.md`, `LEAVE_DESIGN.md`, `TIMESHEET_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`) and re-confirmed here. No CRUD method is invented here, per instruction.

---

# 6. Service

**Cannot be defined today.**

Blocked by the unresolved aggregate and model (§3-4), and further by:
- **Lifecycle beyond create-then-overwrite** — `domain-model-discovery.md` §5 found no repository precedent anywhere for "replace" as distinct from "overwrite," or for historical preservation; whether Work Schedule needs either is unresolved.
- **Whether "recurring schedules" and "effective dates" are one concern or two** — `decision.md` §6 left this explicitly unmerged and unresolved, directly affecting what a service's own responsibilities would even be.
- **Planned-versus-actual comparison** — `architecture-gap-analysis.md` §2 classifies this as a **Governance Gap**: a mechanism precedent already exists (`ReconciliationService`'s read-time join against `Holiday`, `domain-model-discovery.md` §7), but whether/how to extend it to Work Schedule is undecided.

No business logic is invented here, per instruction.

---

# 7. API

**Cannot be planned today.**

No model (§4) and no service (§6) exist to expose. Additionally, **authorization posture** remains `Unknown` (`decision.md` §7, `domain-model-discovery.md` §8, `architecture-gap-analysis.md` §1/§6 item 4) — whether endpoints would be `CurrentUser`-only (the majority pattern, matching `Assignment`) or require a dedicated evaluator is unresolved, directly determining the API layer's own dependency injection. No route or operation is invented here, per instruction.

---

# 8. Migration

**Cannot be planned today.**

A migration requires a finalized table definition. The exact architectural decisions still missing are identical to those blocking §4: aggregate shape (§3), identity convention, employee-scoping, temporal shape, and the two confirmed Repository Gaps (recurrence identity, temporal uniqueness). `architecture-gap-analysis.md` §7 states directly that no minimum scaffold is proposed for this capability; this document does not propose one either.

---

# 9. Tests

**None authorized.**

Every category of test is blocked by the same upstream gaps:
- Repository tests — blocked by §5 (no model to construct or query, plus the confirmed `BETWEEN`-query Repository Gap).
- Service tests — blocked by §6 (no service surface decided; lifecycle and recurrence-vs-effective-dating framing both unresolved).
- API tests — blocked by §7 (no endpoints, no authorization posture decided).
- Migration tests — blocked by §8 (no schema to migrate).

No meaningful test can be authored today without assuming an answer to at least one unresolved item in §10 — every such assumption would be an invented architectural decision, which this document does not make.

---

# 10. Deferred Decisions

Every unresolved governance item, carried forward without solving or removing any. `architecture-review.md` independently verified this same set complete against `decision.md` §9 with zero items dropped (`architecture-review.md` Observation 4) — presented here in that same, verified form, plus `architecture-gap-analysis.md` §2's Missing-Concepts classifications, which use a distinct taxonomy (Repository/Governance/Business/External Gap) `architecture-gap-analysis.md` deliberately kept separate from its own Blocking-Unknowns framing, and are therefore listed separately rather than merged.

**Blocking Unknowns** (`architecture-gap-analysis.md` §6, full fifteen-item set):
1. Aggregate shape — three of seven candidates `Unknown` (Aggregate Root, Association Aggregate, Projection).
2. Relationship with Shift Assignment — upstream/downstream/peer/unrelated all remain possible.
3. Whether "recurring schedules" and "effective dates" are one concern or two.
4. Authorization posture.
5. Whether `HrEmployee` is actually a dependency (only inferred).
6. Whether `ReconciliationService`/Attendance becomes a real consumer.
7. Whether `LeaveRequest`, `Timesheet`, or Payroll Calculation ever consume Work Schedule.
8. Identity convention — which of three secondary-identity shapes applies.
9. Whether Work Schedule is employee-scoped at all.
10. Which weaker temporal shape (if any) is closer to what's needed.
11. Lifecycle beyond create-then-overwrite.
12. Whether "employee work calendars" ownership overlaps with `HOLIDAY_CALENDAR_DESIGN.md`'s declined calendar-container scope.
13. `BaseRepository` `BETWEEN`-query gap resolution.
14. Overnight-shift/timezone attribution ambiguities.
15. Capability naming.

**Missing-Concepts gap classifications** (`architecture-gap-analysis.md` §2, distinct taxonomy, not solved):
- Recurring relationships — **Repository Gap**.
- Recurrence identity — **Repository Gap**.
- Temporal uniqueness (date-scoped/overlap-aware constraints) — **Repository Gap**.
- Overlap validation — **Repository Gap**.
- Historical schedule lookup — **Repository Gap**.
- Planned-versus-actual comparison — **Governance Gap**.

---

# 11. Remaining Risks

Restated only from `architecture-gap-analysis.md` §8 and `architecture-review.md` §5, none invented:

- Building the wrong aggregate shape — three genuinely different, live candidates remain.
- No overlap-validation or `BETWEEN`-query support existing anywhere, risking inconsistent schedule data if built before this repeatedly-flagged gap is addressed.
- Attendance/`ReconciliationService`'s own already-existing "shift schedules" exclusion being retrofitted awkwardly if Work Schedule is built without coordinating with Attendance's own future governance.
- No historical-preservation or lifecycle mechanism existing anywhere, risking silent loss of prior schedule states.
- Authorization being retrofitted later if Work Schedule turns out to need dedicated-evaluator treatment rather than the CRUD-majority treatment it currently resembles.
- The relationship with Shift Assignment remaining undefined, risking duplicated or conflicting capability scope if both are eventually built independently without reconciling their overlap.

---

# 12. Recommendation

```
Additional Governance Required
```

Every implementation artifact evaluated above (§3-9) is blocked by at least one specific, cited, unresolved governance finding — none is a missing-evidence gap that more repository search would close (`architecture-gap-analysis.md` §6 already established why-more-search-would-not-help for each). This matches `architecture-gap-analysis.md` §9's own Final Recommendation and `architecture-review.md` §6's independently-reached Final Recommendation exactly — both `Additional Governance Required`, not `Ready for Architecture Review`/`Ready for Implementation Planning`. Not **Ready for Implementation**: the aggregate shape alone spans three live, structurally distinct candidates, with identity, employee-scoping, temporal shape, and authorization posture all downstream of it — no stable target exists for scaffolding of any kind.

---

# References

- `docs/architecture/capabilities/work-schedule/discovery.md`
- `docs/architecture/capabilities/work-schedule/decision.md`
- `docs/architecture/capabilities/work-schedule/domain-model-discovery.md`
- `docs/architecture/capabilities/work-schedule/architecture-gap-analysis.md`
- `docs/architecture/capabilities/work-schedule/architecture-review.md`
