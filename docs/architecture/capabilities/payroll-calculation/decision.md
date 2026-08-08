# Payroll Calculation — Capability Decision

**Capability:** Payroll Calculation (distinct from `PayrollRun`, `Payslip`, Payroll Authorization, Payroll Processing, Payroll Integration)

**Status:** Approved — Boundary Decision Only, Extensive Unknowns Recorded

**Version:** 1

**Owner:** Architecture

---

# Purpose

This document decides only what `docs/architecture/capabilities/payroll-calculation/discovery.md` and the repository evidence it cites can support. No architecture is invented. Where evidence is insufficient, this document records `Unknown`, not a recommendation, per the governing instruction.

---

# 1. Capability Ownership

**Repository Evidence**

- `payroll/decision.md` §4 already recorded, as prior governance fact: *"Payroll-specific business rules for combining inputs into an amount, once those rules and their required data exist... this ownership is asserted by exclusion (no other existing capability owns pay computation; every producer capability's own docstring explicitly disclaims it)."*
- `discovery.md` §9 confirms three of four named input-aggregation responsibilities (leave deduction, overtime duration, timesheet aggregation) have **no owner anywhere in the repository** — not partially built, absent.
- `discovery.md` §1 confirms `PayrollRun` and `Payslip`, as merged, contain zero calculation logic.
- `discovery.md` §3-5 confirms no monetary model, precision type, or calculation engine exists anywhere to define what a computation would produce.

**Decision**

Payroll Calculation owns the *responsibility* for combining already-persisted upstream data into a payroll-relevant computed result — decided by exclusion: no other existing capability owns this responsibility (`payroll/decision.md` §4, restated), and the specific gaps this responsibility would fill (leave deduction, overtime duration, timesheet aggregation) are confirmed unowned (`discovery.md` §9). Payroll Calculation does **not** own: persistence of `PayrollRun` (owned by `PayrollRunService`) or `Payslip` (owned by `PayslipService`), both already implemented as structural aggregates independent of any calculation logic; any upstream producer's own data (§6); the generic authorization mechanism.

What the *content* of that responsibility is — a formula, a rate source, a monetary field to write — is not decided here; no repository evidence supports deciding it (§7, §10).

**Rejected Alternatives**

- Payroll Calculation owning no responsibility at all (leaving the exclusion in `payroll/decision.md` §4 unfulfilled by any capability) — rejected; the exclusion already asserts something must eventually own this, and nothing else in the repository does.
- Payroll Calculation owning `PayrollRun`'s or `Payslip`'s persistence — rejected; both already have a dedicated, already-decided, already-implemented owning service, and no repository precedent exists for one capability absorbing another's already-assigned aggregate (uniform one-entity-one-service pattern, zero exceptions, `discovery.md` §1).

---

# 2. Relationship to `PayrollRun`

**Repository Evidence**

- `PayrollRun`'s merged code (`models/payroll_run.py`, `services/payroll_run.py`) contains zero calculation logic and zero orchestration of any other capability — confirmed directly, not inferred (`discovery.md` §1).
- `payroll/implementation-plan.md` and `payslip/implementation-plan.md` both list "Payroll Calculation" as a distinct, separately-named item excluded from `PayrollRun`'s own scope — treating them as two different capabilities, not one.
- `payroll/decision.md` §4's statement that Payroll "owns... whatever computation logic combines its own inputs... into a result" is qualified by its own text — *"once those rules and their required data exist"* — describing a hypothetical future state, not current ownership; `payroll/architecture-review.md` Finding 2 already flagged this exact line as needing its qualifier read, not taken as a present-tense claim.

**Decision**

`PayrollRun` does not own calculation. As currently implemented, `PayrollRun` also does not orchestrate calculation — it is a bare persistence anchor (`code`/`name` identity only) with no call path into any other capability and no field (e.g. a status column) a calculation step could hook into. If Payroll Calculation is later built, repository evidence supports it operating as a separate capability that reads/references `PayrollRun` (the same read-only, FK-based relationship direction already established for `Payslip → PayrollRun`), not one `PayrollRun`'s own service calls into, or that calls into `PayrollRun`'s service — no such call path exists in either direction today, and none is invented here. Of the two options given, "orchestrate" is the only one not directly contradicted by evidence, but no orchestration is implemented; this is a decision about future role by elimination, not a description of present behavior.

