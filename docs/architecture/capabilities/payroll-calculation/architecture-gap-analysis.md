# Payroll Calculation — Architecture Gap Analysis

**Status:** Complete

**Capability:** Payroll Calculation

**Owner:** EOP Architecture Governance

**Based On:** `discovery.md`, `decision.md`, `domain-model-discovery.md`

---

# Purpose

This document classifies every gap standing between the repository's current state and a viable Payroll Calculation implementation. Every gap is classified as exactly one of **Repository Gap**, **Business Gap**, **Governance Gap**, **Architecture Gap**, or **External Dependency**. No architecture is invented; no gap is solved here.

**Classification key**, applied consistently below:

- **Repository Gap** — a thing that could be built with existing patterns/tools once its content is known, but does not exist yet.
- **Business Gap** — requires product/business decision-making the repository cannot supply (compensation rules, tax rules, cadence).
- **Governance Gap** — requires an architecture-authority decision, not business input — an `Unknown` already on record in prior governance.
- **Architecture Gap** — the codebase's own structural patterns don't yet support the shape needed, independent of content.
- **External Dependency** — depends on something outside this repository entirely (a real broker/worker, external tax/regulatory data).

---

# 1. Missing Upstream Capabilities

**Repository Evidence**: Every capability `decision.md` §6 names as an input producer — Attendance, Leave, Leave Balance, Overtime, Timesheet, Employee, Holiday, Shift, `PayrollRun` — already exists and is implemented. No named upstream *capability* is absent.

One capability is absent that no prior document named as a checklist item, but that `discovery.md` §1/§3 and `decision.md` §7/§10 repeatedly surface by its absence: **a capability owning compensation/rate data** (e.g., an "Employee Compensation" or "Pay Profile" concept). No model, service, or field anywhere in the repository — not `HrEmployee`, not `JobGrade`, not any other reviewed entity — carries a rate, salary, or compensation value (`discovery.md` §3, confirmed by zero matches for `Decimal|Numeric|Money|Float` and by direct field-level inspection of every reviewed model).

**Classification**: **Business Gap**, primarily — the reason no such capability exists is that its content (what a compensation record contains: fixed salary, hourly rate, currency, effective dating) has never been decided, not that building it is technically hard. Secondarily a **Repository Gap** once that content is decided (it does not yet exist as code).

---

# 2. Missing Domain Concepts

Every concept `discovery.md` confirmed absent by direct search, classified individually:

