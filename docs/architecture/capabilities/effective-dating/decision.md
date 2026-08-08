# Effective Dating — Capability Decision

**Capability:** Effective Dating

**Status:** Approved — Boundary Decision Only (no schema, mechanism, or algorithm decided)

**Version:** 1

**Owner:** Architecture

---

# 1. Capability Ownership

**Repository Evidence**: `discovery.md` §1/§5 found no capability or mechanism anywhere owns temporal validity, historical identity, or point-in-time interpretation as first-class concepts. Only two narrow, capability-specific point-in-range queries exist (`AttendanceEventRepository.exists_between`, `LeaveRequestRepository.find_for_employee_on_date`, `discovery.md` §4); no reusable infrastructure exists for any of the three (`discovery.md` §5). `discovery.md` §6-7 found three independent capabilities (Compensation, Shift Assignment, Work Schedule) each concluding "if this mechanism is ever built, it belongs to me" — the same structural pattern, at the same three-capability threshold, that produced Authorization Foundation's and Monetary Representation's own extraction as shared mechanisms.

**Logical Consequence**: By elimination, and by direct structural analogy to Authorization Foundation's own proven mechanism/policy separation (`ADR-007`, restated), Effective Dating owns the *mechanism* for temporal validity (how a value's applicability over time is represented), historical identity (a technical identity scheme letting one logical thing be tracked across multiple time-scoped values — zero precedent exists anywhere for this shape, per `discovery.md` §1), and point-in-time interpretation (evaluating what was/is true as of a given date).

**Decision**:
- **Temporal validity**: **Yes**, mechanism owned by Effective Dating, if built.
- **Historical identity**: **Yes**, mechanism owned by Effective Dating, if built — this is squarely unowned elsewhere (`discovery.md` §1) and is the concept's own defining technical concern.
- **Point-in-time interpretation**: **Yes**, mechanism owned by Effective Dating, if built.

**Does not own**: The specific business content of *when* or *how* any individual capability's values actually change — that remains each capability's own, mirroring the identical mechanism/policy split already used throughout this trail (§2, §6).

---

# 2. Relationship with Business Capabilities

Evaluated independently, repository evidence only:

- **Compensation** — **Consumer**. `discovery.md` §3/§6 found `compensation/capability-boundary-analysis.md` flags history/effective-dating as a gap for a *separate* capability, not something it claims to own itself.
- **Work Schedule** — **Consumer**. `work-schedule/decision.md` §6 concluded that *if* effective dating is ever built for its own relationship, it would conceptually belong to Work Schedule. This is not contradicted here: Work Schedule would continue to own the *policy* layer (whether/how effective dating applies to its own recurring-pattern content), while Effective Dating, if built, would own the underlying *mechanism* — the identical relationship Compensation already has to Monetary Representation.
- **Shift Assignment** — **Consumer**, same reasoning as Work Schedule (`shift-assignment/decision.md` §7).
- **Payroll Calculation** — **Unrelated**. `discovery.md` §6 does not list Payroll Calculation among either the Explicit or Implicit anticipators — no repository evidence connects it to Effective Dating. Prior discovery in this trail confirmed the *absence* of any versioning/history mechanism from Payroll Calculation's own perspective, but never found it anticipating a need for one — a real, evidenced distinction from Compensation/Work Schedule/Shift Assignment, not an oversight.
- **Payslip** — **Unrelated**. `Payslip`'s own already-decided immutable-after-creation shape (`create`/`get`/`list` only, no `update`/`delete`) achieves point-in-time correctness through immutability, not through effective-dating of a mutable value — it has no "current value that changes over time" for effective dating to apply to. Its own design structurally obviates the need this capability would address.

---

# 3. Relationship with Repository Infrastructure

