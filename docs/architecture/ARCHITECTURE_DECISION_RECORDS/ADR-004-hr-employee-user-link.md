# ADR-004 — HrEmployee User Identity Link

Status: Accepted

Date: 2026-08-04

---

# Context

Sebelum PR-050:

User
X
HrEmployee

tidak memiliki hubungan.

Akibatnya:

- authentication tersedia
- employee context tidak tersedia

Authorization berbasis employee tidak dapat dibangun.

---

# Decision

Identity link menggunakan:

hr_employees.user_id

dengan:

nullable FK
references users.id
ON DELETE SET NULL

---

# Rationale

Dipilih karena:

1. Konsisten dengan precedent migration HR.

2. Employee adalah domain yang membutuhkan identity mapping.

3. Tidak membutuhkan perubahan User domain.

4. Tidak membuat UserService baru.

---

# Repository Rule

Lookup menggunakan:

HrEmployeeRepository

bukan:

UserRepository

---

# Cardinality Decision

Status:

UNRESOLVED

Tidak ada keputusan bahwa:

user_id UNIQUE

atau:

user_id NON UNIQUE

---

# Repository Contract

Karena uniqueness belum ditentukan:

lookup harus memperlakukan hasil sebagai:

Sequence[HrEmployee]

bukan:

HrEmployee | None

---

# Consequences

Positive:

- employee context dapat dibangun
- authorization foundation dapat dibuat

Negative:

- caller harus menentukan behavior jika:
  - zero employee
  - multiple employee

---

# Out of Scope

Tidak termasuk:

- authorization
- ownership rule
- manager hierarchy
- automatic linking
- synchronization
