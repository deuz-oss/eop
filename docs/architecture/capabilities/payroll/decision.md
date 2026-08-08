# Payroll — Capability Decision

**Capability:** Payroll (data-owning capability)

**Status:** Approved — Boundary Decision (Version 1) + Iteration 2 Addendum (Version 2) resolving lifecycle, batch-processing shape, and pay-rate source + Iteration 3 Addendum (Version 3, below) recording business scope (tax/overtime/attendance out of scope, no new rate sources, eligibility unchanged). §1–§10 below are retained unmodified as Version 1's boundary decision; neither Addendum reopens or restates them except where explicitly cited.

**Version:** 3 (Addendum) — Version 1 and Version 2 stand as written; Version 3 adds business-scope decisions only, superseding nothing already decided.

**Owner:** Architecture

---

# Addendum (Version 2) — Iteration 2: Lifecycle, Batch Shape, Pay-Rate Source

## Purpose

Version 1 (§7, §9 below) left three items explicitly open, naming them as the prerequisite work before Payroll implementation could proceed past structural scaffolding: (1) `PayrollRun`'s lifecycle/state machine, (2) batch-processing shape, (3) where compensation/rate data originates. This Addendum resolves all three, using only evidence already in the repository and in already-approved governance (`compensation/decision.md`, merged Payroll/Compensation Iteration 1 code). It does not reopen Payroll Iteration 1, Payroll Authorization, Compensation, or Monetary Representation, and it does not design a computation formula — it decides shape and source only, consistent with Version 1's own scope discipline (§ Purpose, "no business rule... is invented anywhere in this document").

## Contradiction Check (performed before recording any decision below)

- `payroll/decision.md` §7/§9 (Version 1, this document): lifecycle and batch shape are explicitly "left open" / "has no repository precedent" — no prior decision to contradict.
- `compensation/decision.md` §4 ("Compensation Content"): records **Hourly Rate: Supported** as a compensation concept, and **Deduction: Excluded... "Belongs to Payroll Calculation / Payroll Run."** Neither is a contradiction of the decisions below — the first confirms Hourly Rate is Compensation's own future concept, not yet implemented (`models/compensation.py`, Iteration 1, has only `base_salary_amount`/`base_salary_currency`/`effective_from`/`is_active` — no `hourly_rate` column exists), and the second confirms Payroll already owns "Deduction" by Compensation's own boundary decision, consistent with not inventing a deduction-shaped rate field here.
- No contradiction found. Proceeding to record the decisions.

## 1. PayrollRun Lifecycle

**Decision: `DRAFT → PROCESSING → COMPLETED`. No `CANCELLED` state.**

- `PayrollRun` is the lifecycle boundary for one payroll batch: it enters `DRAFT` on creation, moves to `PROCESSING` once payslip calculation for the batch begins, and reaches `COMPLETED` once calculation for the batch has finished. This is the smallest state machine consistent with Version 1 §2's own framing of `PayrollRun` as "the output of a decision process" that must not be silently recomputed once issued (the same audit-trail rationale Version 1 already used to justify persisting `PayrollRun`/`Payslip` at all).
- **`CANCELLED` is rejected**, per this Addendum's own governing instruction not to add it "merely for completeness." Concrete repository evidence against adding it now: `api/payroll_runs.py` already exposes `DELETE /hr/payroll-runs/{id}`, a hard delete inherited from `BaseRepository`. A `DRAFT` `PayrollRun` (no `Payslip` rows yet) can already be abandoned via that existing endpoint — no gap exists for `CANCELLED` to fill at that stage. Once `Payslip` rows exist, `Payslip.payroll_run_id` is `ON DELETE RESTRICT` (`models/payslip.py`), so the database already refuses to delete a `PayrollRun` with payslips — again, no code path exists today that a `CANCELLED` state would unblock. Introducing it now would be adding state with no evidenced consumer, which Version 1's own Evidence Rule prohibits.
- This field does not exist on `PayrollRun` today (`models/payroll_run.py` has only `code`/`name`); this Addendum decides the state machine's shape, not its column type or migration — that is Implementation Plan territory, per Version 1's own boundary (§ Purpose).

## 2. Batch Processing

**Decision: `PayrollRun` represents a batch for all eligible employees in its payroll scope. No per-employee `PayrollRun` lifecycle.**

