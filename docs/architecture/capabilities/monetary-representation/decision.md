# Monetary Representation — Capability Decision

**Capability:** Monetary Representation

**Status:** Approved — Boundary and Ownership Decision

**Version:** 2

**Owner:** Architecture

---

# 1. Executive Summary

Monetary Representation is a reusable capability responsible for the consistent representation of monetary values across consuming business capabilities.

Round 1 established the architectural boundary:

- Monetary Representation owns monetary representation mechanism.
- Consuming capabilities own monetary business meaning and policy.
- Payroll Calculation owns computation policy.
- Compensation owns compensation meaning.
- Monetary Representation does not become an owner of salary, payroll, accounting, or financial business rules.

Round 2 incorporated Business Domain Definition and reduced ownership Unknowns:

Decided:

- monetary representation mechanism ownership
- precision ownership
- scale ownership
- rounding ownership split
- formatting exclusion
- serialization ownership direction
- persistence ownership split
- currency ownership split

Still not decided:

- concrete monetary type shape
- precision value
- rounding rule
- supported currency list
- serialization format
- implementation mechanism

No implementation technology is decided by this document.

---

# 2. Capability Ownership

## Monetary Representation owns representation

**Decision: Yes.**

Monetary Representation owns the reusable mechanism for representing monetary values.

This includes:

- how monetary values are represented
- precision handling convention
- scale handling convention
- representation consistency

It does not own the meaning of individual monetary values.

---

## Monetary Representation does not own business meaning

**Decision: No.**

Business meaning belongs to consuming capabilities.

Examples:

- Compensation owns salary meaning.
- Payroll Calculation owns calculation meaning.
- Payslip owns payment record meaning.

A monetary value exists only inside the business context that owns it.

---

## Monetary Representation does not own payroll policy

**Decision: No.**

Payroll Calculation owns:

- formulas
- rates
- calculations
- payroll rules

Monetary Representation only represents monetary values used by those calculations.

---

# 3. Business Meaning

Monetary Representation exists to express monetary values consistently.

It represents:

- monetary amount
- currency association
- monetary comparison semantics

It does not represent:

- salary policy
- allowance policy
- deduction policy
- taxation
- accounting policy
- exchange-rate policy

---

# 4. Relationship with Compensation

| Concern | Owner |
|---|---|
| Monetary representation | Monetary Representation |
| Precision convention | Monetary Representation |
| Scale convention | Monetary Representation |
| Rounding mechanism | Monetary Representation |
| Rounding business rule | Business |
| Salary meaning | Compensation |
| Compensation policy | Compensation |

Decision:

Compensation consumes Monetary Representation.

Compensation remains the owner of compensation business meaning.

---

# 5. Relationship with Payroll Calculation

Payroll Calculation consumes Monetary Representation.

Payroll Calculation owns:

- calculation rules
- payroll formulas
- combining monetary inputs

Monetary Representation does not calculate.

---

# 6. Relationship with Payslip

Payslip may consume Monetary Representation when monetary fields are introduced.

Payslip owns:

- immutable payment record
- payslip meaning

Payslip does not own monetary representation.

---

# 7. Mechanism vs Policy

Repository evidence continues to support separation between:

## Mechanism

Owned by Monetary Representation:

- monetary representation
- precision convention
- scale convention
- serialization convention

## Policy

Owned elsewhere:

- salary policy
- payroll policy
- rounding rule
- supported currencies
- financial rules

This follows the same mechanism/policy separation pattern established by Authorization Foundation.

---

# 8. Aggregate / Service Classification

The Round 1 classification remains unchanged.

## Aggregate Root

Rejected.

Monetary Representation has no independent business lifecycle, identity, or persistence ownership.

---

## Domain Service

Rejected.

It does not orchestrate business processes or repository operations.

---

## Value Object

Still unresolved as an implementation shape.

The capability boundary is decided, but the concrete representation mechanism is not.

---

## Shared Infrastructure / Library / Utility / Type Extension

Still unresolved.

The final implementation form requires an architecture decision.

---

# 9. Precision

## Ownership

Decision: Monetary Representation owns precision convention.

Reason:

Precision is part of how monetary values are represented.

---

## Value

Still open.

The business has not decided:

- number of decimal places
- fractional unit requirement
- organizational precision standard

---

# 10. Scale

## Ownership

Decision: Monetary Representation owns scale convention.

Scale is treated as part of precision representation.

---

## Value

Still open.

No concrete scale is defined.

---

# 11. Rounding

## Ownership Split

Decision:

Monetary Representation owns the mechanism of applying rounding consistently.

Business owns the rounding rule.

Examples of business-owned decisions:

- rounding direction
- financial policy
- regulatory requirement

The capability does not invent rounding policy.

---

# 12. Formatting

Decision:

Formatting does not belong to Monetary Representation.

Formatting depends on:

- locale
- presentation requirement
- product behavior

Formatting belongs to consuming applications or presentation concerns.

---

# 13. Serialization

Decision:

Serialization convention belongs to Monetary Representation.

Reason:

Serialization defines how the representation mechanism is exposed.

Still open:

- string vs structured representation
- API representation format
- transport convention

---

# 14. Persistence

Decision:

Monetary Representation does not own consumer persistence.

Consumers own their own persisted business data.

Examples:

- Compensation owns compensation records.
- Payroll owns payroll records.
- Payslip owns payslip records.

Whether Monetary Representation requires its own persisted mechanism remains unresolved.

---

# 15. Currency

## Ownership

Decision:

Currency handling mechanism belongs to Monetary Representation.

Business owns:

- whether currencies are required
- supported currencies
- organizational currency policy

---

## Business Decision

Closed:

- Currency is part of monetary meaning.
- Every monetary value has exactly one currency.

Open:

- supported currency list
- currency configuration policy

---

# 16. Deferred Decisions

Remaining decisions:

## Architecture

- Concrete monetary representation mechanism.
- Final capability shape.
- Whether implementation uses type, convention, or another mechanism.

## Business

- Precision value.
- Rounding rule.
- Supported currencies.
- Currency configuration policy.
- Display conventions.

## Integration

- Consumer-specific adoption path.

---

# 17. Rejected Alternatives

## Compensation owns monetary representation

Rejected.

Would mix reusable mechanism with business meaning.

---

## Payroll Calculation owns monetary representation

Rejected.

Would mix representation with computation.

---

## Payslip owns monetary representation

Rejected.

Would make a consumer responsible for a shared mechanism.

---

## Decide concrete numeric type now

Rejected.

No implementation mechanism is selected by this decision.

---

# 18. Recommendation

```
Architecture Gap Analysis may continue.
```

The capability boundary is now clearer than Round 1.

Ownership questions are substantially reduced.

Remaining decisions are limited to:

- implementation mechanism
- business policy values
- consumer adoption details

---

# References

- discovery.md
- domain-model-discovery.md
- architecture-gap-analysis.md
- architecture-review.md
- capability-boundary-analysis.md
- decision-round-2.md
- business-domain-definition.md
- final-governance-summary.md
