# Monetary Representation — Implementation Design

**Capability:** Monetary Representation

**Status:** Design Complete — Ready for Implementation

**Owner:** EOP Architecture Governance

**Depends On:**

- `architecture-decision.md`
- `business-decision.md`
- `implementation-readiness-review.md`

---

# 1. Purpose

This document defines the technical implementation design for Monetary Representation after completion of:

- Governance decisions
- Architecture decisions
- Business boundary decisions
- Implementation readiness review

This document translates approved architecture into implementation structure.

It does not introduce new business policy.

It does not decide:

- precision value
- rounding rule
- currency policy

Those remain Business-owned inputs.

---

# 2. Architecture Summary

## Final Architecture Decision

Monetary Representation is implemented as:

Shared Domain Type Extension

Owned by:

Architecture Foundation

---

## Responsibility

Monetary Representation provides:

- monetary value abstraction
- consistent representation behavior
- common validation boundary
- serialization contract

---

## It Does Not Provide

- salary rules
- payroll calculation
- payment workflow
- accounting policy
- compensation lifecycle

---

# 3. Design Goals

The implementation must provide:

## 3.1 Consistent Representation

All monetary consumers use the same representation abstraction.

---

## 3.2 Explicit Boundary

The type must clearly separate:

Monetary value representation

from:

Business meaning

---

## 3.3 Consumer Independence

Consumers should not need to understand internal implementation details.

---

## 3.4 Future Policy Adaptation

Business decisions such as:

- precision
- rounding
- currency

must be configurable without changing consumer ownership.

---

# 4. Proposed Module Placement

## Location

Monetary Representation belongs to:

Architecture Foundation Layer

Suggested structure:

foundation/
monetary/

    type
    validation
    serialization

---

# 5. Public Contract

The public contract exposes a monetary abstraction.

Conceptually:

MonetaryValue

---

## Responsibilities

The type is responsible for:

- holding monetary amount
- enforcing representation rules
- exposing serialization behavior
- preserving currency context when applicable

---

## The Type Must Not Know

The type must not know:

- Employee
- Compensation
- Payroll
- Payslip
- Salary Component

---

# 6. Internal Design Boundary

## Consumer Layer

Examples:

Compensation
Payroll
Payslip

uses:

MonetaryValue

---

## Foundation Layer

Provides:

MonetaryValue
        |
        + validation
        |
        + serialization
        |
        + representation behavior

---

# 7. Validation Design

## Ownership

Validation belongs to Monetary Representation.

---

## Validation Categories

## Representation Validation

Owned by:

Monetary Representation

Examples:

- invalid monetary state
- invalid representation format
- invalid internal structure

---

## Business Validation

Owned by consumers.

Examples:

Compensation:

- salary constraints

Payroll:

- calculation rules

---

# 8. Precision Design

## Architecture Responsibility

Provide a place for precision enforcement.

---

## Business Responsibility

Define:

- precision value
- scale value

---

## Constraint

Implementation must avoid embedding business assumptions.

---

# 9. Rounding Design

## Architecture Responsibility

Provide consistent rounding mechanism.

---

## Business Responsibility

Define:

- rounding policy
- rounding mode
- rounding timing

---

## Constraint

No consumer-specific rounding logic.

---

# 10. Currency Design

## Architecture Responsibility

Support currency representation when required.

---

## Business Responsibility

Define:

- supported currencies
- currency policy
- operational requirements

---

## Constraint

Do not introduce currency conversion.

---

# 11. Serialization Design

## Ownership

Serialization belongs to Monetary Representation.

---

## Goal

Consumers should not manually transform monetary values.

---

## Design Principle

Serialization should preserve:

- amount meaning
- precision behavior
- currency context when applicable

---

# 12. Persistence Design

## Decision

No dedicated persistence.

---

## Ownership

Consumers persist their own data.

Example:

Compensation table
monetary values


Payroll table
monetary values


Payslip table
monetary values

---

# 13. Integration Design

## Compensation

Integration:

Compensation
        |
        ↓
MonetaryValue

Compensation owns:

- compensation lifecycle
- salary semantics

---

## Payroll

Integration:

Payroll
        |
        ↓
MonetaryValue

Payroll owns:

- calculation logic

---

## Payslip

Integration:

Payslip
        |
        ↓
MonetaryValue

Payslip owns:

- payment record meaning

---

# 14. Testing Design

## Unit Tests

Required:

- create valid monetary value
- reject invalid representation
- serialization behavior
- precision handling behavior
- currency handling behavior when enabled

---

## Consumer Tests

Required:

## Compensation

Verify:

- monetary values accepted
- business rules remain unchanged

---

## Payroll

Verify:

- calculations remain unchanged
- representation integration works

---

## Payslip

Verify:

- monetary output remains compatible

---

# 15. Migration Design

## Initial Adoption

No database migration.

Reason:

Monetary Representation has no persistence ownership.

---

## Consumer Migration

Consumers migrate independently.

Example:

Compensation
        ↓
replace primitive monetary fields
Payroll
        ↓
replace primitive monetary fields
Payslip
        ↓
replace primitive monetary fields

---

# 16. API Compatibility

## External API

The serialization contract must be defined before breaking changes.

---

## Constraint

Existing API consumers must not be broken unintentionally.

---

# 17. Implementation Sequence

## Step 1

Create foundation monetary module.

---

## Step 2

Implement monetary type.

---

## Step 3

Implement validation boundary.

---

## Step 4

Implement serialization contract.

---

## Step 5

Add unit tests.

---

## Step 6

Integrate consumers incrementally.

Order:

Compensation
↓
Payroll
↓
Payslip

---

# 18. Out of Scope

This implementation does not include:

- Compensation module redesign
- Payroll redesign
- Accounting engine
- Currency conversion
- Tax calculation
- Financial reporting
- Approval workflow

---

# 19. Implementation Constraints

Mandatory:

- no monetary aggregate
- no monetary table
- no monetary repository
- no business workflow
- no consumer-specific monetary implementation

---

# 20. Final Design Decision

APPROVED

Monetary Representation will be implemented as a shared domain type extension in the Architecture Foundation layer.

The implementation provides a reusable monetary representation mechanism while preserving ownership boundaries of consuming capabilities.

---

# References

- `architecture-decision.md`
- `business-decision.md`
- `implementation-readiness-review.md`
- `final-governance-summary.md`
- `implementation-plan.md`
