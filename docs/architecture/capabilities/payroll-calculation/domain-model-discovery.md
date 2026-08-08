# Payroll Calculation — Domain Model Discovery

**Status:** Complete

**Capability:** Payroll Calculation

**Owner:** EOP Architecture Governance

**Depends On:** `docs/architecture/capabilities/payroll-calculation/discovery.md`, `docs/architecture/capabilities/payroll-calculation/decision.md`

---

# Purpose

This document investigates the ten domain-model questions posed for Payroll Calculation, using only `discovery.md`, `decision.md`, and the repository evidence they cite. No architecture is invented. Every statement is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**, per the governing instruction.

---

# 1. Possible Aggregate Candidates

Each candidate evaluated against repository evidence only. No candidate is invented a shape it is not evidenced to have.

## `PayrollCalculation`

- Repository Evidence: `decision.md` §1 decided the *capability* named "Payroll Calculation" owns a responsibility (combining upstream data into a result), by exclusion — but this is a capability-boundary decision, not evidence that an entity named `PayrollCalculation` should be persisted. Two existing precedents exist in the repository for a capability implemented as pure process with no owned table: `ApprovalService` (writes onto other entities' rows, owns none itself) and `ReconciliationService` ("owns no aggregate, no table, and no repository of its own," `payroll/discovery.md` §5).
- Logical Consequence: `PayrollCalculation`, if built as the capability's entry point, most closely resembles a **Domain Service** — the shape both existing precedents share (no owned persistence, orchestrates reads across other capabilities' repositories, returns or writes a result elsewhere). This is inferred by structural analogy, not observed, since no such code exists.
- Unknown: Whether it would resemble `ApprovalService`'s shape (mutate a target row) or `ReconciliationService`'s shape (compute and return, mutate nothing) is not decidable — `decision.md` §3-4 leaves exactly this distinction open (produces data for `Payslip` vs. computing a transient value).

## `PayrollResult`

- Repository Evidence: already directly examined under this name in `payroll/domain-model-discovery.md` A1: *"repository evidence is insufficient even to hypothesize a shape"* — its only analogy, `AttendanceReconciliationResponse`, is a non-persisted Projection, explicitly for low-stakes, non-financial data. `decision.md` §4 reached the same "Unknown" conclusion independently, this time under the literal name "calculation result."
- Logical Consequence: no positive classification is supported. The weak `AttendanceReconciliationResponse` analogy would suggest Projection if anything, but two separate prior analyses already found this insufficient to commit to.
- Unknown: shape, persistence, and existence are all unresolved — restated, not newly resolved here.

## `PayrollFormula`

- Repository Evidence: repository-wide search for `RuleEngine|FormulaEngine|ExpressionEngine|StrategyPattern|PolicyEngine|Strategy\b|class.*Policy` returns zero matches (`discovery.md` §5). No table, class, or abstraction representing a formula exists anywhere.
- Logical Consequence: none can be drawn — there is no structural precedent to reason from, positively or negatively.
- Unknown: **Not Supported.** No repository evidence of any kind addresses this candidate.

## `PayrollRule`

- Repository Evidence: identical to `PayrollFormula` — the same zero-match search covers this candidate. Every actual "rule" found anywhere in the repository (`LeaveAuthorizationEvaluator`, `ApprovalAuthorizationEvaluator`, `AttendanceAuthorizationEvaluator`) is a hard-coded Python comparison inside an authorization evaluator class, not a data-represented, independently-persisted rule entity.
- Logical Consequence: none can be drawn.
- Unknown: **Not Supported.**

## `PayrollExecution`

- Repository Evidence: the closest analogy is the dormant `Job`/`Event` schema shape (`schemas/job.py`, `schemas/event.py`: `id`, `name`, `payload`, a timestamp) used by `JobService`/`EventService` — but both are held in a plain in-memory Python list (`InMemoryJobProvider._jobs`, `InMemoryEventPublisher._events`), never a database table, and neither has any caller anywhere (`discovery.md` §6, re-confirmed).
- Logical Consequence: this is the weakest form of precedent found for any candidate in this section — an unpersisted, unused, in-memory-only shape for tracking "a unit of work occurred," not a persisted Aggregate Root.
- Unknown: **Not Supported** as a persisted entity. Whether execution tracking would be needed at all is itself unresolved (`decision.md` §5).

## `PayrollSnapshot`