**Repository Evidence**: `discovery.md` §4 found two real, narrow, hand-written point-in-range queries exist, but no generic `BaseRepository` `BETWEEN` support. `discovery.md` §5 found no reusable infrastructure for any of the five listed concerns. `work-schedule/capability-boundary-analysis.md` §8 (examined as evidence, cited directly) already evaluated and **rejected** extracting the `BETWEEN`-query gap as its own capability, classifying it instead as *"a low-level ORM/repository-abstraction enhancement... not a business capability."*

**Mechanism vs. business policy, per topic**:
- **`BETWEEN` queries** — generic repository/ORM mechanism, **not Effective Dating's own to own**, consistent with `work-schedule/capability-boundary-analysis.md`'s own rejection. Effective Dating, if built, would *depend on* this being solved, not solve it itself.
- **Overlap validation** — same classification, same reasoning — a generic query-building concern, not specific to time-effectiveness.
- **Temporal uniqueness** — **mechanism owned by Effective Dating**, if built — this is directly about time-based value correctness, the concept's own defining subject matter, not a generic query-building concern.
- **Historical lookup** — **mechanism owned by Effective Dating**, if built — same reasoning.
- **Active-at-date lookup** — **mechanism owned by Effective Dating**, if built — same reasoning.

No business policy is implied by any of these five — all are HOW-shaped (mechanism), not WHAT-shaped (content) questions. No abstraction is invented here, per instruction.

---

# 4. Relationship with VersionMixin

Optimistic concurrency and temporal versioning kept strictly separate, per instruction — not merged.

- **Ownership**: `VersionMixin`, if ever activated, would be a repository/ORM-infrastructure concern (write-conflict prevention on a single current row) — **not Effective Dating's own to own**. `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` (examined as evidence, `discovery.md` §2) itself frames this as *"a repository-wide infrastructure gap,"* addressing a completely different problem than temporal/historical versioning.
- **Relationship**: None currently. `VersionMixin` protects a single, current row from a lost concurrent update; temporal versioning preserves and exposes *multiple* values over time. Neither depends on or feeds the other.
- **Overlap**: Superficial only — both use the word "version." One is about concurrency safety (preventing two writers from silently clobbering each other on the *same, current* row); the other is about temporal history (multiple, all-queryable values across time). A system could have either without the other.
- **Independence**: **Yes.** These are independent concerns that happen to share vocabulary. Not merged here, per instruction.

---

# 5. Relationship with `AuditLog`

**Repository Evidence**: `discovery.md` §2/§8 found `AuditLog` is a generic, append-only action log (`action`/`entity_type`/`entity_id`/`details`) — `entity_id` is a raw UUID column with no `ForeignKey()`, and it records that an action occurred, not the field-level value that resulted.

**Decision**: `AuditLog` provides an **audit trail** (a record that some action happened, to some entity, by some user). It does **not** provide **business history** (the actual prior values of a field) and does **not** provide **temporal validity** (the ability to determine what was true/effective as of a given date) — its shape supports none of these without additional interpretation logic that does not exist anywhere in the repository.

---

# 6. Mechanism vs. Policy

| Concern | Owner |
|---|---|
| Validity mechanism | **Effective Dating**, if built (§1) |
| Effective-date mechanism | **Effective Dating**, if built (§1) |
| Point-in-time lookup | **Effective Dating**, if built, depending on lower-level repository query support (§3) |
| Business rules (which specific dates/values apply, per consuming capability) | **Individual consuming capability** — Compensation, Work Schedule, Shift Assignment, each on their own already-decided content (§2) |
| Replacement policy (whether old values are retained, discarded, or archived) | **Business** — a content question, not decidable from repository evidence |
| Retention policy (how long history is kept, if at all) | **Business** — same reasoning |

---

# 7. Aggregate Classification

Each candidate evaluated independently; rejected only where repository evidence supports rejection, per instruction. `Unknown` retained where genuinely unresolved.

