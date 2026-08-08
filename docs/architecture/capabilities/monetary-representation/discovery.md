# Monetary Representation — Discovery

**Status:** Complete

**Capability:** Monetary Representation (candidate — validity as an independent capability not yet established)

**Owner:** EOP Architecture Governance

---

# Purpose

This document determines whether Monetary Representation is an independent architectural capability or merely an implementation detail of Compensation, using repository evidence only. It follows the same methodology already used for `payroll/discovery.md`, `payslip/discovery.md`, `payroll-calculation/discovery.md`, and `compensation/discovery.md`: observation only, no architecture chosen, no schema authored, no concept invented. Every statement is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**. This document originates from `compensation/capability-boundary-analysis.md` §3/§8, which identified Monetary Representation as a candidate capability warranting its own discovery — that document's own reasoning is treated as prior governance evidence here, not re-derived.

---

# Discovery Scope

Full file reads unless noted. All searches run fresh for this discovery.

- Repository-wide, case-insensitive grep for `Decimal|Numeric|MONEY|Float|double|BigDecimal|currency|amount|precision|scale` across `services/api` (source, tests, and alembic together) — 3 files matched, every match read in context.
- Repository-wide, case-insensitive grep for `Money|Monetary|Currency|Amount|Price|Cost|Salary|Wage|Compensation` scoped to `services/api/src` — zero matches.
- Separate grep for `\bPrice\b|\bCost\b` across `services/api/src` — zero matches.
- Repository-wide grep for `TypeDecorator|class.*\(str\)|class.*\(int\)|NewType` across `services/api/src` — zero matches.
- Corrected, precise grep for real numeric-bound Pydantic constraints (`\bge=\d|\ble=\d|\bgt=\d|\blt=\d`, not the substring-prone `ge=`/`le=` alone, which false-matches inside `min_length=`/`max_length=`) across `services/api/src/eop_api/schemas` — zero matches, confirmed after an initial looser search returned 22 files that were all false positives on `length=`.
- Filename search for `*types*`, `*value_object*`, `*primitives*` under `services/api/src/eop_api` — only `employment_types.py`/`location_types.py` matched, both ordinary entity-named files, not a shared value-type module.
- Repository-wide, case-insensitive grep for `Money|Monetary|Currency|Amount|Price|Cost|Salary|Wage|Compensation` across all of `docs/` — 17 files matched, all already authored within, or catalogued by, this conversation's own Payroll/Payslip/Payroll Calculation/Compensation/Payroll Authorization governance trail; no new document found.
- `docs/architecture/ARCHITECTURE_DECISION_RECORDS/ADR-007-authorization-foundation.md`, `services/event.py`, `services/job.py`, `events/base.py`, `jobs/base.py` — re-consulted from prior discoveries in this conversation, not re-derived.
- `docs/architecture/capabilities/compensation/capability-boundary-analysis.md` — this conversation's own prior output, the direct source of this discovery's own existence, re-consulted as evidence.

---

# 1. Numeric Representation

**Repository Evidence**: Repository-wide grep for `Decimal|Numeric|MONEY|Float|double|BigDecimal|currency|amount|precision|scale` across all of `services/api` returns 3 files (`tests/conftest.py`, `tests/test_files_api.py`, `tests/test_file_service.py`). Every match, read in context, is a false positive: `conftest.py`'s "scale" match is the ordinary English phrase "at scale" (describing test suite design); `test_files_api.py`'s and `test_file_service.py`'s "double" matches are both the testing term "test double" (a mock/stub), unrelated to a numeric `double` type. **No monetary or fractional-precision type exists anywhere in the repository.**

A separate, corrected search for real Pydantic numeric-bound constraints (`ge=`/`le=`/`gt=`/`lt=` followed by a digit, distinct from the substring `length=` that a looser pattern falsely matches) across every schema file returns zero matches. The only validation convention found anywhere in `services/api/src/eop_api/schemas` is string length (`min_length=`/`max_length=`).

**Every numeric field reviewed across the entire codebase in this and prior discoveries is a plain `Integer`** — `LeaveBalance.allocated_days`/`used_days`/`remaining_days`, `JobGrade.level`. No exception was found.

**Logical Consequence**: Only `Integer` exists as a numeric convention in this repository. No monetary representation, no fractional-precision type, and no numeric-bounds validation convention of any kind exists anywhere, for any purpose.

