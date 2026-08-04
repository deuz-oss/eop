# Identity & Authorization Architecture Decision

Status: Accepted

Date: 2026-08-04

Capability:

Identity & Authorization Foundation

---

# 1. Decision Summary

EOP akan menggunakan:

Hybrid Authorization Model
RBAC

Resource Policy

Authorization tidak hanya berdasarkan role.

Authorization juga mempertimbangkan:

- resource context
- employee context
- business policy

---

# 2. Problem Statement

Saat ini EOP memiliki:

Authentication
✓
Authorization Context
✗

Current flow:

User
↓
JWT
↓
CurrentUser

Tidak ada resolusi:

CurrentUser
↓
HrEmployee
↓
Business Context

Akibatnya:

- ownership tidak dapat diverifikasi
- approval tidak memiliki boundary
- employee-scoped endpoint terbuka untuk seluruh authenticated user

---

# 3. Identity Context Decision

## Decision

EOP membutuhkan konsep:

Employee Context

Employee Context adalah representasi employee yang terkait dengan authenticated user.

Flow:

CurrentUser
|

    v

Employee Context Resolver
|

    v

HrEmployee Context

---

# 4. Authorization Model Decision

## Chosen Model

Hybrid Authorization

Terdiri dari:

## Role Layer

Menjawab:

What capability does this user have?

Contoh:

HR_ADMIN
APPROVER
MANAGER

---

## Policy Layer

Menjawab:

Can this user perform this action
on this resource?

Contoh:

CanApproveLeave(
user,
leave_request
)

---

# 5. Why Not Pure RBAC

Pure RBAC:

Role
↓
Permission

Tidak cukup untuk:

- manager approval
- employee ownership
- resource scope

Contoh:

Role:

Manager

tidak menjawab:

Manager boleh approve employee siapa?

---

# 6. Why Not Pure Policy

Policy-only:

User
↓
Policy

mengabaikan:

- existing Role model
- existing user_roles structure

---

# 7. Authorization Boundary Decision

## Decision

Authorization decision berada pada dedicated authorization component.

Target:

Service
↓
Authorization Component
↓
Policy Evaluation
↓
Allow / Deny

---

# 8. Layer Responsibility

## API

Tetap:

- authentication
- request handling
- exception mapping

Tidak memiliki business authorization logic.

---

## Service

Memanggil authorization boundary.

Contoh:

LeaveService
↓
Authorization Check
↓
Continue Operation

---

## Repository

Tidak mengetahui authorization.

---

# 9. Initial Implementation Scope

Phase pertama:

Foundation only.

Include:

- Employee Context Resolver
- Authorization abstraction
- Permission abstraction

Tidak termasuk:

- approval rules
- manager hierarchy
- leave policy
- overtime policy

---

# 10. Deferred Decisions

Tetap unresolved:

## user_id uniqueness

Reason:

Tidak diperlukan untuk foundation.

---

## Manager hierarchy

Reason:

Membutuhkan business definition.

---

## User provisioning

Reason:

Operational process belum ditentukan.

---

# 11. Future Consumers

Authorization foundation akan digunakan oleh:

- Approval
- Leave
- Timesheet
- Overtime
- Reconciliation
- HR Administration

---

# 12. Architecture Principle

No business operation should bypass authorization context once the capability is available.
