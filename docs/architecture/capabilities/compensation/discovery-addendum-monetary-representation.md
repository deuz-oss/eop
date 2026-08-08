# Compensation — Discovery Addendum: Monetary Representation

**Status:** Complete

**Capability:** Compensation

**Type:** Architectural Delta — not a new Discovery

**Owner:** EOP Architecture Governance

**Baseline:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `implementation-plan.md`, `capability-boundary-analysis.md`, `final-governance-summary.md` (all unchanged, all remain authoritative)

---

# Purpose

This addendum records what has changed since Compensation's original governance chain was completed: the Monetary Representation capability, which that chain's own `capability-boundary-analysis.md` originated as a candidate, is now a completed foundation capability with a real, implemented type. This document identifies what that fact does and does not change about Compensation's own conclusions. It does not reopen, rewrite, or invalidate anything in the existing chain.

---

# 1. Monetary Representation Now Exists as a Completed Foundation Capability

**Repository Evidence**: `services/api/src/eop_api/foundation/monetary/types.py` implements `Money` — an immutable, frozen-dataclass value object with mandatory currency, amounts normalized to 2 decimal places via `ROUND_HALF_UP` at construction, and zero dependency on any business capability, persistence layer, or framework (`decimal`/`dataclasses` stdlib only). Verified working: 15/15 unit tests passing, clean `ruff`/`mypy`. Monetary Representation's own governance chain closed with recorded business policy — fixed system precision (2 decimal places), rounding applied at the final calculation boundary (half up), and currency context mandatory with single-currency scope initially.

**Logical Consequence**: This did not exist in any form — as governance or as code — when Compensation's `discovery.md` was written. `discovery.md` §4's own finding, *"Zero monetary fields exist anywhere in the repository,"* and its broader search for `Decimal|Numeric|MONEY|Float|currency` returning zero matches, was accurate at the time and remains accurate about Compensation's own code specifically (still none exists), but is no longer accurate as a repository-wide statement — a monetary type now exists, just not inside Compensation.

---

# 2. Compensation Is Expected to Become the First Monetary Consumer

**Repository Evidence**: `monetary-representation/decision.md` §2, `capability-boundary-analysis.md`, and `monetary-representation/consumer-discovery.md` (Phase 3.1) all independently name Compensation as a documented future consumer of `Money` — `consumer-discovery.md`'s own Consumer Inventory table classifies it *"High priority, once implemented — this is the evidenced future owner of monetary content."* No code-level consumption exists yet; Compensation has zero implementation, confirmed directly in that same discovery pass.

**Logical Consequence**: This directly confirms, rather than contradicts, Compensation's own original `decision.md` §6: *"If monetary values are introduced, Compensation — not any other capability — is the evidence-supported owner."* That conclusion was reached entirely by elimination, before `Money` existed in any form, and has now been independently corroborated from the opposite direction — by Monetary Representation's own governance, reasoning about its future consumers rather than about who owns monetary content.

---

# 3. Effect on Original Discovery Conclusions

Reviewed against every finding in `discovery.md` and decision in `decision.md`/`domain-model-discovery.md`/`architecture-gap-analysis.md`.

**Genuinely affected (narrowed, not reversed)**:
- `decision.md` §9's Deferred Decision *"What monetary/precision type would be used — no monetary type has ever existed in this codebase"* — the *mechanism* half of this is no longer accurate: a type now exists. The *content* half — which specific fields Compensation needs, and whether/how it adopts `Money` — remains exactly as undecided as before. This is a narrowing of scope, not a resolution.
- `architecture-gap-analysis.md` §2's "Monetary type support" gap, classified `Business Gap` with reasoning *"no monetary content... has been decided"* — the type-existence half of the blocker is gone; the content-decision half, which was always the primary blocker per that same table entry, is unchanged.

**Not affected — the core blocker is untouched**:
- `architecture-gap-analysis.md` §7's *"Can Iteration 1 Begin? NO"* — its reasoning was never "no type exists," it was *"a record containing only an `employee_id` FK and no monetary value would not represent 'compensation' in any meaningful sense."* `Money`'s existence supplies a mechanism to hold a value; it supplies no value, and no decision about which fields Compensation needs. This conclusion stands unchanged.
- `decision.md` §5 (current-value-only vs. history vs. versioned shape) — `Unknown`, untouched. `Money` has no history/versioning behavior of any kind; that territory belongs to the separate Effective Dating capability, not addressed by this addendum.
- `domain-model-discovery.md` §2.6 (lifecycle mutability tension) — untouched; unrelated to monetary representation mechanics.
- `domain-model-discovery.md` §2.5 (relationships to `JobGrade`/`PayrollRun`/`Payslip`, mostly `Unknown`) — untouched.
- `decision.md` §7 (Authorization, blocked — no resource exists) — untouched.
- `decision.md` §1-4 (ownership, separation from `HrEmployee`, `JobGrade` boundary, Aggregate Root classification) — untouched; none of these questions concerned monetary mechanics.

