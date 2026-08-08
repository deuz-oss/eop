# Monetary Representation — Decision Round 2

**Status:** Complete

**Capability:** Monetary Representation

**Owner:** EOP Architecture Governance

**Reviews:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `capability-boundary-analysis.md` (all approved, none modified by this document)

---

# Purpose

This document evaluates whether repository governance has now accumulated enough evidence to reduce any of the remaining Unknowns on exactly eight topics: monetary type shape, precision ownership, scale ownership, rounding ownership, formatting ownership, serialization ownership, persistence ownership, currency ownership. It answers only *"can this now be decided?"* — not *"what should the implementation be?"* No Money type, `Decimal`/`Numeric`, `Currency`, ISO 4217, rounding algorithm, precision value, serialization format, JSON structure, SQLAlchemy type, Pydantic type, or API behavior is introduced anywhere below. Capability ownership, aggregate classification, producer/consumer direction, authorization, and the relationships with Compensation, Payroll Calculation, and `Payslip` are already decided and are not reopened here.

---

# 1. Monetary Type Shape

**Repository Evidence**: `domain-model-discovery.md` §1 rejected three of seven candidates (Aggregate Root, Domain Service, Value Object) on direct evidence and left four `Unknown` (Shared Infrastructure, Library, Utility, Type System Extension). `architecture-gap-analysis.md` §1 restates "4 of 7" unresolved. `architecture-review.md` Observation 2 independently re-counted this arithmetic and confirmed it exact. `capability-boundary-analysis.md` §14 re-examined this question directly and concluded the shape "remains genuinely `Unknown`, unchanged from `domain-model-discovery.md` §1."

**Logical Consequence**: No document produced after `domain-model-discovery.md` introduces any new evidence bearing on which of the four remaining candidates fits — each subsequent document restates the same count without narrowing it.

**Unknown**: Which of Shared Infrastructure, Library, Utility, or Type System Extension applies, unchanged.

**Can this now be decided? No.** Four independent passes across four documents (domain-model-discovery, architecture-gap-analysis, architecture-review, capability-boundary-analysis) touched this question and none added evidence beyond what `domain-model-discovery.md` §1 already found. Nothing accumulated.

---

# 2. Precision Ownership

**Repository Evidence**: `decision.md` §3's table assigns "Precision" to Monetary Representation directly ("a technical convention, not business content"). `capability-boundary-analysis.md` §2 independently re-evaluated the same question and reached the identical conclusion by the identical reasoning ("Same reasoning as §1 [Type]. Belongs to Monetary Representation.").

**Logical Consequence**: Two separate governance passes, at two different phases, using the same underlying rationale, reached the same answer without contradiction anywhere in between (`architecture-review.md` §3 found no reclassification of any candidate across all four documents it reviewed).

**Can this now be decided? Yes.** Ownership of the precision *convention* (who decides how precision is handled, not what the precision value is) has been reached twice, independently, with no contradicting evidence anywhere. This is a narrower claim than deciding a concrete precision value, which remains untouched and is not addressed by this conclusion.

---

# 3. Scale Ownership

**Repository Evidence**: No document prior to `capability-boundary-analysis.md` §3 evaluated Scale as a question distinct from Precision — `decision.md` §3's table has no separate row for it, and `discovery.md`'s search treated "scale" only as a search term. `capability-boundary-analysis.md` §3 is the only document to address it, concluding it is "a technical sub-component of Precision, not a conceptually distinct concern," and extending Precision's ownership reasoning to it "by direct extension... not independently re-decided."

**Logical Consequence**: Scale (digits after a decimal point) has no repository meaning separate from Precision (total digits) — both describe the same `NUMERIC(precision, scale)`-shaped technical convention. Nothing in any of the six documents treats them as separable concerns requiring different owners.

**Can this now be decided? Yes, with a caveat.** The extension is sound and uncontradicted, but unlike Precision (§2), it rests on one document's logical extension rather than two independent evaluations. Ownership follows Precision's already-decided conclusion (§2) by direct consequence; it has not been independently re-derived from first principles anywhere.

---

# 4. Rounding Ownership

