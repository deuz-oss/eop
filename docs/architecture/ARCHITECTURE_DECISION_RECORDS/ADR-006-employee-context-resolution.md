# ADR-006 — Employee Context Resolution Model

Status: Accepted

Date: 2026-08-04

Decision Owner:

EOP Architecture Governance

---

# Context

EOP memiliki dua identity domain:

## Authentication Identity

Represented by:

User

Digunakan untuk:

- login
- JWT authentication
- system access

---

## Business Employee Identity

Represented by:

HrEmployee

Digunakan untuk:

- HR operations
- leave
- overtime
- timesheet
- approval

---

PR-050 memperkenalkan:

hr_employees.user_id

sebagai link antara:

User
↓
HrEmployee

Namun relasi tersebut belum memiliki resolver layer.

---

# Problem

Application layer membutuhkan cara standar untuk mendapatkan employee context dari authenticated user.

Tanpa resolver:

Setiap service akan melakukan:

CurrentUser
↓
HrEmployeeRepository.get_by_user_id()
↓
custom handling

yang menyebabkan:

- duplicate logic
- inconsistent behavior
- future authorization complexity

---

# Decision

EOP akan menggunakan:

Employee Context Resolver

sebagai shared application capability.

---

# Context Flow

CurrentUser
|

    v

Employee Context Resolver
|

    v

Employee Context

---

# Employee Context Contract

Resolver menghasilkan:

EmployeeContext

yang berisi:

- authenticated user reference
- resolved employee reference

---

# Zero Employee Behavior

Decision:

When authenticated user has no linked employee:

EmployeeContextNotFound

dilempar.

Reason:

Business HR operation requires employee identity.

A silent empty context creates security ambiguity.

---

# Multiple Employee Behavior

Decision:

Multiple linked employees are rejected.

Behavior:

MultipleEmployeeContextError

Reason:

Authorization decision requires deterministic identity.

EOP does not currently support:

- multiple employee identities
- employee switching
- delegated identities

---

# Why Not Select First Employee

Rejected.

Reason:

Would create hidden authorization ambiguity.

---

# Why Not Support Multiple Contexts Now

Rejected.

Reason:

No business requirement exists yet.

Future support requires explicit product decision.

---

# Relationship Assumption

Current database remains:

User
1
to
0..n
HrEmployee

Database uniqueness is intentionally unchanged.

Resolver enforces deterministic behavior at application level.

---

# Layer Placement

Resolver belongs to:

Application Capability Layer

Not:

- API
- Repository
- Database

---

# Consequences

Positive:

- consistent employee resolution
- reusable authorization foundation
- centralized identity interpretation

Negative:

- users without employees cannot access employee-scoped operations
- future multi-employee scenarios require extension

---

# Related ADR

- ADR-004 HrEmployee User Link
- ADR-005 Authorization Context Model