**Net effect**: Compensation's Implementation Gate remains **BLOCKED**, for the same reason `final-governance-summary.md` already identified — business content, not a missing mechanism.

---

# 4. Architectural Impacts

- If/when Compensation is implemented, its monetary fields should be constructed as `Money` (`eop_api.foundation.monetary.types.Money`) rather than an independently-chosen `Numeric`/`Decimal` column type — this avoids duplicating precision/rounding logic Monetary Representation already owns, and avoids a later migration to adopt it retroactively.
- **`Money` has no persistence of its own** — confirmed directly in its implementation (a plain, unmapped value object) and in Monetary Representation's own governance (*"No independent persistence... belongs inside the lifecycle of the consuming capability"*). Compensation would still need to define its own database column(s) to store what a `Money` value represents (e.g., a `Numeric` column with a scale matching `Money`'s 2-decimal-place convention) and construct/deconstruct `Money` instances at its own service layer. Adopting `Money` does not resolve Compensation's own persistence design — that remains entirely Compensation's to decide, unaffected by anything in this addendum.
- Since `Money` mandates a currency value per instance, any Compensation schema adopting it would need its own currency column/value too — this doesn't resolve the currency-scope question `architecture-gap-analysis.md` §8 already deferred to Business; it only means Compensation's eventual schema, whenever designed, must account for a currency field to satisfy `Money`'s own contract.

No entity, schema, or migration is created by this observation — these are named as future implications only, per instruction.

---

# 5. Compensation Governance Documents That Should Be Updated in the Future

Identified only — none modified by this addendum:

- `decision.md` §9 — the "monetary/precision type" Deferred Decision should be narrowed to reflect that the mechanism now exists; the content question remains open.
- `architecture-gap-analysis.md` §2, §6, §8 — the "Monetary type support" gap entry and the corresponding "Decide whether Compensation carries a monetary representation at all" blocking item should be revised to state the mechanism is available, narrowing the blocker to content decisions only.
- `implementation-plan.md` §4 — its reasoning for why no model can be defined cites, among other things, that no monetary type exists in the codebase; that specific sub-reason is now outdated, though its overall conclusion (no model authorized) is not.
- `final-governance-summary.md` — its Remaining Decisions section should note `Money`'s existence as a resolved prerequisite, narrowing what "remaining" actually means.

---

# 6. Conclusions That Remain Unchanged

Restated, not re-derived:

- Compensation owns its own data, by elimination (`decision.md` §1).
- Compensation remains separate from `HrEmployee`, not fields added to it (`decision.md` §2).
- Monetary *interpretation* belongs to Compensation, not `JobGrade`; the relationship mechanism between them remains undecided (`decision.md` §3).
- Compensation classifies as an Aggregate Root (`decision.md` §4).
- History/versioning shape remains `Unknown` (`decision.md` §5, `domain-model-discovery.md` §2.1-2.2).
- Lifecycle mutability remains unresolved, with genuinely conflicting repository evidence (`domain-model-discovery.md` §2.6).
- Relationships to `PayrollRun`/`Payslip`/Payroll Calculation's exact mechanism remain `Unknown` (`domain-model-discovery.md` §2.5, §2.9).
- Authorization remains not decidable today (`decision.md` §7).
- **Can Iteration 1 Begin? Still `NO`** (`architecture-gap-analysis.md` §7) — for the original reason, not a new one.
- Overall Implementation Gate: still **BLOCKED**, still waiting on Business content (`final-governance-summary.md`).

---

# References

- `docs/architecture/capabilities/compensation/discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `implementation-plan.md`, `capability-boundary-analysis.md`, `final-governance-summary.md` (baseline, unchanged)
- `docs/architecture/capabilities/monetary-representation/decision.md`, `capability-boundary-analysis.md`, `consumer-discovery.md`, `final-governance-summary.md`
- `services/api/src/eop_api/foundation/monetary/types.py`
- `services/api/tests/test_monetary_types.py`
