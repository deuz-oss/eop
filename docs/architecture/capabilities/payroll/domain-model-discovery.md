# Payroll — Domain Model Discovery

**Status:** Complete

**Capability:** Payroll (data-owning capability)

**Owner:** EOP Architecture Governance

**Depends On:** `docs/architecture/capabilities/payroll/discovery.md`, `docs/architecture/capabilities/payroll/decision.md`

---

# Purpose

This document determines the minimal domain model required before Payroll can exist, using only repository evidence plus the conclusions already reached in `payroll/discovery.md` and `payroll/decision.md`. It is a domain analysis, not a design exercise: no schema is authored, no business rule is invented, no calculation is proposed. Every conclusion below is labeled **Repository Evidence**, **Logical Consequence** (a direct inference from that evidence, not itself observed), or **Unknown / Not Yet Decidable** (evidence is insufficient), per the governing instruction.

---

# Summary

Repository evidence supports exactly one persisted-vs-computed distinction already applied twice by this repository (decisions, persisted; views, recomputed) and reused in `payroll/decision.md` to justify `PayrollRun`/`Payslip` as persisted aggregate roots. It does not support a specific state machine, a batch-processing mechanism, or any monetary concept. A previously unexamined part of the repository — unused `EventPublisher`/`JobProvider` scaffolding — is directly relevant to Payroll's likely batch/period nature and is analyzed here for the first time in this conversation. `PayrollPeriod`, `PayrollItem`, and `PayrollResult` each have weaker or no repository grounding than `PayrollRun`/`Payslip`. The recommendation is **Yes, scaffolding only** — unchanged in substance from `decision.md`, now derived independently through domain-model analysis rather than restated from it.

---

# Evidence

## E1. Existing Producers (mapped to owner capability, entity, lifecycle, mutability, approval dependency, synchronization dependency, and payroll consumption timing)

| Producer | Owner capability | Produced entity | Lifecycle | Immutable / Mutable | Approval dependency | Synchronization dependency | Payroll consumption timing |
|---|---|---|---|---|---|---|---|
| HR Master Data | `HrEmployeeService` | `HrEmployee` | Plain CRUD, no status field | **Mutable** — `update`/`delete` exist (`hr_employee.py:218,323`); "effective" in its own docstring refers to referential-integrity validation of FK targets after an update, not temporal effective-dating — confirmed by direct read (`hr_employee.py:218-233`), not inferred | None | None | Would be read at whatever `HrEmployee` state exists at computation time — no historical/point-in-time read is possible (no versioning table, no effective-dated fields) |
| Attendance | `AttendanceEventService` | `AttendanceEvent` | Docstring describes it as an append-only "single clock transaction" | **Mutable in practice** — `update`/`delete` methods and `PUT`/`DELETE` routes exist and are exposed (`attendance_event.py:151-194`, `api/attendance_events.py:122-162`), despite the model's own "append-only" framing | None | None | After the fact; raw events or via Reconciliation's derived per-day status |
| Attendance Reconciliation | `ReconciliationService` | Computed response, **not persisted** | Recomputed on every call | N/A — no row exists to be mutable or immutable | None | None | Must be re-queried at Payroll computation time; nothing upstream caches or stores its result |
| Leave | `LeaveRequestService` (CRUD) / `ApprovalService` (decision) | `LeaveRequest` | `pending → approved/rejected` | **Mutable** — `LeaveRequestService.update` (`leave_request.py:156-189`) has no status-based guard; a request can be edited after submission regardless of `status` | Yes — Manager Approval (`ApprovalService`, ADR-008) | None on `LeaveRequest` itself | Only `status == "approved"` rows are meaningful, per every design document reviewed in `discovery.md` §1 |
| Leave Balance | `LeaveBalanceService` | `LeaveBalance` | Static snapshot, no transitions | Mutable (plain `update`, non-negative validation only) | None | **Yes — explicitly unsynchronized with `LeaveRequest` approval** (`approval.py:94-108`, named gap) | Unsafe to consume without accepting documented staleness |
| Overtime | `OvertimeRequestService` (CRUD) / `ApprovalService` (decision) | `OvertimeRequest` | `pending → approved/rejected` | Mutable, same unguarded-`update` shape as `LeaveRequest` | Yes — Manager Approval | None | Only `status == "approved"`; CRUD itself has **no authorization** (`discovery.md` §1) — an integrity caveat on top of the timing requirement |
| Timesheet | `TimesheetService` (CRUD) / `ApprovalService` (decision) | `Timesheet` | `pending → approved/rejected` | Mutable, same shape | Yes — Manager Approval | None | Only `status == "approved"`; same CRUD-authorization caveat as Overtime |
| HR Reference Data | `Shift`/`Holiday`/`JobGrade`/`EmploymentType`/`EmploymentStatus` services | `Shift`, `Holiday`, `JobGrade`, `EmploymentType`, `EmploymentStatus` | Plain CRUD | Mutable (`job_grade.py:44,87,113` confirms `create`/`update`/`delete` on `JobGrade`; identical pattern on the other four, per `discovery.md` §1) | None | None | Read at computation time; no effective-dating on any of them |

