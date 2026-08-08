# Payslip — Discovery

**Status:** Complete

**Capability:** Payslip (data-owning capability — distinct from Payroll and Payroll Authorization)

**Owner:** EOP Architecture Governance

---

# Purpose

This document records repository evidence for the Payslip capability. It follows the same methodology already used for `docs/architecture/capabilities/payroll/discovery.md` (and, before it, `LEAVE_DESIGN.md`/`ATTENDANCE_DESIGN.md`): observation and interpretation only, no architecture chosen, no schema authored, no calculation proposed. Every conclusion below is labeled **Repository Evidence**, **Logical Consequence** (a direct inference from that evidence, not itself observed), or **Unknown** (evidence is insufficient), matching `payroll/domain-model-discovery.md`'s convention.

`PayrollRun` now exists as real, merged code (Payroll Iteration 1) — this discovery treats it as repository evidence like any other entity, not as a plan. `Payslip` itself does not exist anywhere in the repository, confirmed by a fresh, repository-wide search (§10) — no prior document, including this conversation's own `payroll/decision.md`, which reserved its name, constitutes an implementation.

---

# Discovery Scope

Full file reads unless noted:

- `models/audit_log.py`, `services/audit_log.py`, `repositories/audit_log.py`, `api/audit_logs.py`, `core/audit.py` — not reviewed in any prior discovery in this conversation; read in full for this discovery (§1, §6)
- `models/payroll_run.py`, `repositories/payroll_run.py`, `services/payroll_run.py`, `schemas/payroll_run.py`, `api/payroll_runs.py` — the repository's own current, merged implementation (Payroll Iteration 1), reviewed as source-of-truth evidence, not as a plan
- Repository-wide grep for `ForeignKey(` across every file in `models/` — full result set reviewed (§2, §9), not sampled
- `models/task.py`, `models/assignment.py` — not previously reviewed; read for their FK shape (§2, §9)
- `models/attendance_event.py`, `models/leave_request.py`, `models/leave_balance.py`, `models/overtime_request.py`, `models/timesheet.py`, `models/hr_employee.py` — re-consulted from prior discoveries in this conversation, not re-derived
- `services/approval.py` — re-consulted (§4)
- `db/mixins.py`, `db/base.py`, `repositories/base.py` — re-consulted (§7, §8)
- Repository-wide, case-insensitive grep for `payslip|payroll|salary|compensation|earnings|deduction`, run fresh for this discovery (not reused from prior turns) — 47 files matched; every new match (not already catalogued by `payroll/discovery.md`) read in context (§10)
- Repository-wide, case-insensitive grep for `payslip` alone, run fresh — 8 files matched, all authored within this conversation (§10)
- `docs/architecture/capabilities/payroll/discovery.md`, `domain-model-discovery.md`, `decision.md`, `implementation-plan.md`, `architecture-review.md` — this conversation's own prior output, carried forward as evidence of what has already been established, not re-derived
- `docs/architecture/capabilities/attendance-authorization/policy-discovery.md` — not previously read in this conversation; read in full for its one payroll-adjacent mention (§10)

---

# 1. Immutable Financial-Style Records — Existing Precedents

**Repository Evidence**: Exactly one entity in the repository is documented as intentionally immutable: `AuditLog` (`models/audit_log.py:13-19`). Its own docstring: *"An immutable record of an action taken against some entity. Append-only: the repository/service layer never updates or deletes rows here, even though `BaseEntity` carries soft-delete/version columns shared by every entity in this project."* `AuditLogRepository`'s own docstring confirms the same at the persistence layer: *"Append-only: callers only create, get, and paginate"* (`repositories/audit_log.py:16`) — it does not call, wrap, or override `BaseRepository.update`/`.delete`, it simply never calls them.

`AuditLog`'s fields are `user_id` (nullable FK → `users.id`, `SET NULL`), `action` (`String(100)`), `entity_type` (`String(100)`), `entity_id` (bare `UUID`, **not** a FK), `details` (`JSONB`, nullable) — a generic action-log shape, not a financial or business-domain record. `core/audit.py`'s `AuditEntityType` enum lists `ORGANIZATION`, `PROJECT`, `EMPLOYEE`, `ASSIGNMENT`, `TASK`, `USER`, `ROLE` only — no HR-domain entity (`LeaveRequest`, `AttendanceEvent`, `Timesheet`, `OvertimeRequest`, `PayrollRun`) appears in it.

