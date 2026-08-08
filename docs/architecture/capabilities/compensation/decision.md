# Compensation — Capability Decision

**Status:** Updated after Decision Round 2

**Capability:** Compensation

**Inputs:**

- `discovery.md`
- `decision.md` (original capability decision)
- `domain-model-discovery.md`
- `architecture-gap-analysis.md`
- `business-domain-definition.md`
- `decision-round-2.md`

---

# 1. Capability Ownership

## Decision

Compensation owns the representation of an employee's agreed monetary employment terms.

Compensation represents:

- what the organization has committed to pay an employee;
- the basis of compensation;
- the effective business validity of those terms.

Compensation does not represent:

- payroll calculation;
- payment execution;
- payslip output;
- deductions;
- bonuses;
- transactional payment events.

---

# 2. Business Meaning

## Decision

Compensation represents employment compensation terms that are valid for a period.

The core meaning is:

> The monetary terms an employee is entitled to according to their employment agreement.

A Compensation record describes entitlement, not the final amount paid.

Examples:

- An employee with unpaid leave still has Compensation terms.
- Payroll Calculation may later reduce payable amount based on attendance, leave, or deduction rules.
- Payslip represents the calculated result, not the compensation agreement.

---

# 3. Monetary Representation Relationship

## Decision

Compensation consumes Monetary Representation.

Compensation does not own:

- monetary precision;
- rounding behavior;
- serialization format;
- currency mechanism.

Those concerns belong to Monetary Representation.

---

## Closed Decisions

The following ownership questions are resolved:

| Concern                                 | Owner                   |
| --------------------------------------- | ----------------------- |
| Monetary mechanism                      | Monetary Representation |
| Compensation monetary usage             | Compensation            |
| Payroll calculation of monetary outcome | Payroll Calculation     |

---

## Remaining Business Decisions

Still required:

- single currency vs multi-currency organization;
- exact monetary values required by Compensation;
- currency policy.

---

# 4. Compensation Content

## Decision

The primary compensation concepts are:

## Base Salary

Supported.

Represents fixed salary terms for salaried employees.

---

## Hourly Rate

Supported.

Represents compensation basis for hourly employees.

---

## Daily Rate

Deferred.

Reason:

Daily rate may be:

- an independently agreed employment term; or
- a derived payroll calculation value.

Business decision required before ownership is finalized.

---

## Allowance

Deferred.

Reason:

Allowances may require:

- multiple simultaneous values;
- independent effective periods;
- separate business lifecycle.

Possible future model:

Compensation-related allowance entity.

Not included in the current core decision.

---

## Bonus

Excluded.

Reason:

Bonus represents discretionary or event-based payment rather than standing compensation terms.

Belongs closer to Payroll Calculation or incentive management.

---

## Deduction

Excluded.

Reason:

Deduction affects payable amount, not compensation entitlement.

Belongs to Payroll Calculation / Payroll Run.

---

# 5. History Requirement

## Decision

Compensation requires historical interpretation.

Reason:

Business scenarios require understanding previous compensation terms:

- promotion;
- salary increase;
- annual increment;
- correction;
- temporary adjustment.

The business meaning requires knowing:

- what compensation was valid previously;
- when a change became effective.

---

# 6. Effective Dating Requirement

## Decision

Compensation requires effective dating.

Reason:

Compensation changes are time-dependent business facts.

Examples:

- salary increase effective next month;
- promotion effective on a future date;
- temporary compensation adjustment.

---

## Ownership Boundary

Effective Dating owns:

- temporal validity mechanism;
- historical interpretation mechanism.

Compensation owns:

- compensation business meaning;
- reason for change;
- compensation values.

---

# 7. Lifecycle

## Decision

Compensation changes should not overwrite historical business facts.

A compensation change creates a new effective compensation state.

Examples:

Previous:

```
Salary = X
Effective: January
```

New:

```
Salary = Y
Effective: July
```

Both remain meaningful historical records.

---

## Remaining Decision

Correction behavior remains open:

- amend existing record;
- create compensating correction;
- approval-based replacement.

---

# 8. Relationship with JobGrade

## Decision

Compensation does not own JobGrade.

JobGrade provides classification context.

Compensation may be influenced by:

- promotion;
- grade change;
- compensation policy.

But JobGrade remains its own capability concern.

---

## Remaining Decision

Whether JobGrade should define:

- compensation bands;
- salary ranges;
- minimum/maximum limits.

This is deferred.

---

# 9. Relationship with Payroll Calculation

## Decision

Payroll Calculation consumes Compensation.

