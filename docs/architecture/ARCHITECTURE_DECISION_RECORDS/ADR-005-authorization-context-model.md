# ADR-005 — Authorization Context Model

Status: Accepted

Date: 2026-08-04

Decision Owner:

EOP Architecture Owner

---

# Context

EOP memiliki authentication capability:

User
JWT
CurrentUser

Namun business capability membutuhkan:

User

Employee Context

Authorization Decision

PR-050 menyediakan:

hr_employees.user_id

tetapi belum digunakan.

---

# Decision

EOP menggunakan:

Authorization Context Layer

sebagai boundary antara identity dan business operation.

---

# Target Flow

Authenticated User
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

Business Operation

---

# Authorization Model

Decision:

Hybrid Model

menggabungkan:

## RBAC

Untuk capability access.

Contoh:

HR_ADMIN
APPROVER

---

## Resource Policy

Untuk contextual decision.

Contoh:

Can user approve this request?

---

# Boundary Decision

Authorization tidak ditempatkan:

## API only

Rejected.

Reason:

Business operation dapat dipanggil dari service layer.

---

## Repository

Rejected.

Reason:

Repository adalah persistence boundary.

---

## Service inline logic

Rejected.

Reason:

Menyebabkan duplication.

---

Chosen:

Dedicated Authorization Component

---

# Consequences

Positive:

- authorization reusable
- policy centralized
- domain tetap bersih

Negative:

- membutuhkan capability tambahan
- membutuhkan policy design

---

# Implementation Constraint

Implementation tidak boleh:

- mengubah existing business behavior tanpa policy
- membuat manager hierarchy assumption
- membuat role vocabulary tanpa decision
- membuat automatic employee linking

---

# Future Extensions

Possible:

- manager policy
- ownership policy
- approval policy
- organization policy

---

# Related ADR

- ADR-001 Modular Monolith
- ADR-002 Service Boundary
- ADR-004 HrEmployee Identity Link