- Repository Evidence: exactly two "immutable record" precedents exist in the repository — `AuditLog` and `Payslip` (`discovery.md` §8) — neither is a computed/versioned snapshot; `LeaveBalance`'s own docstring uses the word "snapshot" but is confirmed to be a static, independently-editable stored value with no computation or versioning behind it (`discovery.md` §8, `payroll/domain-model-discovery.md` E4).
- Logical Consequence: none — no entity in the repository has ever represented a versioned or point-in-time computed snapshot.
- Unknown: **Not Supported.**

## Or None

- Logical Consequence, drawn from the six analyses above: only `PayrollCalculation` (as a Domain Service, by weak structural analogy) has any repository-evidenced classification at all. The other five candidates are **not supported** by any repository precedent, positive or negative — the honest conclusion is closer to "none," qualified only by `PayrollCalculation`'s own weak, inferred Domain Service classification.

---

# 2. Domain Ownership Classification

| Candidate | Classification | Basis |
|---|---|---|
| `PayrollCalculation` | **Domain Service** (weak Logical Consequence) | Structural analogy to `ApprovalService`/`ReconciliationService`, §1 |
| `PayrollResult` | **Unknown** (weak Projection analogy, previously found insufficient) | §1; `payroll/domain-model-discovery.md` A1; `decision.md` §4 |
| `PayrollFormula` | **Unknown / Not Supported** | §1 — zero repository precedent |
| `PayrollRule` | **Unknown / Not Supported** | §1 — zero repository precedent |
| `PayrollExecution` | **Unknown / Not Supported** | §1 — weakest analogy found (unpersisted, unused `Job`/`Event` shape) |
| `PayrollSnapshot` | **Unknown / Not Supported** | §1 — no versioned/computed-snapshot precedent anywhere |

No candidate is classified as Aggregate Root, Entity, or Value Object with repository support — a materially different outcome than `PayrollRun`/`Payslip`'s own domain-model discovery, where both were classified as Aggregate Roots with direct, strong precedent (`payroll/domain-model-discovery.md` A1). This asymmetry is itself a finding: `PayrollRun`/`Payslip` had decidable minimal identities; none of these six candidates does.

---

# 3. Calculation Output

**Repository Evidence**: `decision.md` §4 already found this Unknown, citing the same tension found here: `ReconciliationService`'s computed/transient shape is the only **proven, currently-working** precedent in the repository for producing a derived value (§1) — but it is proven only for low-stakes, non-financial, same-day data, and `payroll/decision.md` §2's own rationale for persisting `PayrollRun`/`Payslip` at all was that a payroll figure must not be freely recomputable ("silently change after being issued"). The `EventService` "event" option has some repository presence (a typed, existing abstraction) but zero callers and no working transport (`discovery.md` §6). A purely "temporary" (request-scoped, never returned as a distinct object) result has no distinguishing precedent from "computed" — the repository does not differentiate the two anywhere.

**Logical Consequence**: Precedent strength, ranked: `ReconciliationService`'s computed/transient shape is the only one **proven working end-to-end**; the `BaseEntity`-backed persisted shape is proven working for identity records (`PayrollRun`, `Payslip`) but never yet for a computed value; the event-based shape exists only as unused scaffolding. None of the three is proven *for this specific purpose* (a financial calculation result), and `decision.md` §2's audit-trail rationale weighs against the only fully-proven option (transient/computed).

**Unknown**: Whether the output is persisted, computed-transient, or event-carried remains undecided — restated from `decision.md` §4, not newly resolved. This document does not infer an answer.

---

# 4. Formula Ownership — Business Rules as Data vs. Code

**Repository Evidence**: Searched for every precedent representing a business rule as stored data (a table/column read and interpreted at runtime) rather than as Python code. Two categories found:

