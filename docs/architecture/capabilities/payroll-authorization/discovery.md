# Payroll Authorization — Discovery

**Status:** Complete

**Capability:** Payroll Authorization

**Owner:** EOP Architecture Governance

---

# Purpose

This document records repository evidence for the Payroll Authorization capability.

Discovery exists to understand the current repository state.

It does not define architecture.

It does not choose a policy model.

Architecture decisions and policy discovery are documented separately, per `AI_DISCOVERY_GUIDE.md`.

---

# Discovery Scope

The following areas were inspected (full file reads unless noted):

- Repository-wide filename search for `*payroll*`, `*payslip*`, `*salary*`, `*compensation*` under `services/api/src`, `services/api/tests`, `services/api/alembic`
- Repository-wide content grep (case-insensitive) for `payroll|payslip|salary|compensation` across the entire repository (26 files matched; every match read in context)
- `services/api/src/eop_api/main.py` (full router registration list)
- `services/api/src/eop_api/models/hr_employee.py`, `models/job_grade.py` (candidate pay-rate/compensation carriers)
- `services/api/src/eop_api/dependencies/rbac.py` (role-based access mechanism)
- Authorization Foundation (ADR-007): `services/authorization.py`, `services/authorization_evaluator.py`, `services/authorization_request.py`, `services/authorization_decision.py`
- Existing authorization-integrated capabilities (precedent): `services/approval_authorization.py`, `services/leave_authorization.py`, `services/attendance_authorization.py`, and their owning services (`services/approval.py`, `services/leave_request.py`, `services/attendance_event.py`) and API routers
- Identity Context Foundation: `services/employee_context.py`, `dependencies/employee_context.py`
- Design/discovery documents that reference Payroll as a named future consumer: `ATTENDANCE_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`, `LEAVE_DESIGN.md`, `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`, `TIMESHEET_DESIGN.md`, `APPROVAL_WORKFLOW_DESIGN.md`, `APPROVAL_ORCHESTRATION_DESIGN.md`
- Governance documents: `MASTER_ARCHITECTURE_ROADMAP.md`, `MASTER_ARCHITECTURE_BLUEPRINT.md` (no match), `ARCHITECTURE_STATUS.md`, `CAPABILITY_CATALOG.md`, `TECHNICAL_DEBT_REGISTER.md`, `ARCHITECTURE_VISION.md`, `CAPABILITY_DEPENDENCY_GRAPH.md`
- Product documentation: `docs/product/02_PRODUCT_SCOPE.md`
- Prior capability discovery precedent (closest analog and immediate roadmap predecessor): `docs/architecture/capabilities/attendance-authorization/discovery.md`, `.../decision.md`
- `docs/architecture/ARCHITECTURE_DECISION_RECORDS/` directory listing (ADR-001 through ADR-008)
- `services/api/alembic/versions/` — all 26 migration files, filename/content search only (no payroll match)
- `services/api/tests/` — full directory listing (107 test files), filename search for payroll-related names
- `git log --format='%h %ad %s' --date=short` for recent commit history and dates

---

# 1. Repository Summary

Repository discovery finds **no Payroll-related component of any kind**. A repository-wide filename search for `*payroll*`, `*payslip*`, `*salary*`, `*compensation*` under `services/api/src`, `services/api/tests`, and `services/api/alembic` returns zero files. A repository-wide case-insensitive content grep for `payroll|payslip|salary|compensation` returns 26 files; every one is either (a) a docstring "out of scope" note in an unrelated, already-implemented service/model (`AttendanceEvent`, `OvertimeRequest`, `Timesheet`, `LeaveBalance`), (b) a "Future Compatibility" or "Not proposed" section in a design/discovery document for a different capability, (c) a governance/roadmap document listing "Payroll" or "Payroll Authorization" as `Planned`, or (d) `docs/product/02_PRODUCT_SCOPE.md` listing "Payroll Processing" under "HRIS" as a named exclusion. No source file, test file, or migration in the repository defines, imports, references, or tests any `Payroll`, `PayrollRun`, `PayrollPeriod`, `PayrollItem`, `PayrollEntry`, `Payslip`, `Salary`, `Compensation`, `PayrollCalculation`, `PayrollAdjustment`, or `PayrollBatch` symbol.

