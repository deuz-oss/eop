# EOP Master Architecture Roadmap

Version: 1.0

---

# Phase 0 — Foundation

Status:

Completed

PR:

PR-001 → PR-050

Capability:

- Authentication
- Organization
- HR Foundation
- Leave Foundation
- Attendance Foundation
- Project Tracking
- Basic Approval

---

# Phase 1 — Identity & Authorization

## PR-051

Identity Context & Authorization Architecture

Type:

Discovery + Design

Deliver:

- authorization model
- employee context design
- permission boundary
- policy placement

---

## PR-052

Authorization Foundation Implementation

Deliver:

- authorization abstraction
- current employee resolver
- policy framework

---

# Phase 2 — Workflow Governance

## PR-053

Approval Authorization

Deliver:

- approver validation
- approval policy enforcement

---

## PR-054

Workflow History Foundation

Deliver:

- approval history
- decision audit

---

# Phase 3 — HR Automation

## PR-055

Leave Balance Rule Discovery

Resolve:

- period definition
- calculation method
- accrual model

---

## PR-056

Leave Balance Engine

Deliver:

- deduction
- accrual
- adjustment

---

# Phase 4 — Platform Capability

## PR-057

Notification Platform

---

## PR-058

Background Processing

---

# Phase 5 — Enterprise Capability

## PR-059

Reporting Model

---

## PR-060

Business Audit Platform

---

## PR-061+

External Integration

Examples:

- Payroll
- ERP
- Attendance Device

---

# Roadmap Rule

Architecture decision precedes implementation.

Sequence:

Discovery

↓

Architecture Decision

↓

Implementation

↓

Validation

↓

Merge
