# Compensation — Domain Model Discovery

**Status:** Complete

**Capability:** Compensation

**Owner:** EOP Architecture Governance

**Depends On:** `docs/architecture/capabilities/compensation/discovery.md`, `docs/architecture/capabilities/compensation/decision.md`

---

# 1. Summary

This document investigates ten domain-model questions for Compensation using only `discovery.md`, `decision.md`, and the repository evidence they cite. It designs nothing, invents no field, and converts no `Unknown` into a recommendation. Of six named aggregate candidates, only `Compensation` itself has any repository-evidenced classification (Aggregate Root, already decided in `decision.md` §4); the other five (`CompensationHistory`, `CompensationSnapshot`, `CompensationVersion`, `CompensationRevision`, `CompensationChange`) have no repository precedent to classify against. History modeling, lifecycle mutability, and the `JobGrade`/`PayrollRun`/`Payslip` relationship mechanisms all remain `Unknown`. What is decidable, and confirmed repeatedly across three separate documents in this conversation, is that the repository has never modeled a temporal/versioned value of any kind — Compensation would be the first, if that shape is ever required.

---

# 2. Major Findings

## 2.1 Aggregate Candidates

**Repository Evidence**

- `decision.md` §4 already decided `Compensation` classifies as an **Aggregate Root**, with Child Entity, Domain Service, Projection, and Value Object each explicitly rejected using repository evidence (uniform one-entity-one-service pattern; Compensation owns data rather than orchestrating over others'; no source data exists for a Projection to compute over; Compensation requires independent identity a Value Object shape lacks).
- Filename search for `*History*`, `*Snapshot*`, `*Version*`, `*Revision*`, `*Change*` under `services/api/src/eop_api/models` returns zero matches (`discovery.md` §5, restated). No entity anywhere in the repository is shaped like any of the five remaining candidates.
- The only "record of a change" precedent anywhere is `AuditLog` — generic (`action`/`entity_type`/`entity_id`/`details`), not employee-scoped, not field-level, unused by any producer capability (`discovery.md` §5, `payslip/discovery.md` §1).

**Logical Consequences**

- `CompensationHistory`, `CompensationSnapshot`, `CompensationVersion`, and `CompensationRevision` have no repository precedent to classify against at all — not even a weak analogy exists, since no history/versioning mechanism of any kind exists anywhere in the repository.
- `CompensationChange` has the weakest available analogy (`AuditLog`), but `AuditLog`'s own shape (generic, non-employee-scoped, unused) does not support classifying `CompensationChange` as any of the five offered categories with confidence.

**Unknowns**

- Whether any of the five non-`Compensation` candidates would be needed at all, and if so, in what shape — not decidable from repository evidence.

## 2.2 History Modeling

**Repository Evidence**

- `decision.md` §5 already recorded this exact question as `Unknown`, citing `discovery.md` §5's confirmation that no effective-dating or history mechanism exists anywhere, and `discovery.md` §6's finding that no entity combines "current value" and "historical record" in any shape.

**Logical Consequences**

- Every entity in the repository defaults to a current-value-only shape, but only because no entity has ever needed an alternative — this describes an absence, not a considered choice applicable to Compensation.

**Unknowns**

- Whether Compensation requires current-record-only, append-only history, versioned records, or effective dating — restated as `Unknown`, not resolved here, per the governing instruction that `Unknown` must never become a recommendation.

## 2.3 Temporal Modeling

**Repository Evidence**

- Fresh search (this document) for `effective_from`, `effective_to`, `valid_from`, `valid_to`, `history`, `revision`, `version` across the repository confirms, a third time across three separate documents in this conversation (`payroll/domain-model-discovery.md` E4, `payroll-calculation/domain-model-discovery.md` §6, `compensation/discovery.md` §5): zero matches for any temporal-versioning field; `VersionMixin.version` exists on every entity but is an unenforced in-place counter, never a version-row mechanism; every "history"/"revision" occurrence found anywhere is prose disclaiming that no such mechanism is implemented.

**Logical Consequences**

- **If Compensation requires any temporal/effective-dating modeling, it would introduce a completely new architectural pattern for this repository.** This is a direct, repeatedly-confirmed conclusion, not an inference from silence — the absence has been searched for specifically, three separate times, with identical results.

**Unknowns**

- Whether Compensation actually requires temporal modeling at all remains open (§2.2) — only the absence of existing precedent is confirmed, not the requirement.

## 2.4 Identity

**Repository Evidence**

- Every one of the twelve business/HR-domain aggregates reviewed across this conversation uses a single surrogate `id` (`UUIDMixin`, `db/base.py`) as its primary identity — zero exceptions. The only composite-key structure anywhere in the repository is `user_roles`, a pure many-to-many join table, structurally unrelated to any business aggregate's own identity. No aggregate anywhere derives its identity from another aggregate (e.g., reusing another table's primary key as its own) — every relationship is a separate FK column referencing another table's `id`.