Neither `HrEmployee` (`models/hr_employee.py`) nor `JobGrade` (`models/job_grade.py`) — the two models a payroll rate computation would most plausibly read from — carries a salary, pay-rate, or compensation field. `JobGrade`'s own docstring describes it as "ranking positions by seniority/pay grade," but its only columns are `code`, `name`, `level` (an `Integer` rank), and `description`; no monetary field exists.

`main.py`'s router registration list (`main.py:82-112`) contains no Payroll router; every one of the 24 registered routers corresponds to an already-implemented, non-Payroll capability.

`MASTER_ARCHITECTURE_ROADMAP.md` lists "Payroll Authorization" as `Planned`, positioned immediately after "Attendance Authorization" in both its "Remaining Capability Authorizations" table and its "Dependency Roadmap" diagram (`... → Approval Authorization → Leave Authorization → Attendance Authorization → Payroll Authorization → Enterprise Authorization`). Repository evidence (`git log`) confirms Attendance Authorization — the capability immediately preceding Payroll Authorization in this sequence — is merged (`afce53e`, `356764a`, 2026-08-06) and implemented (`services/attendance_authorization.py`, `AttendanceEventService._authorize`, wired into `api/attendance_events.py`).

Every design/discovery document reviewed for an unrelated capability that mentions Payroll does so only to name it as a **future, not-yet-built consumer** of that capability's own `APPROVED`/finalized data (`ATTENDANCE_DESIGN.md` §9, `LEAVE_DESIGN.md` §10, `TIMESHEET_DESIGN.md` §11, `ATTENDANCE_RECONCILIATION_DESIGN.md` §10, `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` §10, `APPROVAL_WORKFLOW_DESIGN.md` §12) — each of these documents independently states that no `Payroll`/`PayPeriod` concept exists anywhere in the codebase.

`docs/product/02_PRODUCT_SCOPE.md` lists "Payroll Processing" under a section titled "HRIS," alongside Recruitment, Performance Review, Learning Management, and Employee Benefits, with the note: *"Exception: EOP may integrate with HR systems."* This is the only product-level statement found regarding Payroll's intended relationship to EOP, and it does not by itself resolve whether "Payroll Authorization" (named as an in-repo `Planned` capability in `MASTER_ARCHITECTURE_ROADMAP.md`) refers to the same thing this scope document excludes (see §7, §8).

---

# 2. Repository Evidence

## 2.1 Payroll-Named Components — Search Result

| Search | Result |
|---|---|
| Filename glob `*payroll*`, `*payslip*`, `*salary*`, `*compensation*` under `services/api/src` | 0 files |
| Filename glob, same terms, under `services/api/tests` | 0 files |
| Filename glob, same terms, under `services/api/alembic` | 0 files |
| Content grep `payroll\|payslip\|salary\|compensation` (case-insensitive), whole repository | 26 files, none defining a Payroll component (§2.2) |
| Content grep `payroll\|payslip\|salary\|compensation\|pay_grade\|base_pay\|hourly_rate` in `models/employee.py` | 0 matches |
| Content grep `payroll` in `dependencies/rbac.py` | 0 matches |
| Content grep `payroll` in `main.py` | 0 matches |

No `PayrollRun`, `PayrollPeriod`, `PayrollItem`, `PayrollEntry`, `Payslip`, `Salary`, `Compensation`, `PayrollCalculation`, `PayrollAdjustment`, or `PayrollBatch` symbol exists anywhere in the repository under any of the search strategies above.

## 2.2 Classification of the 26 Content-Grep Matches

Every file returned by the repository-wide content grep falls into exactly one of four categories, confirmed by reading each in context:

**(a) Docstring "out of scope" notes in unrelated, already-implemented modules** — these state that payroll is *not* handled by the module being documented:
- `services/attendance_event.py:42` — `AttendanceEvent` docstring: "not an employee-day summary, timesheet, or payroll record"
- `models/attendance_event.py:24` — same note, model docstring
- `services/overtime_request.py:25` — `OvertimeRequest` docstring: "not a calculation or payroll record"
- `models/overtime_request.py:15,17` — same note, model docstring
- `services/timesheet.py:35` — "payroll integration remain out of scope"
- `models/timesheet.py:18` — same note, model docstring
- `services/leave_balance.py:29` — "payroll synchronization... explicitly out of scope"

