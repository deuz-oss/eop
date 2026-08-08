# Monetary Representation — Domain Model Discovery

**Status:** Complete

**Capability:** Monetary Representation

**Owner:** EOP Architecture Governance

**Depends On:** `docs/architecture/capabilities/monetary-representation/discovery.md`, `docs/architecture/capabilities/monetary-representation/decision.md`

---

# 1. Candidate Architectural Shapes

Each candidate evaluated independently; none forced.

- **Aggregate Root** — **Repository Evidence** + **Logical Consequence**: `decision.md` §7 already rejected this — every Aggregate Root in this repository has independent identity, its own repository, and a CRUD lifecycle; Authorization Foundation, the closest analog, is not one itself (`AuthorizationRequest`/`AuthorizationDecision` are plain dataclasses). **Rejected**, restated not re-derived.
- **Domain Service** — **Repository Evidence** + **Logical Consequence**: `decision.md` §7 already rejected this — the established Domain Service shape (`ApprovalService`, `ReconciliationService`) actively orchestrates reads across other capabilities' repositories; a representation mechanism does neither. **Rejected**, restated.
- **Shared Infrastructure** — **Unknown**: `decision.md` §7 found this the closest resemblance (to Authorization Foundation) but not a formally-recognized repository category with its own confirmed precedent to check against. Remains `Unknown`.
- **Value Object** — **Repository Evidence** + **Logical Consequence**: `decision.md` §7 already rejected this — the repository's one Value Object precedent (`LeaveBalance.period_year`) is a bare `Integer` with no reusable type behind it; `discovery.md` §4 found zero `TypeDecorator`/`NewType`/wrapper-class precedent anywhere. **Rejected**, restated.
- **Library** — **Unknown**: No formally-recognized "library" module/package pattern was found or reviewed anywhere in this codebase across any discovery in this conversation. No evidence to reject or confirm.
- **Utility** — **Unknown**: Same reasoning as Library — no precedent either way.
- **Type System Extension** — **Repository Evidence**: `discovery.md` §4 found zero `TypeDecorator`, zero `NewType`, and zero custom column/schema type anywhere in the repository — a complete absence, not merely an unreviewed pattern. **Unknown**: unlike Aggregate Root/Domain Service/Value Object (which had active, positive precedent patterns that clearly did not match), Type System Extension has no existing example anywhere to compare shape against at all — the absence is total, so this cannot be confirmed or cleanly rejected the way the first three were.

**Result**: three candidates rejected on direct, positive evidence (Aggregate Root, Domain Service, Value Object); four remain `Unknown` (Shared Infrastructure, Library, Utility, Type System Extension). No winner is forced among the four.

---

# 2. Representation Model

**Repository Evidence**: §1 rejected Aggregate Root (entity-shaped, persisted, independent identity) and Value Object (a reusable value type, of which none exists anywhere) on direct evidence.

**Logical Consequence**: "Entity" is not supported as a representation model — it was rejected in §1 on the same grounds as Aggregate Root. "Value" (in the strict, persisted Value-Object sense already evaluated) is likewise not supported. "Infrastructure concern" maps to the `Unknown` Shared Infrastructure finding (§1) and is neither confirmed nor rejected. "Language/type concern" maps to the `Unknown` Type System Extension finding (§1) and is likewise neither confirmed nor rejected.

**Unknown**: Which of "infrastructure concern" or "language/type concern" (or some combination) actually fits is not decidable from repository evidence — no example of either exists anywhere in this repository to compare against. No representation is chosen here, per instruction.

---

# 3. Relationship to Repository Patterns

Architectural similarity only — no conclusion by analogy alone, consistent with `decision.md` §6's own restraint:

| Pattern | Repository Evidence | Structural Similarity |
|---|---|---|
| `BaseEntity` | Composes a persisted row via `UUIDMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin`/`VersionMixin`, used by every Aggregate Root in the repository | **None found** — requires independent identity and a lifecycle, both rejected for Monetary Representation in §1. |
| Mixins (`db/mixins.py`) | The repository's only existing "technical concern reused across many entities" mechanism, applied via multiple inheritance to compose whole columns onto an already-persisted entity | **Partial** — the closest existing reuse mechanism in spirit (a technical concern applied broadly), but its actual reuse *mechanism* (inheritance composing entire columns onto an aggregate) does not match what a single scalar field type would need (a column/schema type, of which `discovery.md` §4 found zero precedent). |
| Authorization Foundation | `ADR-007`'s documented mechanism/policy separation, proven, three capability-specific consumers | **Strong** — already the basis for `decision.md` §2/§6's ownership decision. Restated, not re-derived, here. |
| `EventService` | Generic interface, zero callers, no working transport (`discovery.md` §7) | **Weak** — same general shape (mechanism built ahead of consumers) but entirely unproven. |
| `JobService` | Identical state to `EventService` | **Weak** — same reasoning. |

**Unknown**: Whether the "Partial" similarity to Mixins indicates Monetary Representation should extend that pattern, or whether its absence of a matching reuse mechanism (no type-level equivalent to mixins) rules it out — not decided.

---

# 4. Ownership Boundary (Re-Evaluated After Decision)

**Monetary Representation owns:**
- The representation mechanism only — how a monetary value would be typed and precision-handled (`decision.md` §2).

**Does not own:**
- Business meaning of any monetary value — Compensation's, already decided (`decision.md` §2-3, citing `compensation/decision.md` §1).
- Payroll policy, formulas, or computation — Payroll Calculation's, already decided (`decision.md` §2, §4, citing `payroll-calculation/decision.md` §1).
- `Payslip`'s own record or persistence (`decision.md` §5).
- Its own authorization — mirrors Authorization Foundation's own lack of self-authorization (`decision.md` §8).

