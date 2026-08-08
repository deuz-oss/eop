# Compensation — Business Domain Definition

**Status:** Draft — Business Input Required

**Capability:** Compensation

**Purpose:**
Define the business meaning, scope, and unresolved business decisions of Compensation before Architecture Decision Round 2.

---

# 1. Business Meaning

Compensation represents an employee's agreed monetary terms of employment as they apply during a defined period.

It describes what the organization has committed to provide to an employee.

It does not represent:

- payroll calculation results
- payment transactions
- payslip output
- payroll execution
- deductions processing

---

# 2. Business Boundary

## Compensation Owns

- employee compensation terms
- agreed monetary basis
- effective compensation changes
- compensation change reasons

## Compensation Does Not Own

- payroll calculation rules
- tax calculation
- payment execution
- payroll results
- payslip presentation
- attendance-based calculation

---

# 3. Core Business Concepts

| Concept          | Status              | Notes                                       |
| ---------------- | ------------------- | ------------------------------------------- |
| Base Salary      | Candidate Core      | Applicable for salaried employees           |
| Hourly Rate      | Candidate Core      | Applicable for hourly employees             |
| Currency         | Required Dependency | Depends on Monetary Representation decision |
| Effective Period | Required Concept    | Depends on Effective Dating availability    |
| Change Reason    | Candidate           | Requires business-defined values            |
| Allowance        | Open Question       | Scope not decided                           |
| Daily Rate       | Open Question       | Stored fact vs calculated value             |

---

# 4. Business Scenarios

## Promotion

Effect:

- Job Grade changes
- Compensation may change
- New compensation terms become effective

---

## Salary Increase

Effect:

- Compensation changes
- Job Grade may remain unchanged

Examples:

- merit increase
- cost-of-living adjustment
- annual increment

---

## Acting Assignment

Effect:

- Employee temporarily performs higher responsibility
- May require temporary monetary adjustment

Open question:

Whether this is represented as compensation change, allowance, or separate concept.

---

## Temporary Allowance

Effect:

- Additional monetary benefit exists for a limited period

Open question:

Whether allowance belongs inside Compensation or separate business concept.

---

# 5. Excluded Concepts

| Concept        | Reason                                                     |
| -------------- | ---------------------------------------------------------- |
| Bonus          | Usually event-based payment, not standing employment terms |
| Deduction      | Applied during payroll processing                          |
| Tax            | Payroll policy concern                                     |
| Payment Result | Payroll execution concern                                  |

---

# 6. Business Decisions Required

## Monetary Content

Questions:

- Does Compensation support salary only?
- Does Compensation support hourly rate?
- Can both exist?
- Are allowances included?

---

## Daily Rate

Decision required:

- Stored business value?
- Derived by Payroll Calculation?

---

## Allowance Model

Decision required:

- Part of Compensation?
- Separate capability/concept?

---

## History Requirement

Decision required:

- Must previous compensation terms be preserved?
- How long should history remain available?

---

## Lifecycle

Decision required:

- Can compensation be edited after approval?
- Are corrections new records?
- Is compensation immutable after activation?

---

## Approval

Decision required:

- Do compensation changes require approval?
- Who approves?

---

# 7. Relationship With Existing Capabilities

## Monetary Representation

Consumes monetary representation mechanism.

Does not decide:

- salary meaning
- compensation policy

---

## Effective Dating

Consumes effective dating mechanism if historical validity is required.

Does not decide:

- whether compensation needs history

---

## JobGrade

Open business/architecture decision:

- Is compensation range linked to JobGrade?
- Is JobGrade only descriptive?

---

## Payroll Calculation

Consumer relationship:

Payroll Calculation uses Compensation as an input.

---

# 8. Current Recommendation

Business decisions are required before Architecture Decision Round 2.

The next step is not further repository discovery.

The next step is confirmation of Compensation business meaning and scope.
