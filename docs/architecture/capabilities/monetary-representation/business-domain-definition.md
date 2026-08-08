# Business Domain Definition

Capability: Monetary Representation

---

# Objective

Round 1 governance established Monetary Representation as a reusable architectural foundation rather than a business capability.

This document defines the business meaning and business requirements that consuming capabilities expect from Monetary Representation.

No repository evidence is re-evaluated.

No implementation mechanism is selected.

No architecture decision is made.

---

# Business Purpose

Monetary Representation exists to express monetary values consistently across the Human Resources and Payroll domains.

It does not represent business policy.

It does not calculate payroll.

It does not perform accounting.

It provides a common business language for monetary values.

---

# Business Concepts

## Monetary Amount

Represents a business value measured in money.

Examples:

- Base Salary
- Hourly Rate
- Daily Rate
- Housing Allowance
- Transport Allowance
- Meal Allowance
- Overtime Rate
- Benefit Amount
- Payroll Result
- Tax Amount
- Deduction Amount

The capability does not distinguish between these concepts.

It represents all of them uniformly.

---

## Currency

Every monetary amount belongs to exactly one currency.

Currency identifies the monetary system under which the value is interpreted.

Examples include:

- IDR
- USD
- SGD
- EUR

This capability does not define exchange rates.

---

## Monetary Precision

Business requires monetary values to preserve the precision supplied by the organization.

The exact precision is a business policy outside the scope of this capability.

This capability must be capable of representing monetary values without introducing ambiguity.

---

## Monetary Equality

Two monetary values are comparable only when they represent the same currency.

Business comparison across different currencies requires additional business policy outside this capability.

---

## Monetary Identity

A monetary value has no independent business identity.

Its meaning exists only within the business object that owns it.

Examples:

- Compensation owns Salary.
- Payroll owns Gross Pay.
- Benefit owns Benefit Amount.

Monetary Representation never owns those business concepts.

---

# Business Responsibilities

Monetary Representation is responsible for representing:

- monetary amount
- currency
- equality
- ordering
- display-ready business value

It is not responsible for:

- exchange rates
- taxation
- payroll calculation
- accounting
- rounding policy
- compensation policy
- allowance policy
- deduction policy

---

# Business Scenarios

## Hiring

HR records a starting salary.

Monetary Representation represents the salary value.

It does not determine whether the salary is appropriate.

---

## Annual Salary Increase

Compensation replaces one salary with another.

Monetary Representation represents both values.

It does not determine why the salary changed.

---

## Payroll Calculation

Payroll consumes multiple monetary values.

Examples:

- salary
- allowance
- overtime
- deduction

Monetary Representation represents each value independently.

Payroll determines how they are combined.

---

## International Employee

Two employees may have identical numeric values expressed in different currencies.

Business interpretation differs.

Currency remains part of the represented value.

Currency conversion belongs elsewhere.

---

## Reporting

Reports display monetary values consistently.

Formatting policy belongs to presentation.

Monetary Representation supplies the underlying business value.

---

# Capability Boundary

Owns:

- monetary amount representation
- currency association
- monetary comparison semantics

Consumes:

Nothing.

Provides:

- Compensation
- Payroll Calculation
- Payslip
- Benefits
- Future financial capabilities

---

# Business Constraints

A monetary value always has:

- an amount
- a currency

A monetary value never exists without business context.

A monetary value never defines business rules.

A monetary value never determines business policy.

---

# Out of Scope

This capability intentionally does not define:

- exchange rates
- currency conversion
- payroll formulas
- accounting rules
- taxation
- benefit calculation
- salary bands
- compensation approval
- effective dating
- audit history

These belong to consuming capabilities or separate foundation capabilities.

---

# Business Questions Remaining

The following questions require business decisions before architecture decisions:

- Which currencies must the organization support?
- What monetary precision is required?
- What business rounding policy applies?
- Are fractional currency units required?
- Is cross-currency comparison ever permitted?
- Are presentation rules standardized across the organization?

These questions define business policy.

They do not change the capability boundary.

---

# Summary

Monetary Representation is the common business language for monetary values.

It represents money consistently.

It owns no business policy.

It owns no business process.

It enables every consuming capability to speak the same monetary language without duplicating monetary semantics.
