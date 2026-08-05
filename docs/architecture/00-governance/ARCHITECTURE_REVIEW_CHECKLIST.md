# Architecture Review Checklist

**Status:** Active

**Owner:** EOP Architecture Governance

---

# Purpose

This document defines the mandatory architecture review checklist for every capability developed within EOP.

No capability may proceed to implementation until all applicable review items have been completed.

The checklist exists to ensure architectural consistency across the entire platform.

---

# Architecture Lifecycle

Every capability follows the same lifecycle.

```
Discovery
    ↓
Decision
    ↓
ADR
    ↓
Blueprint
    ↓
Roadmap
    ↓
Implementation Plan
    ↓
Architecture Review
    ↓
Implementation
    ↓
Architecture Audit
    ↓
Merge
```

---

# Review Categories

## 1. Repository Discovery

### Repository Evidence

- [ ] Repository inspected
- [ ] Existing implementation documented
- [ ] Existing dependencies identified
- [ ] Existing architecture identified

### Current State

- [ ] Capability boundary understood
- [ ] Current behavior documented
- [ ] Missing capability identified

### Repository Findings

- [ ] Findings documented
- [ ] Architectural ambiguities documented
- [ ] Open questions documented

---

## 2. Architecture Decision

### Capability

- [ ] Capability responsibility defined
- [ ] Capability boundary defined
- [ ] Out-of-scope documented

### Responsibilities

- [ ] Platform responsibilities defined
- [ ] Business responsibilities defined
- [ ] Repository responsibilities defined

### Dependencies

- [ ] Upstream dependencies defined
- [ ] Downstream dependencies defined
- [ ] Dependency direction approved

---

## 3. ADR

### Architecture Decision Record

- [ ] ADR written
- [ ] Context documented
- [ ] Decision documented
- [ ] Consequences documented
- [ ] Alternatives documented

---

## 4. Blueprint

- [ ] Master Architecture Blueprint updated
- [ ] Capability added
- [ ] Dependencies updated
- [ ] Layer placement verified

---

## 5. Roadmap

- [ ] Roadmap updated
- [ ] Capability sequencing approved
- [ ] Dependencies reflected

---

## 6. Implementation Plan

- [ ] Implementation scope approved
- [ ] Out-of-scope defined
- [ ] Acceptance criteria defined
- [ ] Validation steps documented

---

## 7. Architecture Review

### Architecture

- [ ] No duplicated responsibility
- [ ] No capability overlap
- [ ] No circular dependency
- [ ] Layering preserved

### Platform

- [ ] Business-independent
- [ ] Transport-independent
- [ ] Persistence-independent (where applicable)

### Repository

- [ ] Repository remains persistence-only
- [ ] Service owns business logic
- [ ] API owns transport only

---

## 8. Implementation

Before implementation begins:

- [ ] Claude implementation guide attached
- [ ] Capability implementation plan attached
- [ ] ADR attached
- [ ] Discovery attached

---

## 9. Architecture Audit

After implementation:

- [ ] Architecture matches ADR
- [ ] Architecture matches Decision
- [ ] Architecture matches Implementation Plan

No undocumented architecture changes introduced.

---

## 10. Validation

Required validation completed.

- [ ] Ruff
- [ ] Mypy
- [ ] Alembic (if applicable)
- [ ] Pytest

---

## 11. Merge Review

Before merge:

- [ ] Architecture approved
- [ ] Tests passed
- [ ] Documentation updated
- [ ] No architecture drift detected

---

# Architecture Gate

A capability is considered **Ready for Implementation** only when:

- Repository Discovery is complete.
- Decision is approved.
- ADR is approved.
- Blueprint is updated.
- Roadmap is updated.
- Implementation Plan is approved.
- Architecture Review passes.

---

# Governance Rule

Implementation must never introduce new architecture.

Architecture must be completed before implementation begins.

If implementation reveals missing architectural decisions, implementation must stop until architecture is updated.

---

# Success Criteria

A capability passes architecture review only when:

- Responsibilities are clear.
- Boundaries are clear.
- Dependencies are clear.
- Repository layering is preserved.
- Architecture documentation is complete.
