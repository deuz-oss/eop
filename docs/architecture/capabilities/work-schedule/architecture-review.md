# Work Schedule — Architecture Review

**Status:** Complete

**Capability:** Work Schedule

**Reviews:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`

**Owner:** EOP Architecture Governance

---

# 1. Overall Verdict

```
Approved with Known Risks
```

No Blocking contradiction was found between any two documents in the chain, and no document was found to have silently reopened, reversed, or absorbed a decision already made by an earlier one. Two Non-blocking issues were found (§2), both mild wording/structural imprecisions that do not affect any conclusion currently relied upon. The Deferred Decisions trail was independently verified complete — every item from `decision.md` §9 was traced into `architecture-gap-analysis.md` §6's consolidated list, with no silent drops.

---

# 2. Findings

## Blocking

None found.

## Non-blocking

**Finding 1 — `architecture-gap-analysis.md` §9 compares two different kinds of counts as though directly comparable.**

Its Final Recommendation states: *"the aggregate shape remains open across three live candidates (wider than Shift Assignment's comparable two-item blocker)."* Work Schedule's "three" is a count of unresolved aggregate *classification candidates* (Aggregate Root, Association Aggregate, Projection — `decision.md` §5). Shift Assignment's "two" (relationship shape, delete rule) is a count of distinct *blocking governance questions*, a different kind of measurement — not itself a count of unresolved classification candidates (Shift Assignment's own aggregate classification left only one candidate `Unknown`, not two). The comparison is directionally reasonable — Work Schedule genuinely has more structural uncertainty than Shift Assignment did at the same stage — but the specific "three... wider than... two-item" phrasing conflates two different units. Not blocking: the underlying conclusion (Work Schedule has more open structural questions than Shift Assignment did) is independently supported elsewhere in the same document (`architecture-gap-analysis.md` §6 lists fifteen consolidated Blocking Unknowns for Work Schedule versus ten reached by Shift Assignment's own gap analysis at the comparable stage), so the imprecise phrasing does not change the recommendation it supports.

**Finding 2 — `discovery.md` §5 ("Ownership") does not follow the same explicit Repository Evidence/Logical Consequence/Unknown labeling structure used in every other section of the same document.**

Sections 1-4 and 6-10 of `discovery.md` each explicitly bold-label their **Repository Evidence**, **Logical Consequence**, and **Unknown** content. Section 5 instead opens with *"Stated explicitly where nobody owns something, per instruction:"* followed directly by five bullets, with no explicit **Repository Evidence** or **Unknown** labels anywhere in the section. The content itself is well-supported — each bullet's claim ("nobody owns this") is directly traceable to evidence already established in §1-4 — so this is a labeling-convention inconsistency within one document, not a substantive gap. Not blocking: no later document was found treating §5's conclusions any differently than it would have if the labels had been present, and `decision.md` §1 cites §5 correctly and precisely.

## Observations

**Observation 1 — Every phase's own "next step" recommendation matches what actually happened next, verified in sequence, not assumed.**

`discovery.md` → "Capability Decision may begin" → `decision.md` created next. `decision.md` → "Domain Model Discovery may begin" → `domain-model-discovery.md` created next. `domain-model-discovery.md` → "Architecture Gap Analysis may begin" → `architecture-gap-analysis.md` created next. `architecture-gap-analysis.md` → "Additional Governance Required" → this Architecture Review, a direct instance of additional governance, consistent with the identical sequencing already used for Shift Assignment's and Monetary Representation's own chains.

**Observation 2 — The aggregate-classification arithmetic in `decision.md` §5 was independently re-counted and found correct, with no repeat of the confusing self-correcting wording found in Shift Assignment's own `decision.md` §4.**

`decision.md` §5 lists seven candidates total; four rejected (Child Entity, Transactional Aggregate, Domain Service, Value Object) plus three left `Unknown` (Aggregate Root, Association Aggregate, Projection) sums correctly to seven. Its own "Result" sentence states "Four candidates rejected... Three remain genuinely `Unknown`" — clean and internally consistent on first read, unlike the analogous sentence in Shift Assignment's own `decision.md`.

**Observation 3 — A subtle but correctly-maintained distinction is preserved throughout the chain: `ReconciliationService` is a *Confirmed* consumer of `Shift`, but never conflated with being a *Confirmed* consumer of "Work Schedule" itself.**

`discovery.md` §9 lists `ReconciliationService` as "Confirmed" only in the sense of reading `HrEmployee.shift_id` (i.e., consuming `Shift`) — explicitly "narrow" and "explicitly-scoped-out-of-'schedule.'" `decision.md` §8 and `architecture-gap-analysis.md` §5 both correctly downgrade `ReconciliationService`'s relationship to Work Schedule *specifically* to inference/"Documented," never asserting it as a Confirmed consumer of a capability that does not yet exist. This distinction would have been easy to blur and was not.

**Observation 4 — Every one of `decision.md` §9's eleven Deferred Decisions was independently traced into `architecture-gap-analysis.md` §6's fifteen-item consolidated list, with no item silently dropped.**

Unlike Shift Assignment's own chain (where one Deferred Decision was found not explicitly carried into its Architecture Gap Analysis), this chain's consolidation is complete: all eleven `decision.md` §9 items map directly onto `architecture-gap-analysis.md` §6 items 1-3, 5-7, 12-15, and the four additional items (`domain-model-discovery.md`-introduced identity convention, employee-scoping, weaker-temporal-shape choice, and lifecycle-beyond-overwrite) are legitimately new findings from that phase, not fabricated or duplicated.

---

# 3. Cross-Document Consistency

### Ownership

Consistent across all four documents. `decision.md` §1 decides Work Schedule owns recurring work patterns, planned working days, expected shifts, and employee work calendars, all by elimination; §2 decides it does not own `Shift`; §4 decides Attendance owns recorded (past) facts while Work Schedule would own planned (future) facts. `domain-model-discovery.md` §9 restates the `Shift`- and Attendance-related ownership findings verbatim as Invariants without alteration. `architecture-gap-analysis.md` cites but never redefines ownership anywhere.

### Aggregate Classification

`domain-model-discovery.md` did not silently change `decision.md`'s classification. `decision.md` §5 rejects four candidates and leaves three `Unknown`; `domain-model-discovery.md` §1 explicitly re-evaluates only the three `Unknown` candidates, explicitly declining to reopen the four rejected ones, and reaches conclusions consistent with (and more precisely characterized than) `decision.md`'s own findings. Candidate counts independently verified correct (Observation 2).

### Relationships

- **`Shift`**: `decision.md` §2 (depends on/consumes, does not own or produce) restated identically in `domain-model-discovery.md` §9 and `architecture-gap-analysis.md` §4. No contradiction.
- **Shift Assignment**: `decision.md` §3 leaves this `Unknown`; `domain-model-discovery.md` §6 explicitly confirms it is "Not narrowed... Remains exactly as `decision.md` §3 left it"; `architecture-gap-analysis.md` §4-6 and §9 consistently preserve this as `Unknown` throughout, explicitly declining to resolve it even when choosing a Recommendation. No contradiction.
- **`HrEmployee`**: `decision.md` §8 labels the relationship "inference, not a confirmed dependency"; `domain-model-discovery.md` §3 and `architecture-gap-analysis.md` §4 both restate this identical epistemic status without upgrading or downgrading it. No contradiction.
- **Attendance**: `decision.md` §4 decides the temporal ownership split; `domain-model-discovery.md` §7 explicitly notes it adds a mechanism-precedent observation "without touching the ownership question `decision.md` §4 already settled"; `architecture-gap-analysis.md` §3/§5 classify Attendance as a mechanism precedent and documented future consumer, consistent with both. No contradiction.
- **`Holiday`**: Used consistently for two distinct, never-conflated purposes — a temporal-shape comparison point (`domain-model-discovery.md` §4) and a consultation-mechanism precedent for Attendance (`domain-model-discovery.md` §7, `architecture-gap-analysis.md` §3). `decision.md` §10 explicitly rejects embedding Work Schedule inside `Holiday`/`HolidayCalendar`. No contradiction, no conflation found.

### Deferred Decisions

Verified complete (Observation 4). No item was found resolved without new evidence, and no item was found contradicted.

### Recommendations

Verified correct at every phase (Observation 1).

### Governance Flow

Checked by direct citation scan, not assumed. `discovery.md`'s References cite only code files, prior design documents, and `shift-assignment/discovery.md`/`decision.md` (siblings, pre-existing) — no citation of `decision.md`, `domain-model-discovery.md`, or `architecture-gap-analysis.md`. `decision.md`'s References cite only `discovery.md`, a sibling document, and prior design documents — no citation of later phases. `domain-model-discovery.md`'s References cite only `discovery.md`, `decision.md`, a sibling document, and code — no citation of `architecture-gap-analysis.md`. `architecture-gap-analysis.md`'s References cite only the three prior phases and a sibling document. No future leakage found anywhere in the chain.

---

# 4. Architecture Boundary Review

- **`Shift`**: `decision.md` §2 explicitly declines ownership; no document proposes modifying `Shift`'s own fields or service. No absorption.
- **Shift Assignment**: The relationship is left `Unknown` throughout and never resolved via absorption — no document claims to own, modify, or extend Shift Assignment. No absorption.
- **Attendance**: `decision.md` §4's boundary is restated, not redrawn; `domain-model-discovery.md` §7 explicitly avoids proposing any change to `AttendanceEvent`/`ReconciliationService`. No absorption.
- **`Holiday`**: `decision.md` §10 explicitly rejects embedding Work Schedule inside `Holiday`/`HolidayCalendar`; `Holiday` is used only as an evidence/comparison precedent, never claimed as owned or modified. No absorption.
- **Leave**: `LeaveRequest` is treated throughout only as a weak, inferred/`Unknown` candidate consumer (`architecture-gap-analysis.md` §5) — never claimed as owned, modified, or extended by Work Schedule. No absorption.

No ownership overlap found anywhere across the four documents.

---

# 5. Remaining Risks

Restated only from `architecture-gap-analysis.md` §8, none invented:

- Building the wrong aggregate shape — three genuinely different, live candidates remain.
- No overlap-validation or `BETWEEN`-query support existing anywhere, risking inconsistent schedule data if built before this repeatedly-flagged gap is addressed.
- Attendance/`ReconciliationService`'s own already-existing "shift schedules" exclusion being retrofitted awkwardly if Work Schedule is built without coordinating with Attendance's own future governance.
- No historical-preservation or lifecycle mechanism existing anywhere, risking silent loss of prior schedule states.
- Authorization being retrofitted later if Work Schedule turns out to need dedicated-evaluator treatment rather than the CRUD-majority treatment it currently resembles.
- The relationship with Shift Assignment remaining undefined, risking duplicated or conflicting capability scope if both are eventually built independently without reconciling their overlap.

---

# 6. Final Recommendation

```
Additional Governance Required
```

This review found no contradiction requiring a different conclusion than `architecture-gap-analysis.md` §9 already reached, and both findings above are Non-blocking. Not **Ready for Implementation Planning**: the aggregate shape remains genuinely open across three live candidates, with identity, employee-scoping, and authorization posture all downstream of it — nothing in this review resolves any of them. The blockers are architecture decisions and inference gaps, confirmed consistent across all four documents, matching the identical recommendation reached by `shift-assignment/architecture-review.md` at the same stage.

---

# References

- `docs/architecture/capabilities/work-schedule/discovery.md`
- `docs/architecture/capabilities/work-schedule/decision.md`
- `docs/architecture/capabilities/work-schedule/domain-model-discovery.md`
- `docs/architecture/capabilities/work-schedule/architecture-gap-analysis.md`
- `docs/architecture/capabilities/shift-assignment/architecture-review.md` (review methodology precedent)