**Logical Consequences**

- If Compensation is built as an Aggregate Root (§2.1), the uniform, zero-exception precedent supports a single surrogate identity, not a composite key and not an identity derived from `HrEmployee`.

**Unknowns**

- None for this topic specifically — the precedent is total and unambiguous.

## 2.5 Relationships

Ownership direction only, no foreign keys introduced:

- **`HrEmployee`**: **Repository Evidence** — `decision.md` §2 already decided Compensation stays separate from `HrEmployee`, referencing it rather than being absorbed into it. **Logical Consequence**: `HrEmployee` is upstream (owns employee identity); Compensation would be downstream, dependent on an `HrEmployee` already existing, mirroring every other employee-scoped entity's relationship direction.
- **`PayrollRun`**: **Unknown.** No document anywhere establishes a direct relationship between Compensation and `PayrollRun` — Compensation is evidenced as employee-scoped (§2.5 `HrEmployee`), while `PayrollRun` is run/batch-scoped with zero FKs of its own; nothing in `decision.md` or `discovery.md` connects the two directly.
- **`Payslip`**: **Unknown.** Same reasoning — `discovery.md` §7 already recorded this as open: whether `Payslip` would consume Compensation data directly, or only through an intermediary, "is not addressed anywhere."
- **Payroll Calculation**: **Repository Evidence** — `decision.md` §8 and `discovery.md` §7 both document Compensation as a producer and Payroll Calculation as the named consumer, per `payroll-calculation/architecture-gap-analysis.md`'s own framing. **Logical Consequence**: of the five relationships evaluated, this is the only one with any documented direction at all — Compensation produces, Payroll Calculation consumes.
- **`JobGrade`**: **Unknown.** `decision.md` §3 explicitly scoped its own decision narrowly to "which capability owns monetary interpretation" (Compensation, not `JobGrade`) and explicitly declined to decide whether, or how, Compensation would relate to `JobGrade` at all.

## 2.6 Lifecycle

**Repository Evidence**

- The closest existing precedent for "an aggregate holding a mutable business value that changes over time" is `LeaveBalance` (`allocated_days`/`used_days`/`remaining_days`) — and it is fully mutable, freely overwritable, with no history retained (`discovery.md` §1, `payroll/domain-model-discovery.md` E1).
- The repository's only immutable/append-only precedents (`Payslip`, `AuditLog`) are not "value-owning" in this sense — `Payslip` is a fixed record created once; `AuditLog` is a generic log, neither holds a business value that is expected to change over its own lifetime the way a rate would.
- This conversation's own governance trail (`payroll/decision.md` §2-3) already criticized `LeaveBalance`'s specific shape (mutable, unsynchronized, no audit trail) as inadequate justification for treating mutability as safe for financially-consequential data.

**Logical Consequences**

- Two directly-relevant but conflicting pieces of evidence exist: the one structurally-closest precedent for a "value-owning aggregate" (`LeaveBalance`) is mutable; but this conversation's own prior reasoning about financially-consequential data (used to justify `PayrollRun`/`Payslip`'s persisted, and `Payslip`'s immutable, shape) weighs against extending that same mutable pattern to Compensation without further justification.

