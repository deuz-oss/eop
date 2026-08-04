# EOP Master Architecture Blueprint

Version: 1.0

---

# 1. Architecture Vision

EOP menggunakan:

Modular Monolith

Domain-oriented Architecture

---

# 2. Target Architecture

API Layer
|
Authorization Layer
|
Application Service Layer
|
Repository Layer
|
Database Layer

---

# 3. Domain Boundary

Logical domain:

Identity
Organization
HR
Leave
Attendance
Project
Workflow
Reporting
Integration

---

# 4. Identity Architecture

Target:

User
↓
Employee Context
↓
Authorization Context
↓
Policy Decision

---

# 5. Authorization Architecture

Authorization menjadi capability tersendiri.

Components:

- Permission
- Policy
- Resource ownership
- Role mapping

Target:

CurrentUser
↓
Authorization Context
↓
Policy Evaluation
↓
Allow / Deny

---

# 6. Workflow Architecture

Current:

ApprovalService

Target:

Workflow Capability
|
+-- Decision
|
+-- History
|
+-- Rule

---

# 7. Data Architecture

Current direction:

Single Database

Logical Domain Separation

Tidak ada rencana:

- microservice
- database split
- event sourcing

---

# 8. Future Platform Capability

Future:

Domain Event
↓
Notification
↓
Integration

Namun tidak menjadi prioritas sekarang.

---

# 9. Architecture Principles

1. Service owns business rule.
2. Repository remains persistence-only.
3. API remains thin.
4. No feature bypasses authorization boundary.
5. No automation without explicit business rule.