- Confirmed consistent with Version 1 §6, already decided: *"`PayrollRun` does not require `employee_id`... it is not employee-scoped. That scoping belongs to `Payslip`."* A batch-shaped `PayrollRun` is the only reading consistent with that existing constraint — a per-employee `PayrollRun` would require exactly the `employee_id` field Version 1 already decided against.
- Payroll Calculation operates as part of the `PayrollRun` batch, not as a separate employee-facing workflow. `PayrollCalculationService.calculate(payroll_run_id, employee_id)` (merged, Iteration 1) already takes this exact shape — one `PayrollRun`, many per-employee `calculate` calls producing one `Payslip` each — so this decision ratifies the shape already implemented, rather than introducing a new one.
- "Eligible employees in its payroll scope" is not further defined here (e.g., filtering by employment status, organization, or department) — that selection rule is computation logic, explicitly out of this Addendum's scope, same boundary Version 1 already drew around tax/deduction formulas.

## 3. Pay-Rate Source

**Decision: `Compensation.base_salary` remains the sole authoritative salary source for Iteration 2. No `hourly_rate`, `overtime_rate`, `overtime_multiplier`, `working_day_rate`, or `attendance_deduction_rate` field is introduced.**

- No repository or governance evidence supports inventing any of the listed fields now. `compensation/decision.md` §4 already records `Hourly Rate: Supported` as a *Compensation* concept — but not yet implemented (confirmed above) — and explicitly assigns `Deduction` to Payroll. Both confirm ownership boundaries already exist; neither supplies an actual rate value or conversion formula for Payroll to consume.
- `AttendanceEvent`/`ReconciliationService`'s computed daily status (`holiday`/`leave`/`present`/`absent`) and `OvertimeRequest.status == "approved"` remain available, already-governed, read-only inputs (Version 1 §5; `attendance-authorization/decision.md`) — but neither carries a worked-hours quantity or a rate to multiply it by. Converting either into a monetary amount requires an explicit business rule (a tax/overtime/working-day formula) that does not exist in this repository today and is not invented here, consistent with Version 1's own prohibition on inventing "a tax formula, a rate structure, a pay-period cadence."
- Practical effect: Iteration 2's `PayrollCalculationService` may consume `AttendanceEvent`/`ReconciliationService` output and `OvertimeRequest.status` as read-only signals (e.g., to decide whether a payslip should be generated, or to record a non-monetary attendance summary), but must not derive or persist a monetary amount from them until a separate, explicit business-rule decision exists. Gross/Net Salary computation continues to originate only from `Compensation.base_salary`, per Version 1's Iteration 1 rule (unchanged, not reopened).

## What This Addendum Does Not Decide

- The actual tax, overtime-pay, or attendance-deduction formula (if/when one is introduced) — a future, separate, explicit business decision, not assumed here.
- `PayrollRun`'s exact schema/columns for the new lifecycle state (migration-level detail — Implementation Plan territory).
- "Eligible employees in its payroll scope" selection criteria.
- Any change to Compensation, Monetary Representation, or Payroll Authorization — none are reopened by this Addendum.

## Recommendation

An Implementation Plan may now be written for: (a) adding a `status` column to `PayrollRun` with the three-state lifecycle above, (b) confirming/documenting the existing batch-shaped `calculate` call pattern, and (c) leaving `PayrollCalculationService`'s rate source unchanged (`Compensation.base_salary` only). No new business-rule (tax/overtime/deduction formula) work is authorized by this Addendum.

---

# Addendum (Version 3) — Iteration 3: Payroll Business Scope

## Purpose

The Iteration 2 Addendum (§ above) resolved `PayrollRun`'s lifecycle, batch shape, and pay-rate source, but left tax, overtime, and attendance deduction explicitly open (§3: *"Converting [Attendance/Overtime] into a monetary amount requires an explicit business rule that does not exist in this repository today and is not invented here"*). `docs/architecture/capabilities/payroll-calculation/decision.md` and `discovery.md` independently confirm the same gap from the calculation-capability side: no monetary model, no formula/rule/expression engine, and no computed-hours field exists anywhere in the repository (`payroll-calculation/discovery.md` §3–§5, §7).

