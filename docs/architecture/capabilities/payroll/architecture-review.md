# Payroll — Architecture Review

**Status:** Complete

**Capability:** Payroll (data-owning capability)

**Reviews:** `discovery.md`, `domain-model-discovery.md`, `decision.md`, `implementation-plan.md`

**Owner:** EOP Architecture Governance

---

# Purpose

This is an architecture review, not an implementation review. It evaluates whether the four existing Payroll governance documents are internally consistent, correctly bounded, and sufficient to begin the first implementation iteration — it does not evaluate code, because none exists yet. Repository evidence, and the four documents themselves, are the only sources consulted. No document is modified by this review.

---

# Summary

```
Approved with Known Risks
```

The four documents are consistent on every substantive architectural point: aggregate classification, ownership boundary, and iteration-1 scope all agree across `discovery.md` → `decision.md` → `domain-model-discovery.md` → `implementation-plan.md`, and each later document correctly narrows rather than contradicts the one before it. `implementation-plan.md` v3's structure (`PayrollRun` as a two-field, zero-FK, master-data-shaped aggregate; `Payslip` deferred) is directly supported by repository precedent, verified independently in this review, not merely re-asserted.

Not "Approved" outright: one real phrasing imprecision exists in `decision.md` §6 (§ Consistency Review, Finding 1) that a careless implementer could misread, and several risks already named across the four documents remain genuinely open rather than resolved (§ Risks). None of these block or misdirect the scaffolding work `implementation-plan.md` v3 describes — they are conditions to carry forward, not defects requiring rework.

Not "Rework Required": no document invents an unsupported field, contradicts another document's decision, or expands scope beyond what repository evidence supports. The one imprecision found (§ Consistency Review, Finding 1) is already correctly resolved in substance by `implementation-plan.md`'s actual field/API design — it is a documentation-clarity issue in `decision.md`, not a design error carried into the plan.

---

# Consistency Review

## Checked and Consistent

- **Aggregate classification** (`PayrollRun`, `Payslip` as separate persisted Aggregate Roots) is identical across `decision.md` §2–§3 and `domain-model-discovery.md` A1/A4 — the latter independently re-derives the same conclusion from the repository's persisted-decision-vs-recomputed-view pattern rather than merely citing the former, and the two arrive at the same place.
- **Ownership boundary** (`decision.md` §4 "What Payroll Must Not Own" vs. `domain-model-discovery.md` A2 "Payroll must never own"/"must never modify") — same six items, same reasoning, same citations. No divergence.
- **Dependency direction** (`decision.md` §5's table vs. `domain-model-discovery.md` E1's producer table) — every producer capability named in one appears in the other with the same read-only relationship and the same caveats (`LeaveBalance` unsynchronized, `OvertimeRequest`/`Timesheet` CRUD unauthorized). Column headers differ (`decision.md` groups by capability; `domain-model-discovery.md` adds mutability/timing columns per its own instruction), but no fact conflicts.
- **Producer count** ("nine producer capabilities," `discovery.md` §6) vs. ("eleven [persisted entities] reviewed," `domain-model-discovery.md` A1) — checked directly, not assumed: these count different things. `discovery.md`'s nine are capability-level rows (one row, "HR Master Data (reference)," bundles five entities: `Shift`/`Holiday`/`JobGrade`/`EmploymentType`/`EmploymentStatus`); `domain-model-discovery.md`'s eleven are individual persisted models (the same five, counted separately, plus `HrEmployee`/`AttendanceEvent`/`LeaveRequest`/`LeaveBalance`/`OvertimeRequest`/`Timesheet`). Both numbers are correct for what they count. Not an inconsistency.
- **`Payslip` deferral** — the *classification* of `Payslip` (persisted Aggregate Root, `decision.md` §3, `domain-model-discovery.md` A1) is unchanged and unrevisited by `implementation-plan.md`; only the *sequencing* (build it later, not now) is decided there, in a section `decision.md`/`domain-model-discovery.md` never addressed (neither discusses which aggregate to build first). No contradiction — a later document answering a question the earlier ones left open, not overriding an answer they gave.
- **Excluded concepts** (payroll period, status/lifecycle, monetary fields, currency, tax, effective dating, batch, events, authorization) are named consistently across all four documents' own "not decided"/"must not"/"out of scope" sections, with no document silently reintroducing one another excludes.