**Rejected Alternatives**

- `PayrollRun` owning calculation directly (extending `PayrollRunService` with computation methods) — rejected; contradicted by `PayrollRun`'s own merged code and by both implementation plans' explicit, separate exclusion of "Payroll Calculation" from `PayrollRun`'s scope.

---

# 3. Relationship to `Payslip`

**Repository Evidence**

- `Payslip` is already decided and implemented as its own Aggregate Root, owned exclusively by `PayslipService` (`payslip/decision.md` §1, §7): *"a new, dedicated `PayslipService` — not owned by `PayrollRunService`, `ApprovalService`, or any producer capability's existing service."*
- The uniform one-entity-one-service pattern applies without exception across all twelve entities reviewed across this conversation's discoveries (`discovery.md` §1, `payroll/domain-model-discovery.md` A1).
- `PayslipService.create` currently performs only existence validation of `employee_id`/`payroll_run_id` — no computation of any kind (`discovery.md` §1, confirmed against merged code).

**Decision**

Payroll Calculation does not own `Payslip`. `Payslip` remains owned by `PayslipService`, already decided and implemented. Payroll Calculation, if built, would at most produce data later written into a `Payslip` row through `PayslipService`'s own interface — it does not own `Payslip`'s persistence, aggregate boundary, or lifecycle. This mirrors the identical boundary already drawn for `PayrollRun` (§2): Payroll Calculation is evidenced as a producer of data `Payslip` may consume, not an owner of `Payslip` itself.

**Rejected Alternatives**

- Payroll Calculation owning `Payslip`'s persistence directly (folding `PayslipService`'s responsibilities into a calculation service) — rejected on the same uniform-pattern grounds as §2, and because `payslip/decision.md` §7 already explicitly rejected folding `Payslip` into any other service.

---

# 4. Calculation Result

**Repository Evidence**

- Two, and only two, "immutable record" precedents exist in the repository: `AuditLog` and `Payslip` — neither is a calculation result (`discovery.md` §8).
- `payroll/domain-model-discovery.md` A1 already examined "PayrollResult" as a named candidate and found: *"repository evidence is insufficient even to hypothesize a shape"* — its closest structural analogy (`AttendanceReconciliationResponse`) is a transient, non-persisted Projection, but that analogy was explicitly flagged as weak, for low-stakes, non-financial data only.
- `Payslip` itself is already decided to be persisted and immutable (`payslip/decision.md` §2-4) — but this decision concerns `Payslip`'s own record, not a separate, intermediate "calculation result" distinct from it.

**Decision**

**Unknown.** The term "calculation result" is ambiguous against current repository evidence in a way this document does not resolve: if it means *whatever `Payslip` eventually stores*, that record's persistence and immutability are already decided (`payslip/decision.md`) — but if it means an intermediate or working output of Payroll Calculation's own process, distinct from `Payslip`, no repository evidence establishes whether such a thing would be persisted or transient. `domain-model-discovery.md` A1 already reached the same "Unknown" conclusion examining this exact question under the name "PayrollResult," and no evidence has changed since. This document does not infer an answer.

---

# 5. Calculation Execution

**Repository Evidence**

- Request-driven processing is the only execution shape proven working end-to-end anywhere in the repository — but only for single-entity, single-request operations; no service anywhere iterates "all employees" or performs a multi-record batch (`discovery.md` §4, §6, §9; `payroll/domain-model-discovery.md` A3).
- `EventService`/`JobService` exist, fully typed, but both have zero callers anywhere and no working execution backend — no broker, no queue consumer, no scheduler, no worker (`discovery.md` §6, confirmed by fresh grep for `cron|scheduler|celery|redis.*queue|worker`, no relevant match).

**Decision**

**Not decidable today.** Neither option has established precedent for the specific execution shape Payroll Calculation would need (a computation likely spanning multiple employees per `PayrollRun`): request-driven is proven only for single-entity operations, never batch; `EventService`/`JobService` are unproven scaffolding with no execution mechanism behind either. Choosing between them now would mean inventing which dormant or partially-applicable pattern to extend, not deriving a choice from evidence — explicitly excluded by this document's governing instruction.