No producer in this table is immutable once persisted. Every one exposes an `update` and/or `delete` operation with no guard preventing a change to data a payroll computation may have already consumed.

## E2. Absence of Payroll-Specific Concepts

Restated from `discovery.md`/`decision.md`, not re-derived: no `PayrollRun`, `Payslip`, `PayrollPeriod`, `PayrollItem`, `PayrollResult`, `PayPeriod`, `Salary`, `Compensation`, or any monetary field exists anywhere in the repository (`discovery.md` §1–§4).

## E3. Previously Unexamined: `events/`, `jobs/` Infrastructure

Not reviewed in prior discoveries. Full reads of `events/base.py`, `events/memory_publisher.py`, `services/event.py`, `jobs/base.py`, `jobs/memory_provider.py`, `services/job.py`:

- `EventPublisher` (abstract: `publish`, `publish_many`) and `EventService` (its business-facing wrapper) exist. `EventService`'s own docstring: *"Nothing in this PR calls it yet — it is infrastructure for later adoption."* Repository-wide grep for `EventService` inside `services/` returns matches only in `attendance_event.py`/`attendance_authorization.py` — both false positives from the substring "Event" inside "Attendance**Event**", not actual usage. **Zero producer capability calls `EventService`.**
- `JobProvider` (abstract: `enqueue`, `enqueue_in`, `enqueue_at`) and `JobService` exist with an identical docstring: *"Nothing in this PR calls it yet — it is infrastructure for later adoption."* **Zero producer capability calls `JobService`.**
- The only implementations of either abstraction are `InMemoryEventPublisher`/`InMemoryJobProvider` — both explicitly documented as recording-only: *"There is no broker, queue, or subscriber behind this"* / *"There is no worker, scheduler, or poller behind this... nothing in this class ever executes a job."*

This is scaffolding for two future execution shapes (event-driven, background/batch-driven), present in the codebase, typed, and documented as intentionally unused pending later adoption — but with no working execution mechanism and no existing caller anywhere.

## E4. Mutability and Persistence Mechanics (platform-wide, applies to any future Payroll entity)

- `BaseRepository.delete` performs a hard delete (`session.delete(instance)`, `repositories/base.py:59-66`) on every entity reviewed, despite `SoftDeleteMixin` (`deleted_at`/`is_deleted`) existing on every `BaseEntity` subclass.
- `VersionMixin.version` exists on every entity but is not read or incremented-on-conflict anywhere in the repository (`TECHNICAL_DEBT_REGISTER.md` TD-002 names this gap for Approval Authorization specifically; it is a platform-wide, not capability-specific, absence).
- No entity anywhere carries a `valid_from`/`valid_to`, `effective_date`, or history/audit-trail table. `AuditMixin` (`created_by`/`updated_by`) records who last touched a row, not what the row's value was before that touch.

---

# Analysis

## A1. Candidate Aggregate Roots

Classification uses the repository's own uniform, observed pattern: every persisted `BaseEntity` subclass reviewed (eleven, `discovery.md` §1) has exactly one dedicated repository and one dedicated service; none is persisted as a nested/owned collection through another entity's repository; every relationship between entities is an FK-by-id reference between two independently-transacted aggregates, never a cascaded save. This pattern is Repository Evidence, established across all eleven reviewed entities without exception.

