# Monetary Representation — Implementation Plan

**Capability:** Monetary Representation

**Status:** Planning Complete — Implementation Blocked by Remaining Decisions

**Owner:** EOP Architecture Governance

---

# 1. Purpose

This document defines the implementation plan for the Monetary Representation capability after completion of:

- Repository Governance
- Business Domain Definition
- Decision Round 2
- Capability Decision
- Architecture Gap Analysis
- Architecture Review

This document translates approved governance outcomes into implementation preparation.

It does not introduce new architecture decisions.

It does not select implementation technology where governance is still open.

---

# 2. Implementation Readiness

## Current Status

NOT READY FOR IMPLEMENTATION

Reason:

Several required decisions remain incomplete.

Implementation must not begin until the following are resolved:

Architecture:

- final representation shape
- implementation mechanism
- serialization approach
- persistence requirement (if any)

Business:

- precision value
- rounding rule
- currency policy

---

# 3. Capability Objective

Monetary Representation will provide a consistent mechanism for representing monetary values across business capabilities.

Primary consumers:

- Compensation
- Payroll Calculation
- Payslip
- Future monetary-consuming capabilities

The capability provides representation consistency.

It does not provide business calculation.

---

# 4. Implementation Principles

## 4.1 Separation of Responsibility

Implementation must preserve:

Monetary Representation
        |
        | owns
        ↓
representation mechanism

Consumers own:

business meaning
calculation rules
policy
workflow
lifecycle

---

## 4.2 No Business Logic Leakage

The implementation must not contain:

- salary rules
- payroll formulas
- tax rules
- allowance rules
- deduction rules
- accounting policy

---

## 4.3 No Consumer Ownership Leakage

The implementation must not make Monetary Representation responsible for:

- Compensation lifecycle
- Payroll lifecycle
- Payslip lifecycle
- employee relationships

---

# 5. Implementation Phases

## Phase 1 — Complete Remaining Decisions

Status:

BLOCKED

Required outputs:

### Architecture Decisions

Resolve:

- representation shape
- implementation location
- reusable mechanism
- serialization convention

Possible outcomes:

- shared type
- library component
- utility component
- another approved architecture pattern

No option is selected yet.

---

### Business Decisions

Resolve:

## Precision

Define:

- decimal requirements
- fractional unit behavior
- organizational standard

---

## Rounding

Define:

- rounding rule
- rounding timing
- policy requirements

---

## Currency

Define:

- supported currencies
- operational currency policy
- configuration approach

---

# 6. Phase 2 — Architecture Design

Status:

PENDING

After Phase 1 completion:

Define:

- package/module location
- public interface
- internal structure
- validation responsibility
- serialization boundary
- integration contract

---

# 7. Phase 3 — Implementation

Status:

PENDING

Implementation scope:

## Core Capability

Implement:

- monetary representation mechanism
- approved precision behavior
- approved currency handling
- approved serialization behavior

---

## Consumer Integration

Integrate with:

### Compensation

Compensation consumes monetary representation.

Compensation remains responsible for:

- salary meaning
- compensation lifecycle
- compensation business rules

---

### Payroll Calculation

Payroll consumes monetary representation.

Payroll remains responsible for:

- calculations
- formulas
- payroll policies

---

### Payslip

Payslip consumes monetary representation.

Payslip remains responsible for:

- payment record meaning
- historical payment representation

---

# 8. Testing Plan

Testing begins after architecture decisions are complete.

## Unit Tests

Validate:

- monetary value creation
- precision behavior
- currency handling
- serialization behavior
- invalid states

---

## Integration Tests

Validate:

- Compensation integration
- Payroll integration
- Payslip integration

---

## Regression Tests

Ensure:

- existing monetary fields remain compatible
- existing capabilities are not affected

---

# 9. Migration Strategy

Migration strategy depends on final representation shape.

Possible scenarios:

## No Persistence

No database migration required.

---

## Consumer-Owned Persistence

Consumers migrate their own monetary fields.

Example:

Compensation
Payroll
Payslip

remain owners of their tables.

---

## Dedicated Persistence

Requires separate architecture decision.

Not assumed.

---

# 10. Out of Scope

This implementation does not include:

- salary management
- compensation calculation
- payroll calculation
- tax calculation
- accounting engine
- exchange-rate service
- currency conversion
- financial reporting
- approval workflow
- employee compensation lifecycle

---

# 11. Risks

## Architecture Shape Risk

Current representation shape remains unresolved.

Impact:

Implementation cannot start safely.

---

## Business Policy Risk

Precision, rounding, and currency policy are unresolved.

Impact:

Incorrect assumptions may create incompatible behavior.

---

## Consumer Integration Risk

Consumers may require different monetary behaviors.

Mitigation:

Maintain strict ownership boundaries.

---

# 12. Required Decisions Before Coding

Implementation may start only after:

| Decision | Owner | Status |
|---|---|---|
| Representation shape | Architecture | Open |
| Implementation mechanism | Architecture | Open |
| Serialization convention | Architecture | Open |
| Persistence requirement | Architecture | Open |
| Precision value | Business | Open |
| Rounding rule | Business | Open |
| Currency policy | Business | Open |

---

# 13. Final Recommendation

Do not begin implementation yet.

Complete:

1. Remaining architecture decisions.
2. Remaining business decisions.

After completion:

Implementation Plan
        ↓
Architecture Approval
        ↓
Implementation

The governance chain is complete enough to define implementation scope, but not enough to safely write production code.

---

# References

- discovery.md
- domain-model-discovery.md
- decision.md
- decision-round-2.md
- business-domain-definition.md
- architecture-gap-analysis.md
- architecture-review.md
- capability-boundary-analysis.md