This Addendum closes that gap for Iteration 3 by deciding each item **out of scope**, not by inventing a formula. "Out of scope" is itself a sufficient, complete decision — the same pattern Version 1 and Version 2 already used for tax/overtime/deduction ("no business rule... is invented anywhere in this document"). No Discovery is reopened: the evidence these decisions rest on (§ above, `payroll-calculation/discovery.md` §3–§5, §7, §9) is already gathered and unchanged.

## 1. Tax

**Decision: Out of scope for Payroll Iteration 3.** No tax formula, tax rate, tax bracket, withholding rule, or tax engine is introduced. Confirmed consistent with existing evidence: `payroll-calculation/discovery.md` §5 found zero repository precedent for any rule/formula/expression/policy engine; §7 found "Formula execution: Unknown... Nothing to decide against." No contradiction exists to resolve.

## 2. Overtime

**Decision: Out of scope for Payroll Iteration 3.** Approved `OvertimeRequest` data remains available as a future read-only Payroll input (Version 1 §5; `payroll-calculation/decision.md` §6, "Read-only"), but Payroll Calculation must not convert overtime duration into monetary compensation this iteration. No `overtime_rate`, `overtime_multiplier`, `hourly_rate`, overtime formula, or overtime aggregation logic is introduced. Confirmed consistent: `payroll-calculation/discovery.md` §9 found overtime duration has **no owner anywhere in the repository** — `OvertimeRequest.start_time`/`end_time` are stored as submitted and never subtracted or aggregated by any service. There is no existing hours figure to convert into pay, even setting the rate question aside.

## 3. Attendance

**Decision: Out of scope for Payroll Iteration 3.** `AttendanceEvent`/`ReconciliationService` data remains a future read-only Payroll dependency (Version 1 §5), but no attendance deduction, absence deduction, working-day rate, attendance multiplier, or attendance-based payroll formula is introduced. Confirmed consistent: `ReconciliationService` (`payroll-calculation/discovery.md` §1) produces only a four-value classification (`holiday`/`leave`/`present`/`absent`), never an hours or pay figure, and `Holiday` carries no `is_paid`/pay-multiplier field anywhere in the schema.

## 4. Rate Sources

**Decision: No additional monetary rate source is introduced.** The only currently authorized monetary source remains `Compensation.base_salary` (Version 2 Addendum §3, unchanged). No new Compensation rate field (`hourly_rate`, or any other) is added — `compensation/decision.md` §4's "Hourly Rate: Supported" remains a future *Compensation* concept, not implemented in the merged schema, and not activated by this document (Compensation governance is not reopened).

## 5. Payroll Eligibility

**Decision: The existing eligibility rule remains authoritative and unchanged.** `Compensation.is_active == true` (Version 2 Addendum §3, implemented as `CompensationService.list_active`). No additional employee-status, leave-status, attendance-status, termination-status, organization, or employment-status filter is introduced for Iteration 3.

## Resulting Data Flow (Confirmed Unchanged)

```
Employee -> Active Compensation -> PayrollRun -> PayrollCalculation -> Payslip
```

with `gross_salary = net_salary = Compensation.base_salary`, exactly as Iteration 1/2 already implemented and this Addendum does not change.

## Recommendation

No new Implementation Plan is required beyond verifying the already-merged Iteration 1/2 implementation satisfies §1–§5 above (it does — see the accompanying inspection). This Addendum records business scope; it does not authorize new computation code.

---

# Version 1 (Historical Record — Boundary Decision, Unmodified Except Where Cited Above)

The following sections (§1–§10, original numbering) are Version 1's unmodified text.

---

# Purpose

This document is the Capability Decision for Payroll, following `payroll/discovery.md`. It answers the boundary questions repository evidence can answer — whether Payroll owns a persisted aggregate, whether Payslip is its own aggregate or a projection, what Payroll owns versus consumes, and what depends on what. It does not select a lifecycle state machine, does not design a schema, does not specify computation logic, and does not write an ADR. Every decision below is derived from an existing structural precedent already implemented in this repository, cited by file and line; no business rule (a tax formula, a rate structure, a pay-period cadence) is invented anywhere in this document.