**`PayrollRun`**
- Repository Evidence: does not exist (E2). `decision.md` §2 already concluded it must be persisted, reasoning from the repository's own persisted-decision-vs-recomputed-view distinction (E1: `LeaveRequest`/`OvertimeRequest`/`Timesheet` persist their outcome; `ReconciliationService`, E1, does not persist its computed result at all).
- Logical Consequence: Given the uniform one-entity-one-repository-one-service pattern (no exception exists anywhere for a "root with owned child rows"), `PayrollRun` classifies as an **Aggregate Root** — its own table, own repository, own service, referenced by `Payslip` via FK rather than owning `Payslip` rows through its own repository.
- Unknown: the invariants it would enforce (what makes a `PayrollRun` internally consistent) — not decidable without a decided computation model.

**`Payslip`**
- Repository Evidence: does not exist (E2). `decision.md` §3 already concluded it is its own persisted aggregate, not a projection.
- Logical Consequence: By the same uniform pattern as `PayrollRun`, `Payslip` classifies as its own **Aggregate Root** — not an Entity nested inside `PayrollRun`'s aggregate boundary, since no repository precedent anywhere persists one entity only reachable through another's repository. It references `PayrollRun` and `HrEmployee` by FK, the same way every other entity in the repository references its relations.
- Unknown: none beyond `PayrollRun`'s.

**`PayrollPeriod`**
- Repository Evidence: no `PayPeriod`/period concept exists anywhere (E2). `TIMESHEET_DESIGN.md` §3 (cited in `discovery.md`) directly considered "pay period" as a candidate boundary for `Timesheet` and rejected building one, calling it *"the least-grounded of the four named candidates... presupposes a payroll cadence... that nothing in this codebase defines."* `LeaveBalance.period_year` (E1) is the only repository precedent for "period" as a concept at all — a **bare `Integer` column**, not a reference to a separate persisted entity.
- Logical Consequence: The one existing "period" precedent in the repository (`LeaveBalance.period_year`) is a **Value Object-shaped inline field**, not an Entity or Aggregate Root — no repository evidence anywhere persists a period as its own referenceable row. If `PayrollPeriod` is introduced, the closest-fitting classification by precedent is **Value Object** (e.g., a date range or year/period-number pair stored inline on `PayrollRun`), not a fourth standalone aggregate.
- Unknown / Not Yet Decidable: whether the cadence is fixed (weekly/biweekly/monthly) or caller-supplied is explicitly unresolved by the one document that directly addressed it (`TIMESHEET_DESIGN.md` §3) and is not answered anywhere else. This inference is weaker than `PayrollRun`/`Payslip`'s — it rests on one analogous field, not a repeated pattern.

**`PayrollItem`**
- Repository Evidence: does not exist; not named in any of the 26+ payroll-related file matches found across prior discoveries, unlike `PayrollRun`/`Payslip`-adjacent concepts, which are at least discussed as future consumers. No repository entity anywhere is a one-to-many "line item"/breakdown child of another entity — no such shape exists to classify against.
- Logical Consequence: none can be drawn — there is no structural precedent in the repository for a breakdown/line-item pattern at all, positively or negatively.
- Unknown / Not Yet Decidable: **explicitly** — repository evidence is insufficient even to hypothesize a shape (Aggregate Root vs. Entity vs. Value Object). Whether Payroll needs line-item granularity at all is a business-rule question this document does not answer, per its own governing instruction not to invent payroll calculations.

**`PayrollResult`**
- Repository Evidence: does not exist; not named anywhere. The closest structural analog in the repository is `AttendanceReconciliationResponse` — `ReconciliationService`'s return shape, explicitly not persisted, "owns no aggregate, no table" (`reconciliation.py:23-24`, E1).
- Logical Consequence: if "PayrollResult" denotes a computed, potentially transient view (as distinct from the persisted `Payslip` record `decision.md` already decided on), the nearest fitting classification is **Projection** — a response shape computed over `PayrollRun`/`Payslip`, not a fourth persisted concept.
- Unknown: whether "PayrollResult" as named in this instruction is intended as something distinct from `Payslip` at all cannot be determined from repository evidence — there is no repository referent to disambiguate the naming intent.

## A2. Domain Ownership

