# Monetary Representation — Implementation Task Breakdown

**Capability:** Monetary Representation

**Status:** Ready for Implementation

**Owner:** EOP Architecture Governance

**Depends On:**

- `architecture-decision.md`
- `business-decision.md`
- `implementation-readiness-review.md`
- `implementation-design.md`

---

# 1. Purpose

This document breaks down the implementation work required to introduce Monetary Representation according to the approved architecture and design.

The objective is to provide an execution sequence that preserves:

- architecture boundaries
- capability ownership
- consumer responsibility
- incremental adoption strategy

This document does not introduce new decisions.

---

# 2. Implementation Objective

Implement Monetary Representation as:

Shared Domain Type Extension

owned by:

Architecture Foundation

The implementation provides a reusable monetary representation mechanism consumed by:

- Compensation
- Payroll Calculation
- Payslip
- Future monetary capabilities

---

# 3. Implementation Principles

## 3.1 Foundation First

The monetary type must exist before consumer migration begins.

Order:

Foundation Type
↓
Consumer Adoption

---

## 3.2 No Business Logic

Implementation must not contain:

- salary rules
- payroll rules
- compensation policy
- accounting policy

---

## 3.3 No Persistence Ownership

Implementation must not create:

- monetary table
- monetary repository
- monetary migration

---

## 3.4 Policy Neutrality

The implementation must not hardcode:

- precision policy
- rounding policy
- currency policy

unless explicitly provided through approved business configuration.

---

# 4. Implementation Phases

---

# Phase 1 — Foundation Module Creation

## Objective

Create the Monetary Representation foundation module.

---

## Tasks

Create:

foundation/
    monetary/

Structure:

monetary/
type

validation

serialization

tests

---

## Deliverables

- monetary type definition
- public interface
- internal validation boundary
- serialization boundary

---

## Acceptance Criteria

- module exists in Architecture Foundation layer
- no dependency on business capabilities
- no dependency on Compensation
- no dependency on Payroll
- no dependency on Payslip

---

# Phase 2 — Monetary Type Implementation

## Objective

Implement the shared monetary abstraction.

---

## Tasks

Implement:

- value representation
- object lifecycle
- internal consistency rules
- immutable behavior if required by framework convention

---

## Must Support

- monetary amount representation
- currency context when applicable
- serialization contract

---

## Must Not Support

- salary
- payment workflow
- payroll calculation

---

## Acceptance Criteria

- type can be consumed independently
- type has no business capability dependency

---

# Phase 3 — Validation Implementation

## Objective

Implement representation-level validation.

---

## Tasks

Define validation for:

- invalid monetary state
- invalid internal representation
- invalid serialization state

---

## Ownership Boundary

Foundation validates:

Is this a valid monetary representation?

Consumers validate:

Is this business value allowed?

---

## Acceptance Criteria

Validation does not contain:

- compensation rules
- payroll rules
- accounting rules

---

# Phase 4 — Serialization Implementation

## Objective

Implement the monetary serialization boundary.

---

## Tasks

Define:

- serialization contract
- deserialization behavior
- compatibility expectations

---

## Requirements

Serialization must preserve:

- monetary meaning
- representation consistency
- currency context when applicable

---

## Acceptance Criteria

Consumers do not manually serialize monetary values.

---

# Phase 5 — Foundation Testing

## Objective

Ensure Monetary Representation behavior is stable before adoption.

---

## Unit Tests

Required coverage:

### Creation

Test:

- valid monetary value creation
- invalid monetary value rejection

---

### Representation

Test:

- internal consistency
- supported states

---

### Serialization

Test:

- serialize behavior
- deserialize behavior
- compatibility expectations

---

### Policy Boundary

Test:

- no embedded business policy

---

## Acceptance Criteria

Foundation tests pass independently.

---

# Phase 6 — Compensation Integration

## Objective

Introduce Monetary Representation into Compensation.

---

## Tasks

Replace direct monetary representation usage with:

Monetary Type

---

## Compensation Retains Ownership

Compensation continues owning:

- compensation lifecycle
- salary meaning
- compensation policy

---

## Acceptance Criteria

No Compensation business rule moves into Monetary Representation.

---

# Phase 7 — Payroll Integration

## Objective

Introduce Monetary Representation into Payroll Calculation.

---

## Tasks

Replace monetary value handling with:

Monetary Type

---

## Payroll Retains Ownership

Payroll continues owning:

- calculation formulas
- payroll rules
- calculation workflow

---

## Acceptance Criteria

Payroll behavior remains unchanged.

---

# Phase 8 — Payslip Integration

## Objective

Introduce Monetary Representation into Payslip.

---

## Tasks

Replace monetary output representation with:

Monetary Type

---

## Payslip Retains Ownership

Payslip continues owning:

- payment record meaning
- presentation responsibility

---

## Acceptance Criteria

Payslip consumers receive compatible monetary representation.

---

# 5. Testing Strategy

## Foundation Tests

Required:

- unit tests
- validation tests
- serialization tests

---

## Integration Tests

Required:

### Compensation

Verify:

- monetary values work correctly
- existing behavior preserved

---

### Payroll

Verify:

- calculations unchanged
- output representation correct

---

### Payslip

Verify:

- monetary output compatibility

---

# 6. Migration Strategy

## Database

No migration required.

Reason:

Monetary Representation has no persistence ownership.

---

## Application Migration

Consumer-by-consumer adoption:

Foundation
↓
Compensation
↓
Payroll
↓
Payslip

---

# 7. File Change Strategy

## New Files

Expected:

foundation/monetary/*

---

## Modified Files

Expected:

Consumer modules only where monetary fields are migrated.

Examples:

Compensation
Payroll
Payslip

---

## Forbidden Changes

Do not modify:

- unrelated HR modules
- unrelated capabilities
- architecture conventions

---

# 8. Dependency Order

Implementation dependency graph:

Monetary Foundation
    ↓
Monetary Type
    ↓
Validation
    ↓
Serialization
    ↓
Foundation Tests
    ↓
Consumer Migration

---

# 9. Acceptance Criteria

Implementation is accepted when:

## Architecture

- Monetary Representation exists as shared domain type
- no independent persistence exists
- no business workflow exists

---

## Boundary

- Compensation owns compensation meaning
- Payroll owns calculation meaning
- Payslip owns payment meaning

---

## Quality

- tests pass
- serialization contract works
- consumers migrate successfully

---

# 10. Risks and Mitigation

## Risk: Business Policy Leakage

Mitigation:

Keep precision, rounding, and currency policy external.

---

## Risk: Consumer Divergence

Mitigation:

Require all monetary handling through the shared type.

---

## Risk: Compatibility Issues

Mitigation:

Perform consumer migration incrementally.

---

# 11. Implementation Sequence Summary

Create Monetary Foundation Module
 ↓

Implement Monetary Type
 ↓

Implement Validation
 ↓

Implement Serialization
 ↓

Add Foundation Tests
 ↓

Integrate Compensation
 ↓

Integrate Payroll
 ↓

Integrate Payslip
 ↓

Final Architecture Review


---

# 12. Final Status

READY FOR IMPLEMENTATION

The implementation scope, ownership boundaries, dependencies, and acceptance criteria are defined.

Implementation may begin following this sequence.

---

# References

- `architecture-decision.md`
- `business-decision.md`
- `implementation-readiness-review.md`
- `implementation-design.md`
- `final-governance-summary.md`
