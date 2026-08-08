# Effective Dating — Domain Model Discovery

**Status:** Complete

**Capability:** Effective Dating

**Owner:** EOP Architecture Governance

**Depends On:** `docs/architecture/capabilities/effective-dating/discovery.md`, `docs/architecture/capabilities/effective-dating/decision.md`

---

# Purpose

This document refines the architectural shape already established by Discovery and Decision. It does not reopen ownership, mechanism/policy classification, or any already-rejected aggregate candidate (Child Entity, Domain Service, Value Object). Every repository citation was re-verified directly this session, including a fresh, complete read of `AuthorizationRequest`, `AuthorizationDecision`, and `AuthorizationEvaluator` not previously read in this exact session. Every conclusion is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**.

---

# 1. Aggregate Candidates

Only the four candidates `decision.md` §7 left `Unknown` or retained (Aggregate Root, Shared Infrastructure, Repository Infrastructure, Projection) are re-evaluated.

- **Aggregate Root** — **Repository Evidence**: A fresh, direct read of `authorization_request.py`, `authorization_decision.py`, and `authorization_evaluator.py` confirms `AuthorizationRequest`/`AuthorizationDecision` are plain, frozen `dataclass`es — not `BaseEntity` subclasses, no `id`, no repository — and `AuthorizationRequest`'s own docstring states directly: *"Authorization Foundation performs no persistence and gains none by carrying it."* Authorization Foundation is `decision.md` §7's strongest-supported analog for Effective Dating's own likely shape. **Logical Consequence — a genuine narrowing**: if Effective Dating mirrors this precedent, it would not itself be an Aggregate Root — persistence of historical values would live in each *consuming* capability's own table, not in Effective Dating. **Remains `Unknown`, but now leaning away from persistence** rather than genuinely undecided in either direction.
- **Shared Infrastructure** — **Repository Evidence**: The same fresh reads confirm Authorization Foundation's actual code shape — immutable request/decision objects plus a single, replaceable `evaluate()` method on a base class meant to be subclassed, not extended by inheritance-composition the way `Mixins` are. **Logical Consequence**: This is real, working, positively-supported structural precedent, not merely a shared abstract principle. **Retained, more precisely characterized than before** — not merely "the closest resemblance," but a directly comparable code shape.
- **Repository Infrastructure** — **Repository Evidence**: `BaseRepository`'s generic interface (`get`/`list`/`create`/`update`/`delete`/`exists`/`count`/`paginate`) includes no range-query primitive. Both existing point-in-range queries (`exists_between`, `find_for_employee_on_date`, `discovery.md` §4) are written directly on their own concrete repository subclass — no shared mixin or base-class extension exists for *query behavior* the way `db/mixins.py` exists for *column composition*. **Logical Consequence**: the repository's only precedent for generalizing query behavior would be adding a method directly to `BaseRepository` itself, or repeating the pattern per-repository (the current, actual practice) — no third, mixin-like pattern exists for behavior the way one exists for columns. **Retained as a related, lower-level, prerequisite concept**, not Effective Dating's own shape, consistent with `decision.md` §7.
- **Projection** — **Repository Evidence**: No read-model/projection precedent exists anywhere (restated, not reopened). `decision.md` §1 established historical identity — tracking one logical thing across multiple time-scoped values — as Effective Dating's own defining concern. **Logical Consequence — a genuine narrowing**: a pure Projection (derived-only, nothing of its own persisted) cannot, by itself, provide historical identity — you cannot derive history from data that was never preserved somewhere. A Projection could at most be a secondary read-shape layered on top of data persisted elsewhere (in a consuming capability's own table, per Aggregate Root's finding above), not a complete answer on its own. **Remains `Unknown`, narrower than before**: not rejected, but no longer a self-sufficient candidate — only a possible read-layer on top of whatever the real persistence mechanism turns out to be.

**Result**: All four candidates remain formally `Unknown`/Retained, per instruction — none is forced. Aggregate Root and Projection are each narrower than `decision.md` left them, converging toward the same conclusion from different angles: Effective Dating itself likely does not persist historical values; whatever persists them belongs to each consuming capability.

---

# 2. Representation Model

**Repository Evidence**: Two genuinely different, both-real "reusable technical concern" shapes exist in the repository: (a) Authorization Foundation's stateless evaluator shape — dataclasses plus a replaceable `evaluate()` method, zero persistence, policy state living entirely in each consumer's own table (e.g., `LeaveRequest.status`); (b) `db/mixins.py`'s column-composition shape — `VersionMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin` each contribute actual columns to every consuming entity via multiple inheritance at class-definition time.

**Logical Consequence**: Effective Dating plausibly needs elements of *both* shapes simultaneously — a mixin-like piece contributing `effective_from`/`effective_to`-style columns to consuming capabilities' own tables (mirroring how `VersionMixin` contributes `version`), and an Authorization-Foundation-like piece providing the shared "resolve what's effective as of date X" interpretation logic. Neither existing single pattern alone covers both needs. "Persisted concept" (Effective Dating owning a dedicated table of its own) is not directly supported by either precedent — both apply to or interpret data *owned by the consuming entity*, not data of their own.