`AuditLogService.record()` — the only way to create a row — is never called by any other service in the repository (confirmed by grep: `AuditLogService` appears only inside `services/audit_log.py` itself). Its own docstring: *"Nothing in this PR calls it yet — it is infrastructure for later adoption."* `api/audit_logs.py` exposes only `GET /audit-logs` — no `POST` route exists, so the only way to create an `AuditLog` row via HTTP is not available at all; only an internal service-to-service call (which none currently makes) can create one.

No monetary, currency, or financial-domain field exists on `AuditLog` or on any other entity (confirmed by the repository-wide search already conducted in `payroll/discovery.md` §3, not re-run here).

**Logical Consequence**: The repository's only immutability precedent is (a) enforced entirely by service-layer discipline/convention, not by any database constraint, model-level override, or removed method — `BaseRepository.update`/`.delete` remain technically callable against an `AuditLog` row; nothing prevents it beyond `AuditLogRepository`/`AuditLogService` simply not exposing that call path; and (b) generic and administrative in purpose, not employee-scoped and not shaped like a business/financial record. There is no precedent in the repository for an immutable record that also carries business-domain fields (an amount, a period, a status) the way a Payslip would need to.

**Unknown**: Whether a future Payslip's immutability (if decided) would follow `AuditLog`'s convention-only pattern (a service that simply never calls `update`/`delete`) or would require a different, stronger mechanism (e.g., a database-level constraint) is not addressed anywhere in the repository — no entity anywhere enforces immutability below the service layer.

---

# 2. Aggregate Patterns Involving Foreign Keys — Existing Precedents

**Repository Evidence**: A repository-wide grep for `ForeignKey(` across every file in `models/` (36 matches, full result set reviewed, not sampled) shows every foreign key in the repository falls into one of four categories:

1. **Reference/master-data FKs** — an entity pointing to organization/department/position/team/location/job-grade/employment-type/employment-status/shift/location-type (e.g. `hr_employees.organization_id`, `hr_employees.job_grade_id`).
2. **Identity FKs** — pointing to `users.id` or `roles.id` (e.g. `LeaveRequest.approved_by`, `AuditLog.user_id`, `user_roles`).
3. **Self-referential FKs** — `departments.parent_id`, `teams.parent_team_id`, `hr_employees.manager_id`, `locations.parent_id`.
4. **One business/workflow entity referencing another** — exactly two instances exist: `Task.project_id` (`models/task.py:25`, `ondelete="CASCADE"`) and `Assignment.project_id`/`Assignment.employee_id` (`models/assignment.py:26,29`, both `ondelete="CASCADE"`). Both belong to the repository's older Project Tracking domain, not the newer HR domain.

Every FK in categories 1–3, and every FK anywhere in the HR domain specifically (`AttendanceEvent`, `LeaveRequest`, `LeaveBalance`, `OvertimeRequest`, `Timesheet`, `HrEmployee` itself), uses `ondelete="RESTRICT"` (the two exceptions being `HrEmployee.user_id`, `SET NULL`, and `AuditLog.user_id`, `SET NULL` — both nullable, optional links, not the primary scoping FK). Category 4's two instances (`Task`, `Assignment`, Project Tracking domain) use `ondelete="CASCADE"` instead.

`AttendanceEvent` (`models/attendance_event.py:45,48`) is the only entity in the HR domain with **two** required FKs on one row: `employee_id` (→ `hr_employees.id`, `RESTRICT`) and `shift_id` (→ `shifts.id`, `RESTRICT`) — one pointing to the employee the row is about, one pointing to reference data.