- **Aggregate Root** — **Unknown, not rejected.** `BaseEntity`/`UUIDMixin` is universal, but `discovery.md` found zero precedent anywhere for a "one identity, many time-scoped values" persistence shape. Unlike Monetary Representation's own Aggregate Root (rejected outright, since it had nothing to persist), Effective Dating conceptually *would* need to persist historical values if built as a mechanism — this candidate is not cleanly rejectable, only unprecedented.
- **Child Entity** — **Rejected.** No entity anywhere in the repository is accessed only through another aggregate's own repository/service — the same direct structural mismatch found repeatedly across this trail.
- **Domain Service** — **Rejected.** `ApprovalService`/`ReconciliationService` orchestrate reads/writes *across other capabilities' own repositories* with no owned table. A validity/point-in-time mechanism would primarily evaluate or store data in its own right, not orchestrate across many other repositories the specific way these two do — the same reasoning already used to reject this shape for Monetary Representation, Shift Assignment, and Work Schedule.
- **Shared Infrastructure** — **Retained, strongly supported.** `ADR-007`'s Authorization Foundation is the proven precedent for exactly this shape: a mechanism needed by three or more capability-specific consumers, built once, capability-agnostic. `discovery.md` §6-7 found this exact three-capability anticipation (Compensation, Shift Assignment, Work Schedule). The strongest candidate found.
- **Repository Infrastructure** — **Retained, as a related but distinct, lower-level, prerequisite concept — not Effective Dating's own aggregate shape.** §3 found the `BETWEEN`/overlap sub-concern is repository/ORM-abstraction-shaped, sitting *below* and separate from whatever Effective Dating's own mechanism turns out to be — a dependency, not an identity for Effective Dating itself.
- **Value Object** — **Rejected.** `LeaveBalance.period_year`, this repository's one Value Object precedent, is a bare scalar with no independent identity. Effective Dating's own defining concern — historical identity (§1) — requires independent identity by definition, a direct structural mismatch.
- **Projection** — **Unknown, not rejected.** Zero read-model/projection precedent exists anywhere. `ReconciliationService` is the closest comparison (a computed, transient, non-persisted read), but if Effective Dating needs to *persist* prior values for lookup (rather than only compute them transiently from other data), it does not cleanly match a Projection's derived-not-owned shape either. No positive or negative evidence either way.

**Result**: Three rejected (Child Entity, Domain Service, Value Object). Two remain `Unknown` (Aggregate Root, Projection). Shared Infrastructure retained as the strongest candidate. Repository Infrastructure retained as a related, lower-level prerequisite, explicitly not chosen as Effective Dating's own shape. No winner is forced.

---

# 8. Authorization

**Repository Evidence**: A fresh grep for `effective|temporal|version` across every authorization-related service file (`authorization_evaluator.py`, `authorization_request.py`, `authorization_decision.py`, `authorization.py`, `approval_authorization.py`, `leave_authorization.py`, `attendance_authorization.py`) returns **zero matches**.

**Decision**: Effective Dating does not own authorization today — mirrors the identical structural finding already reached for every other capability in this trail: no resource or Service exists yet for `AuthorizationRequest.resource` to resolve against. Additionally, and more specifically: Authorization Foundation itself — Effective Dating's own closest structural analog (§7) — has never had, and structurally does not need, its own authorization policy, since it is the mechanism other capabilities' policies consume, not itself a protected resource. The same reasoning already used identically for Monetary Representation's own §8.

---

# 9. Rejected Alternatives

Evaluated at least five, per instruction; rejected only where evidence supports rejection.