**(b) "Future Compatibility" / "Must NOT belong" sections in design or discovery documents for other capabilities** — these name Payroll as a hypothetical future reader of already-built data, and each independently confirms no such component exists yet:
- `ATTENDANCE_DESIGN.md:74,85,178,199,266-268` — Payroll named as a future consumer of `AttendanceEvent`/a possible future `AttendanceDailySummary`; explicitly listed under "Must NOT belong in `AttendanceService`"
- `ATTENDANCE_RECONCILIATION_DESIGN.md:197,311-313,512-514` — "no `Payroll`/`PayPeriod` concept exists anywhere in the codebase or roadmap"
- `LEAVE_DESIGN.md:272,345-348,388-389` — Payroll named as a future consumer of `APPROVED` `LeaveRequest`s; "Payroll interaction... not modeled"
- `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md:23-29,159-160,294-296,573-578` — quotes `LeaveBalanceService`'s own docstring on payroll synchronization being out of scope; names Payroll as the "clearest anticipated consumer" of a future, still-unbuilt capability
- `TIMESHEET_DESIGN.md:52-55,126-131,371-373,451-459,513-516,530-532,564-566,613-614` — "no `PayPeriod`/`Payroll` concept anywhere in the codebase or in `docs/product/06_PRODUCT_ROADMAP.md`"; lists "Payroll pay-rate/deduction computation" under "Must NOT belong in `TimesheetService`"
- `APPROVAL_WORKFLOW_DESIGN.md:417-418,611-621` — "Payroll computation triggered by an approval... a downstream consumer's concern"
- `APPROVAL_ORCHESTRATION_DESIGN.md` — not matched by this grep in a Payroll-specific way beyond what's captured above (file present in match list via a different section not reproduced here)
- `HOLIDAY_CALENDAR_DESIGN.md:148-149,309-313,343-344,351-353,379-380,387-388` — Payroll named as a plausible future consumer of `is_paid`/pay-multiplier data that does not exist; "explicitly out of scope"

**(c) Governance/roadmap documents recording "Payroll Authorization" as a named, `Planned` (not implemented) capability:**
- `MASTER_ARCHITECTURE_ROADMAP.md:223,337,433-434,460-466` — "Payroll" listed under Architecture Vision layers; "Payroll Authorization | Planned" in two separate tables; positioned between "Attendance Authorization" and "Enterprise Authorization" in the Dependency Roadmap diagram
- `ARCHITECTURE_DECISION_RECORDS/ADR-007-authorization-foundation.md` — matched by this grep; content is a passing reference consistent with the roadmap's "Planned" framing, not a Payroll-specific architectural decision
- `docs/architecture/capabilities/authorization/decision.md`, `.../implementation-plan.md` — matched; same "Planned"-consistent passing references, no Payroll-specific content
- `CAPABILITY_DEPENDENCY_GRAPH.md:118` — "Payroll Integration" appears once, in a "Secondary" critical-path diagram (`Leave Rules → Leave Balance Engine → Payroll Integration`), in a document that also contains Indonesian-language governance text elsewhere (§7)
- `ARCHITECTURE_VISION.md:197` — "Authorization does not know Payroll" (a boundary statement about Authorization Foundation, not evidence of a Payroll component)

**(d) Product scope document:**
- `docs/product/02_PRODUCT_SCOPE.md:196` — "Payroll Processing" listed under "HRIS," with an "EOP may integrate with HR systems" exception noted immediately after (§1, §7)

No file in categories (a)–(d) defines, implements, or tests a Payroll component. This exhausts all 26 matches.

## 2.3 Authorization Foundation Components (ADR-007) — Current State

All four files exist under `services/`: `authorization.py` (`AuthorizationService.authorize`), `authorization_evaluator.py` (`AuthorizationEvaluator.evaluate` — base class, unconditionally returns `AuthorizationDecision(allowed=True)`), `authorization_request.py` (`AuthorizationRequest`, wraps `RequestContext` + optional `resource: Any | None`), `authorization_decision.py` (`AuthorizationDecision`, frozen dataclass, `allowed: bool`, `reason: str | None`).