**Repository Evidence**: `decision.md` §3: *"Rounding — Monetary Representation, mechanism only — The behavior of applying rounding consistently is mechanism-shaped; no repository evidence exists for which rounding rule."* `architecture-gap-analysis.md` §2 classifies "Rounding model" as a **Business Gap**: *"a specific rounding convention... is an accounting/regulatory policy choice, not an architecture question."* `capability-boundary-analysis.md` §4 confirms both findings are consistent, not contradictory, and preserves the split.

**Logical Consequence**: This is not a single-owner question — three documents, read together, consistently split it the same way every time it has been evaluated.

**Can this now be decided? Yes, as a split, not a single owner.** Ownership of the mechanism/behavior of applying rounding consistently belongs to Monetary Representation. Ownership of the specific rounding rule belongs to Business. Both halves of this split have now been reached consistently across three independent documents with zero contradiction. The rule's content remains undecided — that is a separate, unaddressed content question, not an open ownership question.

---

# 5. Formatting Ownership

**Repository Evidence**: `architecture-gap-analysis.md` §2 classifies Formatting as a **Business Gap**: *"Display/locale formatting conventions depend on product/business requirements... no repository evidence addresses this at all."* `capability-boundary-analysis.md` §6 confirms: *"Formatting belongs to Business (locale/display conventions, no repository evidence bears on it)."*

**Logical Consequence**: Two independent documents reach the same conclusion by the same reasoning, with no contradicting evidence anywhere in any of the six documents.

**Can this now be decided? Yes.** Formatting ownership belongs to Business, not Monetary Representation. This is a decidable *exclusion* — Monetary Representation does not own it — reached consistently twice. No formatting convention itself is decided or implied.

---

# 6. Serialization Ownership

**Repository Evidence**: `architecture-gap-analysis.md` §2 classifies Serialization as a **Governance Gap**, explicitly distinct from Formatting's Business Gap, and explicitly left unassigned: *"an architecture/API-design convention question... no repository precedent exists for any numeric serialization beyond plain `Integer`."* `capability-boundary-analysis.md` §6 goes one step further: *"serialization convention would most naturally extend to Monetary Representation's own ownership... since it concerns how the representation mechanism surfaces itself, not what any value means,"* while explicitly flagging this is *"a **Logical Consequence**, not a re-statement of an already-made decision — no document has explicitly assigned Serialization the way §1-2 explicitly assign Type/Precision."*

**Logical Consequence**: The reasoning pattern is identical to the one already used twice to decide Precision ownership (§2) and once to extend it to Scale (§3): a representation mechanism owns how it surfaces itself, distinct from what any value means. No repository evidence contradicts extending that same pattern to Serialization.

**Unknown**: The concrete serialization convention itself (string, structured object, or otherwise) — not addressed here.

**Can this now be decided? Yes, with the same caveat as Scale.** Serialization *ownership* (who would decide the convention, if one is ever needed) follows from the same repeatedly-applied mechanism-owns-its-own-surface reasoning already used for Type and Precision. It rests on one document's explicit self-described logical extension rather than direct, independent repository evidence the way Precision's was — a thinner but consistent basis, not a contradicted one.

---

# 7. Persistence Ownership

**Repository Evidence**: `domain-model-discovery.md` §1 rejected Aggregate Root and Value Object — the two shapes with independent persistence — leaving whether Monetary Representation is persisted at all `Unknown`. `capability-boundary-analysis.md` §7 draws a direct structural analogy to Authorization Foundation: *"it persists nothing itself; every capability-specific evaluator's *data*... is resolved and held by the consuming capability's own service."* On that basis it concludes: *"Persistence representation (the type) belongs to Monetary Representation, if a type-shaped form is eventually chosen; persistence ownership (the table/column) belongs to whichever consuming capability holds the value."*

**Logical Consequence**: This is a conditional split, not a flat statement. The table/column-ownership half (consuming capability owns its own row) does not depend on Monetary Representation's still-undecided shape (§1) — it follows directly from every persisted entity in this repository already owning its own table, with zero exception found anywhere. The type-definition half is conditioned on Monetary Representation eventually taking a type-shaped form, which §1 has not resolved.

