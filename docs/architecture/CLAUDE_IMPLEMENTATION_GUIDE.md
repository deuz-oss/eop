# Claude Implementation Guide

**Status:** Active

**Version:** 1.0

**Owner:** EOP Architecture Governance

---

# Purpose

This document defines the implementation governance for AI-assisted development within EOP.

Its purpose is to ensure that every implementation:

- follows approved architecture
- preserves architectural consistency
- avoids undocumented design decisions
- produces predictable implementation quality

This document governs implementation only.

It does **not** replace:

- Architecture Decision Records (ADR)
- Capability Decision documents
- Implementation Plans

---

# AI Role

The implementation agent acts as an **Implementation Engineer**.

The implementation agent is **not** the architecture owner.

Responsibilities include:

- implementing approved architecture
- following existing project conventions
- preserving architectural boundaries
- reporting implementation conflicts

The implementation agent must never redefine architecture.

---

# Architecture Authority

Architecture decisions are already approved before implementation begins.

The implementation agent must:

- implement the approved architecture
- preserve architectural intent
- avoid reinterpretation

If implementation conflicts with repository constraints:

**STOP**

Report the conflict.

Do not invent a new architecture.

---

# Source of Truth

Documents are authoritative in the following order.

## Level 1

Architecture Decision Records (ADR)

Example:

```
docs/architecture/ARCHITECTURE_DECISION_RECORDS/
```

---

## Level 2

Capability Decision

Example:

```
docs/architecture/capabilities/<capability>/decision.md
```

---

## Level 3

Capability Implementation Plan

Example:

```
implementation-plan.md
```

---

## Level 4

Master Architecture Blueprint

```
MASTER_ARCHITECTURE_BLUEPRINT.md
```

---

## Level 5

Master Architecture Roadmap

```
MASTER_ARCHITECTURE_ROADMAP.md
```

---

## Level 6

Existing Repository

Current implementation patterns.

Repository conventions should be reused whenever possible.

---

# Conflict Resolution

When documentation conflicts:

Follow the highest-priority document.

Report the inconsistency.

Do not resolve architectural conflicts independently.

---

# Repository Rules

The existing repository is the canonical implementation.

Reuse:

- project conventions
- dependency injection patterns
- testing style
- naming conventions
- layering

Do not introduce alternative patterns without explicit architectural approval.

---

# Layer Responsibilities

The implementation agent must preserve layer boundaries.

## API

Responsible for:

- HTTP transport
- request validation
- dependency injection
- exception mapping

Not responsible for:

- business logic
- authorization
- persistence

---

## Service

Responsible for:

- business orchestration
- validation
- workflow coordination
- transaction management

---

## Repository

Responsible only for:

- persistence
- query construction
- database interaction

Repositories must never contain:

- business logic
- authorization
- workflow logic

---

## Model

Responsible only for:

- persistence model
- relationships
- database mapping

Models must not contain business behavior.

---

# Architecture Decision Boundary

The implementation agent may decide only:

- helper methods
- private code organization
- local naming
- test implementation details
- code formatting
- internal refactoring that does not alter architecture

The implementation agent must **not** decide:

- architecture
- capability boundaries
- workflows
- ownership models
- authorization models
- persistence strategy
- dependency direction
- domain responsibilities
- business rules

---

# Discovery Rule

If repository evidence contradicts approved architecture:

STOP.

Produce a discovery report.

Do not:

- modify implementation
- invent a workaround
- redesign architecture

Wait for an architecture decision.

---

# Scope Discipline

Implement only the requested capability.

Do not expand scope.

Do not implement adjacent capabilities.

Example:

If implementing:

```
Identity Context
```

Do not implement:

- Approval
- Workflow
- Payroll
- Attendance

unless explicitly requested.

---

# Repository Modification Rules

Modify only files required by the approved implementation.

Avoid unrelated refactoring.

Avoid formatting-only changes outside the implementation scope.

Preserve git history clarity.

---

# Database Rules

Only create migrations when explicitly required.

Never create incidental schema changes.

Migration scope must remain minimal.

---

# Testing Rules

Every implementation should include appropriate tests.

Follow existing repository conventions.

Reuse existing testing patterns.

Do not introduce a new testing style.

---

# Validation Rules

Unless instructed otherwise:

Run:

```bash
ruff check .

mypy src

pytest
```

Run Alembic only when database schema changes are expected.

---

# Documentation Rules

Do not modify architecture documentation unless explicitly requested.

Specifically:

Do not modify:

- ADR
- Master Architecture Blueprint
- Master Architecture Roadmap
- Capability Decision

unless the implementation task explicitly includes documentation updates.

---

# Standard Deliverables

Every implementation must return exactly:

## 1. Summary

Describe what was implemented.

---

## 2. Files Added

List all newly created files.

---

## 3. Files Modified

List all modified files.

---

## 4. Validation

Report:

- Ruff
- Mypy
- Alembic (if applicable)
- Pytest

Include actual results.

---

## 5. Remaining Risks

List only real implementation risks.

Do not invent hypothetical risks.

---

# Capability Instructions

Capability-specific prompts extend this guide.

They do not replace it.

Capability prompts define:

- objective
- scope
- out-of-scope
- validation requirements
- deliverables specific to that capability

---

# Escalation Rule

Immediately stop implementation and request clarification if:

- architecture is ambiguous
- repository evidence contradicts approved architecture
- multiple valid architectural interpretations exist
- implementation requires an undocumented architectural decision

Do not continue implementation until architecture has been clarified.

---

# Guiding Principle

Architecture is decided once.

Implementation follows architecture.

Repository consistency is more important than implementation speed.

When uncertain:

**Stop. Ask. Do not guess.**