Repository-wide grep for subclasses of `AuthorizationEvaluator` confirms three consumers currently exist: `ApprovalAuthorizationEvaluator` (`services/approval_authorization.py`, ADR-008), `LeaveAuthorizationEvaluator` (`services/leave_authorization.py`), and `AttendanceAuthorizationEvaluator` (`services/attendance_authorization.py`, merged `afce53e`/`356764a`, 2026-08-06). **No `PayrollAuthorizationEvaluator` or equivalently named class exists anywhere in the repository.**

`AttendanceAuthorizationEvaluator` (`attendance_authorization.py:6-24`) is fully implemented (Owner Only policy: `resource.employee_id == context.employee_context.employee.id`) and wired into `AttendanceEventService._authorize` (`attendance_event.py:196-213`), which every `create`/`get`/`update`/`delete` method calls (`attendance_event.py:87,102,163,189`); `list`/`list_paginated` are scoped to the caller's own `employee_id` rather than authorized per-item (`attendance_event.py:106-120`, `122-149`). `api/attendance_events.py` catches `AttendanceAuthorizationDeniedError` and maps it to `403 Forbidden` on every relevant route (`attendance_events.py:75-76,113-114,139-140,156-157`).

## 2.4 Identity Context and `CurrentUser`/`CurrentRequestContext` — Availability

`CurrentUser` (`dependencies/auth.py`), `CurrentEmployeeContext`/`CurrentRequestContext` (`dependencies/employee_context.py`), and `EmployeeContextResolver` (`services/employee_context.py`) all exist and are consumed by Approval Authorization, Leave Authorization, and Attendance Authorization (confirmed §2.3). Since no Payroll API route or service exists (§2.1), there is no code path in which Payroll does or does not depend on these mechanisms — this is a structural absence, not an integration gap in an existing capability.

## 2.5 Candidate Pay-Rate/Compensation Data — Does Not Exist

`HrEmployee` (`models/hr_employee.py:54-105`, full file read) has no salary, pay-rate, hourly-rate, or compensation column. Its fields are: `employee_number`, `first_name`, `last_name`, `full_name`, `email`, `phone`, seven FK columns (`organization_id`, `department_id`, `position_id`, `team_id`, `location_id`, `manager_id`, `job_grade_id`, `employment_type_id`, `employment_status_id`, `shift_id`, `user_id`), `hire_date`, `employment_status`, `notes`.

`JobGrade` (`models/job_grade.py`, full file read) has no monetary field. Its fields are `code`, `name`, `level` (`Integer`), `description`. Its own docstring calls it "ranking positions by seniority/pay grade," but "pay grade" here is descriptive language about rank ordering, not a modeled pay-rate value — no numeric compensation field backs it.

No repository model anywhere carries a salary, wage, rate, or compensation-amount field, confirmed by the content-grep result in §2.1/§2.2 (no such field was found across the whole repository).

## 2.6 `main.py` Router Registration — No Payroll Router

Full read of `main.py` (`main.py:1-123`). 24 routers are registered (`main.py:82-112`): health, auth, organizations, projects, employees, locations, location_types, departments, positions, teams, hr_employees, job_grades, employment_types, employment_statuses, shifts, holidays, attendance_events, leave_requests, leave_balances, overtime_requests, timesheets, reconciliation, assignments, tasks, roles, dashboard, audit_logs, files. No `payroll_router` import or `app.include_router(payroll...)` call exists.

## 2.7 Migrations — No Payroll Table

`services/api/alembic/versions/` contains 26 migration files. Filename and content search for `payroll|payslip|salary|compensation` across this directory returns zero matches. No migration creates a `payroll_runs`, `payroll_periods`, `payroll_items`, `payslips`, or any similarly named table, and no migration adds a salary/compensation column to any existing table.

## 2.8 Tests — No Payroll Test Coverage

`services/api/tests/` contains 107 test files (full directory listing). Filename search for `*payroll*`, `*payslip*`, `*salary*` returns zero files. No repository evidence of a payroll test of any kind — unit, integration, authorization, or otherwise — because no Payroll component exists to test.

---

# 3. Current Payroll Architecture

