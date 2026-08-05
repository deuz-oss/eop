# EOP Capability Catalog

**Status:** Active

**Version:** 1.0

**Owner:** EOP Architecture Governance

---

# Purpose

This document is the authoritative catalog of all architectural capabilities within the EOP platform.

It provides a high-level inventory of platform and business capabilities, their ownership, dependencies, and implementation status.

Unlike the Master Architecture Roadmap, this document is not time-based. It reflects the current architectural landscape.

---

# Capability Lifecycle

Each capability progresses through the following lifecycle:

```
Proposed
    ↓
Discovery
    ↓
Decision
    ↓
ADR
    ↓
Implementation Plan
    ↓
Implementation
    ↓
Architecture Review
    ↓
Complete
```

---

# Capability Classification

Capabilities are classified into one of the following categories:

| Category       | Description                               |
| -------------- | ----------------------------------------- |
| Platform       | Shared capabilities reused across domains |
| HR             | Human Resource domain                     |
| Attendance     | Attendance and workforce operations       |
| Payroll        | Payroll and compensation                  |
| Infrastructure | Cross-cutting technical capabilities      |

---

# Platform Capabilities

| Capability               | Category | Status      | Depends On       | Used By                      |
| ------------------------ | -------- | ----------- | ---------------- | ---------------------------- |
| Authentication           | Platform | Complete    | —                | All secured APIs             |
| Identity Context         | Platform | Complete    | Authentication   | Authorization Foundation     |
| Authorization Foundation | Platform | In Progress | Identity Context | Future business capabilities |
| Audit _(planned)_        | Platform | Planned     | Authentication   | All business domains         |
| Notification _(planned)_ | Platform | Planned     | Authentication   | Workflow capabilities        |
| Workflow _(planned)_     | Platform | Planned     | Authorization    | Approval, Leave, Overtime    |
| Scheduling _(planned)_   | Platform | Planned     | Authentication   | Attendance, Payroll          |

---

# HR Master Data

| Capability        | Status   |
| ----------------- | -------- |
| Job Grade         | Complete |
| Employment Type   | Complete |
| Employment Status | Complete |
| Shift             | Complete |
| Holiday           | Complete |
| HR Employee       | Complete |

---

# Workforce Operations

| Capability     | Status                           |
| -------------- | -------------------------------- |
| Leave          | Complete (authorization pending) |
| Timesheet      | Complete (authorization pending) |
| Overtime       | Complete (authorization pending) |
| Attendance     | Planned                          |
| Reconciliation | Complete (authorization pending) |

---

# Authorization Roadmap

| Capability               | Status      |
| ------------------------ | ----------- |
| Authorization Foundation | In Progress |
| Approval Authorization   | Planned     |
| Leave Authorization      | Planned     |
| Timesheet Authorization  | Planned     |
| Overtime Authorization   | Planned     |
| Attendance Authorization | Planned     |

---

# Dependency Overview

```
Authentication
        │
        ▼
Identity Context
        │
        ▼
Authorization Foundation
        │
        ▼
Business Capabilities
```

Business capabilities consume platform capabilities but never the reverse.

---

# Capability Ownership

Platform capabilities are maintained by the Architecture team.

Business capabilities are maintained by their respective domain owners.

Architecture governance remains responsible for:

- Capability boundaries
- Architectural consistency
- Dependency direction
- ADR approval

---

# Capability Status Definitions

| Status      | Meaning                        |
| ----------- | ------------------------------ |
| Proposed    | Identified but not started     |
| Discovery   | Repository evidence collected  |
| Decision    | Architecture approved          |
| Planned     | Implementation planned         |
| In Progress | Implementation underway        |
| Complete    | Implemented and reviewed       |
| Deprecated  | Scheduled for removal          |
| Retired     | No longer part of the platform |

---

# Governance

Every new capability must include:

- Discovery
- Decision
- ADR (if required)
- Implementation Plan

Capabilities must be registered in this catalog before implementation begins.

---

# Relationship to Other Documents

This document answers:

> **What capabilities exist?**

Related documents answer different questions:

| Document                      | Purpose                                   |
| ----------------------------- | ----------------------------------------- |
| Repository Census             | What exists in the repository?            |
| Architecture Inventory        | How is the repository organized?          |
| Capability Dependency Graph   | How do capabilities depend on each other? |
| Master Architecture Blueprint | What is the target architecture?          |
| Master Architecture Roadmap   | In what order will capabilities evolve?   |
| Architecture Status           | What is the implementation progress?      |

---

# Success Criteria

The Capability Catalog is considered healthy when:

- every architectural capability is registered
- ownership is explicit
- dependencies are documented
- lifecycle status is current
- capability boundaries remain clear

This catalog serves as the primary inventory of the EOP architecture.