- **Compensation owns everything** — **Rejected.** `discovery.md` §6-7 found three independent capabilities, not only Compensation, anticipate this gap; Compensation's own `capability-boundary-analysis.md` explicitly flags it as a candidate for a *separate* capability, not something it claims for itself — direct evidence against exclusive Compensation ownership.
- **Repository owns everything** — **Not fully rejected, only partially correct.** §3/§7 found the `BETWEEN`/overlap sub-concern genuinely is a repository-abstraction concern. But the broader historical-identity and validity-mechanism layer (§1) is not purely repository-shaped — it involves an identity scheme no generic ORM enhancement alone resolves. Rejected as a *complete* explanation; retained as a *partial* one for the query-mechanism sub-layer specifically.
- **`VersionMixin` evolves into Effective Dating** — **Rejected.** §4 found `VersionMixin`'s own shape (a single `Integer` counter on the current row) cannot represent multiple historical values at all — a direct structural mismatch, not merely an unprecedented gap.
- **`AuditLog` evolves into Effective Dating** — **Rejected.** §5 found `AuditLog` records actions, not field-value history or point-in-time validity; its own shape (`entity_id` as a raw UUID, no FK, generic `details` blob) does not support reconstructing a specific field's value as of a specific date without interpretation logic that does not exist.
- **Every capability solves history independently** — **Not rejected.** This is what has happened so far (`Assignment`'s own date range, `HrEmployee`'s own overwrite) and remains technically possible going forward — repository evidence cannot rule it out as impossible, only weigh against it by the same three-capability-anticipation precedent that already justified not leaving Monetary Representation to Compensation alone (§9 above). Not asserted as rejected where the evidence only supports "undesirable by analogy," not "structurally impossible."

---

# 10. Deferred Decisions

Not solved here:

- Which of Aggregate Root or Projection applies, if either (§7).
- How "Repository Infrastructure" (the `BETWEEN`/overlap sub-layer) relates architecturally to Effective Dating's own mechanism — a strict dependency, or a wholly separate initiative (§3, §7).
- The specific relationship direction and integration path with each of Compensation, Work Schedule, and Shift Assignment beyond "consumer" — e.g., whether retrofitting any of their already-approved governance would be required (§2).
- Whether Payroll Calculation or Payslip ever become consumers — currently `Unrelated`, no evidence found either way (§2).
- Business content: replacement policy, retention policy, and which specific effective-dating rules apply per consuming capability (§6).
- Authorization — not decidable today (§8).
- Capability naming — "Effective Dating" originates entirely from this governance trail's own reasoning, not any pre-existing repository or product source (`discovery.md` §9, restated).
- Whether "every capability solves history independently" should be formally closed off as an alternative, or remains available as a fallback if Effective Dating's own governance stalls (§9).

---

# 11. Recommendation

```
Domain Model Discovery may begin.
```

Ownership is decided by elimination and mechanism/policy separation (§1, §6), all five named business-capability relationships were evaluated with real, evidence-based distinctions drawn — including correctly identifying Payroll Calculation and Payslip as `Unrelated` rather than forcing every capability into "Consumer" (§2) — `VersionMixin` and `AuditLog` were both cleanly distinguished and rejected as evolution paths on direct structural grounds (§4-5, §9), and aggregate classification narrowed three candidates on direct structural grounds while identifying Shared Infrastructure as a strongly-supported candidate (§7). This is a comparable or greater degree of resolution than Monetary Representation's own `decision.md` reached at the same stage. The unresolved items (§10) are appropriately left to a Domain Model Discovery pass — no new repository search is expected to change any of them, since each was already checked exhaustively in `discovery.md` or directly re-verified here.

---

# References

- `docs/architecture/capabilities/effective-dating/discovery.md`
- `docs/architecture/capabilities/compensation/capability-boundary-analysis.md`, `shift-assignment/decision.md` §7, `work-schedule/decision.md` §6, `work-schedule/capability-boundary-analysis.md` §8 (all cited only as evidence, directly verified)
- `docs/architecture/ARCHITECTURE_DECISION_RECORDS/ADR-007-authorization-foundation.md` (mechanism/policy precedent, cited §1, §6, §7, §8)
- `docs/architecture/LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` (`VersionMixin` framing, cited §4, §9)

---

# 12. Addendum — Aggregate/Persistence Shape Resolved

**Status:** Accepted — Architecture Owner Approved

