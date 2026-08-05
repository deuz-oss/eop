# EOP Master Architecture Blueprint

Status: Active

Version: 1.1

Date: 2026-08-04

Owner:

EOP Architecture Governance

---

# 1. Purpose

This document defines the target architecture direction of EOP.

It describes:

- system architecture principles
- domain boundaries
- capability relationships
- application layering
- identity and authorization model
- workflow architecture
- future extension boundaries

This document is architecture guidance.

It is not an implementation specification.

Implementation decisions must reference:

- ADR documents
- capability decisions
- implementation plans

---

# 2. Architecture Vision

EOP is designed as:

Modular Monolith

Domain-Oriented Architecture

Shared Platform Capabilities

The system prioritizes:

- strong domain boundaries
- explicit business ownership
- reusable platform capabilities
- controlled dependency direction

---

# 3. High Level Architecture

Target architecture:

                Client Applications

                       |

                       v


                API Layer

                       |

                       v


             Application Services

                       |

                       v


          Domain Capabilities

                       |

                       v


          Repository / Persistence

                       |

                       v


                Database

---

# 4. Architecture Principles

## 4.1 Modular Monolith

EOP remains a single deployable application.

Reasons:

- current scale does not require distributed services
- transaction consistency is important
- operational complexity should remain controlled

---

## 4.2 Layer Responsibility

### API Layer

Responsible for:

- HTTP transport
- authentication dependency
- schema validation
- exception mapping

Not responsible for:

- business rules
- authorization decisions
- workflows

---

### Service Layer

Responsible for:

- business orchestration
- validation
- transaction coordination
- domain operations

---

### Repository Layer

Responsible for:

- persistence
- query construction
- database access

Not responsible for:

- business decisions
- authorization
- workflows

---

# 5. Capability Architecture

EOP capabilities are grouped:

Identity
|
Organization
|
Human Resource
|
Workforce Operations
|
Workflow
|
Project Management

---

# 6. Identity Architecture

## Current State

Authentication capability exists.

Flow:

User
↓
Authentication
↓
JWT
↓
CurrentUser

Authentication answers:

"Who is this user?"

---

## Target State

Identity context expands:

User
↓
Authentication
↓
CurrentUser
↓
Employee Context
↓
Authorization Context
↓
Business Operation

---

# 7. Employee Identity Context

ADR Reference:

ADR-004

EOP uses:

hr_employees.user_id

as identity linkage.

Purpose:

Provide a bridge between:

Authentication Identity
and
Business Employee Identity

---

Current capability:

HrEmployeeRepository
get_by_user_id()

returns:

Sequence[HrEmployee]

because cardinality remains an explicit unresolved business decision.

---

# 8. Authorization Architecture

ADR Reference:

ADR-005

EOP uses:

Hybrid Authorization Model

Combination:

RBAC

Resource Policy

---

## RBAC Layer

Answers:

What capabilities does this user have?

Example:

HR_ADMIN
APPROVER
MANAGER

---

## Policy Layer

Answers:

Can this user perform this action
on this resource?

Example:

CanApproveLeave(
user,
leave_request
)

---

# 9. Authorization Context Flow

Target:

CurrentUser
|

    v

Employee Context Resolver
|

    v

Authorization Context
|

    v

Policy Decision
|

    v

Service Operation

---

# 10. Authorization Boundary

Authorization is implemented as a dedicated capability.

Target:

Service
|
v
Authorization Component
|
v
Policy Evaluation
|
v
Allow / Deny

---

Rules:

- API does not own authorization logic.
- Repository does not know authorization.
- Service requests authorization decision.

---

# 11. Workflow Architecture

ADR Reference:

ADR-003

Approval is a shared workflow capability.

Not owned by:

- Leave
- Overtime
- Timesheet

Target:

Business Request
|

    v

Workflow Engine
|

    v

Decision
|

    v

Domain Update

---

Current limitation:

Approval supports:

- approve
- reject
- state transition

Authorization integration remains future work.

---

# 12. Domain Capability Boundaries

## Identity

Owns:

- users
- authentication
- roles

---

## Organization

Owns:

- company structure
- organizational relationships

---

## HR

Owns:

- employee master data
- employment information

---

## Workforce Operations

Owns:

- leave
- attendance
- overtime
- timesheet

---

## Workflow

Owns:

- approval process
- decisions
- workflow state

---

# 13. Dependency Direction

Allowed:

Application Service
↓
Shared Capability
↓
Domain Operation

Forbidden:

Repository
↓
Business Decision

---

# 14. Future Architecture Goals

Future capabilities:

- permission framework
- policy engine
- workflow history
- organization hierarchy authorization
- auditability
- delegated authority

---

# 15. Related ADR

| ADR     | Decision                     |
| ------- | ---------------------------- |
| ADR-001 | Modular Monolith             |
| ADR-002 | Service Repository Boundary  |
| ADR-003 | Approval Workflow Capability |
| ADR-004 | Employee Identity Link       |
| ADR-005 | Authorization Context Model  |

---

# Employee Context Resolution

Employee identity resolution is centralized.

Flow:

CurrentUser

↓

Employee Context Resolver

↓

EmployeeContext

Rules:

- no implicit employee selection
- no ambiguous identity
- no automatic switching