**Unknown**: Whether these two roles (column contribution, interpretation logic) would combine into one mechanism or remain two separate pieces — not decided. This is a more structurally complex representation-model question than any prior capability in this trail faced at the same stage, since no single existing pattern fully matches.

---

# 3. Pattern Comparison

Structural behavior, not names, per instruction.

| Pattern | Behavioral Shape | Repository Evidence |
|---|---|---|
| Authorization Foundation | Stateless evaluator | Immutable dataclasses in, immutable dataclass out; zero persistence; consumer owns all real state. Confirmed by fresh, direct read this session. |
| `VersionMixin` | Column-composition mixin | Contributes exactly one `Integer` column to every entity via inheritance; the entity itself decides whether to use it (none do, `discovery.md` §1-2). |
| `AuditLog` | Central log | A genuinely separate, persisted, independently-addressable entity (own repository/service/table) that other capabilities are meant to call into (`record()`) to append a row describing an action elsewhere — a third shape distinct from both above. |
| `Assignment` | Capability-owned content | A normal Aggregate Root with its own current-state row, including a date range — not a reusable mechanism at all, only the closest content-level analog for "an entity with a date range." |
| `BaseRepository` | Generic CRUD base class | Uniform across every concrete repository; extra query behavior is added directly on each concrete subclass, not via any shared, cross-cutting extension mechanism. |
| Mixins (general category) | Column-composition | The repository's own established pattern for applying a reusable *technical* concern to many entities via multiple inheritance; every existing mixin contributes columns, none contributes behavior/methods. |

**Logical Consequence**: Three genuinely distinct "reusable mechanism" shapes coexist in this repository: (a) stateless evaluator (Authorization Foundation) — logic only, zero persistence; (b) column-composition mixin (`VersionMixin` et al.) — contributes columns via inheritance; (c) central log (`AuditLog`) — one separately-owned, persisted table others write into. Per §2, Effective Dating plausibly needs elements of (a) and (b) together — but not (c): a central-log shape does not fit "one logical value with a validity period," which is inherently per-consuming-entity, not a single shared log.

**Unknown**: Whether Effective Dating would combine (a) and (b) into one thing, keep them separate, or resemble something not yet precedented — not decided.

---

# 4. Ownership Boundary

Not reopened, per instruction — only refined structurally.

`decision.md` §1-2 already decided Effective Dating owns the *mechanism*, and Compensation/Work Schedule/Shift Assignment each own their own *content*. §2-3 above refine what "the mechanism" structurally means: Effective Dating would own (a) a reusable column-composition pattern (analogous to `VersionMixin`) that each consuming capability applies to its *own* table, and (b) a shared interpretation capability (analogous to `AuthorizationEvaluator`) for resolving "what's effective as of date X" against whichever columns exist on the consumer's own row. Consuming capabilities would continue to own their own actual historical rows in their own tables — exactly mirroring how `LeaveRequest`/`AttendanceEvent` own their own rows while consuming Authorization Foundation's evaluator shape, or how every entity owns its own `version` column while `VersionMixin` only defines it.

**Repository layer**: Effective Dating's mechanism, per §3, would sit *alongside* `BaseRepository`/Mixins, extending the same established composition pattern — not be part of `BaseRepository` itself, and not replace it.

---

# 5. Cross-Capability Relationships

| Capability | Relationship | Reasoning |
|---|---|---|
| Compensation | **Consumer** | `decision.md` §2, restated and refined (§4): would apply Effective Dating's column pattern to its own table. |
| Work Schedule | **Consumer** | Same reasoning. |
| Shift Assignment | **Consumer** | Same reasoning. |
| Payroll Calculation | **Unrelated** | `decision.md` §2, restated — no evidence found anywhere. |
| `Payslip` | **Unrelated** | `decision.md` §2, restated — its own immutability already solves point-in-time correctness a different way. |
| Authorization Foundation | **Peer** | Not a producer/consumer relationship — both are Shared-Infrastructure-shaped mechanisms with directly comparable structural shapes (§3), neither depending on nor feeding the other. |
| Repository layer (`BaseRepository`/Mixins) | **Dependency** | Effective Dating would depend on and extend the existing mixin-composition mechanism specifically (§3-4), not be produced by any capability. |
| `AuditLog` | **Unrelated** | `decision.md` §5/§9 already rejected this as an evolution path; no relationship exists or is implied. |
| `VersionMixin` | **Unrelated** | `decision.md` §4 already established independence. |

---

# 6. Lifecycle

**Repository Evidence**: Authorization Foundation itself has no lifecycle — its dataclasses are created fresh per request and discarded; its evaluator is stateless (§3). Mixins have no lifecycle of their own — they are composed at class-definition time, never created/updated/deleted as their own thing.

