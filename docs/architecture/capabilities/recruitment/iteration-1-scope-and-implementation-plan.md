# Recruitment — Iteration 1 Scope and Implementation Plan

**Status:** Authorized — CPO/CTO Product Decision

**Capability:** Recruitment

**Owner:** Engineering (CPO/CTO-directed)

---

# 0. Authority

The CPO/CTO has explicitly selected Recruitment as the next product capability (superseding `docs/product/02_PRODUCT_SCOPE.md`'s prior "Out of Scope — HRIS" listing, updated alongside this plan), following the same precedent Payroll Processing already set in this repository: that same exclusion list named Payroll Processing, yet Payroll was built as a first-class capability without ever being treated as blocked by it.

No prior Discovery/Decision/Domain-Model-Discovery/Architecture-Gap-Analysis chain exists for Recruitment — this is a genuinely new capability, not a previously-blocked one being reconciled. Per the explicit execution order governing this work, this single document scopes and plans Iteration 1 directly, rather than repeating the full six-phase governance sequence, and makes every implementation-level decision needed to ship a production-ready vertical slice without inventing unspecified business/product policy.

---

# 1. Scope (Iteration 1 — Structure Only)

Mirrors the "bounded context structure only" precedent already used for Payroll's own Iteration 1 and Payslip's "CRUD-minus-mutation" scoping: three plain CRUD aggregates, no workflow engine, no interview scheduling, no offer/approval process, no notification/email integration, no candidate self-service portal.

- **`JobRequisition`** — an open position to fill. Master-data-shaped (mirrors `Shift`/`JobGrade`): `code` (unique), `title`, `organization_id`/`department_id`/`position_id` (mirrors `HrEmployee`'s own identity-field shape), `status` (free-form string, not an enforced state machine — mirrors `HrEmployee.employment_status` exactly, deliberately not a business-rule-bearing enum), `description`.
- **`Candidate`** — a person applying, explicitly **not** an `HrEmployee** (candidates are not employees; no FK relationship between them, mirroring `HrEmployee`'s own explicit independence from Project Tracking's `Employee`). Master-data-shaped: `first_name`/`last_name`/`full_name`, `email` (unique), `phone`.
- **`Application`** — links a `Candidate` to a `JobRequisition`. Peer-association aggregate, mirroring `Assignment` (Project Tracking's `Employee`↔`Project` link) exactly: two FKs to independently-owned aggregates, its own payload, pair-uniqueness (`candidate_id`, `job_requisition_id`) — a candidate applies once per requisition. `status` (free-form string, same rationale as `JobRequisition.status`), `applied_date` (required, mirrors `Assignment.start_date`).

**Explicitly out of scope for Iteration 1** (no business decision exists for any of these; none is invented here): interview scheduling, offer management, a recruitment pipeline/stage state machine, hiring-manager/recruiter role assignment, candidate self-service/external-facing auth, résumé/document storage, email/notification integration, any relationship to Payroll/Compensation/Attendance/Leave/Work Schedule.

---

# 2. Implementation-Level Decisions

Each decision below follows directly from existing repository precedent; none changes business policy, none creates a new domain-ownership boundary.

- **Delete rule**: `RESTRICT` for every FK (`organization_id`, `department_id`, `position_id`, `candidate_id`, `job_requisition_id`) — the now-dominant repository convention (matches `HrEmployee`, `Work Schedule`, every FK relevant to this context), not `Assignment`'s own outlier `CASCADE`.
- **`status` fields**: plain, unconstrained `String`, not an enum or state machine — mirrors `HrEmployee.employment_status` exactly. Avoids inventing recruitment-pipeline stages (applied/screening/interviewing/offered/hired/rejected) that no governance or product document defines. The API stores and returns whatever string is supplied; no service-level transition validation exists, matching `employment_status`'s own precedent.
- **Uniqueness**: `Application` gets a `UniqueConstraint(candidate_id, job_requisition_id)`, mirroring `Assignment`'s own `UniqueConstraint(employee_id, project_id)` exactly — the closest, most directly on-point precedent in the repository for "peer-association entity linking two independently-owned aggregates."
- **Authorization**: `CurrentUser`-only, no dedicated `AuthorizationEvaluator` — mirrors `Shift`/`JobGrade`/`Holiday`/`Assignment` (the majority pattern: 8 of 11 previously-reviewed capabilities, and every entity in this repository without a natural single-employee "owner" field). None of these three aggregates has an `employee_id`-shaped owner the way `Compensation`/`Work Schedule` do — there is no Owner Only candidate here, and inventing a new authorization mechanism (e.g., a "recruiter" role) is explicitly out of scope per the governing execution order.
- **Cross-aggregate validation**: `Application.create`/`update` validates both `candidate_id` and `job_requisition_id` exist, mirroring `AssignmentService`'s existence checks exactly. No organization-mismatch check is added (unlike `Assignment`'s `Employee`/`Project` check) — `Candidate` is not organization-scoped in this iteration (candidates are people, not yet linked to any organization until hired), so there is nothing to compare `JobRequisition.organization_id` against.
- **`JobRequisition` identity fields**: `organization_id`, `department_id`, `position_id` all required, mirroring `HrEmployee`'s own field set — `Position` already implies a `department_id`, but `HrEmployee` carries both directly regardless, an established repository convention this document follows rather than second-guesses.

---

# 3. Vertical Slice (per aggregate)

Model → Migration → Repository → Service → Schema → API → Tests, mirroring `Shift`'s stack for `JobRequisition`/`Candidate` and `Assignment`'s stack for `Application` exactly. No new abstractions; `BaseRepository`/`BaseEntity`/`SQLAlchemyUnitOfWork` reused unmodified.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` (updated alongside this plan — Recruitment removed from HRIS exclusion list)
- `services/api/src/eop_api/models/shift.py`, `services/shift.py`, `api/shifts.py` (master-data CRUD precedent)
- `services/api/src/eop_api/models/assignment.py`, `services/assignment.py`, `api/assignments.py` (peer-association precedent)
- `services/api/src/eop_api/models/hr_employee.py` (identity-field-set precedent, `employment_status` free-string precedent)
