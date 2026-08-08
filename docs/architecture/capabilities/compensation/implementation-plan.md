# Compensation — Implementation Plan

**Status:** Updated after Business Domain Definition and Decision Round 2

**Capability:** Compensation

---

# 1. Purpose

This document determines whether implementation of Compensation is now authorized after completion of:

- Business Domain Definition
- Decision Round 2
- updated Decision
- updated Architecture Gap Analysis
- updated Architecture Review

It does not redesign the capability.

Its purpose is to evaluate implementation readiness against the completed governance chain.

---

# 2. Current Governance Status

Completed

- Discovery
- Decision
- Domain Model Discovery
- Architecture Gap Analysis
- Architecture Review
- Business Domain Definition
- Decision Round 2

Remaining external dependencies:

- Monetary Representation
- Effective Dating

---

# 3. Business Readiness

## Status

Completed

The business domain is now sufficiently defined.

Confirmed:

- Compensation represents agreed monetary employment terms.
- Compensation is an agreement, not a payroll transaction.
- Compensation is independent from Payroll Calculation.
- Compensation is independent from Payslip.
- Compensation changes are business events.
- Compensation owns business meaning only.

Previously unresolved business ownership questions have been closed.

---

# 4. Architecture Readiness

## Status

Partially Complete

The aggregate boundary is stable.

Ownership is stable.

Relationships are stable.

Consumer/provider directions are stable.

Remaining architecture questions concern implementation mechanics rather than business ownership.

---

# 5. Aggregate

## Status

Conditionally Authorized

The repository now contains sufficient governance to construct the Compensation aggregate itself.

However, the aggregate cannot yet expose finalized monetary fields because Monetary Representation remains incomplete.

Authorized:

- Aggregate boundary
- Aggregate responsibility
- Aggregate lifecycle
- Aggregate ownership

Blocked:

- Monetary field implementation

---

# 6. Model

## Status

Partially Authorized

The entity itself can now be designed.

Not yet authorized:

- monetary value type
- currency representation
- precision implementation
- serialization mechanism

Those belong to Monetary Representation.

Likewise,

historical validity fields remain blocked until Effective Dating's architecture is finalized.

---

# 7. Repository

## Status

Conditionally Authorized

CRUD behavior itself is no longer blocked.

Remaining blockers:

- active-at-date lookup
- historical lookup
- temporal uniqueness

These belong to Effective Dating.

Ordinary repository operations are otherwise straightforward.

---

# 8. Service

## Status

Partially Authorized

Business validation can now be implemented for:

- ownership
- relationship validation
- JobGrade interaction
- business scenarios defined by Business Domain Definition

Still blocked:

- monetary validation
- historical replacement behavior
- temporal activation logic

Those belong to external capabilities.

---

# 9. API

## Status

Partially Authorized

API surface is no longer blocked by missing business meaning.

Remaining blocked payload elements:

- monetary representation
- historical activation

Everything else follows the existing repository architecture.

---

# 10. Migration

## Status

Not Yet Authorized

The aggregate exists.

The persistence model does not.

Current blockers:

- monetary columns
- temporal columns
- history representation

Creating tables now would almost certainly require later schema migration.

Implementation should wait.

---

# 11. Tests

## Status

Partially Authorized

Repository tests

Partially Ready

Service tests

Partially Ready

API tests

Partially Ready

Blocked areas:

- monetary precision
- rounding
- currency
- temporal validity
- historical replacement

The remaining business scenarios can already be tested.

---

# 12. Remaining Deferred Decisions

## Monetary Representation

- monetary type
- precision
- rounding
- currency
- serialization

Owner:

Monetary Representation

---

## Effective Dating

- history mechanism
- effective dating
- temporal identity
- active record interpretation

Owner:

Effective Dating

---

## Compensation

- Allowance relationship
- Daily rate persistence
- JobGrade relationship implementation
- authorization policy

These remain Compensation-specific decisions.

---

# 13. Implementation Readiness

| Artifact | Status |
|----------|--------|
| Aggregate | Partial |
| Model | Partial |
| Repository | Partial |
| Service | Partial |
| API | Partial |
| Migration | Blocked |
| Tests | Partial |

---

# 14. Can Iteration 1 Begin?

## No

Unlike the previous governance revision, Business is no longer the blocker.

However, the persistence contract remains incomplete.

Building Compensation today would require inventing:

- monetary representation
- temporal representation

Both belong to external capabilities whose governance has completed but whose implementation contracts do not yet exist.

---

# 15. Remaining Risks

Real risks only.

- Monetary Representation may choose a representation incompatible with an early Compensation schema.
- Effective Dating may require temporal columns incompatible with an early Compensation schema.
- Allowance may later become its own aggregate, changing Compensation relationships.
- Authorization policy remains intentionally undefined.

---

# 16. Final Recommendation

## Waiting for Foundational Capability Implementation

Compensation governance is complete.

Business definition is complete.

Aggregate ownership is complete.

The remaining blockers are implementation dependencies rather than governance uncertainty.

Implementation should begin only after:

1. Monetary Representation establishes its concrete implementation contract.
2. Effective Dating establishes its concrete implementation contract.

At that point Compensation can proceed directly into implementation without further governance.
