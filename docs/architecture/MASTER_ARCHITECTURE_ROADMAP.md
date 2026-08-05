# EOP Master Architecture Roadmap

Status: Active

Version: 1.1

Date: 2026-08-04

Owner:

EOP Architecture Governance

---

# 1. Purpose

This roadmap defines the capability evolution sequence of EOP.

The roadmap is capability-driven.

It is not tied to GitHub Pull Request numbering.

---

# 2. Roadmap Principles

Implementation follows:

Foundation
↓
Platform Capability
↓
Domain Capability
↓
Automation

No domain feature should bypass required platform foundations.

---

# 3. Phase Overview

Phase 1
Identity & Authorization Foundation
Phase 2
Workflow Governance
Phase 3
Workforce Authorization
Phase 4
Business Automation
Phase 5
Enterprise Intelligence

---

# Phase 1 — Identity & Authorization Foundation

Status:

Discovery Complete

Architecture Decision Complete

Implementation Pending

Objective:

Create the foundation required for secure business operations.

---

## Completed

### Identity Link

Status:

Completed

Artifact:

ADR-004

Implemented:

HrEmployee.user_id

---

### Authorization Discovery

Status:

Completed

Artifact:

capabilities/
identity-authorization/
discovery.md

---

### Authorization Decision

Status:

Completed

Artifacts:

decision.md
ADR-005

---

## Implementation Scope

Build:

Employee Context Resolver

Defined by:

ADR-006

Behavior:

- missing employee rejected
- multiple employee rejected
Authorization Context
Permission Abstraction

---

## Not Included

Do not implement:

- approval policy
- manager hierarchy
- ownership rules
- organization authorization
- delegated authority

---

# Phase 2 — Workflow Governance

Dependency:

Phase 1

Objective:

Make workflow decisions secure and auditable.

Capabilities:

## Approval Authorization

Implement:

- approve permission
- reject permission
- authorization policy

Consumers:

- Leave Approval
- Overtime Approval
- Timesheet Approval

---

## Workflow History

Future:

- decision history
- actor tracking
- timestamps
- audit trail

---

# Phase 3 — Workforce Authorization

Dependency:

Phase 1

Phase 2

Objective:

Protect employee-scoped operations.

Consumers:

## Leave

Authorization:

- employee ownership
- approver scope

---

## Overtime

Authorization:

- employee ownership
- approval boundary

---

## Timesheet

Authorization:

- employee ownership
- project scope

---

## Reconciliation

Authorization:

- employee access scope

---

# Phase 4 — Business Automation

Objective:

Introduce business intelligence.

Capabilities:

- leave balance engine
- attendance rules
- payroll integration
- policy automation

---

# Phase 5 — Enterprise Intelligence

Future capability:

- analytics
- reporting
- compliance
- workforce insights

---

# 4. Current Priority Queue

Order:

Identity Authorization Foundation

Approval Authorization

Ownership Authorization

Workflow History

Business Automation

---

# 5. Architecture Governance Rule

Every future capability must provide:

1. Discovery

2. Architecture Decision

3. ADR (when needed)

4. Implementation Plan

5. Code

6. Validation

---

# 6. Source Documents

Related:

MASTER_ARCHITECTURE_BLUEPRINT.md
ARCHITECTURE_INVENTORY.md
CAPABILITY_DEPENDENCY_GRAPH.md
ARCHITECTURE_DECISION_RECORDS/