No execution flow exists. There is no API route, service, repository, model, schema, or migration to diagram. Repository evidence for this section is limited to the absence recorded in §2.

---

# 4. Authorization Surface

| Mechanism | Used by any Payroll component? | Used elsewhere |
|---|---|---|
| `CurrentUser` | N/A — no Payroll endpoint exists | Every authenticated endpoint in the repository |
| `CurrentEmployeeContext` / `CurrentRequestContext` | N/A | `api/leave_requests.py`, `api/attendance_events.py`, `services/leave_request.py`, `services/approval.py`, `services/attendance_event.py` |
| `AuthorizationService` | N/A | `services/approval.py`, `services/leave_request.py`, `services/attendance_event.py` |
| `AuthorizationEvaluator` (or a subclass) | N/A — no `PayrollAuthorizationEvaluator` exists | `ApprovalAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`, `AttendanceAuthorizationEvaluator` |
| `AuthorizationRequest` / `AuthorizationDecision` | N/A | Same three capabilities, plus Authorization Foundation's own files |
| `*AuthorizationDeniedError` (403-mapped) | N/A | `ApprovalAuthorizationDeniedError`, `LeaveAuthorizationDeniedError`, `AttendanceAuthorizationDeniedError` |
| `RequireRole` / `RequireAdmin` (`dependencies/rbac.py`) | N/A — grep for `payroll` in `rbac.py` returns 0 matches | `api/roles.py` only |
| `HrEmployee.manager_id` read | N/A | `ApprovalService._authorize` |

No repository evidence supports or refutes any statement about how Payroll "currently performs authorization," because no Payroll code exists to inspect. Per the Repository First / Evidence Rule: **no repository evidence found.**

---

# 5. Dependency Analysis

## 5.1 Declared (Documentation-Level) Dependencies

`MASTER_ARCHITECTURE_ROADMAP.md`'s Dependency Roadmap places Payroll Authorization here:

```
Authentication
  ↓
Identity Context
  ↓
Authorization Foundation
  ↓
Approval Authorization
  ↓
Leave Authorization
  ↓
Attendance Authorization
  ↓
Payroll Authorization
  ↓
Enterprise Authorization
```

`CAPABILITY_DEPENDENCY_GRAPH.md`'s separate "Secondary" critical-path diagram (§5 of that document) places a differently-named item, "Payroll Integration" (not "Payroll Authorization"), here instead:

```
Leave Rules
  ↓
Leave Balance Engine
  ↓
Payroll Integration
```

These are two different documents naming two differently-worded items ("Payroll Authorization" vs. "Payroll Integration") in two structurally different dependency chains — repository evidence does not establish whether these refer to the same capability (§7, §8).

## 5.2 Actual (Code-Level) Dependencies

None exist, because no Payroll code exists. For completeness, every reviewed capability's own design document independently names Payroll as a **future reader** of its `APPROVED`/finalized output, with no dependency existing in the reverse direction today:

