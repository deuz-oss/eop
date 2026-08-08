# Payroll — Discovery

**Status:** Complete

**Capability:** Payroll (data-owning capability — distinct from Payroll Authorization)

**Owner:** EOP Architecture Governance

---

# Purpose

This document records repository evidence for the Payroll capability itself — what it would own, what it would consume, and what does not yet exist to support it. It is distinct from `docs/architecture/capabilities/payroll-authorization/`, which addresses access control and was found blocked (`payroll-authorization/decision.md`) precisely because this capability does not yet exist.

Discovery exists to understand the current repository state. It does not define architecture, does not choose an aggregate shape, and does not select a lifecycle. Per `AI_DISCOVERY_GUIDE.md`, this document reports observation and interpretation; it does not resolve architectural questions.

---

# Discovery Scope

Full file reads unless noted:

- Every HR producer model and its owning service: `models/hr_employee.py`, `models/attendance_event.py` + `services/attendance_event.py`, `models/leave_request.py` + `services/leave_request.py`, `models/leave_balance.py` + `services/leave_balance.py`, `models/overtime_request.py` + `services/overtime_request.py`, `models/timesheet.py` + `services/timesheet.py`, `models/shift.py`, `models/holiday.py`, `models/job_grade.py`, `models/employment_type.py`, `models/employment_status.py`
- Cross-entity orchestration precedents: `services/approval.py` (`ApprovalService`), `services/reconciliation.py` (`ReconciliationService`)
- API routers for the above: `api/timesheets.py`, `api/overtime_requests.py`, `api/reconciliation.py`, plus previously reviewed `api/attendance_events.py`, `api/leave_requests.py`
- Platform foundations: `db/base.py`, `db/mixins.py` (`UUIDMixin`, `TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`, `VersionMixin`), `repositories/base.py` (`BaseRepository`), `repositories/leave_request.py` (concrete repository pattern)
- Authorization Foundation and its three existing consumers (carried forward from prior discoveries in this conversation)
- Every design document previously reviewed for Payroll mentions: `ATTENDANCE_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`, `LEAVE_DESIGN.md`, `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`, `TIMESHEET_DESIGN.md`, `APPROVAL_WORKFLOW_DESIGN.md`, `APPROVAL_ORCHESTRATION_DESIGN.md`, `HOLIDAY_CALENDAR_DESIGN.md`
- Governance documents: `MASTER_ARCHITECTURE_ROADMAP.md`, `CAPABILITY_CATALOG.md`, `ARCHITECTURE_STATUS.md`, `TECHNICAL_DEBT_REGISTER.md`, `ARCHITECTURE_INVENTORY.md`, `CAPABILITY_DEPENDENCY_GRAPH.md`, `docs/product/02_PRODUCT_SCOPE.md`
- `docs/architecture/capabilities/payroll-authorization/discovery.md` and `decision.md` (this conversation's own prior output — carried forward as evidence of what has already been established, not re-derived)

---

# 1. Producer Capabilities

Every capability the repository already implements that produces data a future Payroll capability would plausibly read. For each: produced entity, lifecycle, ownership, completion state.

| Capability | Produced entity | Fields (repository evidence) | Lifecycle | Ownership | Completion / authorization state |
|---|---|---|---|---|---|
| HR Master Data | `HrEmployee` | `employee_number`, name fields, `email`, `phone`, FKs to `organization`/`department`/`position`/`team`/`location`/`manager`/`job_grade`/`employment_type`/`employment_status`/`shift`/`user`, `hire_date`, `employment_status`, `notes` | Plain CRUD, no status field | `HrEmployeeService` | Implemented. No salary/rate/compensation field (`hr_employee.py:54-105`, full read). |
| Attendance | `AttendanceEvent` | `employee_id`, `shift_id`, `event_type`, `event_time`, `source` | Append-only clock transaction, no status field | `AttendanceEventService` | Implemented. Owner Only authorization on `create`/`get`/`update`/`delete` (`attendance_authorization.py`); `list`/`list_paginated` scoped to caller. |
| Attendance Reconciliation | Computed result (`holiday`/`leave`/`present`/`absent`), **not persisted** | `employee_id`, `date`, `status` (response shape only — no table) | Read-time computation, single employee + single date per call (`reconcile(employee_id, target_date)`) | `ReconciliationService` — "owns no aggregate, no table, and no repository of its own" (`reconciliation.py:23-24`) | Implemented. `CurrentUser` only; caller-supplied `employee_id` query parameter, unscoped (`api/reconciliation.py:25`). |
| Leave | `LeaveRequest` | `employee_id`, `start_date`, `end_date`, `status` (default `"pending"`), `reason`, `approved_by`, `approved_at`, `rejection_reason` | `pending → approved/rejected` | CRUD + per-request authorization: `LeaveRequestService` (Owner Only). Approve/reject: `ApprovalService` (Manager Approval, ADR-008) | Implemented end-to-end, including authorization. |
| Leave Balance | `LeaveBalance` | `employee_id`, `period_year`, `allocated_days`, `used_days`, `remaining_days` | Static snapshot, no transitions, non-negative validation only | `LeaveBalanceService` | Implemented as **storage only** — not synchronized with `LeaveRequest` approval; `ApprovalService.approve_leave_request`'s own docstring names this an explicit, intentional gap (`approval.py:94-108`). No authorization of any kind (`leave_balance.py`, full read — no `RequestContext`/`Authorization` import). |
| Overtime | `OvertimeRequest` | `employee_id`, `overtime_date`, `start_time`, `end_time`, `status` (default `"pending"`), `approved_by`, `approved_at`, `rejection_reason` | `pending → approved/rejected` | CRUD: `OvertimeRequestService` — **no authorization of any kind** (grep for `Authorization\|RequestContext\|CurrentUser` in `services/overtime_request.py` returns zero matches; `api/overtime_requests.py` gates CRUD routes with plain `CurrentUser` only, no ownership check). Approve/reject: `ApprovalService` (Manager Approval) | Implemented for CRUD and approval; CRUD authentication-only, any authenticated user may act on any employee's `OvertimeRequest`. No overtime-hours calculation (`overtime_request.py:15-18`, explicit). |
| Timesheet | `Timesheet` | `employee_id`, `start_date`, `end_date`, `status` (default `"pending"`), `approved_by`, `approved_at`, `rejection_reason` | `pending → approved/rejected` | CRUD: `TimesheetService` — same authorization gap as Overtime (identical grep result, zero matches; `api/timesheets.py` CRUD routes use `CurrentUser` only). Approve/reject: `ApprovalService` | Implemented for CRUD and approval; CRUD authentication-only. No computed hour totals, no reconciliation with Attendance/Overtime/Leave/Holiday (`timesheet.py:16-19`, explicit). |
| Approval (cross-entity orchestrator) | No own entity — writes `status`/`approved_by`/`approved_at`/`rejection_reason` onto `LeaveRequest`/`OvertimeRequest`/`Timesheet` | — | `pending → approved` / `pending → rejected` only; any other transition raises `InvalidApprovalStateError` (`approval.py:22-30`) | `ApprovalService` — explicitly "does not own a single entity's CRUD... reaches into `LeaveRequestRepository`/`OvertimeRequestRepository`/`TimesheetRepository` directly" (`approval.py:42-56`); explicitly excludes "decision history, audit logging, and event/notification dispatch" | Implemented. Gated by Approval Authorization (Manager Approval, ADR-008): `entity.employee.manager_id == approver.employee.id`. |
| HR Master Data (reference) | `Shift`, `Holiday`, `JobGrade`, `EmploymentType`, `EmploymentStatus` | `Shift`: `code`, `name`, `start_time`, `end_time`, `break_duration_minutes`, `grace_period_minutes`. `Holiday`: `code`, `name`, `holiday_date`. `JobGrade`: `code`, `name`, `level` (int rank), `description`. `EmploymentType`/`EmploymentStatus`: `code`, `name`, `description`. | Plain CRUD, no lifecycle | One dedicated `*Service` per entity | Implemented. No monetary field on any of the five (full model reads). `Shift` explicitly excludes "assigning a shift to an employee, a work calendar, and rostering" (`shift.py:12-19`). `Holiday` has no type/category and no pay-multiplier field. |

---

# 2. Potential Payroll Inputs — Entities Confirmed to Exist

Per the instruction to report only entities that actually exist: `AttendanceEvent`, `LeaveRequest`, `Timesheet`, `Holiday`, `Shift`, `HrEmployee` ("Employee" in the instruction's terms — the repository's HR-context employee, not the separate, pre-existing Project Tracking `Employee`), `EmploymentType`, `EmploymentStatus`, `JobGrade` — every one of these is confirmed implemented (§1). `OvertimeRequest` and `LeaveBalance` additionally exist and were not named in the instruction's example list but are equally confirmed producers (§1).

No `PayrollRun`, `PayrollPeriod`, `PayrollItem`, `PayrollEntry`, `Payslip`, `Salary`, `Compensation`, `PayrollCalculation`, `PayrollAdjustment`, or `PayrollBatch` entity exists (confirmed by the prior discoveries' repository-wide search, not re-run here).

---

# 3. Current Data Availability

| Data | Exists? | Evidence |
|---|---|---|
| employee | Yes | `HrEmployee` (§1) |
| attendance | Yes | `AttendanceEvent` (raw events) + `ReconciliationService` (computed per-day status, not persisted) |
| leave | Yes | `LeaveRequest` (request + status) + `LeaveBalance` (unsynchronized allocation/usage snapshot) |
| approval | Yes | `ApprovalService` — uniform `pending → approved/rejected` outcome on `LeaveRequest`/`OvertimeRequest`/`Timesheet` |
| working day | **No** | `Shift` defines a reusable time-of-day template only (`start_time`/`end_time`/`break_duration_minutes`/`grace_period_minutes`); its own docstring excludes "assigning a shift to an employee, a work calendar, and rostering." No weekly/calendar working-day concept exists anywhere. |
| holiday | Yes (dates only) | `Holiday` — `code`/`name`/`holiday_date`. No holiday-type/category field, no `is_paid`/pay-multiplier field (`HOLIDAY_CALENDAR_DESIGN.md`, prior discovery). |
| shift | Yes (template only) | `Shift`, as above — not assigned to any employee, calendar, or roster. |
| overtime | Yes (request + approval status only) | `OvertimeRequest` — no computed hours, no rate multiplier (`overtime_request.py:15-18`, explicit). |
| salary | **No** | No field on `HrEmployee`, `JobGrade`, or any other model (confirmed by repository-wide grep in the prior discovery). |
| allowance | **No** | Same as salary — no matches anywhere in `services/api/src`. |
| deduction | **No** (as currency) | The only "deduction" language in the repository is `LeaveBalance`'s own unimplemented "deduction" of leave *days* (`leave_balance.py:29`, explicitly out of scope) and `ARCHITECTURE_INVENTORY.md`'s "Deduction rule" listed as an open Gap under Leave — neither is a monetary concept. |
| tax | **No** | No matches anywhere in source. |
| benefit | **No** | No matches anywhere in source (the two prose matches found in `PR-050_DISCOVERY.md`/`ADR-001` use "benefit" as an ordinary English word, not a compensation concept). |

---

# 4. Missing Core Concepts

Reported as absence, not as a recommendation to build:

- No `PayPeriod`/pay-period boundary concept anywhere in the codebase — independently confirmed by `ATTENDANCE_RECONCILIATION_DESIGN.md`, `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`, and `TIMESHEET_DESIGN.md`, each in their own words.
- No monetary field (salary, wage, hourly rate, allowance, deduction, tax, benefit) exists on any model in the repository (§3).
- No paid/unpaid flag on `LeaveRequest`; no `is_paid`/pay-multiplier flag on `Holiday`.
- No computed hour totals on `Timesheet`; no computed overtime hours on `OvertimeRequest`.
- No working-day/calendar concept — `Shift` is a time-of-day template, not a weekly pattern or roster.
- No accrual/deduction engine for `LeaveBalance` — `ARCHITECTURE_INVENTORY.md:162-166` lists "Balance engine / Accrual rule / Deduction rule" as an open Gap under "Leave — Status: Partial."
- No authorization on `OvertimeRequest`/`Timesheet` CRUD (§1) — any authenticated user can currently read or modify any employee's overtime request or timesheet prior to approval.
- No precedent anywhere in the repository for a **multi-employee, batch** process. `ReconciliationService` — the closest structural analog to a payroll computation (reads multiple repositories, produces a computed result, owns no table) — is explicitly scoped to one employee and one date per call (`reconcile(employee_id, target_date)`, `reconciliation.py:68`). No service in the repository iterates "all employees for a period."
- No workflow-history or business-audit-trail mechanism exists — `ARCHITECTURE_INVENTORY.md` §8 lists "Business Audit" as a `High` priority Architecture Gap; `TECHNICAL_DEBT_REGISTER.md` records no dedicated item for it but `ARCHITECTURE_STATUS.md`'s Deferred Architecture section does not include it either, meaning it is an acknowledged but unowned gap.

---

# 5. Architectural Precedents Available

Three distinct, already-implemented service shapes exist in the repository that a future Payroll capability could draw structural precedent from (observed, not recommended):

1. **Per-entity CRUD service** (`HrEmployeeService`, `AttendanceEventService`, `LeaveRequestService`, `OvertimeRequestService`, `TimesheetService`, `LeaveBalanceService`, `Shift`/`Holiday`/`JobGrade`/`EmploymentType`/`EmploymentStatus` services): owns one model, one repository, one router, full CRUD. This is the repository's dominant pattern (eleven of twelve reviewed producer services follow it).
2. **Cross-entity orchestrator with no owned table** (`ApprovalService`): reaches into other capabilities' repositories directly, applies one uniform transition (`pending → approved/rejected`), writes back onto the target entity's own row. Adopted only after "an explicit architectural decision" (`APPROVAL_ORCHESTRATION_DESIGN.md`, "Option B"), not inferred from repository convention — its own docstring calls it "the repository's first orchestration service."
3. **Read-only, computed-result orchestrator with no owned table** (`ReconciliationService`): reads multiple repositories, combines them into one response object, persists nothing, recomputes on every call. Explicitly single-employee, single-date scoped (§4).

No fourth shape — a persisted, multi-employee, batch-computed aggregate — exists anywhere in the repository today.

---

# 6. Findings

- Nine producer capabilities (§1) already generate data; none carries a monetary field or a working-day/pay-period concept (§3, §4).
- `LeaveBalance` is explicitly unsynchronized with `LeaveRequest` approval — a named, intentional gap in the repository's own code, not an oversight (§1).
- `OvertimeRequest` and `Timesheet` CRUD have no authorization at all — a materially different (weaker) state than `LeaveRequest`/`AttendanceEvent`, both fully authorization-gated (§1, §4).
- The repository's only read-oriented, multi-repository orchestration precedent (`ReconciliationService`) is explicitly single-employee/single-date; no batch-over-employees-for-a-period shape exists anywhere (§4, §5).
- `ApprovalService`'s cross-entity-orchestrator shape was adopted only via an explicit, documented architectural decision ("Option B"), not inferred from convention — this is itself evidence that the repository's governance does not treat "reach into another capability's repository" as a default-available pattern; it required its own decision.
- `ARCHITECTURE_INVENTORY.md` independently flags "Business Audit" as a named, `High` priority, currently-unowned Architecture Gap (§4) — directly relevant to whether a future Payroll capability's output should be a durable record or a recomputable view (deferred to Capability Decision, not resolved here).

---

# 7. Open Questions

Repository evidence does not answer:

- Whether a future Payroll capability's protected computation would be triggered per-employee (matching `ReconciliationService`'s shape) or as a genuine multi-employee batch (a shape with no repository precedent at all).
- Where compensation/rate data would be sourced from — no existing model has a place for it, and no document proposes where it would be added.
- Whether `OvertimeRequest`/`Timesheet`'s current lack of CRUD authorization is expected to be resolved (by capability decisions of their own) before Payroll depends on their `status == "approved"` output, or whether Payroll would depend on potentially-unauthorized upstream data regardless.
- Whether `LeaveBalance`'s unsynchronized state is expected to be resolved before a Payroll computation could safely read `remaining_days`.

---

# 8. Recommended Next Step

```
Payroll Capability Decision
```
