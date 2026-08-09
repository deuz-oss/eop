# Product Scope

Version: 1.0

---

# Purpose

This document defines the functional boundaries of the Enterprise Operations Platform (EOP).

Its purpose is to ensure that product development remains focused on improving field execution while avoiding unnecessary feature expansion.

Any feature request outside this scope must be evaluated before implementation.

---

# Product Positioning

EOP is an Enterprise Operations Platform designed to improve field execution.

It is **not** intended to become a general-purpose ERP or accounting system.

Every module must contribute directly or indirectly to improving field operations.

---

# Target Business Process

EOP supports the complete field execution lifecycle.

```text
PLAN
    ↓
ASSIGN
    ↓
EXECUTE
    ↓
VERIFY
    ↓
MEASURE
    ↓
ANALYZE
    ↓
IMPROVE
```

Every feature should strengthen at least one stage of this execution loop.

---

# In Scope

## 1. Platform Foundation

- Authentication
- Authorization
- Multi-Tenant Organization
- Role & Permission
- User Management
- Audit Log
- Notification
- File Storage
- API
- System Configuration

---

## 2. Organization Management

- Company
- Business Unit
- Region
- Area
- Territory
- Branch
- Team Structure

---

## 3. Workforce Management

- Employee
- Sales Representative
- SPG/SPB
- Merchandiser
- Supervisor
- Area Manager
- Regional Manager

---

## 4. Customer & Store

- Customer
- Outlet
- Modern Trade
- General Trade
- Store Classification
- Geolocation

---

## 5. Planning

- Route Planning
- Mission Planning
- Territory Assignment
- Target Assignment
- Schedule Planning

---

## 6. Field Execution

- Attendance
- Check In
- Check Out
- GPS Validation
- Selfie Verification
- Visit
- Survey
- Competitor Activity
- Display Audit
- Stock Check
- POSM Audit
- Photo Evidence

---

## 7. Performance Management

- KPI
- Target
- Achievement
- Productivity
- Scorecard
- Leaderboard
- Incentive Calculation

---

## 8. Analytics

- Dashboard
- Operational Report
- Territory Analysis
- Productivity Analysis
- Heatmap
- Forecast
- Trend Analysis

---

## 9. AI Intelligence

- Operational Recommendation
- Target Prediction
- Route Recommendation
- Risk Detection
- Anomaly Detection
- Executive Summary
- AI Assistant

---

## 10. Integration

- REST API
- Webhook
- ERP Integration
- HR Integration
- BI Integration

---

# Out of Scope

The following capabilities are intentionally excluded from EOP.

## ERP

- General Ledger
- Journal
- Accounting
- Tax
- Procurement
- Manufacturing

---

## HRIS

- Learning Management
- Employee Benefits

Exception:
EOP may integrate with HR systems.

Note: Payroll Processing, Recruitment, and Performance Review were
originally listed here but have since been explicitly brought into scope
by CPO/CTO product decision (see
`docs/architecture/00-governance/ARCHITECTURE_CHANGELOG.md` and, for
Recruitment specifically, `docs/architecture/capabilities/recruitment/
iteration-1-scope-and-implementation-plan.md` §0; for Performance
Review, `docs/architecture/capabilities/performance/
iteration-1-scope-and-implementation-plan.md` §0). "Performance Review"
here refers specifically to individual HR employee reviews, distinct
from the already-in-scope "Performance Management" (§7 above, field/
sales operational KPIs) -- the two are unrelated concepts that happen to
share a word. This list is not re-audited for other stale entries as
part of that decision.

---

## CRM

- Opportunity Management
- Lead Management
- Marketing Automation

---

## E-Commerce

- Marketplace
- Online Store
- Payment Gateway

---

## Consumer Applications

- Customer Loyalty
- Consumer Rewards
- Consumer Mobile Apps

---

# Product Boundaries

EOP manages **field execution**.

Other enterprise systems remain the source of truth for their own domains.

Example:

ERP
→ Financial transactions

HRIS
→ Employee administration

CRM
→ Sales pipeline

EOP
→ Operational execution

---

# Future Expansion

Possible future modules:

- Workflow Automation
- Low-Code Automation
- AI Agent
- Predictive Workforce Planning
- Digital Twin
- IoT Integration

These modules are not part of the MVP.

---

# MVP Scope

The first production release includes only:

- Authentication
- Organization
- Employee
- Store
- Attendance
- Visit
- Mission
- Dashboard
- KPI
- Basic Reporting

Everything else will be delivered incrementally.

---

# Scope Governance

Any new feature must satisfy at least one of the following:

- Improves field execution.
- Improves operational visibility.
- Improves execution quality.
- Improves managerial decision making.

If a feature does not satisfy these conditions, it should not be included in EOP.