**Resolves:** `architecture-gap-analysis.md` §6 items 1–2 (Aggregate/persistence shape; Representation model combination), carried into `final-governance-summary.md` §3 (Architecture-owned) and §6 (Readiness).

This addendum does not reopen or modify §1–§11 above. All prior content is preserved verbatim.

## Decision

Effective Dating is **Shared Infrastructure only**. It owns no table, no row, and no persisted state of its own.

The capability consists of two separate infrastructure pieces, not a single merged mechanism:

1. **Column-composition mixin** — the same architectural shape as `VersionMixin`/`TimestampMixin` (`db/mixins.py`). Contributes effective-dating columns (`effective_from`/`effective_to`) to the consuming capability's own table. Persistence remains entirely owned by the consuming aggregate.
2. **Stateless evaluator** — the same architectural shape as `AuthorizationEvaluator`/`AuthorizationRequest`/`AuthorizationDecision`. Resolves the effective state of a consumer-owned row as of a requested date, reading the effective-dating columns already present on that row. Owns no persistence and no lifecycle.

This resolves the two candidates §7 left `Unknown`:

- **Aggregate Root — Rejected.** Effective Dating owns no persistence of its own; the two closest structural precedents (Mixins, Authorization Foundation) both apply to or interpret data owned by the consumer, never data of their own.
- **Projection — Rejected.** There is no Effective-Dating-owned persisted data to project; the evaluator reads the consumer's own row directly.
- **Single merged mixin + evaluator abstraction — Rejected.** No repository precedent exists for a mechanism that both composes columns and evaluates behavior in one class; every existing mixin contributes columns only, and Authorization Foundation contributes behavior only. No new combined pattern is invented.

`Shared Infrastructure` — already `decision.md` §7's strongest-supported candidate — is confirmed as Effective Dating's sole aggregate classification.

## Evidence

- `domain-model-discovery.md` §1–3 — fresh, direct reads of `authorization_request.py`, `authorization_decision.py`, `authorization_evaluator.py` (evaluator shape: immutable dataclasses in/out, replaceable `evaluate()`, zero persistence) compared against `db/mixins.py` (column-composition shape: contributes columns only, no behavior, none read/write their own state).
- `domain-model-discovery.md` §2 — "Effective Dating plausibly needs elements of *both* shapes simultaneously... Neither existing single pattern alone covers both needs."
- `domain-model-discovery.md` §6 — mirroring either or both precedents means Effective Dating "would itself have no lifecycle, replacement, versioning, or persistence of its own."
- `decision.md` §7 — Shared Infrastructure "Retained, strongly supported"; Aggregate Root and Projection left open specifically pending this comparison.
- `architecture-gap-analysis.md` §1 — every infrastructure component classified "Sufficient, conditionally... relevant only to consuming capabilities' own tables," consistent with no persistence of Effective Dating's own.

## Boundary — Not Resolved By This Addendum

This addendum resolves the aggregate/persistence shape and representation-model-combination questions only. It does not authorize implementation and does not decide:

- replacement / retention policy (Business-owned)
- `BaseRepository` BETWEEN / overlap-query support (Repository-owned, separate initiative)
- per-consumer Effective Dating rules for Compensation
- per-consumer Effective Dating rules for Work Schedule
- per-consumer Effective Dating rules for Shift Assignment
- authorization posture
- capability naming

Each of these remains a separate, still-open governance decision, exactly as `final-governance-summary.md` §3 already categorized them.

## Implementation Gate

```
BLOCKED — NOT READY FOR IMPLEMENTATION
```

The architecture classification is now resolved, but implementation remains blocked by the already-identified:

1. Business-owned replacement/retention policy.
2. Repository-owned `BETWEEN`/overlap-query support.
3. Per-consumer rules for the capabilities that will consume Effective Dating (Compensation, Work Schedule, Shift Assignment).

No production code, migration, model, service, repository, or API is authorized by this addendum.
