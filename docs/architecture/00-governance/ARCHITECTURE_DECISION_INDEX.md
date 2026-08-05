# EOP Architecture Decision Index

**Status:** Active

**Version:** 1.0

**Owner:** EOP Architecture Governance

---

# Purpose

This document is the authoritative index of all Architecture Decision Records (ADRs) within the EOP platform.

It provides a centralized reference for architectural decisions, their scope, current status, and relationships to platform capabilities.

Unlike individual ADRs, this document contains no architectural reasoning. It exists solely as a navigation and governance aid.

---

# ADR Lifecycle

```
Proposed

↓

Draft

↓

Accepted

↓

Superseded

↓

Deprecated
```

Only **Accepted** ADRs govern production architecture.

---

# Architecture Decision Index

| ADR     | Title                          | Capability    | Status   | Supersedes |
| ------- | ------------------------------ | ------------- | -------- | ---------- |
| ADR-001 | _(Reserved / Existing)_        | Platform      | Accepted | —          |
| ADR-002 | _(Reserved / Existing)_        | Platform      | Accepted | —          |
| ADR-003 | Approval Service Boundary      | Approval      | Accepted | —          |
| ADR-004 | User ↔ Employee Identity Model | Identity      | Accepted | —          |
| ADR-005 | Authorization Context Model    | Authorization | Accepted | —          |
| ADR-006 | Identity Context Foundation    | Identity      | Accepted | —          |
| ADR-007 | Authorization Foundation       | Authorization | Accepted | —          |

---

# Decision Categories

## Platform

- Authentication
- Identity
- Authorization
- Workflow
- Audit
- Notification

---

## Business

- Leave
- Attendance
- Payroll
- Timesheet
- Overtime

---

## Infrastructure

- Repository Pattern
- Unit of Work
- Dependency Injection
- Persistence

---

# ADR Relationships

```
ADR-004

↓

ADR-006

↓

ADR-005

↓

ADR-007
```

Identity precedes Authorization.

Authorization depends upon Identity Context.

---

# Future ADRs

Examples of future architecture decisions include:

- Approval Authorization
- Leave Authorization
- Attendance Authorization
- Notification Architecture
- Audit Architecture
- Event Architecture

---

# Governance Rules

Every accepted architecture decision must:

- have an ADR
- appear in this index
- reference affected capabilities
- update the Blueprint if required
- update the Roadmap if required

---

# Relationship to Other Documents

| Document                | Purpose                  |
| ----------------------- | ------------------------ |
| Architecture Principles | Architectural philosophy |
| Architecture Governance | Process                  |
| ADR                     | Decision details         |
| Decision Index          | ADR inventory            |
| Blueprint               | Target architecture      |
| Roadmap                 | Evolution sequence       |

---

# Success Criteria

The Architecture Decision Index is considered healthy when:

- every accepted ADR is indexed
- ADR status is current
- capability ownership is clear
- superseded ADRs are identified

This document is the single entry point for all architectural decisions.