Compensation provides:

- agreed monetary terms;
- effective compensation state.

Payroll Calculation owns:

- calculation rules;
- proration;
- deductions;
- attendance effects;
- payable amount.

---

# 10. Relationship with Payslip

## Decision

Payslip does not own Compensation.

Payslip represents calculated payment output.

Relationship:

```
Compensation
      |
      v
Payroll Calculation
      |
      v
Payslip
```

Payslip does not redefine compensation terms.

---

# 11. Relationship with PayrollRun

## Decision

PayrollRun does not own Compensation.

PayrollRun consumes payroll inputs through Payroll Calculation.

Compensation remains the source of employment compensation terms.

---

# 12. Authorization

## Decision (superseded below)

Deferred, recorded at authorship time because Compensation had no defined resource yet. See the Addendum immediately below for the resolved policy; the original reasoning is retained unmodified as historical record.

Reason:

No Compensation-specific authorization resource or policy exists yet.

Authorization cannot be decided until the capability has:

- defined resources;
- operations;
- approval requirements.

## Addendum — Resolved: Compensation Authorization is Owner Only

Payroll Iteration 1 (merged, `5d4378d`) implemented `Compensation` (`models/compensation.py`, `CompensationService`, `api/compensation.py`), satisfying the prerequisite this section named as blocking (a defined resource and operations now exist). `payroll-authorization/decision.md`'s Addendum records the resolved cross-capability policy table; restated here as it applies to Compensation specifically: **Owner Only** — `resource.employee_id == context.employee_context.employee.id` — because `Compensation.employee_id` is a real, persisted, unique-per-employee FK, the same shape `LeaveRequest`/`AttendanceEvent` already use for their own Owner Only policies. This does not reopen any other section of this document; it resolves only the authorization question this section left open.

---

# 13. Aggregate Boundary

## Decision

Compensation represents employee compensation terms.

The aggregate boundary includes:

- employee relationship;
- compensation basis;
- monetary terms;
- effective validity;
- change reason.

---

## Deferred Architecture Decisions

Still open:

- exact aggregate persistence shape;
- Effective Dating integration mechanism;
- Monetary Representation integration mechanism;
- allowance modeling.

---

# 14. Decision Round 2 Closure

Decision Round 2 formally closes the following questions:

| Question                                           | Status |
| -------------------------------------------------- | ------ |
| What is Compensation?                              | Closed |
| Does Compensation require monetary representation? | Closed |
| Who owns monetary mechanism?                       | Closed |
| Does Compensation require history?                 | Closed |
| Does Compensation require effective dating?        | Closed |
| Does Payroll Calculation consume Compensation?     | Closed |
| Does Payslip own Compensation?                     | Closed |
| Does Compensation own JobGrade?                    | Closed |

---

# 15. Remaining Unknowns

## Business

- Daily rate storage vs derivation.
- Allowance ownership/model.
- Currency scope.
- Compensation reason taxonomy.
- Compensation approval policy.
- JobGrade compensation bands.

---

## Architecture

- Concrete Compensation aggregate shape.
- Persistence model.
- Effective Dating integration.
- Monetary Representation integration.
- Authorization implementation.

---

# 16. Recommendation

Compensation is no longer blocked by missing business meaning.

The capability may proceed to architecture design.

Implementation remains blocked until:

- Monetary Representation provides a usable monetary mechanism;
- Effective Dating architecture decision is complete;
- remaining business decisions are resolved where required.

**Current Status: Ready for Architecture Design**

---

# 17. Addendum — Compensation Aggregate History Architecture Resolved (Option A)

**Status:** Accepted — Architecture Owner Approved

**Resolves:** the contradiction between §7 (Lifecycle) below and the shipped Compensation Iteration 1 schema (`models/compensation.py`), identified during Effective Dating governance continuation.

This addendum does not reopen or modify §1–§16 above. All prior content is preserved verbatim.

## Decision

The accepted history/retention decision in **§7 above** (*"Compensation changes should not overwrite historical business facts. A compensation change creates a new effective compensation state."*) and **`compensation/decision-round-2.md` §5** (*"Compensation records should not be overwritten after activation. A compensation change creates a new effective record."*) apply to the **Compensation aggregate itself**.

Compensation must support multiple effective-dated historical rows per employee. Iteration 1's shipped schema — `UniqueConstraint("employee_id")`, `CompensationService.create()` rejecting any existing row via `DuplicateCompensationError`, `get_by_employee_id()` returning a single optional row, and `update()` mutating the existing row in place with no historical record — no longer reflects the intended architecture and must be reconciled.

