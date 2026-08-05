# Architecture Governance

**Status:** Active

**Version:** 1.0

**Owner:** EOP Architecture Governance

---

# Purpose

This document defines how architecture is governed within EOP.

Architecture governance ensures that:

- architectural decisions are explicit
- implementation follows approved architecture
- repository evolution remains consistent
- AI-assisted development follows a predictable workflow

This document governs the development process.

It does not define application architecture.

---

# Governance Principles

Architecture follows four principles.

## 1. Architecture Before Implementation

Implementation must never precede architecture.

Every significant capability must have:

- discovery
- architecture decision
- implementation plan

before production code is written.

---

## 2. Evidence Before Decision

Architecture decisions must be based on repository evidence.

Discovery produces evidence.

Architecture interprets evidence.

Implementation follows architecture.

---

## 3. Single Source of Truth

The repository is the authoritative source of architecture.

Architecture must be committed before implementation begins.

Architecture must never exist only in conversation.

---

## 4. Explicit Decisions

Significant architectural decisions must be documented.

Undocumented architecture is considered undefined.

---

# Development Lifecycle

Every capability follows the same lifecycle.

```
Discovery

↓

Architecture Decision

↓

ADR (when required)

↓

Implementation Plan

↓

Implementation

↓

Architecture Review

↓

Merge
```

No phase should be skipped.

---

# Roles

## Human

Responsible for:

- product direction
- business priorities
- final approval
- repository ownership

The human remains the final decision maker.

---

## ChatGPT

Role:

Architecture Owner

Responsible for:

- repository analysis
- architecture decisions
- ADR
- blueprint evolution
- roadmap evolution
- implementation planning
- architecture review

Not responsible for:

- production implementation
- repository editing
- committing code

---

## Claude

Role:

Implementation Engineer

Responsible for:

- repository discovery
- implementation
- testing
- documentation updates when requested

Not responsible for:

- architecture decisions
- redesign
- roadmap ownership
- business decisions

---

## Repository

The repository is the canonical source of truth.

Every architecture decision must exist in the repository.

---

# Architecture Workflow

## Phase 1

Discovery

Purpose:

Understand the current repository.

Output:

- repository evidence
- findings
- ambiguities

Governed by:

```
AI_DISCOVERY_GUIDE.md
```

---

## Phase 2

Architecture Decision

Purpose:

Resolve architectural ambiguity.

Output:

- capability decision
- ADR (if needed)

Governed by:

Architecture Governance.

---

## Phase 3

Implementation Planning

Purpose:

Convert architecture into an implementation strategy.

Output:

```
implementation-plan.md
```

No production code.

---

## Phase 4

Implementation

Purpose:

Implement approved architecture.

Governed by:

```
CLAUDE_IMPLEMENTATION_GUIDE.md
```

---

## Phase 5

Architecture Review

Purpose:

Verify:

- ADR compliance
- blueprint compliance
- repository consistency

Implementation is reviewed before merge.

---

# Architecture Artifacts

The repository contains several architecture artifacts.

## Master Documents

```
MASTER_ARCHITECTURE_BLUEPRINT.md

MASTER_ARCHITECTURE_ROADMAP.md
```

---

## Architecture Decisions

```
ARCHITECTURE_DECISION_RECORDS/
```

---

## Capability Documents

Each capability owns:

```
discovery.md

decision.md

implementation-plan.md
```

---

## Governance Documents

```
ARCHITECTURE_GOVERNANCE.md

AI_DISCOVERY_GUIDE.md

CLAUDE_IMPLEMENTATION_GUIDE.md
```

---

# Source of Truth

Architecture documents are authoritative in this order.

## Level 1

ADR

---

## Level 2

Capability Decision

---

## Level 3

Implementation Plan

---

## Level 4

Master Architecture Blueprint

---

## Level 5

Master Architecture Roadmap

---

## Level 6

Repository

---

# Decision Ownership

Architecture decisions belong only to:

- Human
- Architecture Owner

Implementation agents must never create new architecture.

---

# Repository Modification Rules

Architecture documents must be modified only when:

- architecture changes
- governance changes
- capability decisions change

Implementation must not silently modify architecture.

---

# Discovery Governance

Discovery exists to understand.

Discovery must not:

- redesign architecture
- implement code
- update roadmap
- modify ADR

Discovery produces evidence only.

---

# Implementation Governance

Implementation exists to execute approved architecture.

Implementation must:

- follow ADR
- follow implementation plan
- preserve architectural boundaries

Implementation must not:

- redesign architecture
- infer business rules
- expand scope

---

# Architecture Escalation

Stop implementation immediately when:

- architecture is ambiguous
- repository contradicts ADR
- repository contradicts capability decisions
- implementation requires a new architectural decision

Return the conflict.

Wait for Architecture Governance.

---

# Architecture Reviews

Architecture review verifies:

- ADR compliance
- capability boundary compliance
- dependency direction
- repository consistency
- architectural integrity

Architecture review is required before merge for significant capabilities.

---

# Branch Strategy

Architecture work and implementation work should be isolated.

Recommended flow:

```
main

↓

architecture/<capability>

↓

merge

↓

feature/<capability>

↓

merge
```

Architecture becomes repository truth before implementation begins.

---

# Pull Request Expectations

Architecture PRs contain:

- ADR
- blueprint updates
- roadmap updates
- capability decisions

Implementation PRs contain:

- production code
- tests
- migrations (when required)

Architecture and implementation should not be mixed unless explicitly approved.

---

# AI Governance

AI assistance is divided into two modes.

## Discovery Mode

Governed by:

```
AI_DISCOVERY_GUIDE.md
```

Role:

Repository Analyst

---

## Implementation Mode

Governed by:

```
CLAUDE_IMPLEMENTATION_GUIDE.md
```

Role:

Implementation Engineer

---

# Future Evolution

Future governance may include:

- Architecture Compliance Checklist
- ADR Template
- Capability Template
- Technical Debt Register
- Architecture Review Checklist
- Release Governance

These documents extend this governance model.

---

# Guiding Principles

Architecture is designed once.

Architecture is documented.

Architecture is committed.

Implementation follows architecture.

Review verifies architecture.

The repository preserves architecture.

When uncertainty exists:

**Discover first. Decide second. Implement third.**
