# ADR-003 — Approval as Workflow Capability

Status: Accepted

Date: 2026-08-04

---

# Context

ApprovalService saat ini menangani:

- approve
- reject
- state transition

Digunakan oleh:

- Leave
- Overtime
- Timesheet

Approval bukan milik satu domain bisnis saja.

---

# Decision

Approval diposisikan sebagai:

Workflow Capability

bukan:

Leave Capability
Overtime Capability
Timesheet Capability

---

# Target Architecture

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

# Consequences

Positive:

- approval dapat digunakan lintas domain
- rule approval dapat berkembang
- history dapat dipusatkan

Negative:

- membutuhkan authorization layer
- workflow history belum tersedia

---

# Current Limitation

Approval authorization belum diimplementasikan.

Current:

Authentication only

Future:

Authentication

Authorization

Workflow Policy

---

# Rejected Alternatives

## Approval Logic inside LeaveService

Rejected karena:

- overtime dan timesheet membutuhkan pola sama
- menyebabkan duplikasi workflow