**Logical Consequence**: If Effective Dating mirrors either or both of these precedents (§2-3), it would itself have **no lifecycle, replacement, versioning, or persistence of its own** — these would belong entirely to consuming capabilities, which would own their own historical rows, their own replacement semantics, and their own persistence, using Effective Dating's shared column-shape and evaluation logic. This directly confirms `decision.md` §1's mechanism/policy split at a structural level, not merely a conceptual one.

**Unknown**: Whether Effective Dating needs any persisted component of its own (e.g., a lookup/reference table) — not fully ruled out, but no positive evidence supports it either; neither of its two closest precedents (Authorization Foundation, Mixins) has one.

---

# 7. Versioning Relationship

**Repository Evidence**: `decision.md` §4 already established `VersionMixin` (optimistic concurrency) and temporal validity are independent; `decision.md` §5 already established `AuditLog` (immutable audit trail) is distinct from both. §3 above additionally maps each onto a distinct existing (or plausible) repository shape: temporal validity → a hybrid evaluator-plus-mixin shape, not yet built; optimistic concurrency → `VersionMixin`, a dead column; immutable audit → `AuditLog`, a dormant-but-working central log.

**Logical Consequence**: **Yes, all three remain completely separate** after this pass — if anything, more clearly separated now that each maps to a distinct structural precedent (or precedent-shape) rather than only an abstract distinction. No concept is merged here, per instruction.

**Unknown**: None regarding this separation — confirmed, not merely asserted.

---

# 8. Invariants

Only what is directly supported by `decision.md` or this document's own structural findings — restated, not re-derived:

- Effective Dating does not own Compensation's, Work Schedule's, or Shift Assignment's own content (`decision.md` §1-2).
- Effective Dating would not own authorization (`decision.md` §8).
- `VersionMixin` and Effective Dating remain independent (`decision.md` §4).
- `AuditLog` and Effective Dating remain independent (`decision.md` §5, §9).
- Whatever shape Effective Dating takes excludes Child Entity, Domain Service, and Value Object (`decision.md` §7).
- If Effective Dating mirrors Authorization Foundation's own precedent, it has no persistence, lifecycle, or state of its own (§6, directly supported by Authorization Foundation's own docstring: *"performs no persistence and gains none by carrying it"*).

No date algorithm, temporal table, or history entity is invented here, per instruction.

---

# 9. Authorization Foundation Relationship

**Repository Evidence**: §3's fresh, direct reads found genuine structural resemblance — not merely a shared abstract principle. Effective Dating's own plausible shape (immutable request/decision-like objects plus a replaceable evaluator/interpreter class, zero persistence) directly mirrors Authorization Foundation's *actual code shape*, more concretely than the resemblance found for Monetary Representation (which was classified **Conceptual**: a shared design principle only, no structural/dependency coupling, no code existing to be coupled).

**Logical Consequence**: Applying the same definitional test used for Monetary Representation — **Conceptual** requires no structural/dependency coupling and no existing code; **Architectural** requires actual structural/dependency coupling to exist; **Implementation** requires a shared base class or runtime call. Effective Dating has zero code today (candidate only) — no structural or dependency coupling is possible yet, since there is nothing built to couple. By this test, the relationship remains **Conceptual**.

**Decision: Conceptual — but a more precisely-characterized instance of that category than Monetary Representation's own finding.** The resemblance here extends to a shared *shape* (dataclass-like immutable objects plus a replaceable evaluator), not only a shared *principle* (mechanism/policy separation) — a richer conceptual resemblance, but still Conceptual under the same test, since no code exists for Effective Dating to actually couple to anything.

---

# 10. Recommendation

```
Architecture Gap Analysis may begin.
```

This pass surfaced a significant, freshly-verified structural finding — Authorization Foundation's actual non-persisted, dataclass-plus-evaluator shape, confirmed by direct reads not previously performed in this exact session — that meaningfully narrows both the Aggregate Root and Projection candidates (§1) and clarifies the Representation Model as a two-role combination (§2-3) not fully matched by any single existing pattern. This is comparable to or exceeds the narrowing achieved in Shift Assignment's and Work Schedule's own Domain Model Discovery passes at the same stage. The remaining Unknowns (whether the two roles combine into one mechanism, whether any persisted component is needed at all) are consolidation-level design questions, not evidence gaps — every citation in this document was independently re-verified against the repository, not carried from any prior summary.

---

# References

- `docs/architecture/capabilities/effective-dating/discovery.md`
- `docs/architecture/capabilities/effective-dating/decision.md`
- `services/api/src/eop_api/services/authorization_request.py`, `authorization_decision.py`, `authorization_evaluator.py` (read fresh this session)
- `services/api/src/eop_api/db/mixins.py`, `db/base.py`, `models/audit_log.py`, `repositories/attendance_event.py`, `repositories/leave_request.py`, `models/assignment.py`
