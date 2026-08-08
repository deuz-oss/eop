# Monetary Representation — Business Decision Request

**Status:** Approved

**Capability:** Monetary Representation

**Decision Owner:** EOP System Owner

**Prepared by:** EOP Architecture Governance

**Approval Date:** 2026-08-07

---

# Purpose

This document records the approved business policy decisions required for implementation of the Monetary Representation capability.

The decisions recorded here represent the current EOP business policy baseline.

These decisions establish the business rules consumed by architecture and implementation.

They do not change:

- capability ownership
- architecture placement
- responsibility boundaries

---

# Decision Summary

| Decision Area       | Approved Decision                      |
| ------------------- | -------------------------------------- |
| Precision Model     | Fixed system precision                 |
| Precision Value     | 2 decimal places                       |
| Rounding Boundary   | Final business calculation boundary    |
| Rounding Rule       | Half Up                                |
| Currency Context    | Mandatory                              |
| Currency Scope      | Single currency initially              |
| Future Direction    | Multi-currency extensibility preserved |
| Currency Conversion | Out of scope                           |

---

# 1. Precision Policy

## Decision

The system uses a fixed system-wide precision model for monetary values.

All capabilities consuming monetary values must follow the same precision policy.

Individual capabilities must not define their own precision independently.

---

## Approved Precision Value

2 decimal places

---

## Rationale

A fixed precision policy provides:

- consistent monetary behavior
- predictable calculations
- centralized governance
- avoidance of capability-specific monetary rules

The current EOP scope does not require currency-dependent precision behavior.

Future changes require a new business decision.

---

## Ownership

Business policy ownership:

EOP System Owner

Implementation ownership:

Monetary Representation capability

---

# 2. Rounding Policy

## Decision

Rounding occurs at the final business calculation boundary.

Intermediate calculations should preserve available precision until the final monetary result is determined.

---

## Approved Rounding Rule

Half Up

---

## Rationale

Rounding affects business and financial outcomes.

Applying rounding only at the final result boundary reduces:

- cumulative rounding differences
- inconsistent intermediate results
- capability-specific calculation behavior

---

## Ownership

Business policy ownership:

EOP System Owner

Implementation ownership:

Business calculation capabilities apply the policy.
Monetary Representation supports the representation.

---

# 3. Currency Policy

## Decision

Currency context is mandatory for monetary values.

A monetary value must not lose its currency meaning.

---

## Currency Scope

Approved:

Single currency operation initially

---

## Future Direction

The architecture must preserve the possibility of future multi-currency support.

Future expansion requires additional business decisions.

---

## Currency Conversion

Approved:

Out of scope

This capability does not include:

- exchange rate management
- currency conversion
- FX calculation

---

## Rationale

The current EOP scope requires explicit monetary context but does not require multi-currency processing.

---

## Ownership

Business policy ownership:

EOP System Owner

Implementation ownership:

Monetary Representation preserves currency context only.

---

# Impact on Architecture

No architecture change is required.

Existing architecture decision remains:

Monetary Representation
Type System Extension

The capability remains responsible for:

- monetary representation contract
- representation consistency
- approved monetary constraints

The capability does not own:

- compensation policy
- payroll calculation
- accounting workflow
- currency conversion

---

# Implementation Authorization

The required business decisions are now recorded.

| Gate                | Status   |
| ------------------- | -------- |
| Precision ownership | Complete |
| Precision value     | Complete |
| Rounding ownership  | Complete |
| Rounding rule       | Complete |
| Currency ownership  | Complete |
| Currency scope      | Complete |

---

# Final Decision Status

APPROVED

Implementation readiness may proceed after dependent governance documents are synchronized with this decision record.

---

# Approval Record

Decision Owner:

EOP System Owner

Approval Date:

2026-08-07

Decision Status:

Approved

Comments:

Approved as current EOP monetary policy baseline.
Future changes require a new business decision review.