**Can this now be decided? Yes, as a conditional split.** Table/column ownership (consuming capability) is decidable now, unconditionally — it follows the repository's uniform, unbroken persistence pattern and does not wait on §1. Type-definition ownership (Monetary Representation, *if* type-shaped) is decidable only as a conditional rule, not as a standing fact, since the underlying shape (§1) remains Unknown. Whether Monetary Representation is persisted *at all* is not decided by this and remains open, unchanged from `domain-model-discovery.md` §1.

---

# 8. Currency Ownership

**Repository Evidence**: `discovery.md` §9 confirmed zero occurrences of "Currency" anywhere in source code. `decision.md` §10 explicitly refused to decide currency, finding zero repository evidence favoring any choice. `capability-boundary-analysis.md` §5 splits the question three ways: the *mechanism* of attaching a currency identifier (if needed at all) would follow the same reasoning as Type/Precision — Monetary Representation's concern; *which* currencies are supported, and whether multi-currency support is needed at all, is a Business concern with zero evidence anywhere; currency *conversion*, if ever required, would plausibly be an External Dependency. That same document explicitly leaves open, as an unresolved **Unknown**, *whether currency handling is needed by this system at all*.

**Logical Consequence**: Unlike Rounding (§4) or Formatting (§5), this split has one leg — mechanism ownership — resting on the same repeatedly-applied Type/Precision reasoning pattern, and one leg — conversion — resting on a "plausible," not confirmed, classification. The threshold question underneath all three legs (is currency needed at all) has never been evidenced either way.

**Unknown**: Whether currency handling is needed by this system at all — carried forward unresolved from `capability-boundary-analysis.md` §5, not newly addressed here.

**Can this now be decided? Partially.** *If* currency handling is ever needed, ownership of the attachment mechanism can be decided now, by the same consistent, uncontradicted reasoning already applied to Type/Precision/Serialization — Monetary Representation. *Which* currencies, and whether multi-currency support exists at all, cannot be decided — zero repository evidence exists in either direction, and no new evidence appeared across any of the six documents. Conversion ownership remains a "plausible" classification only, not confirmed, and is not decided here.

---

# Summary: Has Governance Accumulated Enough Evidence to Reduce the Remaining Unknowns?

| Topic | Can be decided now? |
|---|---|
| 1. Monetary type shape | **No** — unchanged across four documents |
| 2. Precision ownership | **Yes** — reached independently twice |
| 3. Scale ownership | **Yes** — by direct extension of §2 |
| 4. Rounding ownership | **Yes**, as a split (mechanism decided; rule content still open) |
| 5. Formatting ownership | **Yes** — reached independently twice, as an exclusion |
| 6. Serialization ownership | **Yes**, on a thinner (single-document, self-described logical) basis |
| 7. Persistence ownership | **Yes**, as a conditional split (table/column unconditional; type-definition conditioned on §1) |
| 8. Currency ownership | **Partially** — mechanism ownership decidable if ever needed; whether needed at all remains Unknown |

Six of eight ownership-shaped topics (§2–§7, with §8 partial) can now be formally decided, all by consolidating reasoning that was already present — independently, consistently, and without contradiction — across `decision.md`, `architecture-gap-analysis.md`, and `capability-boundary-analysis.md`. None of this required inventing new evidence; each was already latent in prior documents and is confirmed here by direct cross-check, not by new derivation. The one topic that has not moved at all is the architectural shape itself (§1) — every document that has touched it since `domain-model-discovery.md` restates the same four-of-seven-Unknown finding without narrowing it. Content-level values (which precision, which rounding rule, which currencies, the actual serialization format) remain entirely undecided regardless of ownership — ownership and content are separate questions, and only the former is addressed here.

---

# References

- `docs/architecture/capabilities/monetary-representation/discovery.md`
- `docs/architecture/capabilities/monetary-representation/decision.md`
- `docs/architecture/capabilities/monetary-representation/domain-model-discovery.md`
- `docs/architecture/capabilities/monetary-representation/architecture-gap-analysis.md`
- `docs/architecture/capabilities/monetary-representation/architecture-review.md`
- `docs/architecture/capabilities/monetary-representation/capability-boundary-analysis.md`
