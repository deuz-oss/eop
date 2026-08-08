# Compensation — Architecture Gap Analysis

**Status:** Updated after Decision Round 2

**Capability:** Compensation

**Inputs reviewed:**

- `discovery.md`
- `decision.md`
- `domain-model-discovery.md`
- `architecture-gap-analysis.md` (previous)
- `business-domain-definition.md`
- `decision-round-2.md`

---

# 1. Architectural Readiness

## Summary

Compensation has moved from business-definition uncertainty into architecture-definition uncertainty.

The core business meaning is now established:

- Compensation represents employee monetary employment terms.
- Compensation is a consumer of Monetary Representation.
- Compensation requires historical/effective interpretation.
- Payroll Calculation consumes Compensation.
- Payslip does not own Compensation.

However, implementation is still not authorized because the concrete architecture must integrate with two capability-level mechanisms that are not yet available:

- Monetary Representation
- Effective Dating

---

## Readiness Assessment

| Component | Status | Reason |
|---|---|---|
| BaseEntity | Sufficient | Existing entity foundation is available. |
| BaseRepository | Sufficient | Repository abstraction exists. |
| Repository pattern | Sufficient | Existing HR master-data and transactional patterns are reusable. |
| UnitOfWork | Sufficient | Transaction boundary mechanism exists. |
| API layering | Sufficient | Existing Service/API separation is established. |
| Monetary Representation | Insufficient | Ownership is decided, but mechanism/content is not yet available. |
| Effective Dating | Insufficient | Ownership is decided, but architecture is not finalized. |
| Authorization Foundation | Unknown | Compensation authorization policy is not defined. |

---

# 2. Closed Architectural Questions

The following questions are no longer blocking:

| Question | Status |
|---|---|
| What business concept does Compensation represent? | Closed |
| Does Compensation own payroll calculation? | Closed |
| Does Compensation own payslip output? | Closed |
| Does Compensation consume Monetary Representation? | Closed |
| Does Compensation require historical interpretation? | Closed |
| Does Compensation require effective dating? | Closed |
| Does Payroll Calculation consume Compensation? | Closed |

---

# 3. Remaining Architectural Gaps

## 3.1 Monetary Representation Integration

## Classification

Governance Dependency

---

## Current State

Monetary Representation owns:

- monetary mechanism;
- precision rules;
- rounding rules;
- currency handling mechanism;
- serialization approach.

Compensation consumes this capability.

---

## Remaining Unknown

The following are still unresolved:

- concrete monetary type;
- precision;
- rounding convention;
- currency scope.

---

## Impact

Compensation cannot finalize:

- monetary fields;
- database representation;
- API contracts;
- validation rules.

---

# 3.2 Effective Dating Integration

## Classification

Governance Dependency

---

## Current State

Effective Dating owns:

- temporal validity mechanism;
- historical interpretation mechanism.

Compensation owns:

- compensation meaning;
- compensation change reasons;
- compensation business rules.

---

## Remaining Unknown

Effective Dating still requires decisions regarding:

- representation model;
- persistence relationship;
- reusable mechanism shape.

---

## Impact

Compensation cannot finalize:

- history storage model;
- effective date fields;
- replacement semantics.

---

# 3.3 Compensation Aggregate Shape

## Classification

Architecture Gap

---

## Current State

Business boundary is known:

Compensation represents:

- employee compensation terms;
- monetary basis;
- effective validity;
- change context.

---

## Remaining Unknown

The following architectural choices remain:

- single aggregate with embedded compensation values;
- separate related compensation components;
- allowance modeling;
- daily-rate representation.

---

## Reason

Business scenarios revealed two unresolved seams:

- Allowances may require independent lifecycle.
- Daily rate may be derived rather than stored.

---

# 3.4 Allowance Modeling

## Classification

Business / Architecture Boundary Gap

---

## Current State

Allowance is intentionally deferred.

Evidence suggests:

- multiple simultaneous allowances;
- independent effective periods;
- separate business meaning.

---

## Remaining Decision

Whether allowance becomes:

- part of Compensation;
- separate Compensation-related entity.

---