**Unknowns**

- Whether Compensation should be mutable, immutable, or append-only is not resolved by this tension — both directions have repository support, and no repository evidence breaks the tie. This document does not resolve it.

## 2.7 Versioning

**Repository Evidence**

- Repository-wide search (this document, and independently in `payroll/domain-model-discovery.md` E4 and `payroll-calculation/domain-model-discovery.md` §6) for revisions, historical values, previous versions, and temporal querying returns zero matches anywhere in the repository, for any entity, in any capability.

**Logical Consequences**

- **Compensation would be the repository's first versioned aggregate, if versioning is ever required of it.** This conclusion is well-evidenced and repeatedly confirmed — the absence itself is certain.

**Unknowns**

- Whether Compensation requires versioning at all remains unresolved (§2.2, §2.6) — only the absence of any existing pattern to reuse is certain, not the requirement itself.

## 2.8 Invariants

**Repository Evidence and supported invariants**

- **Compensation owns its own data** — `decision.md` §1, by elimination (no other capability owns any compensation data).
- **Compensation cannot mutate another capability's data** — `decision.md` §8, matching the uniform write-ownership pattern (zero cross-capability writes anywhere except `ApprovalService`'s own narrow, separately-decided exception).
- **One service owns one aggregate** — the uniform, zero-exception pattern across all twelve entities reviewed in this conversation (`payroll/domain-model-discovery.md` A1).
- **Compensation would use a single surrogate identity** — §2.4, uniform precedent.

**Explicitly not supported as an invariant**

- "Only Payroll Calculation may read Compensation" — `decision.md` §8 found no technical access-control mechanism exists anywhere in the repository; this is documented intent, not an evidenced or enforceable invariant, and is not listed as one here.

**Unknowns**

- Any invariant concerning Compensation's own internal value correctness (e.g., constraints between a current value and a historical one) — not derivable, since no history/versioning shape is decided (§2.2, §2.7).

## 2.9 Relationship with Payroll Calculation

**Repository Evidence**

- Neither Compensation nor Payroll Calculation exists as code anywhere in the repository. The only place a producer/consumer relationship between them is stated is `payroll-calculation/architecture-gap-analysis.md` §1/§8, in prose, naming Compensation as Payroll Calculation's prerequisite.

**Logical Consequences**

- The "Compensation produces, Payroll Calculation consumes" framing is **architectural intent only**, drawn from governance-document prose — it is not an observed code-level dependency, since neither capability has any code for a dependency to exist between.

**Unknowns**

- The exact mechanism of that intended relationship (direct read, via an intermediary, via some other data hand-off) — not addressed anywhere (§2.5, restated).

## 2.10 Recommendation Input

Restated from `decision.md` §10 as the basis for §3 below: `decision.md` already found Compensation's boundary well-decided but its content entirely undecided, recommending another governance phase before Implementation Planning. This domain-model pass adds further, still-unresolved structural questions (history modeling, lifecycle, `JobGrade`/`PayrollRun`/`Payslip` relationship mechanisms) on top of that same conclusion — it does not narrow the gap `decision.md` already identified.

---

# 3. Recommendation

```
Another governance phase is still required. Repository evidence is not yet
sufficient to proceed to Architecture Review.
```

Architecture Review, in this repository's established governance sequence, checks consistency across already-decided, stable documents (`payroll/architecture-review.md`, `payslip/architecture-review.md` both reviewed a completed Discovery → Decision → Implementation Plan chain). Compensation has no Implementation Plan, and this domain-model pass leaves substantially more open than it resolves: five of six aggregate candidates remain unclassifiable (§2.1), history modeling is `Unknown` (§2.2), three of five evaluated relationships are `Unknown` (§2.5), and lifecycle mutability has genuinely conflicting, unresolved evidence (§2.6). There is not yet a stable decision set for an Architecture Review to check consistency against — the same conclusion `decision.md` §10 already reached, reinforced rather than narrowed by this discovery.
