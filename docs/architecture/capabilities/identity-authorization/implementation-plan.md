# Identity & Authorization Foundation Implementation Plan

Status: Approved for Implementation

Date: 2026-08-04

References:

- MASTER_ARCHITECTURE_BLUEPRINT.md
- MASTER_ARCHITECTURE_ROADMAP.md
- ADR-004-hr-employee-user-link.md
- ADR-005-authorization-context-model.md

---

# 1. Objective

Implement the foundation required to connect:

User Identity

with

Employee Context

and

Authorization Context.

This implementation creates infrastructure only.

It does not enforce business authorization rules yet.

---

# 2. Scope

Included:

- Employee Context Resolver
- Authorization Context abstraction
- Permission abstraction
- reusable authorization boundary

---

Excluded:

- approval authorization
- leave authorization
- overtime authorization
- timesheet authorization
- manager hierarchy
- ownership rules
- organization policies

---

# 3. Target Architecture

Current:

CurrentUser
↓
Business Service

Target:

CurrentUser
↓
Employee Context Resolver
↓
Authorization Context
↓
Business Service

---

# 4. Components

## Employee Context Resolver

Responsibility:

Resolve authenticated User into HrEmployee context.

Input:

CurrentUser

Output:

Employee Context

Must handle:

- no linked employee
- multiple linked employees

Behavior must follow explicit architecture decision.

Do not infer.

---

# 5. Authorization Context

Purpose:

Provide reusable context for authorization decisions.

Contains:

- current user
- employee context
- roles
- permissions (future)

---

# 6. Permission Abstraction

Create abstraction only.

Example:

Permission
|
Authorization Requirement

Do not create complete permission catalog.

---

# 7. Layer Placement

Follow:

API

↓

Service

↓

Authorization Component

↓

Repository

---

Repository remains persistence-only.

---

# 8. Database Impact

Expected:

No migration.

Reason:

Required identity linkage already exists:

hr_employees.user_id

---

# 9. API Impact

No endpoint behavior changes.

No authorization enforcement.

No breaking changes.

---

# 10. Test Requirements

Required:

- employee context resolution
- missing employee handling
- multiple employee handling
- authorization context construction

No business authorization tests.

---

# 11. Future Consumers

This foundation enables:

- approval authorization
- ownership authorization
- manager authorization