**Option B** (preserving the single-row schema by revising the history decision) and **Option C** (a separate current/history aggregate) are not selected.

## Effective Dating Consumption

Per `effective-dating/decision.md` §12, Compensation will consume the accepted Effective Dating architecture directly:

- The **column-composition mixin** contributes effective-dating columns to Compensation's own table. `effective_from` already exists on the shipped model but is currently unused by any query; an `effective_to`-equivalent does not yet exist. Exact column shape is an implementation-planning concern, not decided here.
- The **stateless evaluator** resolves which Compensation row is effective as of a given date, replacing today's single-row `get_by_employee_id()` lookup.

No change is made to Effective Dating's own governance (`effective-dating/decision.md`) by this addendum.

## Boundary — Not Authorized By This Addendum

This addendum resolves the architecture question only. It does **not** authorize:

- production code, model, schema, or migration changes to `Compensation`
- changes to `CompensationService`, `CompensationRepository`, or the Compensation API
- changes to existing Compensation tests
- changes to Payroll or `PayrollCalculationService`
- resolution of Compensation correction behavior, overlap permission, Daily Rate ownership/persistence, or Allowance ownership/model (remain Business/Product decisions, unchanged)

Reconciling the shipped schema, redefining `CompensationService` create/update/read/`list_active()` semantics, and resolving Payroll's current-Compensation lookup are downstream implementation-planning work, to be taken up as a separate task.

## Implementation Gate

```text
BLOCKED — architecture resolved, implementation plan not yet authorized
```