| Capability | Data Payroll would read (per that capability's own design doc) | Evidence |
|---|---|---|
| `LeaveRequest` (Leave) | `APPROVED` rows, for paid/unpaid deduction | `LEAVE_DESIGN.md:345-348` |
| `LeaveBalance` (Leave Balance) | Synchronized `remaining_days` | `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md:573-578` |
| `OvertimeRequest` (Overtime) | `APPROVED` rows, for overtime pay | `TIMESHEET_DESIGN.md:451-454` (via Timesheet), `ATTENDANCE_DESIGN.md:266-268` |
| `AttendanceEvent` / Reconciliation (Attendance) | Raw events or reconciled per-day result, for payable hours | `ATTENDANCE_DESIGN.md:266-268`, `ATTENDANCE_RECONCILIATION_DESIGN.md:311-313` |
| `Timesheet` (Timesheet) | `status`-filtered rows, for pay computation | `TIMESHEET_DESIGN.md:451-454` |
| `Holiday` (Holiday) | Holiday dates, for rate multipliers (needs unmodeled `is_paid` concept) | `HOLIDAY_CALENDAR_DESIGN.md:309-313` |
| Approval (`ApprovalService`) | `status = APPROVED` outcome only, mechanism-agnostic | `APPROVAL_WORKFLOW_DESIGN.md:611-621` |

No FK, import, or service call exists from any of these modules toward a Payroll component (none exists to reference), and no FK, import, or service call exists from a Payroll component toward any of these (none exists to originate one). `Employee`/Identity Context and `Authorization Foundation` are available as platform capabilities (§2.3, §2.4) but have no Payroll consumer today, for the same reason.

---

# 6. Findings

Findings are stated as repository evidence, not as recommendations.

- No Payroll-related component — model, schema, service, repository, API route, or migration — exists anywhere in the repository, confirmed by filename search and repository-wide content grep (§2.1, §2.2).
- No `PayrollAuthorizationEvaluator` or equivalently named class exists; three other capability-specific `AuthorizationEvaluator` subclasses already exist and are wired end-to-end (Approval, Leave, Attendance) (§2.3).
- Neither `HrEmployee` nor `JobGrade` — the two models most likely to carry pay-rate data — has a salary, wage, rate, or compensation field (§2.5).
- `main.py` registers 24 routers; none is a Payroll router (§2.6).
- No migration creates a payroll-related table or column (§2.7).
- No test file — of 107 in the repository — references Payroll in its name (§2.8).
- Every one of seven independently authored design/discovery documents (Attendance, Attendance Reconciliation, Leave, Leave Balance Synchronization, Timesheet, Approval Workflow, Holiday Calendar) that mentions Payroll does so only to record it as a future, unbuilt consumer of that document's own capability — each document independently states no `Payroll`/`PayPeriod` concept exists in the codebase (§2.2b).
- `MASTER_ARCHITECTURE_ROADMAP.md` (`Planned`) and `CAPABILITY_DEPENDENCY_GRAPH.md` (`Payroll Integration`, undefined relationship to "Payroll Authorization") use different names and different dependency chains for what may or may not be the same future capability (§5.1).
- `docs/product/02_PRODUCT_SCOPE.md` lists "Payroll Processing" under "HRIS" — a category of systems otherwise described as out of EOP's product scope, subject to an "EOP may integrate with HR systems" exception — a different framing than the roadmap's in-repo `Planned` "Payroll Authorization" capability (§7, §8).
- `ARCHITECTURE_STATUS.md`, `CAPABILITY_CATALOG.md`, and `TECHNICAL_DEBT_REGISTER.md` (all `Last Updated: 2026-08-05`) list Authorization Foundation's consumers as Approval Authorization and Leave Authorization only; Attendance Authorization is merged and implemented as of `2026-08-06` (`git log`: `afce53e`, `356764a`) and is not reflected in any of the three documents (§7).

---

# 7. Governance Documentation State

Repository evidence shows discrepancies between merged code and governance documents, and between governance documents themselves, stated here per the Evidence Rule and the Escalation Rule ("repository contradicts documentation," "multiple valid interpretations exist").

- `git log` confirms Attendance Authorization is merged (`afce53e feat(auth): implement attendance authorization capability`, `356764a` merge commit, PR #57, both dated 2026-08-06) and fully wired (`services/attendance_authorization.py`, `AttendanceEventService._authorize`, `AttendanceAuthorizationDeniedError` mapped to `403` in `api/attendance_events.py`).
- `ARCHITECTURE_STATUS.md` (Last Updated: 2026-08-05), `CAPABILITY_CATALOG.md` (Last Updated: 2026-08-05), and `TECHNICAL_DEBT_REGISTER.md` TD-005 (Last Updated: 2026-08-05) each list only "Approval Authorization" and "Leave Authorization" as implemented Authorization Foundation consumers — none lists "Attendance Authorization." All three documents' `Last Updated` date precedes the Attendance Authorization merge date by one day. This is the same governance-staleness pattern already recorded in `attendance-authorization/discovery.md` §7 for Leave Authorization (relative to documents dated the same day Leave Authorization merged) — the pattern has now recurred for a second, consecutive capability.
- `MASTER_ARCHITECTURE_ROADMAP.md` names the next capability "Payroll Authorization" and positions it directly after "Attendance Authorization." `CAPABILITY_DEPENDENCY_GRAPH.md` — a different document — names a differently-worded item, "Payroll Integration," in a separate "Secondary" critical-path diagram rooted in "Leave Rules" rather than in Attendance Authorization. Repository evidence does not establish whether "Payroll Authorization" and "Payroll Integration" refer to the same capability, overlapping capabilities, or two distinct ones.
- `docs/product/02_PRODUCT_SCOPE.md` lists "Payroll Processing" under "HRIS" as a category of external systems, distinct from EOP's own product surface, with a stated exception that "EOP may integrate with HR systems." Repository evidence does not establish whether the roadmap's in-repo, `Planned`, authorization-focused "Payroll Authorization" capability is the same "Payroll" this product document excludes, an integration-only surface consistent with the stated exception, or an unrelated use of the same word.
- `CAPABILITY_DEPENDENCY_GRAPH.md` contains Indonesian-language governance text in at least one section reviewed (§5 of that document, e.g. *"Capability tidak boleh dibangun sebelum dependency-nya tersedia"*), alongside English-language sections elsewhere in the same document — a document-internal inconsistency noted here as repository evidence, not resolved.

This finding is reported per the Escalation Rule and is not resolved here.

---

# 8. Open Questions

Repository evidence does not answer the following:

- Whether "Payroll Authorization" (`MASTER_ARCHITECTURE_ROADMAP.md`, `Planned`, an in-repo authorization capability) and "Payroll Integration" (`CAPABILITY_DEPENDENCY_GRAPH.md`, a separate "Secondary" critical-path item) name the same future capability, overlapping capabilities, or two distinct ones — the two governing documents do not use consistent naming or dependency structure for whichever it/they are.
- Whether "Payroll" as referenced by the roadmap is the same "Payroll Processing" that `docs/product/02_PRODUCT_SCOPE.md` lists under "HRIS" (a category otherwise scoped out of EOP, subject to an integration exception), or a distinct, EOP-native capability — the repository does not reconcile these two framings.
- Whether Payroll, if built, is expected to be a system EOP computes and owns internally (consistent with every design doc's "future consumer that reads `APPROVED` rows and computes pay" framing) or a system EOP integrates with externally (consistent with the product scope document's "EOP may integrate with HR systems" exception) — these are structurally different outcomes and repository evidence supports both readings from different documents.
- What data a Payroll capability would need that does not yet exist in the schema — every design document that names Payroll as a future consumer also independently notes the absence of a `PayPeriod` concept, and of paid/unpaid or pay-multiplier flags on `LeaveRequest`/`Holiday`; the repository does not resolve whether these gaps are Payroll's own future responsibility to model or expected to be added to the upstream capabilities first.
- Whether the governance-staleness pattern identified in §7 (Attendance Authorization merged but not reflected in `ARCHITECTURE_STATUS.md`/`CAPABILITY_CATALOG.md`/`TECHNICAL_DEBT_REGISTER.md`) reflects a process lag that resolves before Payroll Authorization work begins, or a recurring gap in how these documents are maintained — the repository alone cannot distinguish these.

---

# 9. Architectural Ambiguities

Listed per `AI_DISCOVERY_GUIDE.md`; not resolved here.

- The relationship, if any, between "Payroll Authorization" (`MASTER_ARCHITECTURE_ROADMAP.md`) and "Payroll Integration" (`CAPABILITY_DEPENDENCY_GRAPH.md`) is not established by repository evidence (§7, §8).
- The relationship, if any, between the roadmap's in-repo "Payroll Authorization" capability and `docs/product/02_PRODUCT_SCOPE.md`'s "Payroll Processing" (listed under out-of-scope "HRIS," subject to an integration exception) is not established by repository evidence (§7, §8).
- Whether a future Payroll capability's protected resource(s) would be a genuinely new aggregate (e.g. a `PayrollRun`/`Payslip`) or a read-only projection over existing `APPROVED` data in Leave/Overtime/Timesheet/Attendance is not decidable from the repository — every reviewed design document anticipates the latter shape but none commits to it, and no code exists either way.
- `CAPABILITY_DEPENDENCY_GRAPH.md`'s mixed-language content (§7) raises an unresolved question about that document's authoritative status relative to `MASTER_ARCHITECTURE_ROADMAP.md`, which does not share this characteristic.

---

# 10. Recommended Next Step

```
Policy Discovery
```