**Payroll owns** (per `decision.md` §4, restated here as it follows directly from A1's classification):
- `PayrollRun` (Aggregate Root, A1)
- `Payslip` (Aggregate Root, A1)
- Any `PayrollPeriod` value, if introduced, as an inline field of `PayrollRun` rather than a separate owned entity (A1 — weaker inference, flagged as such)

**Payroll references** (read-only, by FK-or-query, matching every existing cross-capability relationship pattern in the repository — E1):
- `HrEmployee`, `LeaveRequest` (`status == "approved"`), `LeaveBalance`, `OvertimeRequest` (`status == "approved"`), `Timesheet` (`status == "approved"`), `AttendanceEvent`/`ReconciliationService` output, `Holiday`, `Shift`, `JobGrade`, `EmploymentType`, `EmploymentStatus`

**Payroll must never own** (already owned elsewhere, per E1's ownership column):
- The `pending → approved/rejected` transition itself, for `LeaveRequest`/`OvertimeRequest`/`Timesheet` — owned by `ApprovalService` and each entity's own service.
- Raw attendance capture or reconciliation computation — owned by `AttendanceEventService`/`ReconciliationService`.
- Leave balance bookkeeping — owned by `LeaveBalanceService`, regardless of its unsynchronized state (E1).
- Any HR reference/master data field — owned by each entity's existing dedicated service (E1); this includes any future compensation/rate field, whose most likely home by precedent (an addition to an existing owner's schema, the way every other field has been added incrementally to `HrEmployee` historically) is **not confirmed** here — flagged as an open question, not decided.
- Its own event-transport or job-execution mechanism — `events/base.py`'s own docstring states *"Business modules must never talk to a concrete transport... directly"* (E3); if Payroll needs asynchronous or batch execution, the repository's own stated rule is that it must consume `EventService`/`JobService`, not invent a parallel mechanism.

**Payroll must never modify**:
- Any producer entity's own row (`LeaveRequest`, `OvertimeRequest`, `Timesheet`, `AttendanceEvent`, `LeaveBalance`, `HrEmployee`, and all HR reference data) — every relationship Payroll has to these, per E1/`decision.md` §5, is read-only. No repository precedent (outside `ApprovalService`'s own narrow, explicitly-decided exception, E1) supports one capability writing into another's owned table.

## A3. Lifecycle Analysis

- **Request-driven processing**: strongly supported by Repository Evidence. Every producer capability without exception (E1) is triggered synchronously, within a single API request/response cycle, by a direct Service method call from a FastAPI route handler. This is the only processing shape the repository actually demonstrates working, end to end, anywhere.
- **Event-driven processing**: infrastructure exists (`EventPublisher`/`EventService`, E3) but has **zero callers** anywhere in the repository and no working transport (in-memory recording only, no subscriber mechanism — `EventPublisher` itself defines no `subscribe`). Repository Evidence supports that this shape is *anticipated* (scaffolded, documented as "for later adoption") but does **not** support that it is proven or currently usable end-to-end.
- **Batch-oriented processing**: `JobProvider`/`JobService` (E3) exist as scaffolding — `enqueue`/`enqueue_in`/`enqueue_at` — but the only implementation "never executes a job," and zero producer capability calls it. Separately, no service anywhere iterates "all employees" for any purpose (`discovery.md` §4/§5 — `ReconciliationService` is explicitly single-employee, single-date). **Repository evidence does not support batch-oriented processing as a working pattern; it supports only that a batch-adjacent mechanism (job enqueueing) has been scaffolded and never used.**

Combined: Repository evidence supports request-driven processing as proven. It supports event-driven and batch/job-driven processing only as available-but-unproven, uncalled infrastructure — **not** as an established pattern a Payroll implementation could follow with confidence. Whether a `PayrollRun` covering many employees would be triggered by a single request-driven call that internally loops (consistent with what the repository proves works) or by enqueuing per-employee jobs through the existing, unused `JobService` (consistent with what the repository has built but never exercised) is **Not Yet Decidable** from repository evidence alone.

## A4. Persistence Analysis

| Candidate | Classification | Basis |
|---|---|---|
| `PayrollRun` | **Persisted** | A1 — direct analogy to `LeaveRequest`/`OvertimeRequest`/`Timesheet`'s persisted-decision pattern, reinforced by `ARCHITECTURE_INVENTORY.md` §8's named "Business Audit" gap (`decision.md` §2) |
| `Payslip` | **Persisted** | A1 — same basis, `decision.md` §3 |
| `PayrollPeriod` | **Undecidable as a standalone persistence question** — if introduced, evidence favors an inline (non-separately-persisted) value on `PayrollRun`, not a fourth table (A1) | `LeaveBalance.period_year`'s bare-`Integer` precedent; weak inference, single data point |
| `PayrollItem` | **Undecidable** | No repository precedent of any kind to classify against (A1) |
| `PayrollResult` | **Computed / Projection**, if it denotes anything distinct from `Payslip` at all | Direct analogy to `AttendanceReconciliationResponse` (A1) — the repository's only precedent for a non-persisted, computed response shape |

