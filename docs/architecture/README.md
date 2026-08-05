# EOP Architecture Documentation

**Status:** Active

---

# Purpose

This directory contains the complete architectural documentation for the EOP platform.

The documentation describes:

- architectural vision
- architecture principles
- governance
- capability architecture
- architecture decisions
- implementation guidance

This documentation is the authoritative source for platform architecture.

---

# Documentation Structure

```
architecture/
│
├── README.md
│
├── 00-governance/
│
├── 10-reference/
│
├── 20-templates/
│
├── adrs/
│
└── capabilities/
```

---

# Reading Order

New architects, developers, and AI assistants should read the documentation in the following order.

## 1. Vision

Start here.

Defines where the platform is going.

- ARCHITECTURE_VISION.md

---

## 2. Principles

Defines architectural philosophy.

- ARCHITECTURE_PRINCIPLES.md

---

## 3. Governance

Defines how architecture evolves.

Read:

- ARCHITECTURE_GOVERNANCE.md
- ARCHITECTURE_REVIEW_CHECKLIST.md
- ARCHITECTURE_STATUS.md
- ARCHITECTURE_CHANGELOG.md

---

## 4. Reference

Understand the existing architecture.

Read:

- REPOSITORY_CENSUS.md
- ARCHITECTURE_INVENTORY.md
- CAPABILITY_CATALOG.md
- CAPABILITY_DEPENDENCY_GRAPH.md
- MASTER_ARCHITECTURE_BLUEPRINT.md
- MASTER_ARCHITECTURE_ROADMAP.md

---

## 5. Templates

Before creating architecture documents.

Read:

- ADR_TEMPLATE.md
- CAPABILITY_TEMPLATE.md
- AI_DISCOVERY_GUIDE.md
- CLAUDE_IMPLEMENTATION_GUIDE.md

---

## 6. Architecture Decisions

Read all accepted ADRs.

Location

```
adrs/
```

---

## 7. Capability Documents

Each capability contains:

```
discovery.md

decision.md

implementation-plan.md
```

Location

```
capabilities/
```

---

# Documentation Categories

## Vision

Long-term architectural direction.

Examples

- Architecture Vision

---

## Governance

How architecture is managed.

Examples

- Architecture Governance
- Review Checklist
- Status
- Changelog

---

## Reference

Current architecture.

Examples

- Repository Census
- Architecture Inventory
- Blueprint
- Roadmap

---

## Templates

Reusable document templates.

Examples

- ADR Template
- Capability Template

---

## Decisions

Architectural decisions.

Examples

- ADR-001
- ADR-002
- ADR-007

---

## Capabilities

Capability-level architecture.

Each capability owns:

- Discovery
- Decision
- Implementation Plan

---

# Architecture Lifecycle

Every capability follows the same lifecycle.

```
Repository Discovery

↓

Architecture Decision

↓

ADR

↓

Blueprint Update

↓

Roadmap Update

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

Architecture always precedes implementation.

---

# AI Workflow

When using AI assistants:

1. Read Architecture Vision.

2. Read Architecture Principles.

3. Read Architecture Governance.

4. Read Blueprint.

5. Read Roadmap.

6. Read the target capability.

7. Read relevant ADRs.

8. Implement only the approved architecture.

AI must not introduce new architecture.

---

# Repository Governance

Architecture changes require:

- Repository evidence
- Architecture review
- Approved ADR
- Updated Blueprint
- Updated Roadmap
- Updated Changelog

---

# Directory Overview

## 00-governance

Platform governance.

Contains:

- Architecture Vision
- Principles
- Governance
- Status
- Changelog
- Review Checklist

---

## 10-reference

Repository reference.

Contains:

- Repository Census
- Architecture Inventory
- Capability Catalog
- Dependency Graph
- Blueprint
- Roadmap

---

## 20-templates

Reusable templates.

Contains:

- ADR Template
- Capability Template
- AI Discovery Guide
- Claude Implementation Guide

---

## adrs

Architecture Decision Records.

One document per accepted architecture decision.

---

## capabilities

Capability architecture.

Each capability contains:

- discovery.md
- decision.md
- implementation-plan.md

---

# Contribution Rules

Before changing architecture:

1. Complete Repository Discovery.
2. Document the decision.
3. Create or update the ADR.
4. Update Blueprint if required.
5. Update Roadmap if required.
6. Update Changelog.
7. Complete Architecture Review.
8. Proceed with implementation.

---

# Success Criteria

The architecture documentation is considered healthy when:

- every capability is documented
- every architectural decision has an ADR
- Blueprint matches implemented architecture
- Roadmap reflects planned evolution
- documentation stays synchronized with production code

This documentation serves as the authoritative architectural knowledge base for the EOP platform.