**Logical Consequence**: `Payslip`'s anticipated shape (`payroll_run_id` + `employee_id`, per `payroll/decision.md` §3/§5) would be the **first HR-domain entity with two required FKs where neither target is reference/master data** — `AttendanceEvent`'s second FK (`shift_id`) points to reference data, not to another business/workflow aggregate the way `payroll_run_id` would point to `PayrollRun`. The closest precedent for "one business aggregate scoped under another via FK" is `Task.project_id`/`Assignment`'s two FKs — but both belong to the older Project Tracking domain and both use `CASCADE`, the opposite retention posture from every RESTRICT-scoped HR entity reviewed. If `Payslip.payroll_run_id` follows the HR domain's own established convention (as `PayrollRun` itself already does — zero FKs, but consistent with every other HR entity's `RESTRICT` posture wherever it does have FKs), it would use `RESTRICT`, not `CASCADE`; if it instead followed the one existing precedent for "business entity referencing business entity" (`Task`/`Assignment`), it would use `CASCADE`. The repository does not resolve this choice by uniform convention — the two applicable precedents disagree.

**Unknown**: Whether `Payslip.payroll_run_id`/`Payslip.employee_id` would use `RESTRICT` or `CASCADE` is not decidable from repository evidence alone — the HR-domain convention and the only existing "business-entity-referencing-business-entity" precedent point in different directions.

---

# 3. Existing Ownership Boundaries

**Repository Evidence**: `payroll/decision.md` §4 and `payroll/domain-model-discovery.md` A2 (both already-established governance documents in this repository, re-consulted, not re-derived here) state: Payroll (and, by the same reasoning, Payslip) must never own the `LeaveRequest`/`OvertimeRequest`/`Timesheet` approval lifecycle, `AttendanceEvent` capture, `LeaveBalance` bookkeeping, or any HR master-data entity. `PayrollRun`'s actual, merged implementation (`services/payroll_run.py`) confirms this in code: it imports and calls nothing from `LeaveRequestRepository`, `AttendanceEventRepository`, `ApprovalService`, or any other producer capability — it is a fully isolated CRUD service, exactly as `implementation-plan.md`/`architecture-review.md` specified and verified.

**Logical Consequence**: `Payslip`, as `PayrollRun`'s sibling aggregate (per `decision.md` §3), would inherit the identical boundary: it may read `PayrollRun` (by FK) and `HrEmployee` (by FK, once added) and would not own or modify any producer capability's data, consistent with every ownership statement already established for Payroll generally.

**Unknown**: None beyond what `payroll/decision.md`/`domain-model-discovery.md` already left open (compensation data source, lifecycle, batch mechanism — restated in §10, not re-derived).

---

# 4. Existing Approval Lifecycle Reuse

**Repository Evidence**: `ApprovalService` (`services/approval.py`, re-consulted) orchestrates exactly three entities — `LeaveRequest`, `OvertimeRequest`, `Timesheet` — via `approve_*`/`reject_*` method pairs, each gated by Approval Authorization (Manager Approval, ADR-008). No other entity in the repository is, or has ever been, wired into `ApprovalService`. `PayrollRun`'s current implementation has no `status` field (§ Model, `payroll/implementation-plan.md`) and is not referenced anywhere in `services/approval.py`.

**Logical Consequence**: There is no existing precedent for `Payslip` (or `PayrollRun`) participating in the `pending → approved/rejected` approval lifecycle `ApprovalService` provides — that mechanism is scoped, by the repository's own code, to exactly the three request-shaped entities it already governs, and extending it to a fourth entity has no precedent (the same finding `payroll/domain-model-discovery.md` A2 already reached for `PayrollRun`, re-confirmed here for `Payslip`).

**Unknown**: Whether `Payslip` would ever need an approval-style workflow of its own (e.g., a payslip requiring sign-off before being finalized) is not addressed by any repository evidence — no document proposes it, and no precedent exists to model it against.

---

# 5. Existing Employee-Scoped Aggregates

**Repository Evidence**: `AttendanceEvent`, `LeaveRequest`, `LeaveBalance`, `OvertimeRequest`, `Timesheet` are each employee-scoped via a required `employee_id` FK → `hr_employees.id`, `ON DELETE RESTRICT` (re-confirmed by the fresh FK grep, §2). `PayrollRun`, in contrast, is explicitly **not** employee-scoped — confirmed both by `payroll/decision.md` §2/§6 and by its actual merged model (`models/payroll_run.py`), which has zero FKs of any kind.

**Logical Consequence**: `Payslip`, per `decision.md` §3 ("scoped to one employee and one `PayrollRun`"), would be the sixth employee-scoped aggregate in the repository, following the same `employee_id` → `hr_employees.id`, `RESTRICT` shape as the other five (consistent with §2's finding that the HR domain's own convention favors `RESTRICT`).

**Unknown**: None — this is the most directly precedented aspect of Payslip's anticipated shape.

---

# 6. Existing Audit/History Patterns

**Repository Evidence**: Beyond `AuditLog` (§1) — which is generic, unused by any producer capability, and carries no employee or business-domain field — the only "history" mechanism anywhere in the repository is `AuditMixin` (`created_by`/`updated_by`, nullable `UUID` columns, `db/mixins.py:27-29`), present on every `BaseEntity` subclass including `PayrollRun`. `AuditMixin` records **who last touched a row**, not what the row's value was before that touch — confirmed by direct inspection: neither column is populated by any reviewed service today (every `create`/`update` call in every reviewed service passes only its own domain fields via `**data.model_dump()`/`**values`, never `created_by`/`updated_by`) — both remain `None` in practice across the entire repository as it stands, a finding not previously stated this explicitly in any prior Payroll document.

No entity anywhere carries a `valid_from`/`valid_to`, a version-history table, or a "previous value" column of any kind (re-confirmed from `payroll/domain-model-discovery.md` E4, not re-derived).

**Logical Consequence**: The repository has no working precedent for reconstructing "what was true at a past point in time" for any entity, including who last modified it (`AuditMixin`'s columns exist but are populated by nothing). A Payslip requiring a defensible historical record (e.g., to answer "what was this figure when it was issued") would have no existing repository mechanism to build on beyond `AuditLog`'s unused, generic, non-financial pattern (§1).

**Unknown**: Whether `AuditMixin`'s `created_by`/`updated_by` columns are expected to be populated by a future, unbuilt mechanism, or are effectively dead columns on every entity today, is not addressed anywhere in the repository.

---

# 7. Existing `BaseEntity` / `VersionMixin` Usage

**Repository Evidence**: Every persisted entity in the repository, without exception — including `AuditLog` and the newly-merged `PayrollRun` — extends `BaseEntity` (`UUIDMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin`/`VersionMixin`, `db/base.py:16-24`). `VersionMixin.version` (`Integer`, default `1`, `db/mixins.py:40-41`) is present on all of them. Repository-wide, `version` is never read, compared, or incremented-on-conflict by any reviewed service (`payroll/domain-model-discovery.md` E4; `TECHNICAL_DEBT_REGISTER.md` TD-002 names this gap for Approval Authorization specifically, not as a repository-wide finding, though the underlying absence is repository-wide).

**Logical Consequence**: `Payslip`, following the uniform pattern every entity in the repository (with no exception found) already follows, would extend `BaseEntity` the same way — this is the one point in this discovery with no competing precedent or ambiguity anywhere. Its `version` column, if added, would be unenforced from day one, consistent with every existing entity, `PayrollRun` included.

**Unknown**: None.

---

# 8. Existing Delete Semantics

**Repository Evidence**: `BaseRepository.delete` (`repositories/base.py:59-66`) performs a hard delete — `await self.session.delete(instance)` — on every entity, despite `SoftDeleteMixin` (`deleted_at`/`is_deleted`) being present on all of them, `PayrollRun` included (re-confirmed against the merged `PayrollRunRepository`, which does not override `.delete`). `AuditLog` is the sole entity where this is never invoked in practice, not because the mechanism differs, but because `AuditLogRepository`/`AuditLogService` simply never call it (§1) — the underlying hard-delete method is identical and equally available.

**Logical Consequence**: Absent a specific override, a future `Payslip` built the same way every other entity in the repository has been (including `PayrollRun` itself, one turn ago) would be hard-deletable via the same inherited `BaseRepository.delete` — `SoftDeleteMixin`'s columns would exist on the row but would not, by themselves, prevent deletion, exactly as they do not for any other entity today. Achieving true delete-prevention or soft-delete-only semantics for `Payslip` would require the same kind of service-layer discipline `AuditLog` uses (simply never calling `.delete`, and not exposing a `DELETE` route) — not something inherited automatically from `BaseEntity`/`BaseRepository`.

**Unknown**: None — this finding is unambiguous and applies uniformly.

---

# 9. Existing Repository/Service/API Patterns Most Similar to Payslip

**Repository Evidence**: Ranking the reviewed precedents by structural closeness to Payslip's anticipated shape (employee-scoped, two FKs, one pointing to a business-workflow aggregate rather than reference data, per `decision.md` §3):

1. **`AttendanceEvent`** (`models/attendance_event.py`) — closest on FK *count* (two required FKs on one row) and on being HR-domain/`RESTRICT`-scoped, but its second FK (`shift_id`) points to reference data, not to another business aggregate.
2. **`Task`/`Assignment`** (`models/task.py`, `models/assignment.py`) — closest on FK *target type* (one business/workflow entity referencing another, `Task.project_id`), but belongs to the older Project Tracking domain, uses `CASCADE` (not `RESTRICT`), and is not employee-scoped the way HR entities are.
3. **`PayrollRun`** itself — the closest precedent for plain CRUD service/repository/API shape (`PayrollRunService`/`PayrollRunRepository`/`api/payroll_runs.py`, merged one turn prior in this conversation) and for the "no computation, no lifecycle, no authorization" scaffolding posture — but has no FK at all, so it is not a precedent for Payslip's FK shape, only for its CRUD-scaffold shape.

No single existing entity matches Payslip's full anticipated shape (employee-scoped + business-aggregate-scoped + CRUD-scaffold-only). It would combine elements of three different existing precedents, no two of which currently coexist on one entity.

**Logical Consequence**: Building `Payslip` by direct analogy to any single existing entity would be incomplete — `AttendanceEvent` for FK count/RESTRICT convention, `Task`/`Assignment` for the "references another business aggregate" shape (noting the CASCADE-vs-RESTRICT tension already flagged in §2), and `PayrollRun` for the service/repository/API CRUD-scaffold shape, would all need to be drawn on together.

**Unknown**: None beyond §2's CASCADE-vs-RESTRICT tension, restated here as it also bears directly on this ranking.

---

# 10. Existing Documents Mentioning Payslip, Payroll, Salary, Compensation, Earnings, Deductions, Payroll Run, or Payroll Integration

**Repository Evidence**: A fresh, repository-wide, case-insensitive grep for `payslip|payroll|salary|compensation|earnings|deduction` returns 47 files. Of these:

- **8 files mention "Payslip" specifically** — and all 8 were authored within this conversation (`payroll_run.py`'s own docstring, and the five `payroll/`-capability documents plus the two `payroll-authorization/`-capability documents). A separate, standalone grep for `payslip` alone (case-insensitive) confirms the same 8 files, no others. **No document or source file that predates this conversation's own work ever mentions "Payslip."**
- **"Earnings"** returns zero matches anywhere in the repository, standalone from the other terms — confirmed by the combined grep returning no file that matched *only* on "earnings"; every file matched on "payroll" and/or "deduction" instead.
- New matches not previously catalogued by `payroll/discovery.md`: `services/approval.py` (the same "deduction calculation... unresolved" language already known from `services/leave_balance.py`'s cross-reference, concerning leave-balance days, not currency); `attendance-authorization/policy-discovery.md` (names "Timesheet/Payroll/Analytics" as future consumers of attendance data — same future-consumer framing found throughout every other design document in `payroll/discovery.md` §2.2); `ADR-007-authorization-foundation.md` and `capabilities/authorization/decision.md` (both list "Payroll" among future capabilities that would integrate Authorization Foundation independently — consistent with, not additive to, `payroll-authorization/discovery.md`'s own findings).
- No new file introduces a monetary field, a `PayrollIntegration`-named concept, or any Payslip-adjacent schema not already catalogued by `payroll/discovery.md`/`domain-model-discovery.md`.

**Logical Consequence**: Every substantive fact this discovery's predecessor documents (`payroll/discovery.md`, `domain-model-discovery.md`) already established about the absence of compensation data, pay-period concepts, and financial fields remains true and unchanged one iteration later — `PayrollRun`'s implementation did not introduce any of them (confirmed directly against its merged code, §3), and no new document has introduced any either.

**Unknown**: Same open items `payroll/decision.md` §7 and `domain-model-discovery.md`'s Remaining Unknowns already recorded (compensation source, pay-period cadence, tax/deduction rules, currency) — not re-litigated here, since no new evidence bears on them.

---

# Findings Summary

- The repository's only immutability precedent (`AuditLog`) is generic, unused, and enforced purely by service-layer convention — not a financial-record pattern, and not a mechanism Payslip could inherit automatically (§1).
- Every FK in the repository targets reference data, `HrEmployee`/`User`, or (in exactly two, older-domain cases) another business entity via `CASCADE` — `Payslip`'s anticipated `payroll_run_id`+`employee_id` shape would be the first HR-domain entity combining an employee-scoping FK with a FK to another business aggregate, and the repository's two applicable conventions (`RESTRICT` vs. `CASCADE`) disagree (§2, §9).
- Ownership boundaries already established for Payroll generally are confirmed, not merely asserted, by `PayrollRun`'s actual merged code — it calls nothing outside itself (§3).
- No precedent exists for extending `ApprovalService`'s lifecycle to a fourth entity (§4).
- `Payslip` would be the sixth employee-scoped HR aggregate, the most directly precedented part of its anticipated shape (§5).
- `AuditMixin`'s `created_by`/`updated_by` columns are populated by no reviewed service today, repository-wide — a finding not previously stated this explicitly (§6).
- `BaseEntity`/`VersionMixin` usage is fully uniform, no exception found (§7).
- Hard-delete is the repository-wide default; true immutability would require the same kind of service-layer discipline `AuditLog` uses, not anything inherited automatically (§8).
- No single existing entity matches Payslip's full anticipated shape; it would combine elements of three different, non-overlapping precedents (§9).
- No document anywhere in the repository predating this conversation ever mentions "Payslip" (§10).

---

# Recommended Next Step

```
Payslip Capability Decision
```
