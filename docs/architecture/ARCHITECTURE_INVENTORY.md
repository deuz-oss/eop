# EOP Architecture Inventory

Version: 1.0
Status: Approved Baseline
Purpose: Current-state architecture reference

---

# 1. Purpose

Dokumen ini mendokumentasikan kondisi aktual arsitektur EOP berdasarkan repository audit.

Dokumen ini menjawab:

- bagaimana sistem saat ini dibangun,
- capability apa yang sudah tersedia,
- boundary antar layer,
- gap arsitektur yang ditemukan.

Dokumen ini bukan target architecture.

Target architecture berada di:

- MASTER_ARCHITECTURE_BLUEPRINT.md
- MASTER_ARCHITECTURE_ROADMAP.md

---

# 2. Current Architecture Style

EOP saat ini menggunakan:

Modular Monolith

- Domain-oriented Service Architecture
- Relational Persistence

Karakteristik:

- satu application deployment,
- satu database,
- multiple business capability,
- service-oriented business layer.

---

# 3. Application Layer Architecture

Current flow:

API
↓
Service
↓
UnitOfWork
↓
Repository
↓
SQLAlchemy Model
↓
Database

Responsibility:

## API

Responsible:

- routing
- request validation
- authentication dependency
- exception mapping

Not responsible:

- business rule
- transaction
- domain decision

## Service

Responsible:

- business rule
- orchestration
- validation
- transaction coordination

## Repository

Responsible:

- persistence
- query
- filtering
- pagination

Not responsible:

- business interpretation
- workflow decision
- authorization

---

# 4. Domain Inventory

## Identity

Status: Mature

Components:

- User
- Role
- JWT authentication

Gap:

- Permission model
- Authorization policy

---

## Organization

Status: Mature

Components:

- Organization
- Department
- Team
- Location

---

## HR

Status: Mature

Components:

- HrEmployee
- EmploymentType
- EmploymentStatus
- JobGrade
- Shift
- Holiday

---

## Leave

Status: Partial

Components:

- LeaveRequest
- LeaveBalance

Gap:

- Balance engine
- Accrual rule
- Deduction rule

---

## Attendance

Status: Partial

Components:

- Attendance
- Reconciliation

Gap:

- Automation
- Device integration

---

## Project

Status: Mature

Components:

- Project
- Assignment
- Task

---

## Workflow

Status: Partial

Components:

- ApprovalService

Gap:

- Authorization
- History
- Audit trail

---

# 5. Security Inventory

Current:

Authentication
✓
Authorization
✗

Available:

- User
- Role
- CurrentUser
- HrEmployee.user_id

Missing:

- Permission
- Policy
- Ownership validation
- Approval authorization

---

# 6. Database Inventory

Architecture:

Single PostgreSQL Database +
Multiple Logical Domains

Current strengths:

- migration discipline
- FK usage
- relational modeling

Missing:

- workflow history storage
- business audit trail
- reporting model

---

# 7. Testing Inventory

Current:

Repository Tests +
Service Tests +
API Tests

Status:

Mature for current architecture.

Missing:

- authorization tests
- workflow policy tests
- integration tests

---

# 8. Architecture Gaps

Priority:

## Critical

Authorization Context

## High

- Workflow History
- Business Audit
- Leave Balance Engine

## Medium

- Notification
- Reporting Model
- Background Processing
- External Integration

---

# 9. Summary

EOP telah berkembang dari CRUD application menjadi:

Operational HR Platform

Fokus architecture berikutnya:

Identity
↓
Authorization
↓
Workflow Governance
↓
Automation
↓
Enterprise Integration