| Concept | Repository Evidence | Classification |
|---|---|---|
| Rate | No field anywhere (`discovery.md` §3) | Business Gap |
| Salary | No field anywhere (`discovery.md` §3) | Business Gap |
| Formula | No formula/rule/expression engine or representation anywhere (`discovery.md` §5, zero matches) | Architecture Gap (no calculation abstraction exists in the codebase's own architecture, independent of what any formula would contain) |
| Pay period | No `PayPeriod` concept anywhere; `TIMESHEET_DESIGN.md` §3 found cadence itself unresolved | Business Gap (cadence is a product decision) + Repository Gap (no field/entity once decided) |
| Earning | No domain-meaningful occurrence anywhere (`discovery.md` §2, confirmed by term-sweep) | Business Gap |
| Deduction | Only a leave-balance *day*-deduction concept exists, itself unimplemented (`discovery.md` §1); no monetary deduction concept exists | Business Gap |
| Tax | Zero matches anywhere (`discovery.md` §2) | Business Gap **and** External Dependency — tax computation, when it exists, is typically driven by jurisdiction-specific external rules, not a purely internal business decision |
| Benefit | Zero matches anywhere, confirmed twice (this and prior discoveries) to be ordinary English usage where matched at all | Business Gap |

**Currency/precision**, not separately listed in the instruction's examples but directly evidenced as absent (`discovery.md` §7: zero matches for `Decimal|Numeric|Money|Float` anywhere in the repository, for any purpose): **Architecture Gap** — the codebase has never used a fractional-precision type at all, independent of currency-specific content.

---

# 3. Missing Infrastructure

Classified only, per instruction — no redesign proposed:

- **`UnitOfWork`**: **Sufficient.** Proven, working, used identically by every service reviewed across this conversation. Not a gap.
- **Repository pattern (`BaseRepository`)**: **Sufficient.** Proven, working, used by every persisted entity without exception. Not a gap.
- **`JobService`**: The abstraction exists and is well-typed, but has zero callers anywhere and, more materially, its only implementation (`InMemoryJobProvider`) has no worker, scheduler, or poller behind it (`discovery.md` §6). The *interface* is not the gap; the *execution backend* (a real queue/worker) is. Classified as **External Dependency** — a real broker/worker is infrastructure outside this repository, not yet provisioned.
- **`EventService`**: Identical reasoning to `JobService` — interface present, zero callers, no working transport. **External Dependency** for the same reason.
- **Authorization Foundation**: **Sufficient as a mechanism** — proven, used by three existing capability-specific evaluators. The gap is not the mechanism but the absence of a Payroll Calculation-specific policy to plug into it, which `decision.md` §8 already found cannot be decided because no resource exists yet. Classified as **Governance Gap** (an already-recorded `Unknown`, not a mechanism deficiency).

---

# 4. Missing Persistence

**Repository Evidence**: `domain-model-discovery.md` §1-2 found that none of the six candidate entities (`PayrollCalculation`, `PayrollResult`, `PayrollFormula`, `PayrollRule`, `PayrollExecution`, `PayrollSnapshot`) has repository support for *any* classification beyond a weakly-inferred Domain Service (`PayrollCalculation` itself, which by definition owns no persistence). `decision.md` §4 and `domain-model-discovery.md` §3 both found whether a calculation output should be persisted at all is `Unknown`.

**Classification**: The question "which persisted entities are absent" cannot be answered with a concrete list, because whether *any* additional persisted entity is required has not been decided — this is a **Governance Gap** (the persist-vs-transient-vs-event decision, `decision.md` §4, `domain-model-discovery.md` §3), not a confirmed set of missing tables. The one persistence gap with clear, positive evidence behind it is the compensation/rate data source (§1) — wherever it ends up (a new field on an existing entity, or a new entity), it does not exist today. Classified as **Business Gap** (content undecided) with a downstream **Repository Gap** once decided, consistent with §1.

---

# 5. Missing Ownership

**Repository Evidence**: `decision.md` §9 and `discovery.md` §9 both confirm three responsibilities have **no owner anywhere in the repository**: leave deduction, overtime duration computation, timesheet hour aggregation. Each is explicitly excluded from its own nearest capability's stated scope (`LeaveBalanceService`, `OvertimeRequestService`, `TimesheetService` docstrings, all cited in `discovery.md` §1) and not claimed by any other reviewed capability.

**Classification**: **Governance Gap** for all three. `decision.md` §7 and `discovery.md` §9 already found, explicitly, that *whether* this responsibility belongs to the upstream capability (Overtime/Timesheet/Leave Balance itself) or to Payroll Calculation is "not addressed by any repository evidence" — this is an undecided architectural boundary assignment, not a missing technical capability (computing `end_time - start_time` is not technically hard; deciding *who* is authorized to own that computation is what's missing).

---

# 6. Blocking Ambiguities

Every `Unknown` already on record that directly blocks implementation — restated, not solved, per instruction:

1. **Calculation result shape** (persisted / transient / event) — `decision.md` §4, `domain-model-discovery.md` §3. Blocks: no model or API can be designed without this.
2. **Execution mechanism** (request-driven / batch / scheduled / event-driven) — `decision.md` §5, `domain-model-discovery.md` §5. Blocks: no entry point or trigger can be built without this.
3. **Aggregation ownership** (overtime duration, timesheet totals — Payroll Calculation's own or an upstream capability's) — `decision.md` §7, `domain-model-discovery.md` §7, restated at §5 above. Blocks: cannot determine what Payroll Calculation must compute itself versus what it can assume is already available.
4. **Formula/rate content** — no rule/formula engine or content exists (`discovery.md` §5, §7). Blocks: the calculation's own core logic cannot be written.
5. **Compensation/rate data source** — inherited, unresolved from `payroll/decision.md` §7 (§1 above). Blocks: no input data exists to compute from.
6. **Pay-period cadence** — inherited, unresolved from `payroll/decision.md` §7, `TIMESHEET_DESIGN.md` §3. Blocks: cannot define what one calculation covers.
7. **Versioning/recalculation model** — confirmed absent, `domain-model-discovery.md` §6. Blocks: cannot define correction/re-run behavior.

Not classified as directly blocking (lower-priority, documentation-level rather than implementation-level): the unresolved naming relationship between "Payroll," "Payroll Calculation," "Payroll Integration," and "Payroll Processing" (`discovery.md` §10, inherited from `payroll/discovery.md` §7-8) — this affects governance-document clarity, not this capability's own buildable content.

---

# 7. Can Any Subset Be Implemented Today?

**No.**

**Repository Evidence and reasoning**: `PayrollRun` and `Payslip` were each implementable at Iteration 1 because domain-model discovery gave each a decidable, minimal, content-free identity — `code`/`name` for `PayrollRun`; `employee_id`/`payroll_run_id` for `Payslip` — a real table, a real CRUD surface, meaningfully testable, independent of any business content still undecided. Payroll Calculation has no analogous minimal identity: `domain-model-discovery.md` §1-2 found it is, at best, a Domain Service (no owned table at all), with no decided output shape (§3), no decided execution mechanism (§5), and no decided persisted entity of any kind. A stub service class with no logic and no callable, meaningful entry point would not constitute implementing a genuine subset of this capability — it would not exercise, test, or resolve any of the six blocking ambiguities in §6, unlike `PayrollRun`/`Payslip`'s own scaffolding, which did establish real, working, tested infrastructure other work could build on.

---

# 8. Dependency Ordering

**Repository Evidence**: Of everything examined, one prerequisite is the most fundamental and repository-confirmed absent as a capability, not merely as a decision: a **compensation/rate-bearing capability** (§1, §2, §4) — without it, no calculation has any input to act on, regardless of how every other blocking ambiguity (§6) is resolved.

**Decision-ordering** (governance, not new capabilities) must additionally precede implementation for: execution mechanism (§6.2), calculation-result persistence (§6.1), and aggregation ownership assignment (§6.3) — each is a governance decision, not a missing capability, but each still must be resolved before Payroll Calculation's own structure can be designed.

**Classification**: The compensation/rate-bearing capability is a genuine **new capability dependency** — not yet built, not yet even named as a formal capability anywhere in governance. The three decision-ordering items are **Governance Gaps**, resolvable without a new capability's code, but still prerequisite in sequence.

---

# 9. Exit Criteria

Evidence that would need to exist before Implementation Planning becomes valid — stated as required evidence, not designed here:

- A compensation/rate data source exists in the repository (a capability decision and, following it, real code) — resolves §1, §2, §4, §8.
- A decided pay-period cadence exists in governance — resolves part of §2, §6.6.
- A decided calculation-result shape (persisted / transient / event) exists in governance — resolves §4, §6.1.
- A decided execution mechanism exists in governance, consistent with whatever shape (request-driven / batch / event-driven) is chosen — resolves §6.2.
- A decided ownership assignment for overtime duration, timesheet aggregation, and leave deduction exists in governance — resolves §5, §6.3.
- Formula/rate content — at minimum, a decision on how a rule/formula would be represented (even a decision to hard-code it, if evidenced by a later precedent) — resolves §6.4.
- A decided versioning/recalculation model, if recalculation is a required capability — resolves §6.7.

Until this evidence exists, any implementation plan for Payroll Calculation would be inventing architecture rather than deriving it — precisely what every document in this line has been instructed not to do.

---

# Recommendation

```
Waiting for New Capability
```

The most fundamental gap (§1, §8) is not a governance decision alone — it is the absence of any capability, complete or incomplete, that owns compensation/rate data. Every other blocking ambiguity (§6) could in principle be resolved by Architecture Governance directly, but even a fully-resolved execution mechanism, output shape, and ownership assignment would leave Payroll Calculation with no input to compute from. A new upstream capability must exist first; Additional Governance Required characterizes the remaining, secondary gaps (§6.1-§6.4, §6.6-§6.7) but not this primary one.

---

# References

- `docs/architecture/capabilities/payroll-calculation/discovery.md`
- `docs/architecture/capabilities/payroll-calculation/decision.md`
- `docs/architecture/capabilities/payroll-calculation/domain-model-discovery.md`
- `docs/architecture/capabilities/payroll/decision.md` §7 (compensation/rate source, inherited)
- `docs/architecture/TIMESHEET_DESIGN.md` §3 (pay-period cadence, inherited)
