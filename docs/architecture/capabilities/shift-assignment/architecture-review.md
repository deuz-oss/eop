# Shift Assignment — Architecture Review

**Status:** Complete

**Capability:** Shift Assignment

**Reviews:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`

**Owner:** EOP Architecture Governance

---

# 1. Overall Verdict

```
Approved with Known Risks
```

No Blocking contradiction was found between any two documents in the chain, and no document was found to have silently reopened, reversed, or absorbed a decision already made by an earlier one. Two Non-blocking issues were found (§2) — a confusing self-correcting sentence within `decision.md` itself, and one Deferred Decision not explicitly carried into `architecture-gap-analysis.md`'s consolidated list — neither of which affects any conclusion currently relied upon.

---

# 2. Findings

## Blocking

None found.

## Non-blocking

**Finding 1 — `decision.md` §4's own "Result" sentence is internally confusing, though self-correcting.**

`decision.md` §4 states: *"**Result**: Three candidates rejected on direct structural mismatch (Child Entity, Transactional Aggregate, Domain Service, Value Object — four, not three); Aggregate Root and Association Aggregate both supported by the one available precedent (two descriptions of the same shape); Projection remains `Unknown`."*

The sentence opens with "Three candidates rejected," then lists four names, then parenthetically corrects itself to "four, not three." The correction is present, so nothing is factually wrong — all four listed candidates were individually evaluated and rejected earlier in the same section, and the parenthetical resolves the apparent error — but a reader skimming only the opening clause would form the wrong count. `domain-model-discovery.md` §1 restates the same result cleanly: *"**Result**: Four candidates rejected on direct behavioral mismatch (Child Entity, Transactional Aggregate, Domain Service, Value Object)..."* — correct on its own terms, and it happens to supersede the confusing original in practice, but the underlying text in `decision.md` itself was not corrected. Not blocking: the correct count (four) is independently verifiable from the four individually-rejected bullets immediately above the "Result" line in the same section, and no downstream document was found to have inherited the wrong count of "three."

**Finding 2 — One Deferred Decision from `decision.md` §11 is not explicitly carried into `architecture-gap-analysis.md` §6's consolidated Blocking Unknowns list.**

`decision.md` §11 lists as a Deferred Decision: *"Whether 'Aggregate Root' and 'Association Aggregate' are meaningfully distinct categories in this repository's own vocabulary, or two descriptions of one precedent (§4)."* `architecture-gap-analysis.md` §6's ten-item consolidated list — checked item-by-item — does not contain this question in any form. This differs from the other nine items in `decision.md` §11, every one of which was verified present in `architecture-gap-analysis.md` §6, either directly or via `domain-model-discovery.md`.

This appears to be a case of the question being addressed rather than dropped: `domain-model-discovery.md` §1 restates the same conclusion `decision.md` §4 reached — *"Aggregate Root and Association Aggregate both behaviorally supported by the one available precedent... two descriptions of the same shape"* — without re-flagging it as open, and no later document treats the two labels as needing separate resolution. Not blocking: nothing in `architecture-gap-analysis.md` relies on these being distinct categories, and no conclusion anywhere in the chain would change if they are or are not. This is a completeness gap in consolidation, matching the same category of finding surfaced in this governance trail's own `monetary-representation/architecture-review.md`.

## Observations

**Observation 1 — Every phase's own "next step" recommendation matches what actually happened next, verified in sequence, not assumed.**

`discovery.md` → "Continue Governance" (the recommendation menu for this document was explicitly constrained to `Continue Governance`/`Capability Already Exists`/`Capability Not Supported by Repository`, a coarser vocabulary than other capabilities' discovery documents in this trail, per that task's own instructions — not an inconsistency). `decision.md` → "Domain Model Discovery may begin" (matches — `domain-model-discovery.md` was created next). `domain-model-discovery.md` → "Architecture Gap Analysis may begin" (matches). `architecture-gap-analysis.md` → "Additional Governance Required" (this Architecture Review is a direct instance of additional governance — the identical sequencing already used for Monetary Representation's own chain, where an Architecture Review followed an identical "Additional Governance Required" recommendation).

**Observation 2 — The aggregate-classification arithmetic (four rejected, two supported, one `Unknown`, out of seven candidates) was independently re-counted across `decision.md` and `domain-model-discovery.md` and confirmed identical, not taken on faith.**

Both documents individually evaluate all seven candidates (Aggregate Root, Child Entity, Association Aggregate, Transactional Aggregate, Domain Service, Value Object, Projection) and reach the same four rejections, the same two supported candidates, and the same one `Unknown`, despite evaluating from different angles (classification vote in `decision.md` §4, behavioral evaluation in `domain-model-discovery.md` §1). No candidate is reclassified between the two documents.

**Observation 3 — The `CASCADE`/`RESTRICT` divergence surfaced in `domain-model-discovery.md` §3 is a genuinely new finding at that phase, not present in `discovery.md` or `decision.md`, and is correctly *not* asserted as a decided invariant anywhere afterward.**

`discovery.md` §3 records `Assignment`'s `ON DELETE CASCADE` as a plain fact with no comparison to other entities' delete rules. `decision.md` does not mention delete rules at all. `domain-model-discovery.md` §3 is the first document to compare `Assignment`'s `CASCADE` against the `RESTRICT` convention used by every other entity relevant to this capability, and explicitly declines to state a delete-rule invariant in its own §7 ("No delete-rule invariant is stated here"). `architecture-gap-analysis.md` §2 and §6 correctly carry this forward as an open Governance Gap / Blocking Unknown, not as a resolved fact. Consistent treatment throughout — this is new information being added at the correct phase and never asserted as decided.

---

# 3. Cross-Document Consistency

### Ownership

Consistent across all four documents. `decision.md` §1 decides Shift Assignment owns the employee↔shift relationship, and explicitly does not own `Shift`, `HrEmployee`, or `AttendanceEvent`. `domain-model-discovery.md` §7 restates the non-ownership findings verbatim as Invariants without alteration. `architecture-gap-analysis.md` §4 restates the same non-ownership (dependency-without-ownership) relationship for `HrEmployee` and `Shift`. No document reclassifies ownership in either direction.

### Aggregate Classification

`domain-model-discovery.md` did not silently change `decision.md`'s classification. `decision.md` §4 rejects Child Entity, Transactional Aggregate, Domain Service, Value Object; leaves Aggregate Root and Association Aggregate both supported (as one precedent, two descriptions); leaves Projection `Unknown`. `domain-model-discovery.md` §1, evaluating independently and explicitly *not* repeating the classification vote (*"Not a repeat of `decision.md` §4's classification vote — this evaluates how each candidate would behave"*), reaches an identical result set. Verified by direct re-count (Observation 2), not assumed.

### Relationship with `HrEmployee`

`decision.md` §2 decides this is Undecidable from repository evidence alone. `domain-model-discovery.md` §3 does not reopen or resolve it — it explicitly states *"No pattern is chosen; comparison only, per instruction"* and its structural comparison table adds information without collapsing the Undecidable status into a decision. Consistent.

### Relationship with `Shift`

`decision.md` §3 decides assignment belongs to Shift Assignment, not inside `Shift`, on the strength of `Shift`'s own docstring exclusion. No later document revisits or contradicts this. Consistent.

### Attendance Relationship

`decision.md` §8 decides "Neither, today," with "consume, not own" as the logical direction *if* Shift Assignment is built. `domain-model-discovery.md` §6 restates the underlying evidence (`AttendanceEvent.shift_id`'s independence) and extends it with a new, compatible Unknown (whether a historical component is needed for consistency) without contradicting the "Neither, today" / "would consume, not own" conclusion. `architecture-gap-analysis.md` §4-5 restate `AttendanceEvent` as "Not Required" upstream and "Unknown" downstream — consistent with both prior documents. No contradiction found.

### Authorization

`decision.md` §9 decides "Not decidable today" who owns authorization, mirroring every other capability in this trail. `domain-model-discovery.md` §8 addresses a related but distinct question — which existing pattern (majority CRUD vs. minority dedicated-evaluator) Shift Assignment more closely resembles — and concludes this is also `Unknown`, without contradicting `decision.md` §9's narrower "not decidable who owns it" finding. `architecture-gap-analysis.md` §1/§3 carry the same `Unknown` classification forward for Authorization Foundation specifically. Consistent — an elaboration across phases, not a contradiction.

### Existing FK Interpretation

`HrEmployee.shift_id` and `AttendanceEvent.shift_id` are described identically across all four documents: required, `ON DELETE RESTRICT`, independent of each other, unvalidated against each other. `discovery.md` §1 establishes this directly from the model files; `decision.md` §5 restates it without alteration; `domain-model-discovery.md` §3's comparison table restates the same delete rule (`RESTRICT (both)` for `AttendanceEvent`, `RESTRICT (all)` for `HrEmployee`'s FKs); `architecture-gap-analysis.md` §2 cites `decision.md` §5 for the same "Existing-FK sufficiency" Governance Gap without redefining the FKs themselves. No drift found anywhere.

### Deferred Decisions

Nine of `decision.md` §11's ten Deferred Decisions were verified present, in substance, in `architecture-gap-analysis.md` §6's consolidated Blocking Unknowns list (directly or via `domain-model-discovery.md`). One — the Aggregate-Root-vs-Association-Aggregate distinctness question — was not explicitly carried forward (Finding 2). No Unknown was found resolved without new evidence, and no Unknown was found contradicted.

### Recommendations

Each phase recommends the correct next phase, verified in sequence, not assumed (Observation 1).

### Governance Flow

Checked by direct citation scan, not assumed. `discovery.md` cites no later document. `decision.md`'s References cite only `discovery.md` and sibling-capability documents (`compensation/capability-boundary-analysis.md`, `monetary-representation/decision.md`), plus code — no citation of `domain-model-discovery.md` or `architecture-gap-analysis.md`. `domain-model-discovery.md`'s References cite only `discovery.md`, `decision.md`, a sibling document, and code — no citation of `architecture-gap-analysis.md`. `architecture-gap-analysis.md`'s References cite only the three prior phases, a sibling document, and no forward citation (nothing later existed yet). No future leakage found anywhere in the chain.

---

# 4. Architecture Boundary Review

Checked against all five named neighbors, each for accidental absorption:

- **`HrEmployee`**: `decision.md` §1 explicitly declines ownership (*"would depend on `HrEmployee` existing, not own it"*). No document proposes modifying `HrEmployee`'s own fields, service, or responsibilities. No absorption.
- **`Shift`**: `decision.md` §3 explicitly declines ownership, on `Shift`'s own authored exclusion. No document proposes modifying `Shift`'s own template fields or service. No absorption.
- **Attendance**: `decision.md` §8/`domain-model-discovery.md` §6 both explicitly state neither owns the other; `domain-model-discovery.md` §6 explicitly states *"No redesign of `AttendanceEvent` is proposed."* No absorption.
- **Leave**: `LeaveRequest` is treated throughout as, at most, a documented-but-unconfirmed future consumer (`discovery.md` §8, `decision.md` §10, `domain-model-discovery.md` §9) — never as something Shift Assignment would own, modify, or extend. No absorption.
- **Authorization Foundation**: `domain-model-discovery.md` §8 compares Shift Assignment's likely authorization posture against existing patterns without claiming to own, extend, or modify Authorization Foundation itself, and without claiming any role/permission/policy content `ADR-007` itself excludes from other capabilities. No absorption.

No ownership overlap found anywhere across the four documents.

---

# 5. Remaining Risks

Restated only from `architecture-gap-analysis.md` §8, none invented:

- Building the wrong relationship shape (over- or under-constraining, per `domain-model-discovery.md` §3).
- A delete-rule mismatch with the rest of the HR domain if `Assignment`'s `CASCADE` is carried over without reconciling with the `RESTRICT` convention used everywhere else this capability would touch.
- `AttendanceEvent`'s already-independent, unvalidated `shift_id` continuing to diverge from whatever "current" shift-assignment model is eventually built, with no reconciliation mechanism.
- Effective dating being needed later but not planned for now.
- Authorization being retrofitted later if Shift Assignment turns out to need Leave/Attendance-style dedicated-evaluator treatment rather than the CRUD-majority treatment it currently resembles.

---

# 6. Final Recommendation

```
Additional Governance Required
```

This review found no contradiction requiring a different conclusion than `architecture-gap-analysis.md` §9 already reached, and both findings above are Non-blocking. Not **Ready for Implementation Planning**: the two structural, non-content decisions found un-scaffoldable in `architecture-gap-analysis.md` §7 (relationship shape, delete rule) remain genuinely open — nothing in this review resolves either. Not **Waiting for New Capability**: `architecture-gap-analysis.md` §4's finding that both real upstream dependencies (`HrEmployee`, `Shift`) already exist and are merged was re-verified here and not contradicted — nothing needs to be built first. The blockers are architecture and business decisions, confirmed consistent across all four documents, matching the identical recommendation reached by `monetary-representation/architecture-review.md` at the same stage.

---

# References

- `docs/architecture/capabilities/shift-assignment/discovery.md`
- `docs/architecture/capabilities/shift-assignment/decision.md`
- `docs/architecture/capabilities/shift-assignment/domain-model-discovery.md`
- `docs/architecture/capabilities/shift-assignment/architecture-gap-analysis.md`
- `docs/architecture/capabilities/monetary-representation/architecture-review.md` (review methodology and recommendation-sequencing precedent)
