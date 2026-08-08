# Monetary Representation — Business Decision

**Status:** Approved

**Capability:** Monetary Representation

**Decision Owner:** EOP System Owner

**Prepared by:** EOP Architecture Governance

**Approval Source:** `business-decision-request.md`

**Approval Date:** 2026-08-07

---

# Purpose

This document records the approved business policy decisions consumed by the Monetary Representation capability.

The purpose of this document is to define business-owned monetary policies required for implementation.

This document does not define:

- architecture placement
- technical implementation details
- domain ownership changes
- consumer capability behavior

The authoritative approval record is maintained in:

business-decision-request.md

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

All capabilities consuming monetary values must follow the approved precision policy.

Individual capabilities must not define their own precision independently.

---

## Approved Precision Value

2 decimal places

---

## Rationale

A fixed precision approach provides:

- consistent monetary representation
- predictable behavior across capabilities
- centralized policy ownership
- reduced risk of capability-specific monetary rules

The current EOP scope does not provide evidence requiring currency-dependent precision.

Future changes to precision policy require a new business decision review.

---

## Ownership

Business ownership:

EOP System Owner

Technical implementation ownership:

Monetary Representation capability

Monetary Representation is responsible for supporting the approved policy.

It is not responsible for deciding the business precision policy.

---

# 2. Rounding Policy

## Decision

Rounding is applied at the final business calculation boundary.

Intermediate calculations should preserve available precision until the final monetary result is determined.

---

## Approved Rounding Rule

Half Up

---

## Calculation Boundary

Approved flow:

Business Calculation
↓
Final Monetary Result
↓
Apply Approved Rounding
↓
Monetary Representation

---

## Not Approved

The following approach is not part of the policy:

Component A → round
Component B → round
Component C → round
Final Total

---

## Rationale

Rounding affects financial outcomes and business meaning.

Keeping rounding at the final calculation boundary reduces:

- cumulative rounding differences
- inconsistent intermediate results
- capability-specific monetary behavior

---

## Ownership

Business owns:

- rounding rule
- rounding timing policy

Business calculation capabilities apply the policy within their calculation boundaries.

Monetary Representation does not own accounting or financial calculation rules.

---

# 3. Currency Policy

## Decision

Currency context is mandatory for monetary values.

A monetary value must preserve its currency meaning.

---

## Currency Requirement

Approved:

Currency context is required.

A monetary value without currency context is considered incomplete.

---

## Current Currency Scope

Approved:

Single currency operation initially

---

## Future Direction

The system should preserve the ability to support future multi-currency requirements.

Future expansion requires additional business decisions covering:

- supported currencies
- currency behavior
- conversion requirements
- operational rules

---

## Currency Conversion

Approved:

Out of scope

This capability does not include:

- exchange rate management
- currency conversion
- FX calculation
- external currency providers

---

## Rationale

The current EOP scope requires explicit monetary context but does not require currency conversion capability.

Keeping conversion outside this capability prevents unnecessary coupling between monetary representation and external financial behavior.

---

## Ownership

Business owns:

- currency policy
- supported currency scope
- future currency expansion decisions

Monetary Representation owns:

- preserving currency context
- representing monetary values consistently

---

# 4. Relationship With Architecture Decision

These business decisions do not modify the approved architecture decision.

Architecture remains:

Monetary Representation
Type System Extension

---

## Monetary Representation Responsibilities

Owns:

- monetary value contract
- monetary representation consistency
- approved precision enforcement mechanism
- currency context preservation

---

## Out of Scope

Monetary Representation does not own:

- Compensation calculation
- Payroll calculation
- Payslip rules
- Accounting workflow
- Exchange rate calculation
- Currency conversion
- Financial reporting rules

---

# 5. Consumer Capability Impact

## Compensation

May consume Monetary Representation.

Must not redefine:

- precision
- currency policy
- rounding policy

---

## Payroll Calculation

Owns:

- payroll calculation logic
- business calculation flow

Consumes:

- approved monetary representation

---

## Payslip

Consumes monetary values for output purposes.

Does not redefine monetary policy.

---

# 6. Implementation Authorization

The following business decisions are resolved:

| Gate                | Status   |
| ------------------- | -------- |
| Precision ownership | Complete |
| Precision value     | Complete |
| Rounding ownership  | Complete |
| Rounding rule       | Complete |
| Currency ownership  | Complete |
| Currency scope      | Complete |

---

# Final Decision

Status:

APPROVED

Implementation may proceed using this document together with:

- `business-decision-request.md`
- `architecture-decision.md`
- `implementation-design.md`
- `implementation-task-breakdown.md`

---

# Approval Record

Decision Owner:

EOP System Owner

Approval Source:

business-decision-request.md

Approval Date:

2026-08-07

Decision Status:

Approved

Comments:

Approved as the current EOP monetary policy baseline.
Future changes to monetary policy require a new business decision review.