This is not Payroll Authorization. `docs/architecture/capabilities/payroll-authorization/decision.md` remains in force and unchanged: no authorization policy is selected here, because this document does not implement the resource that decision found missing — it only decides what shape that resource, once built, should take.

---

# 1. Repository Evidence (carried forward from Discovery)

- Nine producer capabilities exist and are implemented; none carries a monetary field (`payroll/discovery.md` §1, §3).
- No `PayPeriod`, salary, rate, allowance, deduction, tax, or benefit concept exists anywhere (`discovery.md` §3, §4).
- Three distinct orchestration shapes already exist: per-entity CRUD service (dominant pattern), cross-entity orchestrator with no owned table (`ApprovalService`, adopted only via an explicit decision — "Option B," `APPROVAL_ORCHESTRATION_DESIGN.md`), and read-only computed-result orchestrator with no owned table (`ReconciliationService`, explicitly single-employee/single-date) (`discovery.md` §5).
- No batch-over-employees-for-a-period precedent exists anywhere in the repository (`discovery.md` §4, §5).
- `ARCHITECTURE_INVENTORY.md` §8 names "Business Audit" as a `High` priority, currently-unowned Architecture Gap.
- `LeaveBalance` is explicitly unsynchronized with `LeaveRequest` approval, and `OvertimeRequest`/`Timesheet` CRUD have no authorization at all (`discovery.md` §1, §6).

---

# 2. Decision — Does Payroll Own a `PayrollRun`-Shaped Aggregate?

**Yes. Payroll's computed output must be a persisted aggregate, not a purely computed, on-demand view.**

## Rationale

The repository already draws this exact distinction, in its own code, between two categories of derived data:

- **Decisions/outputs that are persisted**: `LeaveRequest`, `OvertimeRequest`, and `Timesheet` all persist their `pending → approved/rejected` outcome (`status`, `approved_by`, `approved_at`) directly on the row — once a decision is made, it is not left to be recomputed later from upstream facts.
- **Views that are recomputed on demand and never persisted**: `ReconciliationService`'s `holiday`/`leave`/`present`/`absent` result is deliberately not stored — it "owns no aggregate, no table" (`reconciliation.py:23-24`) and is re-derived from `HolidayRepository`/`LeaveRequestRepository`/`AttendanceEventRepository` on every call.

A payroll computation is structurally closer to the first category than the second. It is the output of a decision process (what an employee is owed for a period, given the inputs available at computation time), not a pure re-derivable fact about a single point in time the way "was this employee present on this date" is. Unlike Reconciliation's inputs, several of Payroll's own likely inputs are themselves mutable after the fact (a `LeaveRequest` can later be corrected, a `JobGrade` reassigned) — recomputing "live" on every read would silently change a figure that, once communicated to an employee, needs to stay stable. This is also the exact concern `ARCHITECTURE_INVENTORY.md` §8 already names, unprompted by this decision, as a `High` priority, currently-unowned gap ("Business Audit").

This decision reserves the name `PayrollRun` for this aggregate, following the same convention `attendance-authorization/decision.md` used to reserve `AttendanceAuthorizationEvaluator`'s name before any code existed (`attendance-authorization/decision.md` §4: "name reserved by this decision; not yet created — no code is implemented"). No field, column, or schema for `PayrollRun` is specified here — that is implementation-plan or further-decision territory, not boundary territory.

## What Is Not Decided Here

The specific state machine `PayrollRun` would follow (repository evidence shows only a binary `pending → approved/rejected` transition anywhere, which does not obviously fit a computation pipeline) and its exact fields are open (§7).

---

# 3. Decision — Is Payslip Its Own Aggregate or a Projection?

**Payslip is its own persisted aggregate, scoped to one employee and one `PayrollRun`, not a purely computed projection.**

## Rationale

Two structural analogies exist in the repository for "one shared process, multiple per-subject outcomes":

- `ApprovalService` is the closest: one orchestrator, applied to many individual entities, writes its outcome **directly onto each entity's own existing row** (no separate "decision record" aggregate per entity). By this analogy alone, a per-employee payslip could be argued as a value materialized directly wherever it's needed, not its own row.
- However, `ApprovalService`'s target entities (`LeaveRequest`/`OvertimeRequest`/`Timesheet`) are themselves already the durable record of what was asked for — the "outcome" written back is a small, non-financial status change to an existing request. A payslip has no equivalent pre-existing row to attach to; it is an entirely new fact (what was paid) about a period that did not exist as a request beforehand. The closer parallel is `PayrollRun` itself (§2) needing a durable record, extended one level down to the per-employee output within that run.

