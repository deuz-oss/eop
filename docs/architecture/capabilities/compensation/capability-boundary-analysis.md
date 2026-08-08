# Compensation — Capability Boundary Analysis

**Status:** Complete

**Capability:** Compensation

**Owner:** EOP Architecture Governance

**Reviews:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `implementation-plan.md` (all approved, none modified)

---

# 1. Purpose

Every unresolved item left inside Compensation's approved governance is examined here to determine whether it is genuinely Compensation's own responsibility, belongs to another capability (existing or not-yet-modeled), depends on something external, or remains undecidable from repository evidence. This is an architecture-governance analysis only — no code, ADR, decision, or implementation plan is produced. Every conclusion is derived from repository evidence or the six already-approved Compensation documents; nothing is invented.

---

# 2. Review of Every Remaining Unknown

| Topic | Classification | Reasoning |
|---|---|---|
| Monetary representation (type/fields) | **Compensation responsibility — with a Separate-capability candidate flagged (§3)** | `decision.md` §6 already established Compensation is the evidence-supported owner of monetary values, by elimination (five capabilities disclaim it, none else claims it). The specific *content* is Compensation's to decide. But *how* money is represented at all — a reusable type/precision convention — has no owner anywhere yet; see §3. |
| Precision | **Compensation responsibility — same Separate-capability candidate applies** | A sub-question of monetary representation; same reasoning. |
| History | **Separate-capability candidate (§3)** | `domain-model-discovery.md` §2.1 found `CompensationHistory` has no repository precedent of any kind — its only, weak analogy (`AuditLog`) is itself a generic, cross-capability, entity-agnostic mechanism, not something built per-capability. This shape is evidence the repository's own instinct for "history" is cross-cutting, not domain-specific. |
| Effective dating | **Separate-capability candidate (§3), same cluster as History** | Same reasoning as History — no repository precedent exists anywhere, and the closest analog (`AuditLog`) is cross-cutting, not capability-specific. |
| Lifecycle (mutable/immutable/append-only) | **Compensation responsibility** | Every capability in this repository that has made a lifecycle decision (`LeaveRequest`'s mutable+approval-gated shape, `Payslip`'s immutable-after-creation shape, `PayrollRun`'s mutable shape) decided it for itself — there is no cross-cutting "Lifecycle Policy" capability anywhere that decides this on another's behalf. `domain-model-discovery.md` §2.6's unresolved tension is a decision Compensation's own governance must still make, informed by (not delegated to) the audit-trail principle already used elsewhere. |
| `JobGrade` relationship | **Compensation responsibility** | `decision.md` §3 already decided monetary *interpretation* belongs to Compensation, not `JobGrade`; whether/how Compensation *references* `JobGrade` is an ordinary aggregate-design question (does one entity FK another), the same kind of decision every other entity in this repository has made for itself. No evidence suggests a third capability is needed to mediate it. |
| `PayrollRun` relationship | **Compensation responsibility** (in coordination with `PayrollRun`'s own governance) | Same reasoning — an FK/reference-design question, not evidence of a missing capability. |
| `Payslip` relationship | **Compensation responsibility** (in coordination with `Payslip`'s own governance) | Same reasoning. |
| Authorization | **Compensation responsibility (deferred, not leaked)** | `decision.md` §7 found this blocked by the same structural reasoning already applied to Payroll, Payslip, and Payroll Calculation Authorization. Repository precedent for *where* this gets decided is mixed: Payroll Authorization was given its own separate capability folder (`payroll-authorization/`), but Payslip's and Payroll Calculation's own authorization questions were each resolved as an embedded topic inside their own `decision.md` (§8 in both), not spun into a separate folder. The more recent, more consistent pattern (two instances vs. one) is embedded, not separate — Compensation Authorization is not evidence of a missing capability, only of a topic sequenced after Compensation itself exists. |
| Naming ("Compensation") | **Still unknown** | No pre-existing governance document (predating this conversation) uses the term at all (`discovery.md` §9-10); this is a terminology question with no repository evidence pointing either way, not a responsibility question. |

---

# 3. Capability Leakage Analysis

**Yes** — Compensation governance is attempting to answer one question that repository evidence suggests belongs to a capability broader than Compensation itself.

## Monetary representation/precision (primary finding)

**Repository Evidence**: `discovery.md` §4 and `architecture-gap-analysis.md` §2 both establish that no monetary or fractional-precision type has *ever* been used anywhere in this codebase — this is not a Compensation-specific gap, it is a platform-wide absence. Separately, `ADR-007` (Authorization Foundation) documents an explicit design principle already proven twice in this repository: *"Authorization mechanism is separated from authorization policy"* — Authorization Foundation (`AuthorizationRequest`/`AuthorizationDecision`/`AuthorizationEvaluator`/`AuthorizationService`) was built once, generically, before any capability-specific policy (`ApprovalAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`, `AttendanceAuthorizationEvaluator`) was decided, precisely so each capability could plug in its own policy without re-inventing the mechanism.

**Logical Consequence**: A monetary *type/precision convention* is structurally the same kind of thing Authorization Foundation already solved for authorization: a reusable mechanism multiple future capabilities would need (Compensation's own value; `Payslip`'s eventual gross/net/tax/deduction fields, already named as future concerns in `LEAVE_DESIGN.md` §10, `TIMESHEET_DESIGN.md` §11, and this conversation's own `payroll-calculation/discovery.md`; Payroll Calculation's own computed results). Deciding a monetary type *only* inside Compensation's own governance risks the same problem Authorization Foundation was built specifically to avoid — each future money-touching capability re-deciding its own incompatible representation.

**Unknown**: Whether this should take the shape of a formal "Foundation"-style capability (as Authorization did) or something lighter (a shared convention documented once, not a running service) is not decidable from repository evidence — no document anywhere addresses this. This analysis does not invent a name, schema, or design for it.

## History / effective dating (secondary, weaker finding)

**Repository Evidence**: `AuditLog` is the only entity in the repository resembling a "record of change," and its own shape is generic and entity-agnostic (`action`/`entity_type`/`entity_id`/`details`), not built per-capability (`discovery.md` §5, `domain-model-discovery.md` §2.1).

**Logical Consequence**: This is a weaker echo of the same pattern found for monetary representation — the one existing artifact adjacent to "history" was built cross-cutting, not domain-specific — but unlike Authorization Foundation, no document anywhere states this as a deliberate design principle, and `AuditLog`'s own shape (an action log) does not obviously support effective-dated *value* queries ("what was this value as of date X") the way a true temporal-value mechanism would need to. This finding is real but less evidenced than the monetary one.

**Unknown**: Whether `AuditLog` could be extended to serve this purpose, or whether a genuinely different mechanism would be needed, is not addressed anywhere and is not decided here.

## Everything else (`JobGrade`/`PayrollRun`/`Payslip` relationships, lifecycle, authorization sequencing, naming)

No leakage found — each remains Compensation's own to resolve (or, for authorization, Compensation's own to resolve later), per §2's reasoning.

---

# 4. Candidate Capability Extraction

| Leaked responsibility | Outcome | Reasoning |
|---|---|---|
| Monetary type/precision mechanism | **Separate capability (candidate)** | Direct structural analogy to Authorization Foundation's already-proven mechanism/policy separation (§3); not invented, mirrored from an existing, documented repository precedent. No name is proposed here — inventing one is not unavoidable at this stage; the finding is that a *decision about whether this mechanism should exist* is missing, not a specific design. |
| History / effective dating | **Separate capability (candidate), weaker confidence** | Weaker structural analogy (`AuditLog`'s generic shape); flagged, not asserted with the same confidence as the monetary finding. |
| `JobGrade`/`PayrollRun`/`Payslip` relationships | **No capability** | Ordinary aggregate-design questions within Compensation's and its neighbors' own existing governance. |
| Lifecycle | **No capability** | Per-capability decision, matching uniform repository precedent. |
| Authorization | **No capability** (Business decision timing, not a missing capability) | Deferred by sequencing, matching the Payslip/Payroll Calculation precedent, not the payroll-authorization/ precedent. |
| Naming | **Business decision** | Terminology only; no architectural weight. |

---

# 5. Repository Evidence Supporting Every Conclusion

- **Repository Evidence**: Zero monetary/precision type has ever existed in this codebase, at any point, for any purpose (`discovery.md` §4, re-confirmed `architecture-gap-analysis.md` §2). `ADR-007`'s own documented design principle: mechanism separated from policy, already exercised twice (Approval, Leave, Attendance Authorization). `AuditLog`'s shape is generic and cross-entity, confirmed by direct model read (`models/audit_log.py`). No `*History`/`*Version`/`*Revision` entity exists anywhere (`domain-model-discovery.md` §2.1). Every lifecycle decision found in the repository (`LeaveRequest`, `Payslip`, `PayrollRun`) was made independently, per-capability. Payroll Authorization has its own folder; Payslip and Payroll Calculation Authorization do not (`payroll-authorization/`, `payslip/decision.md` §8, `payroll-calculation/decision.md` §8, directly compared).
- **Logical Consequence**: A monetary mechanism, if built only inside Compensation, would not be reusable by `Payslip`/Payroll Calculation without either duplicating it or awkwardly depending on Compensation's own internal representation — the same problem Authorization Foundation's separation was built to prevent. History/effective-dating's analogous case is real but rests on a single, weaker artifact (`AuditLog`) rather than a stated design principle.
- **Unknown**: Whether a Monetary Foundation (or equivalent) should be a running service, a shared type convention, or something else; whether `AuditLog` can be extended for history, or a new mechanism is needed; whether "Compensation" is the correct final name for anything in this analysis.

---

# 6. Cross-Reference with Existing Governance

Checked against Payroll, Payslip, Payroll Calculation, and Payroll Authorization for ownership conflicts:

- **Payroll (`PayrollRun`)**: `payroll/decision.md` §4 already anticipates `PayrollRun` "eventually own[ing]... whatever computation logic combines its own inputs... into a result, once those rules and their required data exist." A Monetary Foundation providing *mechanism* (type/precision) would not conflict with this — `PayrollRun` would still own its own eventual computation *content*, the same separation Authorization Foundation maintains between mechanism and each capability's own policy. No conflict.
- **Payslip**: Already decided as its own Aggregate Root, immutable after creation, owning no computation (`payslip/decision.md` §1, §4). A shared monetary type would not alter this — `Payslip` would still own which fields it has and when it's created; a Monetary Foundation would only provide the type those fields might use. No conflict.
- **Payroll Calculation**: `payroll-calculation/decision.md` §1 already establishes it owns the *responsibility* for combining inputs into a result, by exclusion. A Monetary Foundation is upstream of this, the same way Authorization Foundation is upstream of `ApprovalAuthorizationEvaluator` — it does not compete for the same ownership. No conflict.
- **Payroll Authorization**: Already an independently-blocked, separately-foldered capability (`payroll-authorization/decision.md`), unaffected by anything in this analysis — it concerns access control, not monetary representation. No conflict.

No ownership overlap is introduced by any finding in this document.

---

# 7. Architecture Recommendation

```
New capability required before Compensation can continue.
```

Specifically, and only, for the monetary-representation/precision topic (§2, §3): repository evidence (`ADR-007`'s own mechanism/policy separation principle, already proven twice) indicates this question is broader than Compensation alone and should be decided — at minimum, whether a shared mechanism is warranted — before Compensation's own monetary fields are finalized, to avoid the same duplication-of-mechanism problem Authorization Foundation was built to prevent.

This does **not** mean every Compensation topic is blocked on a new capability: `JobGrade`/`PayrollRun`/`Payslip` relationship design, lifecycle, and authorization sequencing (§2) remain Compensation's own to resolve independently and are not gated on anything new. History/effective dating (§3) is a weaker, secondary candidate for the same treatment, worth carrying forward but not asserted with the same confidence.

---

# 8. Next Action

```
Begin Discovery for a Monetary Representation (mechanism-only) capability,
following the same repository-first method already used for Authorization
Foundation's own discovery — before continuing Compensation's own
field-level decisions.
```

This is the single next governance activity recommended. It does not replace or repeat any Compensation-specific work already completed; it addresses the one finding in this analysis with strong, direct repository-evidenced support (§3, §5).
