# EOP Technical Debt Register

**Status:** Active

**Version:** 1.0

**Owner:** EOP Architecture Governance

---

# Purpose

This document records known architectural and technical debt within the EOP platform.

Only confirmed debt should appear here.

Feature requests, future enhancements, and architectural ideas are not technical debt.

---

# Technical Debt Definition

Technical debt is an intentional or inherited implementation compromise that should be removed in the future.

Technical debt must satisfy at least one of the following:

- temporary implementation
- architectural compromise
- missing platform capability
- known limitation
- legacy compatibility

---

# Severity Levels

| Level    | Meaning                                    |
| -------- | ------------------------------------------ |
| Critical | Blocks architecture evolution              |
| High     | Significantly impacts maintainability      |
| Medium   | Should be addressed in future capabilities |
| Low      | Minor improvement opportunity              |

---

# Current Technical Debt

## TD-001

### Title

RequireRole is legacy authorization.

### Category

Architecture

### Severity

High

### Current State

Role enforcement exists only through `RequireRole`.

Authorization Foundation is the strategic replacement.

### Planned Resolution

Authorization Foundation.

---

## TD-002

### Title

Business capabilities authenticate but do not authorize.

### Category

Architecture

### Severity

High

### Current State

Leave

Timesheet

Overtime

Reconciliation

Approval

only require authentication.

No ownership evaluation exists.

### Planned Resolution

Authorization Foundation

Approval Authorization

Leave Authorization

---

## TD-003

### Title

Approval workflow lacks authorization.

### Category

Business

### Severity

High

### Current State

ApprovalService validates workflow state only.

Authorization is intentionally out of scope (ADR-003).

### Planned Resolution

Approval Authorization capability.

---

## TD-004

### Title

EmployeeContext is implemented but not consumed.

### Category

Platform

### Severity

Medium

### Current State

EmployeeContextResolver exists.

CurrentEmployeeContext exists.

No production endpoint consumes them.

### Planned Resolution

Authorization Foundation integration.

---

## TD-005

### Title

Manager hierarchy is not used for authorization.

### Category

Business

### Severity

Medium

### Current State

manager_id exists.

No authorization logic consumes it.

### Planned Resolution

Manager Authorization.

---

## TD-006

### Title

User ↔ Employee cardinality remains unresolved at schema level.

### Category

Architecture

### Severity

Medium

### Current State

EmployeeContextResolver treats multiple employees as an error.

Database allows multiple rows.

### Planned Resolution

Future architecture decision.

---

# Resolved Technical Debt

Move resolved items here.

Example:

| ID     | Resolution        |
| ------ | ----------------- |
| TD-000 | Removed in PR-051 |

---

# Debt Lifecycle

```
Identified

↓

Accepted

↓

Scheduled

↓

Resolved

↓

Removed
```

---

# Governance

Technical debt may be introduced only when:

- documented
- understood
- temporary
- tracked

Undocumented debt is prohibited.

---

# Relationship to Other Documents

| Document                | Purpose                 |
| ----------------------- | ----------------------- |
| ADR                     | Architectural decisions |
| Architecture Changelog  | Architectural evolution |
| Roadmap                 | Planned implementation  |
| Technical Debt Register | Known compromises       |

---

# Success Criteria

The Technical Debt Register is considered healthy when:

- all known debt is documented
- debt has an owner
- debt has a planned resolution
- resolved debt is archived

The register should always reflect the current known architectural compromises of the platform.