**Rejected Alternatives**

- None rejected — both remain live, undecided options; rejecting either now would itself be an invented choice this document is instructed not to make.

---

# 6. Input Ownership

**Repository Evidence and Decision** (confirmed directly against each capability's current, merged implementation):

| Upstream Capability | Confirmed Owner | Payroll Calculation's Relationship |
|---|---|---|
| Attendance | `AttendanceEventService` (raw events) / `ReconciliationService` (computed daily classification) | Read-only |
| Leave | `LeaveRequestService` (CRUD) / `ApprovalService` (decision) | Read-only |
| Leave Balance | `LeaveBalanceService` | Read-only |
| Overtime | `OvertimeRequestService` (CRUD) / `ApprovalService` (decision) | Read-only |
| Timesheet | `TimesheetService` (CRUD) / `ApprovalService` (decision) | Read-only |
| Employee | `HrEmployeeService` | Read-only |
| Holiday | `HolidayService` | Read-only |
| Shift | `ShiftService` | Read-only |

**Decision**: Payroll Calculation must not absorb ownership of any of the above — every one is already owned and implemented. Payroll Calculation may only read their data, mirroring the read-only relationship pattern already established and verified in code for `PayrollRun` (`discovery.md` §1: *"it imports and calls nothing from `LeaveRequestRepository`, `AttendanceEventRepository`, `ApprovalService`, or any other producer capability"*). This is directly decidable — no repository evidence contradicts it anywhere.

**Rejected Alternatives**

- Payroll Calculation absorbing "leave deduction," "overtime duration," or "timesheet aggregation" as its own owned *data* (as opposed to a computed responsibility over data it reads) — rejected as stated; these remain gaps in the *upstream* capabilities' own scope, not data Payroll Calculation would come to own. See §7 for whether Payroll Calculation may perform the aggregation itself.

---

# 7. Calculation Responsibility

**Repository Evidence and Decision**, evaluated individually, per instruction — only decided where evidence supports it:

- **Aggregation**: **Unknown.** `discovery.md` §9 found overtime duration and timesheet aggregation unowned, but explicitly flagged: *"Whether duration/aggregation computation is expected to be built as part of Overtime's/Timesheet's own capability... or as part of Payroll Calculation itself is not addressed by any repository evidence."* Not decided here; restated, not resolved.
- **Normalization**: **Unknown.** No repository evidence addresses this concept at all — no precedent, positive or negative, exists anywhere in the repository for a "normalization" step.
- **Validation**: **Decidable, narrowly.** Every service reviewed across this conversation validates only its own direct inputs' existence before acting (e.g. `PayslipService.create` checking `employee_id`/`payroll_run_id` exist) — a uniform, zero-exception pattern. By this precedent, Payroll Calculation would validate only its own direct inputs' existence the same narrow way, **not** the business correctness of upstream capabilities' already-persisted or already-approved data (that remains those capabilities'/`ApprovalService`'s own exercised responsibility). This is the one sub-topic with a clear, decidable answer.
- **Formula execution**: **Unknown.** No rule engine, formula engine, expression engine, or any comparable abstraction exists anywhere in the repository (`discovery.md` §5, zero matches). Nothing to decide against.
- **Snapshot creation**: **Unknown.** Depends on §4's unresolved "calculation result" question; not decidable independently of it.

---

# 8. Authorization

**Repository Evidence**

- Payroll Authorization was found blocked because no `PayrollRun` resource/Service existed to resolve an `AuthorizationRequest.resource` against (`payroll-authorization/decision.md`).
- Payslip Authorization was found blocked by the identical reasoning, one level further down the dependency chain, once `Payslip` itself did not yet exist (`payslip/decision.md` §8).
- Payroll Calculation has no model, no Service, and no persisted or transient resource of any kind anywhere in the repository (`discovery.md`, confirmed by the exact-phrase search finding "Payroll Calculation" named only as an exclusion in documents this conversation authored).

**Decision**

**No — Payroll Calculation Authorization cannot be decided or needed today.** The identical structural reasoning already applied twice (Payroll Authorization, then Payslip Authorization) applies again without modification: Authorization Foundation's own design principle requires a calling Service to resolve a concrete `resource` before an evaluator can interpret it; no such Service exists for Payroll Calculation, because Payroll Calculation itself does not exist. This is the third, consistent instance of the same blocking condition, not a new finding.

**Rejected Alternatives**

- Deciding a provisional or placeholder authorization policy now — rejected on the same grounds `payroll-authorization/decision.md` and `payslip/decision.md` §8 already rejected it: no resource exists to attach a policy to, and inventing one would require guessing at a shape no repository evidence supports.

---

# 9. Producer / Consumer Direction

**Repository Evidence** — observed dependency direction only, not inferred intent:

- **Producers of Payroll Calculation's inputs** (§6): `AttendanceEventService`/`ReconciliationService`, `LeaveRequestService`/`LeaveBalanceService`, `OvertimeRequestService`, `TimesheetService`, `ApprovalService` (for the three entities it decides), `HrEmployeeService`, `HolidayService`, `ShiftService`, and `PayrollRunService` (as the batch/run context). All confirmed, already-implemented, already-established read-only relationships.
- **Consumers of Payroll Calculation**: **none observed in code**, because Payroll Calculation does not exist to be called by anything. The only forward reference found anywhere is prose-level: `payroll/implementation-plan.md` and `payslip/implementation-plan.md` both name "Payroll Calculation" as a distinct, out-of-scope item in a list alongside "Payroll Processing"/"Payroll Integration"/"Payroll Authorization" — this establishes that these documents treat it as a separate, presumably-related future capability, but does not establish an observed code dependency from `Payslip` (or anything else) onto it.

**Logical Consequence**: Producer direction is fully evidenced and decidable (§6). Consumer direction is not observed in code anywhere — only named, unlinked, in prose.

---

# 10. Deferred Decisions

Cannot yet be answered from repository evidence. Not solved here:

- Whether Payroll Calculation's result is persisted or transient (§4).
- Which execution mechanism (request-driven, event-driven, job-driven) Payroll Calculation would use (§5).
- Whether aggregation (overtime duration, timesheet totals) is Payroll Calculation's own responsibility or an upstream capability's (§7).
- Whether a "normalization" step exists or is needed at all (§7).
- What formula, rate structure, or rule content Payroll Calculation would execute (§7) — no rule/formula/expression engine exists to draw on.
- Whether "snapshot creation" is a distinct responsibility from `Payslip`'s own already-decided persistence (§7, tied to §4).
- Where compensation/rate data would originate — inherited, unresolved from `payroll/decision.md` §7.
- Pay-period cadence — inherited, unresolved from `payroll/decision.md` §7 and `TIMESHEET_DESIGN.md` §3.
- Whether "Payroll," "Payroll Calculation," "Payroll Integration," and "Payroll Processing" name distinct capabilities or overlapping framings of the same one — inherited, unresolved from `payroll/discovery.md` §7-8, restated by `discovery.md` §10 for this capability specifically.
- Whether `Payslip` is confirmed as Payroll Calculation's actual consumer, and in what data shape — not observed anywhere in code (§9).

---

# Recommendation

```
Another governance phase is required before Implementation Planning.
```

Unlike `PayrollRun`/`Payslip`'s own first iterations — each scaffoldable with a decidable, minimal, zero-computation identity (`code`/`name`; `employee_id`/`payroll_run_id`) — Payroll Calculation's defining responsibility is computation itself, and no repository evidence establishes what that computation would consume as a rate/formula input (§7, §10), how its result would persist (§4), or how it would execute at the scale required (§5). There is no analogous "meaningful zero-computation scaffold" for a capability whose only reason to exist is to compute something. The deferred items in §10 — principally the compensation/rate data source and pay-period cadence, both requiring product or business input this repository does not contain — must be resolved first.

---

# References

- `docs/architecture/capabilities/payroll-calculation/discovery.md`
- `docs/architecture/capabilities/payroll/decision.md`, `domain-model-discovery.md`, `discovery.md`, `implementation-plan.md`, `architecture-review.md`
- `docs/architecture/capabilities/payslip/decision.md`, `discovery.md`, `implementation-plan.md`, `architecture-review.md`
- `docs/architecture/capabilities/payroll-authorization/decision.md` (precedent for §8's authorization-blocked finding)
