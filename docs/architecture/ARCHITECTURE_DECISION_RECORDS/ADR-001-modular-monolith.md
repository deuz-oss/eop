# ADR-001 — Modular Monolith Architecture

Status: Accepted

Date: 2026-08-04

Decision Owners:

- Architecture Team

---

# Context

EOP berkembang sebagai aplikasi HR platform dengan beberapa domain:

- Identity
- Organization
- HR
- Leave
- Attendance
- Project
- Workflow

Repository menunjukkan karakteristik:

- single application deployment
- single database
- shared transaction boundary
- relational persistence
- service-oriented business layer

Belum ditemukan kebutuhan:

- distributed transaction
- independent scaling domain
- independent deployment
- service ownership separation

---

# Decision

EOP menggunakan:

Modular Monolith

- Domain-oriented Architecture

sebagai architecture style utama.

---

# Consequences

Positive:

- transaction tetap sederhana
- database consistency mudah dijaga
- domain boundary tetap dapat berkembang
- operational complexity rendah

Negative:

- domain isolation harus dijaga secara disiplin
- dependency antar module harus dikontrol

---

# Rejected Alternatives

## Microservices

Rejected karena:

- belum ada operational requirement
- belum ada distributed boundary
- menambah complexity tanpa benefit saat ini

---

# Architectural Rule

Jangan memecah service menjadi deployment terpisah tanpa:

- business justification
- scaling requirement
- operational requirement
