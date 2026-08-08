# Compensation — Decision Round 2

Status: Draft Decision

Inputs:

- decision.md
- domain-model-discovery.md
- architecture-gap-analysis.md
- business-domain-definition.md
- Monetary Representation final-governance-summary.md
- Effective Dating final-governance-summary.md

---

# 1. Business Meaning Decision

Decision:

Compensation represents employee agreed monetary employment terms effective for a period.

Included:

- base salary
- hourly rate
- currency reference
- effective period
- compensation change reason

Excluded:

- bonus
- deduction
- payroll result
- payment transaction

---

# 2. Monetary Representation Relationship

Decision:

Compensation consumes Monetary Representation.

Compensation does not define:

- numeric precision
- rounding rules
- serialization format
- currency mechanism

Remaining dependency:

Business must define:

- single currency vs multi currency
- required monetary values

---

# 3. History Decision

Decision:

Compensation requires historical interpretation.

Reason:

Business scenarios:

- promotion
- salary increase
- annual increment
- correction

require knowing previous compensation terms.

---

# 4. Effective Dating Decision

Decision:

Compensation requires effective dating.

Reason:

Compensation changes are future/past valid terms.

Examples:

- salary increase effective next month
- promotion effective date
- temporary adjustment period

---

# 5. Lifecycle Decision

Decision:

Compensation records should not be overwritten after activation.

A compensation change creates a new effective record.

Open:

Correction workflow requires future decision.

---

# 6. JobGrade Relationship

Decision:

Compensation does not own JobGrade.

Relationship:

JobGrade provides classification context.

Open:

Whether JobGrade compensation band/range exists.

---

# 7. Payroll Calculation Relationship

Decision:

Payroll Calculation consumes Compensation.

Compensation provides:

- agreed monetary terms

Payroll Calculation decides:

- calculation rules
- proration
- deductions
- payable amount

---

# 8. Payslip Relationship

Decision:

Payslip does not own Compensation.

Payslip represents calculated output.

---

# 9. Authorization

Deferred.

Reason:

No Compensation authorization mechanism exists yet.

---

# 10. Remaining Decisions

Business:

- allowance model
- daily rate storage
- currency scope
- reason values

Architecture:

- concrete persistence shape
- Effective Dating integration shape
