# Capability Template

**Capability Name:**

```
<capability-name>
```

**Status:** Discovery | Architecture | Implementation | Completed

**Owner:** EOP Architecture Governance

---

# Purpose

Describe the business purpose of the capability.

Avoid implementation.

---

# Business Scope

Describe:

- what the capability owns
- what it does not own

Included:

-

-

-

Excluded:

-

-

- ***

# Repository Status

Current implementation status.

Examples:

- not implemented
- partially implemented
- complete

---

# Capability Lifecycle

Every capability follows:

```
Discovery

↓

Architecture Decision

↓

Implementation Plan

↓

Implementation

↓

Architecture Review

↓

Completed
```

---

# Capability Documents

Each capability owns:

```
discovery.md

decision.md

implementation-plan.md
```

Optional:

```
repository-census.md

dependency-analysis.md

open-questions.md
```

---

# Discovery

## Objective

Understand the current repository.

Produce repository evidence only.

---

## Deliverables

- repository evidence
- dependency analysis
- architectural ambiguities
- open questions

No design decisions.

---

# Architecture Decision

## Objective

Resolve architectural ambiguity.

Output:

- decision.md
- ADR (when required)

---

# Implementation Planning

## Objective

Convert approved architecture into implementation tasks.

Output:

```
implementation-plan.md
```

No production code.

---

# Implementation

Implementation must follow:

```
CLAUDE_IMPLEMENTATION_GUIDE.md
```

No architecture decisions.

---

# Architecture Review

Verify:

- ADR compliance
- repository consistency
- capability boundaries
- dependency direction

---

# Capability Boundaries

## Upstream Dependencies

List dependencies.

---

## Downstream Consumers

List consumers.

---

## Shared Platform Dependencies

List shared capabilities.

Examples:

- Identity
- Workflow
- Notification

---

# Open Questions

Repository evidence could not answer:

-

-

-

These require architecture decisions.

---

# Success Criteria

Capability is complete when:

- approved architecture implemented
- tests completed
- review completed
- documentation updated

---

# Standard Deliverables

Discovery:

- discovery.md

Architecture:

- decision.md
- ADR (if needed)

Implementation:

- implementation-plan.md
- production code
- tests

Review:

- architecture review summary

---

# Future Extensions

Document anticipated future enhancements.

Do not implement them here.

---

# Related Documents

Reference:

- ADR
- Master Architecture Blueprint
- Master Architecture Roadmap
- Architecture Governance
- AI Discovery Guide
- Claude Implementation Guide

---

# Notes

Capability documents describe one capability only.

Do not include unrelated features.

Avoid implementation details unless the document is specifically an implementation plan.
