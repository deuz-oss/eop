# Monetary Representation — Adoption Policy Decision

**Status:** Approved

**Capability:** Monetary Representation

**Document Type:** Consumer Adoption Policy

**Owner:** EOP Architecture Governance

**Date:** 2026-08-07

---

# 1. Purpose

This document defines how future EOP capabilities must adopt the Monetary Representation capability.

The purpose is to ensure monetary values are represented consistently while preserving business ownership boundaries.

This document does not introduce:

- new monetary business rules
- payroll rules
- compensation rules
- accounting rules
- currency conversion behavior

---

# 2. Context

The Monetary Representation capability provides a foundation monetary type contract.

The implemented foundation type:

Money

provides:

- monetary value representation
- precision consistency
- rounding normalization
- currency context preservation

The capability does not own business meaning.

---

# 3. Adoption Decision

## Decision

Future capabilities that introduce monetary concepts MUST use:

Money

as the monetary representation contract.

---

## Rationale

Without a shared monetary contract, consumers may independently create:

- Decimal amount fields
- amount + currency string combinations
- custom rounding behavior
- inconsistent precision handling

This creates monetary inconsistency across capabilities.

---

# 4. Consumer Responsibility Boundary

## Monetary Representation Owns

Monetary Representation owns:

- monetary value structure
- approved precision handling
- currency context preservation
- monetary representation consistency

---

## Consumer Capability Owns

Consumer capabilities own:

- business meaning
- calculation rules
- domain workflows
- business validation

Examples:

Compensation owns:

- salary definition
- allowance rules
- bonus rules

Payroll owns:

- payroll calculation
- statutory calculation
- payment determination

---

# 5. Required Adoption Rules

## Rule 1 — Monetary Values Must Use Money

Required:

```python
Money(amount, currency)
Not allowed:
Decimal salary_amount
combined with:
currency = "IDR"
as separate unmanaged fields.
