# AGENTS.md

# Enterprise Operations Platform (EOP)

AI Engineering Constitution

Version: 1.0

---

# Purpose

This document defines the rules, constraints, engineering principles, and architectural standards that every AI agent must follow when contributing to Enterprise Operations Platform (EOP).

All AI-specific instruction files (CLAUDE.md, CODEX.md, COPILOT.md, GEMINI.md, etc.) inherit from this document.

If another AI instruction file conflicts with this document, AGENTS.md takes precedence.

---

# Project Mission

EOP is not a single application.

EOP is a reusable enterprise platform that provides common business capabilities through modular architecture.

The objective is to build reusable foundations first and business features second.

Every implementation should maximize:

* Maintainability
* Reusability
* Consistency
* Simplicity
* Long-term scalability

Avoid premature optimization.

Avoid unnecessary abstraction.

---

# Engineering Principles

## 1. Consistency Over Cleverness

Always prefer the implementation that matches existing project patterns.

Do not introduce a new pattern when an existing pattern already solves the problem.

---

## 2. Reuse Before Build

Before creating new infrastructure, verify whether a foundation already exists.

Current reusable foundations:

* Authentication
* RBAC
* Dashboard
* Pagination
* Search
* Audit Log
* File Storage
* Background Jobs
* Notification

Reuse them.

Do not duplicate them.

---

## 3. Small Scope PRs

Each Pull Request should solve exactly one problem.

Good:

* Pagination Foundation
* Notification Foundation
* Audit Log Foundation

Bad:

* Pagination + Notification
* Notification + Refactor
* Refactor + API Redesign

---

## 4. Infrastructure First

Prefer building reusable infrastructure before module-specific implementations.

Good:

StorageProvider

Bad:

OrganizationAttachmentService directly talking to MinIO

---

# Architecture

Mandatory architecture:

```text
API
 ↓
Service
 ↓
Repository / Provider
 ↓
Database / External System
```

No layer skipping is allowed.

Forbidden:

```text
API → Repository
API → Database
API → SQLAlchemy Session

Service → SQLAlchemy Session

Business Module → Provider

Business Module → External SDK
```

---

# API Layer Rules

Responsibilities:

* Parse requests
* Validate input
* Call services
* Return responses

API routes must remain thin.

Routes must never contain:

* Business logic
* SQLAlchemy queries
* Repository access
* External provider access

---

# Service Layer Rules

Services own orchestration and business logic.

Services may:

* Coordinate repositories
* Coordinate providers
* Own UnitOfWork boundaries

Services must not:

* Access SQLAlchemy sessions directly
* Return ORM models to APIs
* Execute raw SQL

---

# Repository Rules

Repositories are persistence adapters.

Repositories may:

* Read data
* Write data
* Execute queries

Repositories must not:

* Perform authorization
* Perform business logic
* Call providers
* Call external systems

Keep repositories thin.

---

# Provider Rules

External systems must be hidden behind providers.

Examples:

* StorageProvider
* JobProvider
* NotificationProvider

Future integrations must follow the same pattern.

Never call:

* MinIO
* SMTP
* SendGrid
* Slack
* AWS SDK

directly from business modules.

---

# Dependency Injection

Preferred:

Constructor injection.

Singletons:

Use explicit module-level singleton instances.

Example:

```python
_provider = ExampleProvider()

def get_provider():
    return _provider
```

Do not use:

* functools.lru_cache
* service locators
* dependency injection frameworks
* global mutable registries

---

# Database Rules

Use SQLAlchemy ORM.

Use Alembic for schema migrations.

Every schema change requires a migration.

Before submitting:

```bash
alembic upgrade head
alembic check
```

Migration drift is not acceptable.

---

# Entity Rules

Prefer BaseEntity.

BaseEntity provides:

* UUID
* timestamps
* versioning
* audit fields
* soft delete fields

Only avoid BaseEntity when there is a strong architectural reason.

If deviating, document the reason.

---

# Authentication Rules

Always use:

* AuthService
* CurrentUser dependency

Never:

* Decode JWT manually
* Parse JWT in routes
* Parse JWT in repositories

---

# Authorization Rules

Always use:

* RequireRole(...)

Never:

* Hardcode role names inside services
* Implement custom RBAC logic

---

# Pagination Rules

Use:

* PaginationParams
* Pagination dependency
* Page[T]

Never create custom pagination implementations.

---

# Search Rules

Use:

* SearchParams
* BaseRepository search helpers

Never duplicate search functionality.

---

# File Storage Rules

Always go through:

FileService

Never communicate directly with:

StorageProvider

Never communicate directly with:

* MinIO
* S3
* Cloud Storage

---

# Notification Rules

Always use:

NotificationService

Never call NotificationProvider directly from business modules.

---

# Background Jobs Rules

Always use:

JobService

Never call JobProvider directly from business modules.

---

# Audit Log Rules

Always use:

AuditLogService

Never write audit records directly.

---

# Testing Requirements

Every feature must include tests.

Minimum requirements:

Infrastructure PR:

* Unit tests

Repository PR:

* Repository tests

Service PR:

* Service tests

API PR:

* API tests

---

# Validation Requirements

Before work is considered complete:

```bash
ruff check .
mypy src
pytest
```

All must pass.

No exceptions.

---

# Pull Request Requirements

Every PR must include:

## Summary

Explain what was implemented.

## Files Changed

List all modified files.

## Validation

Provide validation results.

## Remaining Risks

List known limitations.

---

# Commit Policy

AI agents must never:

* Commit automatically
* Push automatically
* Merge automatically

Unless explicitly instructed.

---

# Documentation Rules

If architecture changes:

Update documentation.

If a foundation is added:

Update documentation.

Do not allow docs to drift from implementation.

---

# Refactoring Policy

Do not perform unrelated refactors.

Do not "clean up" neighboring code.

Do not rename files without justification.

Stay within scope.

---

# Performance Policy

Do not introduce:

* caching
* indexing
* batching
* async processing

unless explicitly requested.

Prefer correctness and simplicity first.

---

# Observability Policy

Future observability features must be added as reusable foundations.

Do not embed logging, metrics, or tracing logic directly inside business modules.

---

# Security Policy

Never:

* hardcode secrets
* commit credentials
* disable authentication
* bypass authorization

Development defaults are acceptable only when clearly marked.

---

# Decision Framework

When multiple solutions exist:

1. Reuse an existing foundation.
2. Choose the simplest implementation.
3. Choose the most maintainable implementation.
4. Match existing project architecture.
5. Avoid introducing new patterns.

Consistency is more valuable than novelty.

---

# Final Rule

The goal is not to write the most sophisticated code.

The goal is to build a platform that remains understandable, maintainable, and extensible years from now.

When in doubt:

Choose the simpler solution.