**Unknown:**
- What the mechanism concretely is (§1 — four of seven candidates unresolved).
- Whether it is a running service, a type-level convention, or something else (§2).

---

# 5. Cross-Capability Relationships

Stated only as producer / consumer / none / Unknown, per instruction:

- **Compensation**: **consumer** — `decision.md` §3 established Compensation would use the mechanism for its own values, while Monetary Representation does not consume anything from Compensation.
- **Payroll Calculation**: **consumer** — `decision.md` §4 established this direction directly; Monetary Representation is the producer of the mechanism Payroll Calculation would use during its own (undecided) computation.
- **Payslip**: **consumer** — `decision.md` §5 established this direction directly.
- **PayrollRun**: **Unknown** — no document establishes any relationship in either direction; `discovery.md` §2/§8 explicitly recorded this as unaddressed, restated here, not resolved.

No runtime behavior is speculated on for any of the four.

---

# 6. Lifecycle

**Repository Evidence**: §1 rejected both candidate shapes that carry a lifecycle in this repository's established sense — Aggregate Root (a persisted CRUD lifecycle: `create`/`get`/`list`, sometimes `update`/`delete`) and Domain Service (a per-call orchestration lifecycle, invoked once per request the way `ApprovalService`/`ReconciliationService` are).

**Logical Consequence**: With both lifecycle-bearing candidates rejected, the remaining, unresolved candidates (Shared Infrastructure, Library, Utility, Type System Extension) do not, by their own nature as found elsewhere in this repository (mixins are composed at class-definition time, not invoked per-request; no library/utility/type-extension pattern with its own lifecycle was found anywhere), typically carry a runtime lifecycle at all.

**Result: lifecycle absent** is the best-supported outcome — not because absence was directly observed for Monetary Representation itself (it does not exist in code), but because every candidate shape capable of carrying a lifecycle was independently rejected in §1.

**Unknown**: Whether some other, not-yet-considered notion of lifecycle (e.g., a configuration-loading step) could apply — not addressed by any repository evidence.

---

# 7. Versioning

**Repository Evidence**: No versioning, revision, or effective-dating mechanism exists anywhere in the repository, for any entity, confirmed repeatedly across this conversation's discoveries (`payroll/domain-model-discovery.md` E4, `payroll-calculation/domain-model-discovery.md` §6, `compensation/domain-model-discovery.md` §2.3/§2.7, `discovery.md` §1 of this capability).

**Logical Consequence**: This absence applies to any potential persisted entity in the repository. However, §1 already rejected the persisted-entity-shaped candidates (Aggregate Root, Value Object) for Monetary Representation specifically — meaning the question "is this representation versioned/immutable/mutable" may not apply to it the same way it would to a data-holding entity like Compensation's own (separately tracked, still-unresolved) value history question.

**Unknown**: Whether Monetary Representation, once its concrete shape is decided (§1), would need any versioning treatment at all is not decidable — its shape is itself substantially unresolved. No version model is invented here. This document does not conflate this question with Compensation's own, separately-tracked history/effective-dating question (`compensation/decision.md` §5, `compensation/domain-model-discovery.md` §2.2).

---

# 8. Invariants

Only what is directly supported by `decision.md`:

- Owns representation mechanism only — `decision.md` §2.
- Owns no payroll meaning or business value — `decision.md` §2-3.
- Does not own Payroll Calculation's computation — `decision.md` §4.
- Does not own `Payslip`'s record or persistence — `decision.md` §5.
- Is not authorized on its own terms, mirroring Authorization Foundation — `decision.md` §8.
- Is not an Aggregate Root, Domain Service, or Value Object — §1, restating `decision.md` §7.

No mathematical or monetary rule (rounding direction, non-negativity, decimal places, currency handling) is invented — none is evidenced anywhere.

---

# 9. Relationship with Authorization Foundation

**Repository Evidence**: `ADR-007`'s documented Design Principle (mechanism separated from policy) is the basis `decision.md` §2/§6 used to reason about Monetary Representation's own ownership boundary. No code exists for Monetary Representation anywhere — there is no shared base class, no runtime call, no dependency import, and no test exercising any relationship between the two.

**Decision**: **Conceptual.** The relationship is a shared underlying design *principle* — the same reasoning pattern applied to a different technical concern — not an **architectural** relationship (no structural/dependency coupling exists), not an **implementation** relationship (no code exists to be coupled), and not **none** (the principle-level resemblance is real, repeatedly cited, and directly supports §2's ownership decision, so it cannot be dismissed as unrelated either).

---

# 10. Recommendation

```
Architecture Gap Analysis may begin.
```

This domain-model pass leaves substantial structure unresolved — four of seven candidate shapes remain `Unknown` (§1), the representation model itself is undecided (§2), and lifecycle/versioning conclusions are inferred rather than directly evidenced (§6-7). This mirrors the residual-uncertainty level `payroll-calculation/domain-model-discovery.md` reached before proceeding to its own Architecture Gap Analysis — the next phase is precisely the one designed to consolidate and classify remaining unknowns (as Repository/Business/Governance Gaps or External Dependencies), not to resolve them prematurely here.

---

# References

- `docs/architecture/capabilities/monetary-representation/discovery.md`
- `docs/architecture/capabilities/monetary-representation/decision.md`
- `docs/architecture/capabilities/payroll-calculation/domain-model-discovery.md` (precedent for proceeding to Architecture Gap Analysis under comparable uncertainty)
- `docs/architecture/ARCHITECTURE_DECISION_RECORDS/ADR-007-authorization-foundation.md`