`ARCHITECTURE_INVENTORY.md` §8's "Business Audit" gap applies with particular force to a payslip specifically: it is the kind of individually-referenceable, employee-facing financial record where recomputing it live from current upstream data (after a later correction to a `LeaveRequest` or a `JobGrade` change) would silently rewrite history — the same risk already named, unprompted, as an unresolved repository-wide gap. A "projection, recomputed on read" shape is the shape the repository already uses for exactly the case where that risk is acceptable (`ReconciliationService`, a same-day attendance status with no financial or legal consequence). Extending that same low-durability shape to a financial record the audit gap already flags is not supported by repository evidence to be safe, so it is not selected.

## What Is Not Decided Here

`Payslip`'s exact relationship to `PayrollRun` (one-to-many is the only shape consistent with "one run, many employees," but no cardinality, FK direction, or field list is specified here) and whether it is generated synchronously with `PayrollRun` or as a separate downstream step (§7).

---

# 4. Ownership Boundaries

## What Payroll Owns

- `PayrollRun` (§2) — the computation batch/output record itself, its own CRUD and persistence, and whatever computation logic combines its own inputs (§5) into a result. Name and existence reserved; schema not specified (§2, §7).
- `Payslip` (§3) — the per-employee output of a `PayrollRun`. Name and existence reserved; schema not specified (§3, §7).
- Payroll-specific business rules for combining inputs into an amount, once those rules and their required data exist (§7) — this ownership is asserted by exclusion (no other existing capability owns pay computation; every producer capability's own docstring explicitly disclaims it, per `discovery.md` §1) rather than by any Payroll code that exists today.

## What Payroll Consumes

Per `discovery.md` §1/§3, read-only, from capabilities that already own this data:

- `HrEmployee` (identity/scope key — every existing service's uniform pattern for "which employee is this about")
- `LeaveRequest.status == "approved"` (via `LeaveRequestService`/`LeaveRequestRepository` — Payroll does not re-implement leave request storage)
- `LeaveBalance` (with the caveat, carried from Discovery, that it is not currently synchronized with approval — Payroll would consume whatever value exists, accurate or not, absent a separate fix)
- `OvertimeRequest.status == "approved"`
- `Timesheet.status == "approved"`
- `AttendanceEvent` / `ReconciliationService`'s computed daily result
- `Holiday` (dates)
- `Shift` (time template)
- `JobGrade`, `EmploymentType`, `EmploymentStatus` (reference classification)

## What Payroll Must Not Own (already owned elsewhere, per repository evidence)

- The `pending → approved/rejected` request lifecycle for `LeaveRequest`/`OvertimeRequest`/`Timesheet` — owned by `ApprovalService` and each entity's own `*RequestService`/`TimesheetService`. Payroll reads their final `status`; it does not gain its own approve/reject verbs for these entities.
- Attendance raw-event capture and per-day reconciliation — owned by `AttendanceEventService`/`ReconciliationService`.
- Leave balance bookkeeping — owned by `LeaveBalanceService`, regardless of its unsynchronized state; Payroll does not take over writing `LeaveBalance` rows.
- All HR reference/master data (`HrEmployee`, `JobGrade`, `EmploymentType`, `EmploymentStatus`, `Shift`, `Holiday`) — each stays owned by its existing dedicated service. If a compensation/rate field is later added, the repository's own precedent (every FK/field added to an existing HR entity so far, e.g. `shift_id` added to `hr_employees`) suggests it would be an addition to an existing owner's schema, not a field Payroll's own service writes directly — this is noted as the closest available precedent, not decided as binding here, since no such addition exists yet to confirm the pattern for a monetary field specifically.
- The generic authorization mechanism — owned by Authorization Foundation, unchanged, per `payroll-authorization/decision.md`.

---

# 5. Dependencies

Restated from `discovery.md` §1, with the ownership direction now decided (§4):

| Dependency | Direction | Status |
|---|---|---|
| Identity Context | Payroll would consume, to resolve `HrEmployee`/`RequestContext` the same way every other capability does | Available, unconsumed (no Payroll code exists yet) |
| Authorization Foundation | Payroll Authorization (a separate, already-blocked capability decision) would consume once `PayrollRun`/`Payslip` exist | Available, deferred — `payroll-authorization/decision.md` |
| Approval | Payroll reads `status == "approved"` only; does not call `ApprovalService` | Existing, read-only relationship |
| Attendance | Payroll reads `AttendanceEvent`/`ReconciliationService` output | Existing, read-only relationship |
| Leave | Payroll reads `LeaveRequest.status`, `LeaveBalance` (with the unsynchronized-state caveat, §4) | Existing, read-only relationship |
| Timesheet | Payroll reads `Timesheet.status` | Existing, read-only relationship; inherits the CRUD-authorization gap noted in §7's risks |
| Employee | Payroll reads `HrEmployee` | Existing, read-only relationship |
| Shift | Payroll reads `Shift` (time template only — no calendar to resolve working days against, §7) | Existing, read-only relationship |
| Holiday | Payroll reads `Holiday` (dates only — no `is_paid` flag, §7) | Existing, read-only relationship |
| Job Grade | Payroll reads `JobGrade` (rank only — no rate to resolve, §7) | Existing, read-only relationship |
| Employment Type / Status | Payroll reads for classification | Existing, read-only relationship |

No dependency in this table requires Payroll to write to, or take ownership from, any existing capability (§4).

---

# 6. Architectural Constraints

## `PayrollRun` (§2)

Must:
- Follow the repository's uniform HR-entity persistence precedent: `BaseEntity` (`UUIDMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin`/`VersionMixin`, `db/base.py:16-24`), a dedicated `*Repository(BaseRepository[...])`, a dedicated `*Service` owning its own UoW/transaction boundary.
- Remain an aggregate-level record. `PayrollRun` does not require `employee_id` and does not require any employee-equivalent foreign key — it is not employee-scoped. That scoping belongs to `Payslip` (below), not to `PayrollRun` itself.

## `Payslip` (§3)

Must:
- Follow the same `BaseEntity`/dedicated-repository/dedicated-service precedent as `PayrollRun`.
- Be the employee-scoped aggregate: an `employee_id` FK with `ON DELETE RESTRICT` matching every other FK into `HrEmployee` from HR data (`discovery.md` §1's uniform pattern), plus a `payroll_run_id` FK referencing `PayrollRun`. Both FKs are introduced only when `Payslip` itself is built — `Payslip` remains deferred (§ Deferred Capabilities; `implementation-plan.md`), so neither FK exists yet.

## `PayrollRun` / `Payslip` — Shared Constraints

Must not:
- Be implemented by extending `ApprovalService`, `ReconciliationService`, or any existing producer capability's own service/repository/table. No repository precedent exists for one capability's service writing into another capability's owned table, outside `ApprovalService`'s own narrow, explicitly-decided exception (§1) — extending that exception to Payroll would require its own equivalent explicit decision, not an inference from this one.
- Compute or store any monetary amount whose formula is not itself the subject of a future, separate decision (§7) — this document decides shape and ownership, not arithmetic.

## Authorization Foundation

Unchanged. Not consumed by this decision. `payroll-authorization/decision.md` remains the governing document for when and how Payroll Authorization proceeds, once `PayrollRun`/`Payslip` exist as real Services per this decision.

## Every Consuming Relationship (§5)

Must remain read-only. Payroll must not call `LeaveRequestService.update`, `TimesheetService.update`, or any other producer's mutating method — only repository-level or service-level reads.

---

# 7. Remaining Risks / Explicitly Undecided

Restated and expanded from Discovery's Open Questions, carried forward as binding scope limits on the Implementation Plan:

- **No compensation/rate data source exists anywhere.** This decision does not specify where one would be added (a field on `HrEmployee`, a field on `JobGrade`, or a new dedicated entity) — doing so would be schema design, not boundary decision, and no repository evidence favors one location over another.
- **No lifecycle/state machine is decided for `PayrollRun`.** The repository's only existing multi-step-outcome pattern (`pending → approved/rejected`) is a binary decision workflow; a payroll computation pipeline (e.g., draft/calculated/approved/published, or something else entirely) has no repository precedent to follow. This is left open.
- **No batch-processing shape is decided.** Whether `PayrollRun` is computed for all employees at once, one at a time, or something else has no repository precedent (`discovery.md` §4/§5) — `ReconciliationService`'s single-employee scope is the closest analog but was never extended to a batch in this repository.
- **`OvertimeRequest`/`Timesheet` CRUD have no authorization today** (`discovery.md` §1). Payroll consuming their `status` field inherits whatever integrity gap exists upstream — this decision does not resolve that gap and does not block on it, but implementation must not assume the data Payroll reads from these two entities is protected the way `LeaveRequest`/`AttendanceEvent` already are.
- **`LeaveBalance` is unsynchronized with `LeaveRequest` approval** (`discovery.md` §1). Any Payroll computation reading `remaining_days` would be reading a value the repository's own code already documents as potentially stale.
- **Working-day/holiday pay-multiplier concepts do not exist** (`discovery.md` §3/§4) — Payroll cannot yet determine which calendar days are payable working days versus holidays with a pay implication, beyond `Holiday`'s bare date list.

None of these are resolved by this decision. Each requires either a future, separate capability decision (compensation data source, lifecycle) or product/business input this repository does not contain (pay-period cadence, tax/deduction rules) — inventing any of them here would violate the Evidence Rule.

---

# 8. Rejected Alternatives

## No persisted aggregate — Payroll computed live on every request, `ReconciliationService`-style

Rejected (§2). `ReconciliationService`'s shape is appropriate for a low-stakes, same-day, non-financial status; a payroll amount is exactly the kind of record `ARCHITECTURE_INVENTORY.md` §8 already flags as needing an audit trail this shape cannot provide.

## Payslip as a pure projection over `PayrollRun` plus live upstream data, recomputed on read

Rejected (§3), for the same reason — a payslip that could silently change after being issued, because an upstream `LeaveRequest` was later corrected, is inconsistent with the repository's own named audit-trail concern.

## Payroll writes its outcome directly onto existing rows (`LeaveRequest`/`OvertimeRequest`/`Timesheet`), `ApprovalService`-style, with no new aggregate at all

Rejected (§4, §6). `ApprovalService`'s shape fits a small status change to an existing request; it has no analog for producing an entirely new fact (a computed pay amount) that did not previously exist as a field on any of those rows, and extending an already-narrow, explicitly-decided exception without its own decision is not supported.

## Deciding the compensation-data-source location or the lifecycle state machine now, to keep this decision "complete"

Rejected. Both would require inventing structure with no repository precedent (§7) — explicitly excluded by this document's own instructions and by the Evidence Rule.

---

# 9. Prerequisite Work Before Implementation Can Proceed Past Structural Scaffolding

- A decision (product or architecture) on where compensation/rate data originates.
- A decision on `PayrollRun`'s lifecycle/state machine.
- A decision on batch-processing shape (all-employees-at-once vs. per-employee).
- Optionally, resolution of the `OvertimeRequest`/`Timesheet` CRUD authorization gap and the `LeaveBalance` synchronization gap — not strictly blocking Payroll's own structural existence, but directly affecting the trustworthiness of what it would compute.

None of these prerequisites are met today. The Implementation Plan that follows this decision is scoped accordingly (`implementation-plan.md` §2).

---

# 10. Recommendation

Structural scaffolding (models, repositories, services, routers for `PayrollRun`/`Payslip`, empty of computation logic) may proceed to an Implementation Plan. **Actual pay computation may not be planned or implemented until the prerequisites in §9 are separately decided** — attempting to do so now would require inventing business rules this repository does not evidence.

---

# References

- `docs/architecture/capabilities/payroll/discovery.md`
- `docs/architecture/capabilities/payroll-authorization/discovery.md`, `decision.md` (governs authorization once this capability's resource exists — unchanged by this document)
- `ATTENDANCE_RECONCILIATION_DESIGN.md`, `APPROVAL_ORCHESTRATION_DESIGN.md` (structural precedents cited in §2, §3)
- `ARCHITECTURE_INVENTORY.md` §8 (Business Audit gap, cited in §2, §3)
- `docs/architecture/capabilities/attendance-authorization/decision.md` (precedent for reserving a name without implementing code, cited in §2)