No candidate is supported by repository evidence as **Cached** — no caching layer exists anywhere in the repository for any entity or computed value (confirmed by the absence of any caching import/module across all files reviewed in this and prior discoveries).

---

# Recommendation

**Is the repository now mature enough to begin Payroll implementation?**

```
Yes, scaffolding only
```

Supported entirely by repository evidence assembled above, independent of (though consistent with) `decision.md`'s own recommendation:

- `PayrollRun` and `Payslip` are classifiable, with direct repository precedent, as persisted Aggregate Roots (A1, A4) — sufficient to scaffold as new, empty-of-computation entities following the repository's own uniform per-entity pattern (E1's eleven-for-eleven precedent).
- No repository evidence supports beginning computation logic: no monetary data source exists anywhere (E2), no producer's data is immutable once persisted (E1 — every producer entity remains editable after the fact, undermining any computation that assumes a stable input), no effective-dating or history mechanism exists to say what an input's value was *at the time* a payroll period covered it (E4), and no batch-processing pattern has ever been exercised end-to-end (A3) despite scaffolding existing for it (E3).
- Beginning full implementation now ("Yes") would require inventing a compensation model, a period cadence, and a batch-execution mechanism — none supported by evidence, all explicitly excluded by this document's governing instructions.
- Declining to scaffold at all ("No") is not supported either: the aggregate-root classification (A1) and ownership boundary (A2) are answerable now, with existing precedent, and `decision.md` §10 already reached the same structural conclusion independently.

---

# Remaining Unknowns

Items whose absence is demonstrated by repository evidence above, not assumed:

- **Salary/compensation source** — no field exists on `HrEmployee`, `JobGrade`, or anywhere else (E2); no document proposes where one would be added.
- **Compensation model** (fixed salary vs. hourly vs. mixed) — no repository evidence of any kind addresses this; `JobGrade.level` is a bare seniority rank, not a rate structure.
- **Allowances** — absent (E2); "allowance" returns zero matches anywhere in `services/api/src`.
- **Deductions (monetary)** — absent (E2); the only "deduction" language in the repository concerns `LeaveBalance` day-counts, not currency.
- **Taxes** — absent; zero matches anywhere in source.
- **Currencies** — absent; no currency field or currency-handling code exists anywhere in the repository.
- **Effective dating** — absent platform-wide (E4): no entity anywhere carries `valid_from`/`valid_to`, and `HrEmployee.update`'s own "effective" language refers to referential-integrity validation, not temporal versioning (E1). Every producer entity's current field values are the only values readable — nothing lets Payroll ask "what was this employee's department/rate/status as of period X."
- **Retroactive adjustments** — no repository evidence of any adjustment/correction concept for a previously computed or approved record anywhere; every producer's `update` operation overwrites in place with no history retained (E1, E4).
- **Pay-period cadence** — explicitly unresolved by the one document that considered it (`TIMESHEET_DESIGN.md` §3, cited in A1); no fixed weekly/biweekly/monthly concept exists anywhere.
- **Batch-execution mechanism** — scaffolded (`JobService`/`EventService`, E3) but never exercised by any producer capability; whether Payroll would be the first real caller of this existing infrastructure or would need a different mechanism entirely is unresolved.
- **Line-item/breakdown structure** (`PayrollItem`) — no repository precedent of any kind exists to model this against (A1).
- **Authorization for `OvertimeRequest`/`Timesheet` CRUD** — both remain authentication-only (E1); any Payroll computation reading their `status` inherits this integrity gap.
- **`LeaveBalance` synchronization with `LeaveRequest` approval** — explicitly unresolved, named in the repository's own code (E1).

---

# References

- `docs/architecture/capabilities/payroll/discovery.md`
- `docs/architecture/capabilities/payroll/decision.md`
- `docs/architecture/TIMESHEET_DESIGN.md` §3 (cited in A1, `PayrollPeriod`)
- `docs/architecture/10-reference/ARCHITECTURE_INVENTORY.md` §8 (cited in A1, `PayrollRun`)
- `services/api/src/eop_api/events/`, `services/api/src/eop_api/jobs/`, `services/api/src/eop_api/services/event.py`, `services/api/src/eop_api/services/job.py` (E3 — examined for the first time in this document)