## Findings (Inconsistencies)

**Finding 1 — `decision.md` §6 phrasing does not exempt `PayrollRun` from an FK it should not have.**

`decision.md` §6's "Architectural Constraints" for "`PayrollRun` / `Payslip`" states, as a single "Must" bullet covering both: *"an `employee_id`-or-equivalent FK with `ON DELETE RESTRICT` matching every other FK into `HrEmployee`... "* Read literally and in isolation, this requires an employee-scoping FK on **both** aggregates. But `decision.md` §3 elsewhere states `Payslip` — not `PayrollRun` — is "scoped to one employee," and `implementation-plan.md`'s `PayrollRun` (§ Aggregate, § Model) deliberately has no `employee_id`, exactly because that scoping belongs to `Payslip` alone.

This is a real drafting imprecision in `decision.md` §6, not merely a stylistic nitpick — a reader consulting §6 alone, without cross-referencing §2–§4, could conclude `PayrollRun` needs an employee FK it explicitly must not have (`implementation-plan.md`'s own § Model excludes "employee scope" as a governing-instruction exclusion). `implementation-plan.md` resolves this correctly in substance (no `employee_id` on `PayrollRun`), consistent with the weight of `decision.md` §2–§4, but §6's text itself is not internally precise. This review does not modify `decision.md` (out of scope); it is recorded here as a documentation-clarity risk (§ Risks, Item 1).

**Finding 2 — `decision.md` §4 describes `PayrollRun` as eventually owning "whatever computation logic combines its own inputs... into a result"; `implementation-plan.md` excludes all computation.**

Checked and resolved, not a contradiction: `decision.md` §4 describes ultimate/eventual ownership across the capability's full lifetime ("once those rules and their required data exist," its own qualifying clause). `implementation-plan.md` scopes only iteration 1. The two documents operate at different time horizons on the same point and agree once that distinction is made explicit — worth noting because a reader skimming only `decision.md` §4's headline claim ("Payroll owns... computation logic") without its qualifier could mistake it for a claim about the current iteration.

No other inconsistency was found across the four documents.

---

# Boundary Review

Ownership boundaries are clear and consistently stated. Verified against each item named:

| Capability | Confirmed not owned by Payroll | Evidence |
|---|---|---|
| Attendance | Yes — `AttendanceEventService`/`ReconciliationService` retain raw-event capture and reconciliation; Payroll reads their output only | `decision.md` §4, §5; `domain-model-discovery.md` A2 |
| Leave | Yes — `LeaveRequestService` retains CRUD/authorization; Payroll reads `status == "approved"` only | `decision.md` §4, §5; `domain-model-discovery.md` A2 |
| Leave Balance | Yes — `LeaveBalanceService` retains bookkeeping, including its unsynchronized state; Payroll does not write `LeaveBalance` rows | `decision.md` §4; `domain-model-discovery.md` A2 |
| Approval | Yes — `ApprovalService` retains the `pending → approved/rejected` transition for all three entities it orchestrates; Payroll never calls it, only reads the resulting `status` | `decision.md` §4, §5; `domain-model-discovery.md` A2 |
| Overtime | Yes — `OvertimeRequestService` retains CRUD; Payroll reads `status == "approved"` only, inheriting (not fixing) its CRUD-authorization gap | `decision.md` §4, §5, §7; `domain-model-discovery.md` A2, Remaining Unknowns |
| Timesheet | Yes — same pattern as Overtime | `decision.md` §4, §5, §7; `domain-model-discovery.md` A2, Remaining Unknowns |
| HR Master Data | Yes — `HrEmployee`, `JobGrade`, `EmploymentType`, `EmploymentStatus`, `Shift`, `Holiday` all remain owned by their existing dedicated services; a future compensation field's likely home is explicitly flagged "not confirmed" rather than claimed for Payroll | `decision.md` §4; `discovery.md` §1 |

`implementation-plan.md`'s actual `PayrollRun` design contains no FK to any of the above, no call to any of their services, and no read of their data at all in iteration 1 (§ Implementation Scope Review) — the boundary is not just declared in the governance documents, it is enforced by the concrete design that resulted from them.

**Payroll only consumes existing capabilities**: confirmed. `decision.md` §5 and `domain-model-discovery.md` A2/E1 both describe every relationship as read-only, and no document proposes a write path from Payroll into any producer's table, except through `ApprovalService`'s own already-existing, narrowly-scoped exception (§4, `decision.md` §6) — which Payroll is explicitly barred from extending to itself without its own separate decision.

---

# Aggregate Review

## `PayrollRun`

**Structure is consistent with repository precedent**, verified independently against source in this review, not only against the plan's own claims:

- `code: String(50)`, unique, and `name: String(255)`, indexed — matches `Shift.code`/`.name`, `Holiday.code`/`.name`, `JobGrade.code`/`.name`, `EmploymentType.code`/`.name`, `EmploymentStatus.code`/`.name` exactly, all five confirmed via direct model reads in prior Payroll documents.
- Zero foreign keys — matches the same five entities, all confirmed zero-FK, and matches `ARCHITECTURE_INVENTORY.md`'s own "HR — Status: Mature" grouping cited in `implementation-plan.md` § Aggregate.
- `BaseEntity` mixin inheritance (`UUIDMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin`/`VersionMixin`) — universal across every entity in the repository, not a Payroll-specific choice.
- Repository/Service/API shape (`PayrollRunRepository(BaseRepository[PayrollRun])`, plain-CRUD `PayrollRunService`, `CurrentUser`-only API) — matches `EmploymentTypeRepository`/`EmploymentTypeService`/`api/employment_types.py` line-for-line in structure, confirmed by direct comparison in this review.

`description`'s exclusion is a deliberate, evidence-aware scope decision (`implementation-plan.md` § Model), not an oversight — its presence-precedent (5/5) is acknowledged, and its absence is justified on the narrower "identity" question the governing instruction asked, not on missing precedent. This review finds that reasoning sound: `description` is never part of a `UniqueConstraint` or index in any reviewed entity, so it does not serve the identity role the other two fields do.

The two accepted fields (`code`, `name`) touch none of the excluded concepts (period, status, employee scope, money, currency, lifecycle, effective dating) — verified: neither field's type, constraint, or stated purpose encodes any of them.

## `Payslip` — Deferral Evaluated

**The deferral remains correct**, on the same two grounds `implementation-plan.md` gives, both re-checked against current repository state (not merely re-asserted) as part of this review:

1. `Payslip` requires at minimum two FKs (`payroll_run_id`, `employee_id`) — a shape no reviewed standalone master-data module has, and one `ARCHITECTURE_INVENTORY.md` itself categorizes outside the "Mature," zero-FK group. This remains true independent of anything decided in this review.
2. `payroll_run_id` would reference a table (`payroll_runs`) that does not yet exist in the codebase and would not exist until this same plan's own migration runs — scaffolding `Payslip` in the same iteration means designing against a dependency with no confirmed, migrated shape yet.

No new evidence surfaced in this review changes either ground. The deferral is not a placeholder awaiting justification — it is actively re-derived here and holds.

---

# Implementation Scope Review

Verified directly against `implementation-plan.md`'s actual, current content (not its stated intentions alone):

| Excluded concern | Present in the plan? | Evidence |
|---|---|---|
| Payroll calculation | No | No computation method anywhere in § Service; § Model has no field a calculation could act on |
| Payroll processing | No | No batch, no multi-row operation; single-row CRUD only |
| Authorization | No | Every route uses `CurrentUser` only (§ API); no `RequestContext`, `AuthorizationRequest`, or evaluator referenced anywhere |
| Approval | No | No `ApprovalService` import or call; no `status` field to transition (§ Model explicitly excludes it) |
| Posting | No | Not present in any section |
| Accounting | No | Not present in any section |
| Reporting | No | Not present in any section |
| Integrations | No | § Explicitly Out of Scope states `PayrollRun` "reads nothing from" any producer capability; no FK, import, or repository reference to any of them exists in § Model/§ Repository/§ Service |
| Events | No | § Service explicitly states no `EventService` call; `domain-model-discovery.md` E3's finding that `EventService` has zero existing callers is respected, not violated |
| Jobs | No | Same, for `JobService` |
| Scheduling | No | Not present in any section; `down_revision`/migration versioning (§ Database Migration) is platform migration-chain bookkeeping, not business scheduling, and does not encode a payroll cadence |

Every item is confirmed absent by direct inspection of the plan's Model, Repository, Service, API, and Migration sections, not merely by its own Scope/Out-of-Scope declarations — the declarations and the actual design agree.

---

# Risks

Only risks with direct support in the four reviewed documents; no hypothetical future problem is added here.

1. **`decision.md` §6's phrasing does not clearly exempt `PayrollRun` from an employee-FK requirement it must not have** (§ Consistency Review, Finding 1). Low practical risk today, since `implementation-plan.md` already resolved it correctly — but if a future reader consults `decision.md` §6 in isolation (e.g., during a later `Payslip` iteration) without cross-referencing §2–§4, the imprecise wording could be misapplied. Not modified by this review (out of scope); recorded for awareness.
2. **`code`'s format is unconstrained by any repository precedent beyond length/non-emptiness** (`implementation-plan.md` § Risks, Item 1) — genuinely open; nothing in any of the four documents defines what a "valid" `PayrollRun.code` looks like beyond opacity.
3. **`down_revision` may drift between plan-writing and implementation time** (`implementation-plan.md` § Risks, Item 2) — a process risk inherent to any plan that records a specific migration head, confirmed still open since no implementation has occurred.
4. **`Payslip`'s deferral leaves `PayrollRun` with no consumer or FK target once built** (`implementation-plan.md` § Risks, Item 3) — by design, but genuinely means iteration 1's `payroll_runs` table will sit unreferenced until a second iteration.
5. **Every producer capability Payroll would eventually consume remains mutable, unaudited, and (for `OvertimeRequest`/`Timesheet`) unauthorized** (`domain-model-discovery.md` E1, E4, Remaining Unknowns; `decision.md` §7) — not a risk to iteration 1 itself (which consumes nothing yet, § Implementation Scope Review), but a standing precondition risk for whichever future iteration adds real consumption. Correctly absent from `implementation-plan.md`'s own Risks section, since it is out of that iteration's scope — flagged here as a risk this review confirms is real but appropriately deferred, not overlooked.
6. **Hard-delete and unenforced optimistic-concurrency (`VersionMixin`) apply to `PayrollRun` uniformly with every other entity** (`domain-model-discovery.md` E4; `implementation-plan.md` § Risks, Item 5) — a platform-wide characteristic, not a Payroll-specific defect, but one `PayrollRun` inherits without any capability-specific mitigation.

---

# Recommendation

```
Implementation may begin, scoped exactly as implementation-plan.md v3 describes.
```

This review found no contradiction serious enough to require rework, and the one documentation-clarity finding (§ Consistency Review, Finding 1) is already correctly resolved in the plan's actual design — it does not need to block implementation, only to be kept in mind if `decision.md` is read in isolation during future work.

**Explicitly restated, per the governing instruction**: approval of this iteration's scaffolding does not approve, decide, or presuppose any of the following. Each remains a **separate future capability**, requiring its own discovery, decision, and implementation plan before any code is written for it:

- **Payroll Calculation** — no compensation model, monetary field, or computation logic exists or is approved by any of the four reviewed documents (`decision.md` §7, §9; `domain-model-discovery.md` Remaining Unknowns).
- **Payroll Authorization** — remains independently blocked; `payroll-authorization/decision.md` is unaffected and unchanged by anything reviewed here.
- **Payroll Processing** — no batch, multi-employee, or period-driven mechanism exists or is approved (`discovery.md` §4–§5; `domain-model-discovery.md` A3).
- **Payroll Integration** — no read or write path between `PayrollRun`/`Payslip` and any producer capability exists or is approved beyond the read-only relationships `decision.md` §5 describes as future, not current, work.

---

# References

- `docs/architecture/capabilities/payroll/discovery.md`
- `docs/architecture/capabilities/payroll/decision.md`
- `docs/architecture/capabilities/payroll/domain-model-discovery.md`
- `docs/architecture/capabilities/payroll/implementation-plan.md`
- `docs/architecture/capabilities/payroll-authorization/decision.md` (unaffected by this review)
- `docs/architecture/10-reference/ARCHITECTURE_INVENTORY.md`