The aggregate-shape contradiction is now resolved. Implementation remains blocked pending a separate implementation-planning task (schema migration design, `CompensationService` semantics, Payroll's current-Compensation resolution) and the still-open Business/Product decisions listed above.

---

# 18. Addendum — `is_active` Semantics and PayrollRun As-of Date Resolved

**Status:** Accepted — Architecture Owner Approved

**Resolves:** the two architecture blockers identified during Compensation historical implementation planning: (1) `is_active` semantics under multi-row Compensation, (2) the missing PayrollRun as-of-date field required for Payroll to consume effective-dated Compensation.

This addendum does not reopen or modify §1–§17 above. All prior content is preserved verbatim.

## Decision 1 — `is_active` Semantics: Option A3

`is_active` remains a **business/eligibility concept, distinct from Effective Dating**. The accepted Effective Dating mechanism (`effective-dating/decision.md` §12) remains solely responsible for temporal validity, through `effective_from`/`effective_to`. `is_active` must **not** be redefined as an indicator of a Compensation row's temporal currency.

For the multi-row Compensation model:

- Multiple historical Compensation rows may exist for the same employee.
- Effective Dating's evaluator determines which Compensation row is effective for a given date — `is_active` plays no role in that resolution.
- `is_active` remains an eligibility/business flag, independent of which row is temporally current.
- No "single active row per employee" invariant is introduced merely to preserve the old single-row behavior.
- `is_active` is not deprecated or removed by this decision.
- Existing Payroll eligibility semantics remain authoritative for the current Payroll iteration: `Compensation.is_active == true` (`payroll/decision.md` Version 3 Addendum §5, unchanged, not reopened). Any future change to Payroll eligibility semantics requires a separate governance decision.

**Consequence:** implementations must not use `is_active` to select the temporally effective Compensation record. Effective-date resolution and Payroll eligibility are separate concerns, resolved by separate mechanisms.

## Decision 2 — PayrollRun As-of Date: Option B4

Payroll integration and `PayrollRun` as-of-date semantics are **deferred**. No `PayrollRun` date/period field is introduced by the Compensation historical implementation. `created_at`, `PayrollRun`'s creation timestamp, or any other inferred timestamp must not substitute for a payroll calculation date — no repository evidence supports that equivalence (`payroll/decision.md` §7, `payroll-calculation/decision.md` §10, both confirming pay-period cadence remains unresolved, requiring business/product input the repository does not contain).

Therefore:

- Compensation's historical/effective-dating implementation may proceed independently of Payroll integration.
- Compensation's as-of-date evaluator may be implemented as a capability-level mechanism accepting an explicit `as_of_date` parameter.
- Payroll (`PayrollRun`, `PayrollCalculationService`) is not modified by this decision and must not be changed to invent an as-of date.
- `PayrollCalculationService`'s integration with multi-row Compensation is explicitly deferred to a separate task.
- `PayrollRun` date/period design requires a separate Payroll governance decision before Payroll consumes historical Compensation.

## Governance Consequences

These decisions resolve the two architecture blockers only. They do **not** resolve:

- Compensation correction behavior
- Compensation overlap permission
- Daily Rate ownership/persistence
- Allowance ownership/model

These remain explicitly unresolved Business/Product decisions and are not addressed here.

## Implementation Gate

```text
READY FOR IMPLEMENTATION PLANNING — subject to remaining Business/Product decisions being handled according to their own scope
```

Compensation historical implementation may proceed to implementation planning. It must:

- preserve the accepted multi-row Compensation architecture (§17 above);
- use Effective Dating for temporal validity, not `is_active`;
- keep `is_active` as an eligibility flag, unchanged in meaning, separate from temporal validity;
- introduce no `PayrollRun` date/period semantics;
- leave Payroll integration unmodified;
- stop and escalate if implementation would require deciding any of the still-open Business/Product decisions listed above.

---

# 19. Addendum — Overlap Permission and Correction Behavior Resolved

**Status:** Accepted — Architecture Owner Approved

**Resolves:** the two Business/Product blockers identified during Compensation historical implementation planning: overlap permission and correction behavior (§7, §18).

This addendum does not reopen or modify §1–§18 above. All prior content is preserved verbatim.

## Overlap Permission — O1, Hard Reject

Compensation effective periods are mutually exclusive by default. A new Compensation row whose effective period overlaps another Compensation row for the same employee is rejected.

- No automatic closing of a previous row is introduced.
- Existing rows are not modified during a normal `create()`.
- No replacement semantics are implied by this rule alone.
- Overlap validation is Compensation business policy, not Effective Dating infrastructure — it does not change Effective Dating's own mechanism (mixin + evaluator, §12 of `effective-dating/decision.md`).

## Correction Behavior — C2b, Compensating Correction with Explicit Relation

Compensation correction uses compensating correction semantics. Historical Compensation rows are not amended in place (C1 remains foreclosed, per §7/§17). A correction creates a new Compensation row and explicitly references the Compensation row being corrected — the explicit relation exists because historical lineage must remain auditable, not merely inferable from matching `employee_id`/dates.

**Field/relation shape is not decided here.** No existing repository convention establishes a self-referencing FK from one row to another row of the same entity (confirmed by review of every entity read across this governance trail — none has this shape). This addendum records the architectural requirement only:

- a correction is represented as its own Compensation row;
- that row carries an explicit reference to the Compensation row it corrects;
- the corrected row remains immutable, unchanged by the correction.

The exact field name (e.g. `corrected_compensation_id`, `source_compensation_id`, `supersedes_id`, or otherwise), its nullability, and its FK/index shape are Implementation Plan-level decisions, not decided by this addendum.

## Interaction — Correction Overlap Exemption

The normal overlap prohibition (O1) does not apply to an explicitly identified compensating-correction row when that correction necessarily overlaps the historical period of the row it corrects. This exception is narrow:

- a normal `create()` (no correction reference) → overlap rejected, per O1;
- a future-effective change (no correction reference) → overlap rejected, per O1;
- a row explicitly linked to the Compensation row it corrects (per C2b's relation) → overlap with that specific corrected row may be permitted;
- no implicit exemption exists based only on matching `employee_id`/dates — the exemption applies only via the explicit correction relation itself.

Evaluator priority when a correction row and its corrected row are both effective on the same date is **not decided here** — `EffectiveDatingEvaluator`'s existing `effective_from`-ordering behavior is an implementation detail, not a correction-priority rule, and is not repurposed as one by this addendum.

## Ownership (restated, not changed)

- **Effective Dating** → temporal mechanism only (column-composition mixin + stateless evaluator, no persistence of its own, no business policy) — unchanged by this addendum.
- **Compensation** → owns overlap policy (O1) and correction semantics (C2b), including the correction-overlap exemption.
- **Payroll** → unchanged; integration remains deferred (§18, Option B4) — not reopened here.

## Not Resolved By This Addendum

- Daily Rate ownership/persistence.
- Allowance ownership/model.
- Payroll/`PayrollRun` as-of-date semantics and Payroll integration.
- The correction-relation field's exact name/shape (Implementation Plan territory, see above).
- Evaluator priority/tie-breaking when a correction and its corrected row are simultaneously effective.

## Implementation Gate

```text
READY FOR IMPLEMENTATION PLANNING
```

Overlap permission and correction behavior are now resolved at the architecture/business-policy level. Implementation (schema, migration, repository, service, API, tests) is not authorized by this addendum and remains a separate task.
