# Monetary Representation — Architecture Gap Analysis

**Capability:** Monetary Representation

**Status:** Updated after Decision Round 2 and Business Domain Definition

**Owner:** EOP Architecture Governance

---

# 1. Purpose

This document identifies remaining architecture gaps after:

- repository discovery
- domain model discovery
- capability boundary analysis
- architecture review
- Decision Round 2
- Business Domain Definition

The purpose is not to reopen previous decisions.

This document answers:

- Which questions are now resolved?
- Which questions remain unknown?
- Which unknowns are architecture-owned?
- Which unknowns belong to business?
- Which unknowns belong to infrastructure?

No implementation design is introduced here.

No concrete technology choice is introduced.

---

# 2. Capability Boundary Summary

Monetary Representation is responsible for:

- monetary value representation mechanism
- representation consistency
- precision convention
- scale convention
- serialization convention (ownership)

Monetary Representation is not responsible for:

- compensation meaning
- payroll calculation
- salary policy
- accounting policy
- rounding business policy
- currency policy
- display formatting

The capability remains a reusable representation mechanism consumed by other capabilities.

---

# 3. Resolved Decisions

## 3.1 Precision Ownership

**Status:** Resolved

Owner:

Monetary Representation

Reason:

Precision determines how monetary values are represented.

The capability owns the convention.

The actual precision value remains a Business Decision.

---

## 3.2 Scale Ownership

**Status:** Resolved

Owner:

Monetary Representation

Reason:

Scale is part of monetary precision representation.

No separate ownership boundary exists.

The concrete scale value remains undecided.

---

## 3.3 Rounding Ownership

**Status:** Resolved as split ownership

Mechanism:

Monetary Representation

Policy:

Business

Reason:

The capability owns consistent application of rounding.

Business owns the rule itself.

Examples:

- rounding direction
- financial convention
- regulatory requirements

---

## 3.4 Formatting Ownership

**Status:** Resolved

Owner:

Outside Monetary Representation

Reason:

Formatting depends on:

- locale
- presentation
- product requirements

Formatting is not part of monetary representation.

---

## 3.5 Serialization Ownership

**Status:** Resolved conditionally

Owner:

Monetary Representation

Reason:

Serialization describes how the representation mechanism is exposed.

Remaining:

The actual serialization convention remains undecided.

---

## 3.6 Persistence Ownership

**Status:** Resolved as split ownership

Consumer capabilities own persisted business data.

Examples:

Compensation → compensation records
Payroll → payroll records
Payslip → payslip records

Monetary Representation does not own consumer persistence.

Remaining:

Whether Monetary Representation requires its own persisted artifact remains an architecture question.

---

## 3.7 Currency Ownership

**Status:** Partially resolved

Resolved:

Currency representation mechanism belongs to:

Monetary Representation

Business owns:

- supported currencies
- currency policy
- whether multi-currency is enabled operationally

Remaining:

- supported currency list
- currency configuration model

---

# 4. Remaining Architecture Gaps

## 4.1 Monetary Representation Shape

Status:

OPEN

Candidates remain:

- Shared Infrastructure
- Library
- Utility
- Type System Extension

Previously rejected:

- Aggregate Root
- Domain Service
- Independent Value Object persistence model

Reason unresolved:

Repository evidence does not distinguish between the remaining implementation shapes.

This requires an architecture decision.

---

## 4.2 Concrete Representation Mechanism

Status:

OPEN

Questions:

- Is representation provided as a reusable type?
- Is it a convention?
- Is it a framework extension?
- Is it a shared package?

No implementation mechanism is selected.

---

## 4.3 Serialization Convention

Status:

OPEN

Ownership is decided.

Format is not.

Remaining questions:

- primitive representation
- structured representation
- API transport representation

This requires architecture decision.

---

## 4.4 Persistence Strategy

Status:

OPEN

Resolved:

Consumers own their persisted business data.

Unknown:

Whether Monetary Representation requires:

- no persistence
- supporting metadata persistence
- another persistence mechanism

This depends on final architecture shape.

---

# 5. Remaining Business Gaps

## 5.1 Precision Value

Status:

OPEN

Questions:

- decimal places
- fractional unit requirements
- organizational standard

Owner:

Business

---

## 5.2 Rounding Rule

Status:

OPEN

Questions:

- rounding direction
- rounding timing
- regulatory requirements

Owner:

Business

---

## 5.3 Currency Policy

Status:

OPEN

Questions:

- supported currencies
- single or multi-currency operational configuration
- reporting currency requirements

Owner:

Business

---

## 5.4 Formatting Requirements

Status:

OPEN

Questions:

- display symbol
- locale formatting
- user-facing representation

Owner:

Business/Product

---

# 6. Infrastructure Gaps

No Monetary Representation-specific infrastructure gap has been resolved by repository evidence.

Potential infrastructure requirements depend on future architecture decisions:

- reusable package support
- shared type location
- serialization utilities
- validation helpers

These cannot be decided before representation shape is chosen.

---

# 7. Consumer Impact

## Compensation

Depends on:

- monetary representation mechanism
- precision value
- currency policy

Compensation owns:

- salary meaning
- compensation lifecycle

---

## Payroll Calculation

Depends on:

- monetary representation
- rounding rule

Payroll owns:

- calculation logic

---

## Payslip

Depends on:

- serialization convention
- display requirements

Payslip owns:

- payment record meaning

---

# 8. Deferred Decisions Consolidation

Previous deferred decisions are classified:

| Decision | Status | Owner |
|---|---|---|
| Monetary representation mechanism | Open | Architecture |
| Capability implementation shape | Open | Architecture |
| Precision convention ownership | Closed | Monetary Representation |
| Precision value | Open | Business |
| Scale ownership | Closed | Monetary Representation |
| Rounding mechanism ownership | Closed | Monetary Representation |
| Rounding rule | Open | Business |
| Formatting ownership | Closed | Outside capability |
| Serialization ownership | Closed | Monetary Representation |
| Serialization format | Open | Architecture |
| Currency mechanism ownership | Closed | Monetary Representation |
| Supported currencies | Open | Business |
| Persistence ownership | Closed as split | Architecture |

---

# 9. Architecture Assessment

Repository evidence has been exhausted.

Remaining architecture questions are not caused by missing repository information.

They are design choices between valid patterns.

Additional discovery is unlikely to reduce these gaps.

The next required activity is architecture decision, not more repository investigation.

---

# 10. Recommendation

Status:

Waiting for Architecture Decisions and Business Decisions

Recommended next steps:

1. Decide Monetary Representation implementation shape.
2. Decide concrete serialization convention.
3. Obtain business decisions for:
   - precision value
   - rounding rule
   - currency policy

After those decisions:

- update architecture review
- update implementation plan
- proceed to implementation

---

# References

- discovery.md
- decision.md
- domain-model-discovery.md
- architecture-review.md
- capability-boundary-analysis.md
- decision-round-2.md
- business-domain-definition.md
