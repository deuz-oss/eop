# Monetary Representation — Capability Boundary Analysis

**Status:** Complete

**Capability:** Monetary Representation

**Owner:** EOP Architecture Governance

**Reviews:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md` (all approved, none modified)

---

# Purpose

This document determines whether each unresolved item remaining after Architecture Review genuinely belongs to Monetary Representation, or actually belongs to another capability (existing or not-yet-modeled). It does not resolve any Unknown; it determines whether each is the *correct* Unknown for this capability. Every conclusion is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**.

---

# 1. Monetary Type

**Repository Evidence**: `decision.md` §2 already decided Monetary Representation owns "how a monetary value is typed," by direct analogy to `ADR-007`'s mechanism/policy separation and by elimination (`discovery.md` §1/§4/§6 — nothing else owns any numeric/monetary convention).

**Logical Consequence**: Type selection is the most direct, least ambiguous expression of what Monetary Representation was decided to own. **Belongs to Monetary Representation.**

**Unknown**: Which concrete type — not re-litigated here.

---

# 2. Precision

**Repository Evidence**: `decision.md` §3's table explicitly assigns "Precision" to Monetary Representation ("a technical convention, not business content").

**Logical Consequence**: Same reasoning as §1. **Belongs to Monetary Representation.**

---

# 3. Scale

**Repository Evidence**: No prior document evaluated "Scale" as a distinct ownership question — `decision.md` §3's table has no separate row for it; `discovery.md`'s search treated "scale" only as a search term, not an ownership analysis.

**Logical Consequence**: Scale (the number of digits after a decimal point, the SQL `NUMERIC(precision, scale)` companion to Precision) is a technical sub-component of Precision, not a conceptually distinct concern. The identical reasoning `decision.md` §3 already applied to Precision ("a technical convention, not business content") extends to Scale without requiring separate re-derivation. **Belongs to Monetary Representation, by direct extension of the Precision decision — not independently re-decided here.**

---

# 4. Rounding

**Repository Evidence**: Two prior documents address this and, read together, already draw a split, not a single answer. `decision.md` §3: *"Rounding — Monetary Representation, mechanism only — The behavior of applying rounding consistently is mechanism-shaped; no repository evidence exists for which rounding rule."* `architecture-gap-analysis.md` §2 classifies "Rounding model" as a **Business Gap**: *"a specific rounding convention... is an accounting/regulatory policy choice, not an architecture question."*

**Logical Consequence**: These two findings are consistent with each other, not contradictory — they address different layers of the same question. **The mechanism/behavior of applying rounding consistently belongs to Monetary Representation. The specific rounding rule (which convention) is a Business concern, external to this repository's own architecture.** This split is preserved here, not collapsed into a single answer.

---

# 5. Currency

**Repository Evidence**: `discovery.md` §9 confirmed zero occurrences of "Currency" anywhere in source code. `decision.md` §10 explicitly refused to decide currency, finding zero repository evidence favoring any choice.

**Logical Consequence**: Currency splits across three of the four offered framings, by the same mechanism-vs-content-vs-external reasoning already established elsewhere in this analysis: the *mechanism* of attaching a currency identifier to a monetary value (if one is needed at all) would follow §1-2's reasoning — **Monetary Representation's concern**. *Which* currencies are supported, and whether multi-currency support is needed at all, is a **Business concern** — no product/business requirement for this is evidenced anywhere. Currency *conversion* (exchange rates), if ever required, would plausibly be an **External Dependency** — exchange-rate data originates outside this repository by nature.

**Unknown**: Whether currency handling is needed by this system at all — no document anywhere establishes multi-currency, or even single-currency-labeling, as a requirement. This is not resolved here.

---

# 6. Formatting / Serialization

**Repository Evidence**: `architecture-gap-analysis.md` §2 classified these as two separate concepts: Formatting as a **Business Gap** ("Display/locale formatting conventions depend on product/business requirements"), Serialization as a **Governance Gap** ("an architecture/API-design convention question").

**Logical Consequence**: This split is preserved, not merged. **Formatting belongs to Business** (locale/display conventions, no repository evidence bears on it). **Serialization** — how a monetary value would appear in an API/schema — was classified as an open governance question, not yet assigned; by extension of §1-2's own reasoning (representation mechanism owns how a value is typed and constrained), serialization convention would most naturally extend to Monetary Representation's own ownership if and when decided, since it concerns how the representation mechanism surfaces itself, not what any value means. This is a **Logical Consequence**, not a re-statement of an already-made decision — no document has explicitly assigned Serialization the way §1-2 explicitly assign Type/Precision.

---

# 7. Persistence Representation

**Repository Evidence**: `domain-model-discovery.md` §1 rejected Aggregate Root and Value Object — the two shapes with independent persistence — leaving whether Monetary Representation is persisted at all `Unknown`.

**Logical Consequence**: This question splits cleanly along the same mechanism-vs-content line already established throughout this analysis. *If* Monetary Representation takes a type-shaped form (a column/schema type), then the type definition itself belongs to Monetary Representation — the same way `ADR-007`'s Authorization Foundation defines the *shape* of an `AuthorizationDecision` without itself persisting anything. But the actual *table/column* — which capability's row holds a given monetary value — belongs to the consuming capability (Compensation's own table, `Payslip`'s own table), not to Monetary Representation. Authorization Foundation is the direct precedent for this exact split: it persists nothing itself; every capability-specific evaluator's *data* (e.g., `manager_id`) is resolved and held by the consuming capability's own service. **Persistence representation (the type) belongs to Monetary Representation, if a type-shaped form is eventually chosen; persistence ownership (the table/column) belongs to whichever consuming capability holds the value.**

---

# 8. Relationship with Compensation

**Repository Evidence**: `decision.md` §2-3 explicitly excludes business/salary meaning from Monetary Representation, assigning it to Compensation (`compensation/decision.md` §1, already established). `architecture-review.md` §4 independently re-verified no absorption in either direction.

**Logical Consequence**: No ownership overlap. **Neither capability absorbs the other** — Monetary Representation owns mechanism (§1-7 above); Compensation owns business content and meaning. This finding is re-confirmed here, not newly derived.

---

# 9. Relationship with Payroll Calculation

**Repository Evidence**: `decision.md` §4 — Monetary Representation is producer, Payroll Calculation is consumer; Payroll Calculation owns computation (`payroll-calculation/decision.md` §1), by exclusion.

**Logical Consequence**: No overlap. No speculation about formulas or computation is introduced here, per instruction.

---

# 10. Relationship with Payslip

**Repository Evidence**: `decision.md` §5 — `Payslip` would consume Monetary Representation's mechanism if and when it gains monetary fields (not decided anywhere); `Payslip` does not own representation.

**Logical Consequence**: No overlap.

---

# 11. Relationship with `PayrollRun`

**Repository Evidence**: No document, across five documents in this capability's own governance and every prior sibling-capability document, establishes any relationship between Monetary Representation and `PayrollRun` in either direction (`discovery.md` §2/§8, `domain-model-discovery.md` §5, `architecture-gap-analysis.md` §4, `architecture-review.md` §3, all consistent).

**Unknown, and correctly so**: This is not evidence of leakage to a third capability — it is a genuinely open question belonging jointly to Monetary Representation's own future governance and `PayrollRun`'s own (`payroll/`), neither of which has addressed it. Not resolved here.

---

# 12. Relationship with Authorization Foundation

**Repository Evidence**: `domain-model-discovery.md` §9 already evaluated this exact question directly: *"Conceptual. The relationship is a shared underlying design principle... not an architectural relationship (no structural/dependency coupling exists), not an implementation relationship (no code exists to be coupled), and not none."*

**Logical Consequence**: Re-verified against the source text in this analysis, not re-derived — the classification holds. **Conceptual**, confirmed unchanged.

---

# 13. Future Consumers

**Repository Evidence**, inventoried only from what is already evidenced somewhere in repository governance, nothing invented:

- **Compensation** — `compensation/decision.md` §6, `discovery.md` §2/§8.
- **Payroll Calculation** — `payroll-calculation/architecture-gap-analysis.md` §1/§8, `discovery.md` §2/§8.
- **`Payslip`** — named via `compensation/capability-boundary-analysis.md` §3, citing `LEAVE_DESIGN.md` §10 and `TIMESHEET_DESIGN.md` §11's own "Future Compatibility" sections.

**Logical Consequence**: No fourth consumer is evidenced anywhere. A fresh check against this capability's own terminology sweep (`discovery.md` §9 — 17 matching documents, all already within this same Payroll-family governance trail) confirms no capability outside this cluster (e.g., Project Tracking's `Employee`/`Assignment`/`Task`, or any ERP-adjacent concept named in `docs/product/02_PRODUCT_SCOPE.md`) has any documented need for monetary values. **Exactly three consumers are evidenced; none is invented here.**

---

# 14. Capability Extraction Analysis

**Repository Evidence**: `decision.md` §6 found three independent lines of evidence supporting mechanism/policy separation (Authorization Foundation's proven precedent; five capabilities' own repeated disclaimers; `EventService`/`JobService`'s weaker dormant pattern) — none of these support folding a shared mechanism back into a single consuming capability's own governance. `domain-model-discovery.md` §1 leaves four of seven candidate shapes `Unknown`, including "Shared Infrastructure" (closest resemblance, not confirmed).

**Logical Consequence**: Authorization Foundation itself is the repository's own precedent that "its own capability" and "shared infrastructure" are not mutually exclusive categories — `ADR-007` is both a formally-governed capability (its own ADR, its own `capabilities/authorization/` documents) and infrastructure-shaped (no persisted entity, no independent business content). By this same precedent, the strongest-evidenced framing for Monetary Representation is that it would remain its own capability *while being* shared infrastructure in shape — not a choice between the two.

**No decision is forced.** Folding into Compensation or Payroll Calculation is not supported by any evidence (§8-9, and `decision.md` §10's own rejection of exactly this). Whether the concrete shape converges on "Shared Infrastructure," "Type System Extension," or something not yet named remains genuinely `Unknown`, unchanged from `domain-model-discovery.md` §1 — this analysis narrows *which* capability the responsibility belongs to (Monetary Representation itself, confirmed across §1-13) without narrowing *what shape* that capability ultimately takes.

---

# Major Findings Summary

- Every topic evaluated (§1-7) belongs to Monetary Representation itself, Business policy, or (for currency conversion specifically) a plausible External Dependency — **none belongs to another existing capability**.
- Rounding and Currency are not single-owner questions — both split cleanly along a mechanism/business/external line already implicit in prior documents, made explicit and consistent here for the first time.
- No ownership overlap exists with Compensation, Payroll Calculation, `Payslip`, or Authorization Foundation (§8-10, §12) — each re-verified, not merely re-asserted.
- The `PayrollRun` relationship (§11) remains genuinely `Unknown` and correctly so — it is not evidence of a missing third capability, only an open question between two existing governance trails.
- Exactly three consumers are evidenced anywhere in repository governance (§13); no fourth exists to invent.
- Monetary Representation's continued existence as its own capability is well-supported (§14); its concrete architectural shape is not, and remains appropriately open.

---

# Recommendation

```
Ready for New Decision
```

This analysis confirms the remaining Unknowns are correctly scoped to Monetary Representation itself — none was found to be leaked to Compensation, Payroll Calculation, `Payslip`, `PayrollRun`, or Authorization Foundation. Unlike Compensation's own boundary analysis (which surfaced a genuinely missing capability), this analysis surfaces no missing capability — "Capability Should Not Exist" is not supported (three real, evidenced consumers exist, and the mechanism/policy separation rationale remains well-evidenced). What is needed next is a focused decision round addressing the specific, now-clarified questions this document narrowed (concrete shape among the remaining candidates; type/precision/rounding-rule/currency content, per §1-7) — not a repeat of Architecture Review (already complete and unchanged by this analysis) and not open-ended "Continue Governance."

---

# References

- `docs/architecture/capabilities/monetary-representation/discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`
- `docs/architecture/capabilities/compensation/capability-boundary-analysis.md` (methodology precedent)
- `docs/architecture/ARCHITECTURE_DECISION_RECORDS/ADR-007-authorization-foundation.md`