- Every actual behavioral rule in the repository — every authorization policy (`LeaveAuthorizationEvaluator`'s `resource.employee_id == context.employee_context.employee.id`, `ApprovalAuthorizationEvaluator`'s manager comparison, `AttendanceAuthorizationEvaluator`'s identical Owner Only rule) — is hard-coded as a Python comparison inside a class. None is read from a database row, configuration table, or external source.
- The one candidate field resembling a data-represented business parameter is `Shift.grace_period_minutes`/`break_duration_minutes` (`models/shift.py`) — genuinely stored, per-row, numeric configuration. However, `ReconciliationService`'s own docstring explicitly states *"grace periods... are explicitly out of scope for v1"* — confirming this field is not read or applied by any computation anywhere in the current codebase. It is stored but inert.

**Logical Consequence**: **No working precedent exists anywhere in the repository for representing a business rule as data instead of code.** The one candidate that stores a rule-shaped parameter as data (`Shift.grace_period_minutes`) is not consumed by any reader — it does not demonstrate a working data-driven-rule pattern, only that such a field can be stored without yet being acted on.

**Unknown**: None — the absence is explicit and total, stated per instruction.

---

# 5. Execution Lifecycle

Restated from `decision.md` §5, evaluated against each named option specifically:

- **Request-driven**: **Repository Evidence** — proven, working, the dominant pattern across every capability reviewed in this conversation — but proven only for single-entity, single-request operations. No service anywhere accepts "compute for all employees" or "compute for a period" as a single call.
- **Batch**: **Repository Evidence** — no precedent exists anywhere. `ReconciliationService`, the closest analog to a multi-input computation, is explicitly single-employee/single-date per call (`payroll/discovery.md` §4-5, re-confirmed).
- **Scheduled**: **Repository Evidence** — no scheduler, cron, or time-triggered mechanism exists anywhere in the repository (`discovery.md` §6, confirmed by fresh grep, zero matches).
- **Event-driven**: **Repository Evidence** — `EventService` exists, fully typed, but has zero callers anywhere and no working transport (no subscriber mechanism defined even in the abstraction itself) (`discovery.md` §6).
- **None**: not applicable — some lifecycle must trigger any eventual computation; this option is listed for completeness but not itself evidenced as a repository state.

**Logical Consequence**: Only request-driven has a *proven* precedent, and it is proven for a shape (single-entity) narrower than what Payroll Calculation would plausibly need (multi-employee, per-`PayrollRun`). No option is proven for the actual required shape.

**Unknown**: Which lifecycle applies — restated from `decision.md` §5, "not decidable today."

---

# 6. Versioning

Searched for: effective dating, historical version, snapshot, revision, recalculation.

**Repository Evidence**: **Absent, confirmed across every entity in the repository without exception.**

- No entity anywhere carries `valid_from`/`valid_to`, an `effective_date`, or any temporal-versioning field (`payroll/domain-model-discovery.md` E4, `discovery.md` §8, both re-confirmed, not re-derived).
- `AuditMixin`'s `created_by`/`updated_by` columns exist on every entity but are populated by no reviewed service anywhere (`payslip/discovery.md` §6) — the closest thing to a "who/when" history mechanism in the repository, and it is inert.
- No "revision" or "recalculation" concept exists anywhere — every entity's `update` operation (where one exists) overwrites in place, with no prior value retained, no history row, and no version-increment enforcement (`VersionMixin.version` exists on every entity but is never read, compared, or incremented-on-conflict anywhere, `payroll/domain-model-discovery.md` E4).
- `LeaveBalance`'s "snapshot" language (§1) does not reflect actual versioning — it is one static, freely-overwritable row per employee/period, not a append-only or point-in-time-preserved record.

**Logical Consequence**: There is no repository mechanism, proven or scaffolded, for representing "this value as it was at time X" for any entity in the repository. A Payroll Calculation capability requiring recalculation-with-history (e.g., correcting a prior period's figure without losing the original) would have no existing pattern to build on.

**Unknown**: None — the absence is total and was searched for specifically, not merely inferred from silence.

---

# 7. Relationship to `PayrollRun`

**Repository Evidence**: `decision.md` §2 already decided, directly: `PayrollRun`'s merged code contains zero calculation logic and zero call paths to any other capability; no repository evidence supports `PayrollRun` owning calculation. No repository evidence supports the reverse either — nothing suggests a future Calculation capability would own or control `PayrollRun`'s own persistence, which remains `PayrollRunService`'s alone (`decision.md` §2, §6).

**Logical Consequence**: Neither "`PayrollRun` owns calculations" nor "Calculation owns `PayrollRun`" is supported. "Peer aggregates" is the closest of the four offered options, but only if `PayrollCalculation` were itself classified as an Aggregate Root — and §1/§2 above found that classification unsupported (Domain Service is the better-evidenced, weaker analogy). The most precise statement repository evidence supports is: `PayrollRun` would be a **read-only data source** for Payroll Calculation (the same read-only relationship direction already verified for every other producer, §ownership in `decision.md` §6), not a peer in the aggregate sense, and not an owner/owned relationship in either direction.

**Unknown**: Whether, if `PayrollCalculation` is ever built as something other than a pure Domain Service (e.g., if execution tracking is later decided to need its own persisted record, §1 `PayrollExecution`), that record would then relate to `PayrollRun` as a peer aggregate — not decidable now, since neither `PayrollExecution`'s existence nor shape is evidenced (§1).

---

# 8. Relationship to `Payslip`

**Dependency direction only, as instructed.**

**Repository Evidence**: `decision.md` §3 already decided: Payroll Calculation does not own `Payslip`; at most, it would produce data later written into a `Payslip` row through `PayslipService`'s own interface. `Payslip`'s own decided relationship to `PayrollRun` is a database-level FK (`Payslip.payroll_run_id → payroll_runs.id`, `ON DELETE RESTRICT`, `payslip/decision.md` §6).

**Logical Consequence**: The Calculation-to-`Payslip` relationship is **not** the same kind of relationship — since `PayrollCalculation` is not evidenced as a persisted entity (§1-2), there is no FK to hold. The dependency is process-level/data-flow only: **Payroll Calculation, if built, is upstream of `Payslip`** — the same directional sense in which `Payslip` is upstream-dependent on `PayrollRun` (a prerequisite must exist before the dependent record is created), but expressed as "a service call or data hand-off precedes a `PayslipService.create` call," not as a schema-level relationship.

**Unknown**: The exact mechanism of that hand-off (does `PayslipService.create` gain a new caller that first invokes Payroll Calculation? Does Payroll Calculation call `PayslipService.create` directly, which would be a new, currently-nonexistent cross-capability call?) is not evidenced anywhere — restated from `decision.md` §9's finding that no consumer of Payroll Calculation is observed in code at all.

---

# 9. Domain Invariants

Only invariants directly derivable from already-decided repository evidence (`decision.md`'s own decisions count as repository evidence for this purpose, per that document's own citation convention). Everything else is `Unknown`, per instruction.

**Derivable:**

1. **Payroll Calculation must not write to any upstream producer's data** — directly decided, `decision.md` §6, mirroring `PayrollRun`'s own verified (not merely planned) read-only behavior in code.
2. **Payroll Calculation must not own `PayrollRun`'s or `Payslip`'s persistence** — directly decided, `decision.md` §2-3, consistent with the uniform one-entity-one-service pattern found without exception across twelve reviewed entities.
3. **Payroll Calculation performs no authorization decision of its own today** — directly decided, `decision.md` §8, by the same structural reasoning already applied to Payroll Authorization and Payslip Authorization.

**Unknown (everything else):** Any invariant about the calculation's own internal correctness (e.g., "a result must reconcile to zero," "an output must reference exactly one `PayrollRun`") is not derivable — no such rule is evidenced anywhere, because no formula, output shape, or persisted entity exists to state an invariant about (§1, §3, §4).

---

# 10. Repository Patterns Reusable for This Capability

Identified only — no new pattern proposed, per instruction:

- **Domain Service, no owned table** (`ApprovalService`, `ReconciliationService` shape) — the closest-evidenced structural fit for `PayrollCalculation` itself (§1-2).
- **`UnitOfWork`/session-per-call pattern** (`SQLAlchemyUnitOfWork`, used identically by every service reviewed in this conversation) — reusable regardless of which other decision is eventually made.
- **Existence-validation-before-use pattern** (`PayslipService.create`'s `employee_id`/`payroll_run_id` existence checks via `.exists()`) — directly reusable if Payroll Calculation needs to confirm a referenced `PayrollRun` (or other upstream row) exists before proceeding, consistent with §9's invariant 1 (read-only, not a write).
- **`BaseEntity`/`BaseRepository`/per-entity Service/API CRUD pattern** — reusable *only if* a future decision determines some part of this capability (e.g. `PayrollExecution`, §1) should be persisted; not applicable to the Domain Service shape itself.
- **Dormant `EventService`/`JobService` scaffolding** — present and reusable *as infrastructure*, but not a proven pattern (§5); reuse would make Payroll Calculation the first real exerciser of either, not a capability following an established, working precedent.

---

# Recommendation

```
Another governance phase is still required. Implementation Planning is not
yet possible.
```

This domain-model pass surfaces more unresolved structure than `PayrollRun`/`Payslip`'s own domain-model discovery did, not less: five of six named aggregate candidates are unsupported by any repository precedent: (§1-2), calculation output remains undecided among three live options (§3), no working precedent exists for representing a business rule as data (§4), no execution lifecycle is proven for the required (multi-employee) shape (§5), and versioning/recalculation support is confirmed entirely absent (§6). The three invariants derivable (§9) are boundary rules (what Payroll Calculation must not do), not a positive domain model. Repository evidence supports only that Payroll Calculation would be a Domain Service reading existing producers — it does not yet support a shape for what that service would compute, store, or return.

---

# References

- `docs/architecture/capabilities/payroll-calculation/discovery.md`
- `docs/architecture/capabilities/payroll-calculation/decision.md`
- `docs/architecture/capabilities/payroll/domain-model-discovery.md`, `decision.md`
- `docs/architecture/capabilities/payslip/decision.md`, `discovery.md`