# 3.5 Daily Rate Representation

## Classification

Business Gap

---

## Current State

Daily rate may represent either:

- an agreed employment term;
- a payroll-derived calculation value.

---

## Remaining Decision

Business must decide:

- store daily rate;
- calculate daily rate during payroll processing.

---

# 3.6 JobGrade Relationship

## Classification

Architecture Gap

---

## Current State

Compensation may be influenced by JobGrade changes.

However:

- JobGrade does not own Compensation.
- Compensation does not own JobGrade.

---

## Remaining Unknown

Relationship mechanism:

Possible examples:

- direct reference;
- policy validation;
- compensation band lookup.

---

## Deferred

Whether JobGrade owns:

- salary range;
- compensation band;
- minimum/maximum constraints.

---

# 3.7 Authorization Policy

## Classification

Governance Gap

---

## Current State

Authorization cannot be finalized.

Reason:

No Compensation-specific:

- resource model;
- permission model;
- approval workflow.

---

## Remaining Decision

Requires business definition:

- who may create compensation;
- who may approve changes;
- whether approval is required before effectiveness.

---

# 4. Existing Infrastructure Assessment

## BaseEntity

Applicable.

Compensation can use existing entity infrastructure.

---

## Repository Layer

Applicable.

No repository limitation prevents design.

---

## UnitOfWork

Applicable.

Transaction handling exists.

---

## AuditLog

Partially applicable.

AuditLog may record:

- who changed compensation;
- when changes occurred.

AuditLog does not replace:

- compensation history;
- effective dating.

---

## VersionMixin

Not Applicable.

VersionMixin solves optimistic concurrency, not temporal business history.

---

# 5. Dependency Direction

## Monetary Representation

Producer:

```text
Monetary Representation
          |
          v
Compensation
```

---

## Effective Dating

Producer:

```text
Effective Dating
          |
          v
Compensation
```

---

## Payroll Calculation

Consumer:

```text
Compensation
          |
          v
Payroll Calculation
```

---

## Payslip

Indirect consumer:

```text
Compensation
          |
          v
Payroll Calculation
          |
          v
Payslip
```

---

# 6. Missing Concepts

## Closed

The following concepts are no longer missing:

- Compensation business meaning.
- Compensation boundary.
- Consumer relationships.
- Need for monetary mechanism.
- Need for temporal interpretation.

---

## Remaining Missing Concepts

| Concept | Classification |
|---|---|
| Monetary type implementation | Governance Gap |
| Effective Dating implementation model | Governance Gap |
| Allowance representation | Business/Architecture Gap |
| Daily rate decision | Business Gap |
| Compensation authorization | Governance Gap |
| JobGrade compensation relationship | Architecture Gap |

---

# 7. Can Iteration 1 Begin?

## Answer

Conditionally.

---

## Allowed

Architecture design may begin for:

- aggregate boundary;
- domain responsibilities;
- integration contracts;
- relationship modeling.

---

## Not Allowed

Implementation cannot begin for:

- final database schema;
- migration;
- monetary fields;
- effective-dated persistence;
- payroll integration.

---

## Reason

Implementation would require inventing answers to:

1. Monetary Representation mechanism.
2. Effective Dating mechanism.
3. Allowance ownership.
4. JobGrade relationship implementation.

---

# 8. Blocking Unknowns

Remaining blockers:

## Architecture

1. Monetary Representation integration model.
2. Effective Dating integration model.
3. Compensation aggregate persistence shape.
4. JobGrade relationship mechanism.

---

## Business

5. Allowance ownership.
6. Daily rate storage.
7. Currency policy.
8. Compensation reason taxonomy.
9. Authorization policy.

---

# 9. Recommendation

## Previous State

Waiting for Business Decisions.

---

## Current State

Ready for Architecture Design.

---

The fundamental business uncertainty that previously blocked Compensation has been resolved.

The remaining blockers are now narrower:

- mechanism integration;
- persistence design;
- unresolved business sub-concepts.

Implementation remains deferred until Monetary Representation and Effective Dating provide stable architectural contracts.

**Recommendation: Proceed to Architecture Design.**
