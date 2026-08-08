# Effective Dating — Architecture Gap Analysis

**Status:** Complete

**Capability:** Effective Dating

**Owner:** EOP Architecture Governance

**Based On:** `discovery.md`, `decision.md`, `domain-model-discovery.md`

---

# 1. Architectural Readiness

| Component | Classification | Repository Evidence |
|---|---|---|
| `BaseEntity` | **Sufficient, conditionally** | Universal, proven infrastructure. `domain-model-discovery.md` §1/§6 found Effective Dating itself likely does not persist its own data (mirroring Authorization Foundation's own zero-persistence shape) — `BaseEntity` would remain relevant only to *consuming* capabilities' own tables, which already use it. |
| `BaseRepository` | **Sufficient, conditionally** | Same reasoning — proven for whichever consuming capability's table gains new columns; not necessarily needed by Effective Dating itself. |
| Repository pattern | **Sufficient, conditionally** | Same reasoning. |
| `UnitOfWork` | **Sufficient, conditionally** | Proven, uniform across every reviewed service; would apply to consuming capabilities' own writes. |
| API layering (`API → Service → UoW → Repository → Model`) | **Sufficient, conditionally** | `Assignment`'s own full stack proves this layering works; if Effective Dating itself needs no API of its own (being mixin/evaluator-shaped, not a resource, per `domain-model-discovery.md` §2), this layering is relevant only to consumers' already-existing APIs. |
| Authorization Foundation | **Not Applicable (as direct reuse)** | `domain-model-discovery.md` §9 classifies the relationship `Conceptual` — no structural or dependency coupling exists, and none would be created by literally extending `AuthorizationEvaluator`, which is shaped for access decisions, not temporal interpretation. Its *precedent value* as a structural comparison is real and substantial (§3 below) but distinct from direct reuse. |
| `VersionMixin` | **Not Applicable** | `decision.md` §4 and `domain-model-discovery.md` §7 both confirm this is an independent concern (optimistic concurrency, not temporal history); Effective Dating gains nothing from its own dead mechanism. |
| `AuditLog` | **Not Applicable** | `decision.md` §5/§9 directly rejected this as an evolution path; `domain-model-discovery.md` §3 classifies it a third, unrelated shape (central log) that does not fit Effective Dating's needs. |

---

# 2. Missing Concepts

Each classified as exactly one category, per instruction.

| Concept | Classification | Reasoning |
|---|---|---|
| Temporal identity | **Repository Gap** | Zero precedent anywhere for "one logical thing across multiple time-scoped values" (`discovery.md` §1, `domain-model-discovery.md` §1) — a pure technical absence, Effective Dating's own defining concern regardless of who eventually builds it. |
| Active-at-date lookup | **Repository Gap** | Only two narrow, hand-written, capability-specific examples exist (`discovery.md` §4); no generic mechanism anywhere. |
| Historical lookup | **Repository Gap** | Zero precedent for reconstructing a past value anywhere (`discovery.md` §4-5). |
| Temporal uniqueness | **Repository Gap** | No date-scoped constraint mechanism exists anywhere (`decision.md` §3). |
| Replacement semantics | **Split: Business Gap (policy) + Governance Gap (mechanism, contingent)** | Whether old values are retained, discarded, or archived is a content decision the repository cannot supply (`decision.md` §6, Business). *How* the two states would technically coexist, if retention is chosen, is a downstream architecture decision not yet made (Governance), contingent on the business answer. |
| Validity intervals (the `effective_from`/`effective_to` shape itself) | **Governance Gap** | This is `domain-model-discovery.md` §2's own open Representation Model question (combine mixin + evaluator, or keep separate) — a real architecture decision, not blocked on missing evidence; both candidate patterns were already directly compared. |

**External Dependency**: **None found.** No third-party system or external data source is evidenced anywhere across all three prior documents — confirmed absent, not omitted.

---

# 3. Existing Infrastructure

| Component | Classification | Repository Evidence |
|---|---|---|
| Mixins (category/pattern) | **Partially reusable** | `domain-model-discovery.md` §2-3 found the column-composition *mechanism* (multiple inheritance) is directly reusable as a pattern to follow — but no existing mixin (`Timestamp`/`Audit`/`SoftDelete`/`Version`) provides effective-dating columns itself. The pattern is reusable; the content is not. |
| Authorization Foundation | **Partially reusable** | Same distinction as above: the evaluator *shape* (immutable request/decision objects plus a replaceable `evaluate()` method) is a directly comparable pattern, freshly re-verified (`domain-model-discovery.md` §1, §3), but the actual classes are not literally extendable for a different domain — no inheritance or coupling would make sense between access-decision evaluation and temporal interpretation. |
| `BaseRepository` | **Reusable** | Proven, working, generic CRUD infrastructure; would directly apply to whichever consuming capability's own table gains new columns — universal, zero exceptions found anywhere. |
| `AuditLog` | **Not reusable** | `decision.md` §5/§9 directly rejected this as an evolution path — its central-log, action-based shape (no field-value history) does not fit. |
| `VersionMixin` | **Not reusable** | `decision.md` §4 — structurally cannot represent multiple historical values (a single `Integer` counter on the current row). |

---

# 4. Upstream Dependencies

| Capability | Classification | Reasoning |
|---|---|---|
| Compensation | **Not Required** | `decision.md` §2/`domain-model-discovery.md` §5 establish Compensation as a *consumer* of Effective Dating, not a prerequisite — Effective Dating does not need Compensation to exist first, mirroring Monetary Representation's own identical upstream finding relative to Compensation. |
| Work Schedule | **Not Required** | Same reasoning — a consumer, not a prerequisite. |
| Shift Assignment | **Not Required** | Same reasoning — a consumer, not a prerequisite. |
| Payroll Calculation | **Not Required** | `decision.md` §2 classifies this `Unrelated`, not merely absent as a dependency — no relationship in either direction is evidenced. |
| `Payslip` | **Not Required** | Same reasoning — `Unrelated` (`decision.md` §2); already-implemented code, but not evidenced as a dependency in either direction. |

**Logical Consequence**: None of the five is a genuine prerequisite. Effective Dating, as a mechanism-shaped candidate, does not wait on any of them — mirroring the same sequencing precedent already established for Monetary Representation and Shift Assignment.

---

# 5. Downstream Consumers

Restated from `domain-model-discovery.md` §5, not re-derived:

- **Confirmed**: None. Nothing in code consumes an Effective Dating concept, since it does not exist.
- **Documented**: Compensation, Work Schedule, Shift Assignment — each has its own already-approved governance document directly and explicitly stating this anticipation in writing (`decision.md` §2, `domain-model-discovery.md` §5), not merely inferred.
- **Unknown**: None remaining. Payroll Calculation and `Payslip` — the only other two capabilities evaluated — are classified `Unrelated`, a more resolved status than `Unknown`, per `decision.md` §2's own precise reasoning.

---

# 6. Blocking Unknowns

Consolidated from `discovery.md`, `decision.md`, and `domain-model-discovery.md`. Nothing new added, nothing answered.

1. **Aggregate/persistence shape** (`decision.md` §7; `domain-model-discovery.md` §1, §6) — whether Aggregate Root or Projection applies, and whether Effective Dating persists any component of its own. *Why unresolved*: no repository precedent exists anywhere for "one identity, many time-scoped values," and its two closest structural precedents (Authorization Foundation, Mixins) both lean away from Effective Dating persisting its own data without fully confirming it either way. *Why more search would not help*: two discovery-level passes, plus a fresh direct re-read of Authorization Foundation's own code this session, converged on the same open question without narrowing it further — this is now a design choice, not an undiscovered fact.
2. **Representation model combination** (`domain-model-discovery.md` §2-3, §9) — whether the column-contribution role and the interpretation-logic role combine into one mechanism or remain two separate pieces. *Why unresolved*: no single existing repository pattern covers both roles simultaneously. *Why more search would not help*: both existing candidate patterns (Mixins, Authorization Foundation) were already directly, freshly compared; nothing further exists to compare against.
3. **Repository Infrastructure relationship** (`decision.md` §3, §7; `domain-model-discovery.md` §1) — how `BETWEEN`/overlap-query support relates architecturally to Effective Dating's own mechanism. *Why unresolved*: a dependency-layering question, not a fact repository search would surface. *Why more search would not help*: already characterized as a related-but-distinct, lower-level concern at two separate phases.
4. **Integration path with Compensation, Work Schedule, Shift Assignment** (`decision.md` §2) — the specific retrofit mechanism beyond "consumer." *Why unresolved*: their own already-approved governance names the anticipation but not the mechanism. *Why more search would not help*: this is downstream of items 1-2 above, not independently discoverable.
5. **Business content** — replacement policy, retention policy, specific per-consumer effective-dating rules (`decision.md` §6). *Why unresolved*: product/business decisions the repository's code cannot contain. *Why more search would not help*: by nature, policy is not encoded in source code before an upstream decision is made.
6. **Authorization** (`decision.md` §8) — whether Effective Dating needs it at all. *Why unresolved*: the same structural tie found identically for every capability in this trail. *Why more search would not help*: the same zero-match grep result was independently reproduced twice for this exact capability, in two separate documents.
7. **Capability naming** (`discovery.md` §9, `decision.md` §10) — whether "Effective Dating" is the correct or final name. *Why unresolved*: originates entirely from this governance trail's own reasoning. *Why more search would not help*: already searched exhaustively.
8. **Whether "every capability solves history independently" remains a viable fallback** (`decision.md` §9-10) — not formally closed off. *Why unresolved*: not structurally impossible, only weighed against by precedent-based analogy. *Why more search would not help*: this is a strategic governance choice, not a fact to discover.
9. **Whether Payroll Calculation or `Payslip` could ever become consumers despite currently being `Unrelated`** (`decision.md` §2) — not treated as permanently closed by `decision.md` itself ("no evidence found either way," not an absolute exclusion). *Why unresolved*: absence of current evidence is not proof of permanent irrelevance. *Why more search would not help*: both were already searched exhaustively; nothing further to find without new developments in either capability.

---

# 7. Can Iteration 1 Begin?

```
No
```

The minimum blocking architectural questions are **#1 (aggregate/persistence shape)** and **#2 (representation model combination)** — no code can be scaffolded without knowing whether Effective Dating persists anything of its own, and whether its column-contribution and interpretation-logic roles combine into one mechanism or remain two separate pieces. Both are structural forks with no repository precedent to resolve them either way (§6). No minimum scaffold is proposed here, per instruction.

---

# 8. Remaining Risks

Carried forward in full; none removed, none resolved:

- Building the wrong mechanism combination (mixin-only, evaluator-only, or both) — could require rework across three already-approved consuming capabilities' own governance (Compensation, Work Schedule, Shift Assignment).
- No temporal-uniqueness or overlap-validation mechanism exists anywhere (§2) — risk of inconsistent data if built before this Repository Gap is addressed.
- Retrofitting three already-approved capabilities' own governance once Effective Dating's actual shape is decided — governance-churn risk.
- Business policy (replacement/retention) remaining undecided, risking silent data-loss or unbounded-growth design mistakes if implementation proceeds without it.
- Authorization posture undecided — the same retrofit risk pattern found in every sibling capability.
- The "every capability solves history independently" fallback remaining technically live — a genuine, non-hypothetical risk: Work Schedule's own `decision.md` §6 already independently concluded "if built, belongs to me," and if Work Schedule (or Shift Assignment, or Compensation) proceeds to its own implementation before Effective Dating's governance concludes, exactly this fragmentation risk materializes, defeating the purpose of extracting a shared mechanism in the first place.

---

# 9. Recommendation

```
Additional Governance Required
```

Two fundamental structural Unknowns remain genuinely open — aggregate/persistence shape and representation-model combination (§6, items 1-2) — mirroring exactly the pattern that produced the identical recommendation for both Shift Assignment and Work Schedule at their own comparable stage. Not **Architecture Review may begin**: no stable target exists for a consistency review while the capability's own basic shape (does it persist anything, is it one mechanism or two) remains undecided. The blocking items are architecture decisions and business-content gaps, not missing repository evidence — every citation in this document was independently re-verified, not carried from any prior summary.

---

# References

- `docs/architecture/capabilities/effective-dating/discovery.md`
- `docs/architecture/capabilities/effective-dating/decision.md`
- `docs/architecture/capabilities/effective-dating/domain-model-discovery.md`
- `docs/architecture/capabilities/shift-assignment/architecture-gap-analysis.md`, `work-schedule/architecture-gap-analysis.md` (classification taxonomy and recommendation precedent)
