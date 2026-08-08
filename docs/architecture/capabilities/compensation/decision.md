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
