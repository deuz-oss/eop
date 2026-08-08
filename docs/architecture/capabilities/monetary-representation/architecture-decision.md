# Monetary Representation — Architecture Decision

**Capability:** Monetary Representation

**Status:** Approved

**Decision Type:** Architecture Decision

**Owner:** EOP Architecture Governance

---

# 1. Purpose

This document records the architecture decisions required to complete the remaining architecture gaps identified in:

- `architecture-gap-analysis.md`
- `architecture-review.md`
- `implementation-plan.md`
- `final-governance-summary.md`

The decisions in this document define the architectural form of Monetary Representation.

This document does not define:

- monetary business rules
- compensation rules
- payroll calculation rules
- financial policies
- precision value
- rounding rule
- supported currencies

Those remain Business Decisions.

---

# 2. Context

Monetary Representation is a shared capability consumed by multiple business capabilities:

- Compensation
- Payroll Calculation
- Payslip
- Future monetary-consuming capabilities

The governance process established that Monetary Representation owns:

- representation mechanism
- precision convention
- scale convention
- serialization convention

Consumers own:

- business meaning
- lifecycle
- policy
- calculation

The remaining architecture question was:

> What architectural form should Monetary Representation take?

---

# 3. Decision Drivers

The architecture decision is evaluated against:

## 3.1 Reusability

The mechanism must be usable by multiple capabilities.

---

## 3.2 Business Boundary Protection

The implementation must not absorb:

- salary concepts
- payroll concepts
- accounting concepts

---

## 3.3 No Independent Lifecycle

The representation must not create an artificial business entity.

---

## 3.4 Consistent Representation

All consumers should represent monetary values consistently.

---

## 3.5 Consumer Ownership Preservation

Consumers must remain owners of their own business data.

---

# 4. Considered Options

## Option 1 — Aggregate Root

Status:

Rejected

Reason:

Monetary Representation has:

- no independent lifecycle
- no business identity
- no business workflow
- no independent ownership boundary

It is not a business aggregate.

---

## Option 2 — Domain Service

Status:

Rejected

Reason:

Monetary Representation does not orchestrate business operations.

It does not:

- execute workflows
- coordinate aggregates
- apply business policies

---

## Option 3 — Persisted Value Entity

Status:

Rejected

Reason:

Persistence ownership belongs to consuming capabilities.

Examples:

Compensation
Payroll
Payslip

own their own persisted business records.

---

## Option 4 — Shared Infrastructure Component

Status:

Rejected as primary classification

Reason:

Although Monetary Representation is shared, it is not only technical infrastructure.

It represents a domain concept:

> monetary value representation

The concept is reusable, but its responsibility is more specific than generic infrastructure.

---

## Option 5 — Utility Module

Status:

Rejected

Reason:

Utility modules typically provide generic helpers.

Monetary Representation has defined semantic responsibility.

It is not a collection of unrelated helpers.

---

## Option 6 — Type System Extension

Status:

Selected

---

# 5. Final Architecture Decision

## Decision

Monetary Representation will be implemented as a:

Type System Extension

---

# 6. Rationale

A monetary value has characteristics of a reusable semantic type:

- represents a specific concept
- has consistent behavior
- is consumed by multiple capabilities
- does not own business lifecycle
- does not require persistence ownership

The architecture should provide a shared representation abstraction rather than a business object.

---

# 7. Architectural Shape

The capability provides:

Monetary Representation Type


The type represents:

- monetary amount
- optional currency context when required
- representation rules

The type does not represent:

- salary
- payment
- compensation
- accounting transaction

---

# 8. Implementation Mechanism

## Decision

Implementation will use:

Shared Domain Type

provided through the architecture foundation layer.

---

## Ownership

The type belongs to:

Architecture Foundation

Consumers depend on it.

Example:

Compensation
        ↓
Monetary Representation Type
Payroll Calculation
        ↓
Monetary Representation Type
Payslip
        ↓
Monetary Representation Type

---

# 9. Persistence Decision

## Decision

Monetary Representation has:

No independent persistence

---

## Reason

The value belongs inside the lifecycle of the consuming capability.

Examples:

Compensation record:

employee compensation
        |
        + monetary values

Payroll record:

pay calculation result
        |
        + monetary values

Payslip:

payment record
        |
        + monetary values

---

# 10. Serialization Decision

## Decision

Serialization responsibility belongs to the Monetary Representation type.

The serialization contract will be defined as part of the type boundary.

---

## Constraint

Serialization must preserve:

- monetary value meaning
- precision behavior
- currency context when applicable

---

## Not Allowed

Consumers must not create their own monetary serialization formats independently.

---

# 11. Precision and Scale Relationship

## Decision

Precision and scale remain configuration/business inputs applied through the monetary representation mechanism.

The architecture provides the place where these rules are enforced.

The architecture does not decide:

- decimal places
- scale value

---

# 12. Rounding Relationship

## Decision

The type may provide consistent rounding capability.

However:

The rounding rule remains Business-owned.

Example:

Architecture owns:

apply rounding consistently

Business owns:

which rounding rule applies

---

# 13. Currency Relationship

## Decision

Currency handling is supported by the representation mechanism.

The architecture provides the ability to associate currency information.

Business decides:

- supported currencies
- operational policy

---

# 14. Consumer Impact

## Compensation

Before:

Compensation owns monetary fields directly

After:

Compensation owns compensation meaning.
Monetary values use Monetary Representation Type.

---

## Payroll Calculation

Before:

Payroll owns calculation outputs.

After:


Payroll owns calculation logic.
Monetary values use Monetary Representation Type.

---

## Payslip

Before:


Payslip owns payment representation.

After:


Payslip owns payment record.
Monetary values use Monetary Representation Type.

---

# 15. Consequences

## Positive Consequences

- consistent monetary representation
- reduced duplication
- clear ownership boundary
- reusable across capabilities
- no artificial aggregate introduced

---

## Negative Consequences

- requires all consumers to adopt the shared type
- requires migration from primitive monetary fields where applicable
- requires careful API compatibility handling

---

# 16. Remaining Business Decisions

Architecture decision does not close:

## Precision

Need:

- decimal precision value

Owner:

Business

---

## Rounding

Need:

- rounding policy

Owner:

Business

---

## Currency Policy

Need:

- supported currencies
- operational currency rules

Owner:

Business

---

# 17. Implementation Constraints

Implementation must follow:

- no Monetary Representation table
- no Monetary Representation aggregate
- no business workflows
- no compensation rules
- no payroll rules
- no accounting rules

---

# 18. Final Decision

APPROVED

Monetary Representation is a shared domain type extension owned by Architecture Foundation.

It provides reusable monetary representation behavior without owning business lifecycle, persistence, or financial policy.

---

# References

- discovery.md
- domain-model-discovery.md
- decision.md
- decision-round-2.md
- business-domain-definition.md
- architecture-gap-analysis.md
- architecture-review.md
- implementation-plan.md
- final-governance-summary.md
