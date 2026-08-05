# EOP Architecture Documentation

**Status:** Active

**Version:** 1.0

**Owner:** EOP Architecture Governance

---

# Purpose

This directory contains the architectural knowledge of the EOP platform.

Its purpose is to ensure that architecture:

- is explicitly documented
- evolves consistently
- remains independent of implementation
- can be understood without relying on historical conversations

This directory is the architectural source of truth for EOP.

---

# Architecture Philosophy

EOP follows a strict separation between:

```
Discovery

↓

Architecture

↓

Implementation

↓

Review
```

Each phase has a different responsibility.

Architecture is documented before implementation.

Implementation follows architecture.

Architecture is never inferred from implementation.

---

# Architecture Lifecycle

Every significant capability follows the same lifecycle.

```
Repository Discovery

↓

Capability Discovery

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

# Repository Structure

```
docs/
└── architecture/
    │
    ├── README.md
    │
    ├── ARCHITECTURE_GOVERNANCE.md
    ├── AI_DISCOVERY_GUIDE.md
    ├── CLAUDE_IMPLEMENTATION_GUIDE.md
    │
    ├── MASTER_ARCHITECTURE_BLUEPRINT.md
    ├── MASTER_ARCHITECTURE_ROADMAP.md
    │
    ├── ARCHITECTURE_DECISION_RECORDS/
    │
    ├── capabilities/
    │
    └── templates/
```

---

# Document Overview

## README.md

Entry point for the architecture repository.

Start reading here.

---

## ARCHITECTURE_GOVERNANCE.md

Defines the architecture governance process.

Describes:

- roles
- responsibilities
- development lifecycle
- review process
- architecture authority

Read before contributing.

---

## AI_DISCOVERY_GUIDE.md

Defines how repository discovery is performed.

Applies to:

- repository audits
- architecture inventory
- dependency analysis
- capability discovery

Discovery produces evidence only.

---

## CLAUDE_IMPLEMENTATION_GUIDE.md

Defines implementation governance.

Applies to:

- implementation
- testing
- repository modification

Implementation follows approved architecture.

---

## MASTER_ARCHITECTURE_BLUEPRINT.md

Defines the current architecture of the platform.

Contains:

- capability map
- dependency graph
- platform architecture
- layer boundaries

Represents the current architecture.

---

## MASTER_ARCHITECTURE_ROADMAP.md

Defines the architectural evolution of EOP.

Contains:

- implementation phases
- future capabilities
- architectural milestones

Represents future architecture.

---

## ARCHITECTURE_DECISION_RECORDS

Stores permanent architecture decisions.

Each ADR documents:

- context
- decision
- consequences

ADRs are immutable historical records.

---

## capabilities

Each capability owns its own architecture.

Typical structure:

```
<capability>/

    discovery.md

    decision.md

    implementation-plan.md
```

Additional documents may be added when necessary.

---

## templates

Provides reusable templates.

Templates include:

- ADR template
- Capability template

New capabilities should begin from these templates.

---

# Reading Order

For new contributors:

1.

```
README.md
```

↓

2.

```
ARCHITECTURE_GOVERNANCE.md
```

↓

3.

```
MASTER_ARCHITECTURE_BLUEPRINT.md
```

↓

4.

```
MASTER_ARCHITECTURE_ROADMAP.md
```

↓

5.

Relevant capability documents

↓

6.

Relevant ADR

---

# Capability Workflow

Every capability follows:

```
Discovery

↓

decision.md

↓

ADR (if required)

↓

implementation-plan.md

↓

Implementation

↓

Architecture Review
```

This workflow is mandatory.

---

# Source of Truth

Architecture documents are authoritative in the following order.

Level 1

Architecture Decision Records

↓

Level 2

Capability Decision

↓

Level 3

Implementation Plan

↓

Level 4

Master Architecture Blueprint

↓

Level 5

Master Architecture Roadmap

↓

Level 6

Existing Repository

Repository implementation must follow approved architecture.

---

# Repository Governance

Architecture documentation should evolve independently from production code whenever practical.

Recommended workflow:

```
Architecture Branch

↓

Architecture Review

↓

Merge

↓

Implementation Branch

↓

Implementation Review

↓

Merge
```

This preserves a clear separation between architecture and implementation.

---

# AI-Assisted Development

EOP supports AI-assisted development.

AI operates in two modes.

## Discovery

Governed by:

```
AI_DISCOVERY_GUIDE.md
```

Role:

Repository Analyst

Produces:

- evidence
- findings
- dependency analysis

Does not produce architecture.

---

## Implementation

Governed by:

```
CLAUDE_IMPLEMENTATION_GUIDE.md
```

Role:

Implementation Engineer

Produces:

- production code
- tests
- documentation updates (when requested)

Does not redesign architecture.

---

# Architecture Principles

The following principles apply throughout EOP.

1.

Architecture precedes implementation.

2.

Discovery precedes architecture.

3.

Repository evidence precedes architectural decisions.

4.

Architecture is documented.

5.

Architecture evolves through ADR.

6.

Implementation follows architecture.

7.

Architecture review precedes merge.

---

# Contributing

Before implementing a new capability:

1.

Perform discovery.

2.

Review existing architecture.

3.

Review relevant ADR.

4.

Review the capability decision.

5.

Review the implementation plan.

6.

Implement according to governance.

---

# Future Evolution

This architecture repository is expected to evolve over time.

Future additions may include:

- Architecture Review Checklist
- Technical Debt Register
- Architecture Metrics
- Capability Maturity Model
- Architecture Decision Index
- Dependency Heatmap

These documents extend the governance process without replacing it.

---

# Guiding Principle

Architecture is a product.

It evolves intentionally.

Discovery provides evidence.

Architecture provides direction.

Implementation provides execution.

Review preserves consistency.

The repository remains the single source of truth.
