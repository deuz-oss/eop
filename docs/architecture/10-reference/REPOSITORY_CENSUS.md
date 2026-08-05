# EOP Repository Census

**Status:** Active

**Version:** 2.0

**Last Updated:** YYYY-MM-DD

**Owner:** EOP Architecture Governance

---

# Purpose

Repository Census is the authoritative inventory of the EOP source repository.

It documents what currently exists in the repository.

It intentionally contains no architectural decisions.

Architecture decisions belong to ADRs.

Repository Census records implementation reality.

---

# Repository Overview

Repository Name

```
eop
```

Architecture

```
Layered Architecture

Repository Pattern

Unit of Work

Capability-Oriented Platform
```

Primary Language

```
Python
```

Framework

```
FastAPI

SQLAlchemy

Alembic

Pydantic
```

Testing

```
pytest
```

Static Analysis

```
ruff

mypy
```

---

# Repository Structure

```
docs/

services/

frontend/

docker/

scripts/

.github/
```

---

# Services

## API

Location

```
services/api
```

Responsibilities

- REST API
- Business Services
- Persistence
- Authentication

---

# Source Layout

```
api/

models/

repositories/

services/

schemas/

dependencies/

core/

database/

unit_of_work/

security/
```

---

# Existing Platform Capabilities

## Authentication

Status

```
Implemented
```

Primary Components

- JWT
- CurrentUser
- AuthenticationService

---

## Identity Context

Status

```
Implemented
```

Primary Components

- EmployeeContext
- RequestContext
- EmployeeContextResolver

---

## Authorization Foundation

Status

```
Architecture Approved

Implementation In Progress
```

---

# Existing Business Capabilities

HR

Implemented

- Job Grade
- Employment Type
- Employment Status
- Shift
- Holiday
- HR Employee

Operational

Implemented

- Leave
- Timesheet
- Overtime
- Approval
- Reconciliation

---

# Existing Infrastructure

Authentication

Authorization (partial)

Dependency Injection

Unit of Work

Repository Pattern

Database Migration

Logging

Validation

---

# Existing Architectural Layers

```
API

↓

Service

↓

Unit Of Work

↓

Repository

↓

Database
```

Layering is consistent across the repository.

---

# Existing Database

Migration Tool

```
Alembic
```

ORM

```
SQLAlchemy
```

Entity Base

```
BaseEntity
```

---

# Existing Testing

Repository Tests

Service Tests

API Tests

Integration Tests

---

# Existing Documentation

Architecture Governance

Architecture Inventory

Capability Dependency Graph

Master Architecture Blueprint

Master Architecture Roadmap

ADRs

Capability Documents

---

# Existing Standards

Repository Pattern

Unit Of Work

Dependency Injection

Service Layer

Pydantic Schemas

FastAPI Routing

---

# Repository Health

## Layering

✅ Consistent

## Repository Pattern

✅ Consistent

## Service Layer

✅ Consistent

## Unit Of Work

✅ Consistent

## Authentication

✅ Complete

## Identity Context

✅ Complete

## Authorization

🟡 Platform Approved

Implementation In Progress

---

# Repository Metrics

Maintain high-level metrics only.

Example:

| Metric             | Value |
| ------------------ | ----- |
| Production Modules | —     |
| Models             | —     |
| Services           | —     |
| Repositories       | —     |
| API Routers        | —     |
| Alembic Migrations | —     |
| Tests              | —     |

Avoid documenting volatile implementation counts unless periodically refreshed.

---

# Known Architectural Gaps

Current gaps include:

- Authorization integration
- Manager authorization
- Workflow authorization
- Permission model

These gaps are intentional and tracked by the architecture roadmap.

---

# Repository Evolution

Repository Census should be updated when:

- new capability introduced
- platform capability added
- repository structure changes
- new architectural layer added

Routine implementation changes should not require Repository Census updates.

---

# Relationship to Other Documents

Repository Census documents:

> What exists.

Architecture Inventory documents:

> How the repository is organized.

Master Architecture Blueprint documents:

> Target architecture.

Master Architecture Roadmap documents:

> Planned evolution.

ADRs document:

> Architectural decisions.
