# Claude Implementation Guide

## Purpose

This guide defines how implementation must be performed.

Architecture is defined elsewhere.

Claude implements approved architecture.

Claude does not create architecture.

---

# Required Inputs

Before implementation, read:

1. ADR(s)
2. Capability Discovery
3. Policy Discovery (if present)
4. Capability Decision
5. Implementation Plan

If any required document is missing:

STOP.

Do not implement.

---

# Authority Order

Implementation shall follow this order.

1. ADR
2. Capability Decision
3. Implementation Plan
4. Repository

Higher-level documents always take precedence.

---

# Implementation Rules

Implement exactly what has been approved.

Do not:

- redesign architecture
- extend scope
- simplify business rules
- introduce new abstractions
- infer missing behavior

---

# Repository Rules

Repository evidence supports implementation.

Repository evidence does not override approved architecture.

If repository contradicts approved architecture:

STOP.

Escalate.

---

# Escalation Rules

Stop implementation immediately if:

- business rules are missing
- architecture is ambiguous
- implementation requires a new capability
- implementation contradicts an ADR
- implementation contradicts the Capability Decision
- implementation requires assumptions

Never resolve ambiguity by assumption.

---

# Deliverables

When implementation is complete, provide only:

1. Summary
2. Files Added
3. Files Modified
4. Validation
5. Remaining Risks

---

# Validation

Run all validation required by the Implementation Plan.

Typical validation includes:

- Ruff
- Mypy
- Alembic
- Pytest

---

# Architecture Review Checklist

Before completion, verify:

- approved architecture unchanged
- layering preserved
- repository contains persistence only
- services contain business logic only
- APIs contain transport logic only
- no inferred business rules
- no scope expansion

---

# Completion Criteria

Implementation is complete only when:

- Implementation Plan is fully satisfied.
- Validation succeeds.
- No unresolved ambiguity remains.
- No architectural decisions were made during implementation.
