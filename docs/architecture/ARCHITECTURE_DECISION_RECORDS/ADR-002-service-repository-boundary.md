# ADR-002 — Service Repository Boundary

Status: Accepted

Date: 2026-08-04

---

# Context

EOP menggunakan pola:

API
↓
Service
↓
Repository
↓
Database

Beberapa PR sebelumnya menunjukkan pentingnya menjaga boundary:

- Repository tetap persistence-only
- Service memiliki business interpretation

---

# Decision

Responsibility dibagi:

## API Layer

Bertanggung jawab:

- HTTP handling
- schema validation
- authentication dependency
- exception translation

Tidak bertanggung jawab:

- business rule
- transaction decision

---

## Service Layer

Bertanggung jawab:

- business validation
- orchestration
- business decision
- transaction coordination

---

## Repository Layer

Bertanggung jawab:

- database access
- query
- filtering
- pagination

Tidak bertanggung jawab:

- business rule
- authorization decision
- workflow interpretation

---

# Consequences

Positive:

- business logic memiliki single location
- repository dapat digunakan kembali
- test lebih terstruktur

Negative:

- service dapat menjadi kompleks jika boundary tidak dijaga

---

# Rejected Alternatives

## Business Logic in Repository

Rejected karena:

- sulit ditest
- mencampurkan persistence dan domain decision

## Business Logic in API

Rejected karena:

- membuat endpoint menjadi domain owner