**Unknown**: None — this was searched for exhaustively and the false positives individually verified, not assumed.

---

# 2. Cross-Capability Usage

**Repository Evidence**: No code exists anywhere that uses a monetary value today — `PayrollRun` and `Payslip` (both merged) carry zero monetary fields, confirmed directly against their current models. Three separate governance documents, authored independently across this conversation, each anticipate a monetary concept being needed by more than one capability: `payroll-calculation/architecture-gap-analysis.md` §1 names a compensation/rate-bearing capability as its own missing prerequisite; `compensation/decision.md` §6 establishes Compensation as the evidence-supported owner of monetary values once introduced; `compensation/capability-boundary-analysis.md` §3 names Compensation, Payslip, and Payroll Calculation together as the capabilities whose own governing documents anticipate eventually needing monetary values (citing `LEAVE_DESIGN.md` §10 and `TIMESHEET_DESIGN.md` §11's own "Future Compatibility" sections, which name Payroll as a future consumer of `APPROVED` data for pay computation).

**Logical Consequence**: If monetary values are introduced, more than one capability's own governance already anticipates needing them — this is documented, prose-level anticipation across three independently-authored documents, not a single capability's private concern.

**Unknown**: Whether `PayrollRun` itself would ever hold a monetary value directly (as opposed to only `Payslip`/Compensation) — no document addresses this, restated from `compensation/discovery.md` §7's own recorded `Unknown`.

---

# 3. Existing Cross-Cutting Mechanisms — Comparison Only

**Repository Evidence**: `ADR-007` (Authorization Foundation) states, as its own documented Design Principle: *"Authorization mechanism is separated from authorization policy."* Authorization Foundation (`AuthorizationRequest`, `AuthorizationDecision`, `AuthorizationEvaluator`, `AuthorizationService`) is a generic, capability-agnostic abstraction, built once; three capability-specific evaluators (`ApprovalAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`, `AttendanceAuthorizationEvaluator`) each supply their own policy by subclassing the same base, without modifying the Foundation itself.

**Comparison, not a conclusion, per instruction**: Monetary Representation — as a question, not a decided architecture — poses a structurally comparable shape: a technical concern (how a fractional/currency value is typed and precision-handled) that, per §2, more than one future capability's own governance already anticipates needing, separate from what each capability's own monetary *content* means. Whether this resemblance is close enough to warrant treatment as a Foundation-shaped mechanism, a lighter shared convention, or neither, is not concluded here.

**Unknown**: Whether the resemblance to Authorization Foundation's specific shape holds beyond this structural comparison — not decided.

---

# 4. Persistence — Reusable Value Representations

**Repository Evidence**: Repository-wide search finds zero `TypeDecorator` custom SQLAlchemy types, zero `NewType` wrappers, and zero dedicated value-object classes anywhere in `services/api/src`. The only "reusable" persistence pattern found anywhere is the mixin-composition pattern (`UUIDMixin`, `TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`, `VersionMixin`, `db/mixins.py`), applied via multiple inheritance on `BaseEntity`. `UUIDMixin` is the closest analog to a "reusable identifier," but it contributes a whole column (`id`) to every entity via inheritance — it is not a reusable scalar *type* that could be assigned to an arbitrary field the way a `Money` type or a custom column type would be.

**If none exist, state explicitly**: **No repository precedent exists for a reusable, importable value type usable on an arbitrary field.** The mixin pattern is the only reuse mechanism found, and it composes whole columns via inheritance, not individual field types.

**Unknown**: None — searched for specifically and confirmed absent.

---

# 5. Validation

**Repository Evidence**: No precision validation, scale validation, rounding, overflow, or currency validation exists anywhere in the repository — confirmed by the same precise search as §1 (zero real `ge=`/`le=`/`gt=`/`lt=` numeric-bound constraints in any schema). The only validation conventions found repository-wide are string-length constraints (`min_length=`/`max_length=`) and service-layer existence checks (e.g., `PayslipService.create` validating `employee_id`/`payroll_run_id` exist) — neither is a numeric-value validation mechanism.

**Logical Consequence**: None beyond the above.

**Unknown**: None.

---

# 6. Ownership

**Repository Evidence**: No entity, service, or module anywhere in the repository owns precision, rounding, currency, or monetary formatting.

**Stated explicitly, per instruction: none of these four concerns is owned by any existing capability, because none of the four concepts exists anywhere in the repository to be owned.**

---

# 7. Repository Patterns — Structural Comparison Only

**Repository Evidence**: Three examples of a "shared, cross-capability mechanism, built ahead of specific consumers" exist in the repository:

- **Authorization Foundation** — proven and exercised, three capability-specific consumers (`ApprovalAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`, `AttendanceAuthorizationEvaluator`), documented design principle (`ADR-007`).
- **`EventService`** — a generic, typed abstraction (`EventPublisher`), zero callers anywhere, no working transport behind its only implementation (`InMemoryEventPublisher`), own docstring: *"infrastructure for later adoption."*
- **`JobService`** — identical shape and state to `EventService`.

**Comparison only, no equivalence inferred, per instruction**: All three share the structural shape of "a generic interface, built once, intended for multiple future capability-specific consumers to plug into" — confirming the repository *does* have precedent for this general pattern, in three different states of maturity (one proven and exercised; two dormant and unused). Whether Monetary Representation would resemble any of these three specifically — in maturity, in mechanism, or in adoption pattern — is not inferred here.

---

# 8. Consumers

**Repository Evidence, drawn only from existing governance documents already in this repository — no consumer invented beyond what is already named**:

- `compensation/decision.md` §6, §8 — Compensation is the evidence-supported owner of monetary values, and (per `compensation/capability-boundary-analysis.md` §3) a plausible first consumer of a shared monetary mechanism.
- `payroll-calculation/architecture-gap-analysis.md` §1/§8 — Payroll Calculation is named as needing compensation/rate-bearing data to function at all.
- `compensation/capability-boundary-analysis.md` §3 — names `Payslip` as a third capability whose own governance (via `LEAVE_DESIGN.md` §10, `TIMESHEET_DESIGN.md` §11) anticipates eventually needing monetary fields (gross/net/tax/deduction), though `Payslip`'s own merged code carries none today.

**Logical Consequence**: Three named, documented (not code-observed) potential consumers exist: Compensation, Payroll Calculation, `Payslip`. No document names a fourth.

**Unknown**: Whether `PayrollRun` itself would be a direct consumer — not addressed anywhere (restated from §2).

---

# 9. Terminology

**Repository Evidence**: Fresh, repository-wide, case-insensitive grep for `Money|Monetary|Currency|Amount|Price|Cost|Salary|Wage|Compensation` scoped to `services/api/src` returns **zero matches** — none of these nine terms appears anywhere in production source code. A separate, narrower grep for `\bPrice\b|\bCost\b` alone, across the same scope, also returns zero matches. The same term set searched across all of `docs/` returns 17 files, all already known — authored within, or catalogued by, this conversation's own Payroll/Payslip/Payroll Calculation/Compensation/Payroll Authorization governance trail; no document predating this conversation uses any of these terms in a capability-defining way.

**Existing usage**: none, in source code. **Absence**: total, for all nine terms, in source. **Ambiguity**: none found — there is no competing or inconsistent usage anywhere, only a complete absence outside this conversation's own governance documents.

---

# 10. Unknowns

Listed, not answered:

- Whether Monetary Representation's structural resemblance to Authorization Foundation (§3) is close enough to warrant the same treatment, a lighter mechanism, or neither.
- Whether it would more closely follow `EventService`/`JobService`'s dormant-scaffolding pattern or Authorization Foundation's proven, exercised pattern (§7) — no repository evidence favors one over the other for a not-yet-built mechanism.
- Whether a reusable value type (§4) is even the right shape, given no precedent for one exists anywhere in this repository at all — the mixin-composition pattern is the only reuse mechanism found, and it does not obviously extend to a single scalar field type.
- Whether `PayrollRun` would ever be a direct consumer (§2, §8).
- Whether Compensation, Payroll Calculation, and `Payslip` (§8) are the complete set of eventual consumers, or whether others would emerge once each of those capabilities' own governance progresses further.
- Whether "Monetary Representation" is the correct or final name for this candidate capability — it originates entirely from `compensation/capability-boundary-analysis.md` §3/§8, this conversation's own document, not from any pre-existing governance source.

---

# Recommended Next Step

```
Monetary Representation Capability Decision
```
