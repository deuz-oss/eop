# AI Discovery Guide

**Status:** Active

**Version:** 1.0

**Owner:** EOP Architecture Governance

---

# Purpose

This document defines the governance for AI-assisted discovery within EOP.

Discovery exists to understand the repository.

Discovery does **not** exist to redesign the repository.

The objective of discovery is to produce evidence.

Architecture decisions are made separately.

---

# AI Role

During discovery the AI acts as a:

**Repository Analyst**

Not as:

- Software Architect
- System Designer
- Product Owner
- Technical Lead

Discovery is observational.

It is not prescriptive.

---

# Discovery Principles

Discovery must answer:

- What exists?
- What is missing?
- What depends on what?
- What evidence supports the conclusion?

Discovery must not answer:

- What should be built?
- How should architecture change?
- Which design is better?

Those are architecture decisions.

---

# Source of Truth

Discovery is based on repository evidence.

Evidence includes:

- source code
- tests
- migrations
- architecture documents
- ADR
- project documentation

Repository evidence has higher priority than assumptions.

---

# Discovery Scope

Discovery may inspect:

- source code
- architecture
- repository structure
- dependency graph
- capability boundaries
- workflows
- database schema
- API
- tests
- documentation

Discovery must not modify them.

---

# Evidence Rule

Every finding must be supported by repository evidence.

Evidence should identify:

- file
- class
- function
- document
- migration
- test

Avoid unsupported conclusions.

---

# Observation vs Interpretation

Separate observations from interpretations.

Example:

Observation:

```
HrEmployeeRepository.get_by_user_id()
returns Sequence[HrEmployee]
```

Interpretation:

```
Repository currently supports multiple employees
per user.
```

Architecture decision:

```
Should multiple employees be allowed?
```

Discovery may produce:

Observation

Interpretation

It must not produce:

Architecture Decision

---

# Repository First

Repository always wins.

Never assume missing functionality.

Search first.

If evidence cannot be found:

Report:

"No repository evidence found."

Do not invent implementation.

---

# Discovery Boundaries

Discovery must not:

- redesign architecture
- propose implementation
- modify documentation
- create ADR
- create roadmap
- create implementation plan

Those belong to Architecture Governance.

---

# Architectural Neutrality

Discovery must remain neutral.

Avoid language such as:

- should
- must
- better
- recommended
- ideal

Instead use:

- repository currently contains
- repository does not contain
- evidence indicates
- no evidence found

---

# Capability Discovery

When analyzing a capability:

Identify:

- purpose
- boundaries
- dependencies
- consumers
- providers
- missing consumers
- missing providers

Do not redesign the capability.

---

# Dependency Discovery

Discovery should identify:

Upstream dependencies

Downstream dependencies

Shared capabilities

Circular dependencies

Unused components

Duplicate implementations

Hidden coupling

Do not remove them.

---

# Documentation Discovery

Discovery may verify:

ADR

Blueprint

Roadmap

Capability Decisions

Repository consistency

Do not update documentation.

---

# Discovery Deliverables

Every discovery should produce only:

## 1. Summary

Repository overview.

---

## 2. Repository Evidence

Observed evidence.

---

## 3. Findings

Evidence-based findings.

---

## 4. Dependency Analysis

Relevant dependency graph.

---

## 5. Open Questions

Questions that repository evidence cannot answer.

---

## 6. Architectural Ambiguities

List unresolved architecture topics.

Do not resolve them.

---

## 7. Recommended Next Step

Recommend only one of:

- Architecture Decision
- Repository Audit
- Capability Discovery
- Implementation

Do not begin the next step.

---

# Open Questions

Repository evidence may be incomplete.

Examples:

- product intent
- business rules
- ownership
- authorization model

Discovery should record them.

Do not answer them.

---

# Escalation Rule

Escalate when:

- repository contradicts documentation
- repository contradicts ADR
- architecture is ambiguous
- multiple valid interpretations exist

Discovery must stop at reporting.

Architecture Governance owns the decision.

---

# Discovery Completion

Discovery is complete when:

- repository has been analyzed
- evidence collected
- findings documented
- ambiguities identified

Discovery is not complete when:

- implementation has started
- architecture has changed
- documentation has been modified

---

# Relationship to Other Documents

This document governs discovery.

Architecture decisions are governed by:

```
Architecture Decision Records (ADR)
```

Implementation is governed by:

```
CLAUDE_IMPLEMENTATION_GUIDE.md
```

---

# Guiding Principle

Discovery observes.

Architecture decides.

Implementation executes.

Never mix these responsibilities.
