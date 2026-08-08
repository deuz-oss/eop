# Advanced Payroll — Business/Product Decision Package

**Status:** For CPO / Business / Architecture Owner review — not an architecture decision itself
**Capability:** Payroll Calculation (Advanced tier), extending the already-implemented Payroll Iteration 1–3 base
**Prepared by:** Senior Engineer (Claude), per EOP Master Roadmap
**Scope of this document:** Audit and decision-routing only. No production code, migration, or test was written or modified to produce this package. No business rule is invented — every "Recommendation" below is an engineering risk/consistency judgment, not a proposed business rule (rates, formulas, cadences are never asserted).

---

# 1. Purpose

`docs/architecture/capabilities/payroll-calculation/architecture-gap-analysis.md` concluded Advanced Payroll implementation planning cannot begin because "the most fundamental gap... is not a governance decision alone — it is the absence of any capability... that owns compensation/rate data." That gap has since closed: **Compensation now exists, is effective-dated, and is merged** (`models/compensation.py`, PR #62). This package re-audits the payroll-calculation governance trail against that new fact, against the already-implemented Payroll Iteration 1–3 base, and against current code, then routes every remaining blocker to the party actually able to resolve it.

Nothing here authorizes implementation. Its objective is to make Advanced Payroll **ready** for implementation planning — closing the business/product gaps a governance document cannot close on its own.

---

# 2. Method

Full read of: `payroll-calculation/{discovery,decision,domain-model-discovery,architecture-gap-analysis}.md`, `payroll/decision.md` (all three versions/addenda), `payslip/{decision,architecture-review}.md`, `compensation/decision.md` (all addenda §1–19) and `decision-round-2.md`, `monetary-representation/{decision,monetary-adoption-policy}.md`, `TIMESHEET_DESIGN.md`, `TECHNICAL_DEBT_REGISTER.md`. Cross-checked against current merged code: `models/{payroll_run,payslip,compensation}.py`, `services/{payroll_calculation,compensation}.py`, `core/payroll.py`. Where a governance document's finding could be stale relative to the now-merged Compensation/Effective-Dating/Monetary-Representation work, code was read directly rather than trusting the document.

---

# 3. Already Decided — Implementation-Ready

No further decision needed; implementation planning may cite these directly.

| Item | Decision | Source |
|---|---|---|
| Payroll Calculation ownership boundary (owns pay computation by exclusion; consumes everything else read-only) | Decided | `payroll-calculation/decision.md` §1, §6 |
| `PayrollRun` lifecycle: `DRAFT → PROCESSING → COMPLETED`, no `CANCELLED` | Decided | `payroll/decision.md` V2 §1 |
| Batch shape: one `PayrollRun` = all eligible employees, no per-employee run | Decided | `payroll/decision.md` V2 §2 |
| Base-tier pay-rate source: `Compensation.base_salary` only | Decided | `payroll/decision.md` V2 §3, V3 §4 |
| Base-tier eligibility: `Compensation.is_active == true` | Decided | `payroll/decision.md` V3 §5 |
| Compensation aggregate shape (multi-row, effective-dated, overlap = hard-reject, correction = compensating via `corrects_id`) | Decided | `compensation/decision.md` §17–19 |
| `is_active` is a business/eligibility flag, independent of temporal validity | Decided | `compensation/decision.md` §18 |
| Payslip: Aggregate Root, immutable after creation (convention-level), `RESTRICT` on both FKs | Decided | `payslip/decision.md` §1, §4–6 |
| Monetary mechanism: `Money(amount, currency)` mandatory for all new monetary fields; every amount has exactly one currency | Decided | `monetary-representation/decision.md` §15; `monetary-adoption-policy.md` §5 |
| Compensation / Payroll / Payslip authorization: Owner Only | Decided | respective decision docs' Addenda |
| Deduction (as a concept) is owned by Payroll Calculation / `PayrollRun`, not Compensation | Decided (ownership only — content is §6 below) | `compensation/decision.md` §4 |

---

# 4. Already Implemented — Do Not Touch

Verified directly against merged code (not just governance prose). No part of this package proposes changing any of it.

- `Compensation` model + `CompensationService`, including `EffectiveDatingMixin`, `corrects_id`, overlap rejection, `get_by_employee(..., as_of_date)` resolution via `EffectiveDatingEvaluator` — `models/compensation.py`, `services/compensation.py`.
- `EffectiveDatingMixin` + `EffectiveDatingEvaluator` — `db/mixins.py`, `services/effective_dating_evaluator.py`.
- `Money` type — `foundation/monetary/types.py`.
- `PayrollRun` model + `PayrollRunService`, including `status` lifecycle enforcement — `models/payroll_run.py`, `services/payroll_run.py`, `core/payroll.py`.
- `Payslip` model + `PayslipService` — `create`/`get`/`list` only, no `update`/`delete` — `models/payslip.py`, `services/payslip.py`.
- `PayrollCalculationService.calculate` / `.calculate_batch` — gross = net = `Compensation.base_salary`, request-driven batch loop, duplicate-payslip protection — `services/payroll_calculation.py`.
- Payroll Authorization (Owner Only, enforced) — prior merged PRs.

**One implementation nuance surfaced during this audit, not a defect:** `CompensationService.list_active()` (used only by `calculate_batch`) returns every `is_active=True` row across all employees, **unscoped by effective date** — since `is_active` no longer implies "the one current row" (§18), an employee could theoretically have two `is_active=True` historical rows. `calculate_batch` would attempt `calculate()` twice for that employee; the second attempt hits the existing `DuplicatePayslipError` check and is skipped, so **no incorrect Payslip is produced**, only a redundant lookup. This does not block Advanced Payroll and needs no business input — it is an implementation-level robustness note for whoever next touches `PayrollCalculationService` (§5).

---

# 5. Implementation-Level Choices — Claude May Decide

No escalation required for any of these when implementation begins:

- Exact migration/column naming, index choices for any new field/table once its *content* is decided elsewhere in this package.
- Repository query/filter shape for new lookups (e.g., a period-scoped query), following `BaseRepository`/`FILTERABLE_FIELDS` precedent.
- Whether/how to short-circuit the `list_active()` double-lookup noted in §4 — a pure efficiency cleanup, not a behavior change.
- New error class naming and HTTP status mapping, following the existing `*NotFoundError`/`*InactiveError` pattern in `payroll_calculation.py`.
- Test structure and service composition/DI details.
- Mechanical reuse of `EffectiveDatingMixin` on any new period-bound entity this package's decisions eventually require — the mechanism itself is already approved (§3); applying it again is not a new architecture decision.

---

# 6. Genuine Business/Product Decisions — Require CPO/Business Decision

Each item: the question, options with consequences (not a proposed rule), repository evidence, and an engineering recommendation limited to risk/consistency — never a proposed rate, formula, or cadence.

## D1 — Pay-Period Cadence & Payroll Period Model

**Question:** How often is a `PayrollRun` created, and does the platform enforce a cadence (monthly/bi-weekly/weekly) or leave period boundaries to whoever creates the run?

**Evidence:** No `PayPeriod` concept, cadence field, or calendar-bucket precedent exists anywhere in the repository (`TIMESHEET_DESIGN.md` §3, `payroll/decision.md` §7, `payroll-calculation/architecture-gap-analysis.md` §2, §6). Every other date-span entity in the codebase (`LeaveRequest`, `Timesheet`) uses a caller-supplied arbitrary date range, never a fixed bucket.

**Options:**
- **(a) Arbitrary, caller-supplied period per `PayrollRun`** — no enforced cadence; whoever creates a run picks the dates. Lowest engineering risk (matches existing `start_date`/`end_date` convention), but does not prevent gaps, overlaps, or duplicate periods without a separate business rule.
- **(b) Fixed organizational cadence** (e.g., calendar-month) enforced by the platform — requires inventing and validating a cadence concept with zero precedent, and deciding what happens for new hires/terminations mid-period.
- **(c) Per-employee-group cadence** (e.g., salaried monthly, hourly bi-weekly) — most flexible, most invented structure; no evidence anywhere supports employee-group-scoped cadence.

**Recommendation:** (a) is the lowest-risk starting shape and requires no new business-invented cadence concept — but confirming *whether the business actually needs a period at all beyond an arbitrary label* (vs. genuinely requiring monthly-only) is the open question only Business can answer.

## D2 — Statutory/Tax Formula & Source

**Question:** What tax/statutory formula applies, and where does its content originate?

**Evidence:** Zero rule/formula/expression engine exists anywhere (`payroll-calculation/discovery.md` §5, zero matches); tax is explicitly out of scope through Iteration 3 (`payroll/decision.md` V3 §1); classified as both a Business Gap and an External Dependency (`architecture-gap-analysis.md` §2) since tax rules are jurisdiction-specific.

**Options:**
- **(a) Hard-code a single jurisdiction's formula directly in `PayrollCalculationService`** — matches this codebase's 100%-precedent style (every existing rule, including authorization policies, is hard-coded Python, never data-driven — `architecture-gap-analysis.md` §2/§4). Lowest engineering risk *if* the organization operates in one jurisdiction.
- **(b) Build a configurable formula/rule engine now** — no precedent anywhere to build on; highest risk of over-engineering ahead of a confirmed second need.
- **(c) Integrate an external payroll/tax calculation service** — appropriate if multiple jurisdictions or regulatory complexity is in scope; introduces a new external dependency.
- **(d) Keep tax out of scope for Advanced Payroll v1 too** — compute gross only, defer statutory withholding entirely.

**Recommendation:** (a) if single-jurisdiction, (c) if not — but this is a scope/priority call the business must make; building (b) speculatively would violate the pattern this codebase's own governance has consistently rejected (see `TIMESHEET_DESIGN.md` §7's identical reasoning for declining to generalize ahead of a second real need).

## D3 — Proration Rules (incl. Daily Rate Ownership)

**Question:** How is pay prorated for a partial period (new hire, termination, unpaid leave mid-period), and is "daily rate" a value the business independently negotiates, or one Payroll derives from `base_salary`?

**Evidence:** `compensation/decision.md` §4 explicitly left Daily Rate **Deferred**, framed as exactly this business question: *"Daily rate may be: an independently agreed employment term; or a derived payroll calculation value."* No proration logic or field exists anywhere.

**Options:**
- **(a) Derive daily rate at calculation time** (`base_salary / working_days_in_period`) — no new persisted field, but requires deciding what "working days" means (calendar days? excluding weekends/holidays?).
- **(b) Persist an explicit `daily_rate` on Compensation** as its own negotiated term — reopens Compensation's already-closed governance (§3 above) to add a field; only justified if daily rate is genuinely an independent business fact, not a derivation.
- **(c) No proration in Advanced Payroll v1** — full-period pay only; mid-period joiners/leavers handled outside the system.

**Recommendation:** Prefer (a) unless the business confirms daily rate is independently negotiated (not derived) — inventing a persisted field for a value that might be a pure derivation would add structure the compensation governance trail explicitly declined to add without business confirmation.

## D4 — Overtime Monetization

**Question:** What rate or multiplier converts approved overtime duration into pay, and does it apply uniformly or only to certain employee types (e.g., hourly)?

**Evidence:** `OvertimeRequest.start_time`/`end_time` are stored as submitted and never subtracted/aggregated anywhere (`payroll-calculation/discovery.md` §9); no rate/multiplier field exists anywhere; overtime is explicitly out of scope through Iteration 3 (`payroll/decision.md` V3 §2).

**Options:**
- **(a) Fixed multiplier of a derived hourly rate** — requires first solving the salaried-to-hourly conversion problem (undefined for `base_salary`-only employees).
- **(b) Flat rate per overtime hour, independent of salary** — avoids the conversion problem, but is itself a rate that must come from somewhere (Compensation? a new config?).
- **(c) No overtime pay in Advanced Payroll v1** — approved overtime remains informational only, as it is today.

**Recommendation:** Confirming whether overtime pay applies only to Compensation's already-named-but-unimplemented "Hourly Rate" population would avoid inventing a salary-to-hourly conversion for salaried staff — but which population is in scope, and the multiplier itself, are business calls.

## D5 — Attendance/Leave Deductions

**Question:** Does unpaid absence/leave reduce pay, and by what formula?

**Evidence:** `LeaveBalance` is unsynchronized with `LeaveRequest` approval and has no deduction logic (`payroll-calculation/discovery.md` §1); `ApprovalService`'s own code already carries a "deduction calculation... unresolved" comment (cited in `discovery.md` §2); attendance deduction is explicitly out of scope through Iteration 3 (`payroll/decision.md` V3 §3).

**Options:**
- **(a) Per-day deduction using the same derived-daily-rate concept as D3** — reuses one formula instead of inventing a second.
- **(b) Fixed per-instance penalty**, independent of daily rate.
- **(c) No deduction in Advanced Payroll v1** — attendance/leave remain informational.

**Recommendation:** If deductions are required, (a) avoids inventing a second, unrelated formula alongside D3 — but *whether* deductions apply at all, and to which absence/leave types, is a business policy call this repository cannot supply (no absence-type taxonomy exists anywhere).

## D6 — Allowance Ownership & Content

**Question:** What allowances exist, are they per-employee-negotiated (Compensation-owned) or org-wide policy (Payroll-computed), and should they be in Advanced Payroll v1 at all?

**Evidence:** `compensation/decision.md` §4 explicitly deferred this: *"Possible future model: Compensation-related allowance entity... Not included in the current core decision."* Zero content (which allowances, fixed vs. variable) exists anywhere.

**Options:**
- **(a) New Compensation-owned child entity**, each with its own effective dating — treats allowances as negotiated terms.
- **(b) Payroll Calculation computes allowances transiently per run** from business-configured rules — treats allowances as policy, not agreement.
- **(c) Defer allowances entirely from Advanced Payroll v1.**

**Recommendation:** (c) — with zero content decided (what allowances exist, how many, fixed vs. variable), a real allowance model needs its own business-domain-definition pass (the same governance step Compensation itself required) before this package can responsibly route it to Architecture; forcing a shape now would be inventing structure ahead of business input, exactly what Compensation's own governance trail declined to do for this same item.

## D7 — Deduction Catalog (Non-Statutory)

**Question:** Beyond tax, what deductions exist (loans, insurance/BPJS, garnishments) and where does each originate?

**Evidence:** Ownership is already decided by exclusion (Payroll Calculation / `PayrollRun`, `compensation/decision.md` §4), but zero content, catalog, or source exists anywhere.

**Recommendation:** Defer non-statutory deductions to a later iteration unless the business names specific required deduction types now — listing them is a pure business input this package cannot supply.

## D8 — Currency Scope

**Question:** Does the organization operate in a single currency, or must Payroll support multiple currencies (per employee, per `PayrollRun`, or both)?

**Evidence:** `monetary-representation/decision.md` §15 leaves "supported currency list"/"currency configuration policy" explicitly open; `compensation/decision-round-2.md` §2/§10 repeats "single currency vs multi-currency" as unresolved. Every `Compensation`/`Payslip` row today is single-currency with no conversion mechanism anywhere (Monetary Representation explicitly excludes "exchange-rate policy" from its own scope, `monetary-representation/decision.md` §3).

**Options:**
- **(a) Single organizational currency, platform-wide.** Matches what is already implemented; simplest.
- **(b) Multi-currency, `PayrollRun` scoped to one currency per run** (batches segmented by currency) — no conversion needed, but requires a currency-selection/segmentation rule.
- **(c) Multi-currency, per-employee, aggregated/reported in a base currency via conversion** — requires inventing an exchange-rate mechanism with zero precedent anywhere.

**Recommendation:** (a) unless there is an active, current multi-currency requirement — (b)/(c) each require new structure this repository has never needed before; confirming there is no near-term multi-currency requirement avoids building for a hypothetical.

## D9 — Recalculation / Correction / Reversal Requirement (incl. Payslip Immutability Enforcement Level)

**Question:** Once a `PayrollRun` reaches `COMPLETED` and Payslips are issued, can a mistake be corrected within the system, and if so, through what business workflow (approval? formal void-and-reissue? employee notification?)? Separately: is convention-level immutability (no `update`/`delete` route exposed) sufficient for financial/compliance requirements, or is a stronger enforcement mechanism required?

**Evidence:** Zero versioning/recalculation precedent exists anywhere in the repository (`payroll-calculation/domain-model-discovery.md` §6); `PayrollRun`'s lifecycle deliberately has no `CANCELLED`/re-open state (`payroll/decision.md` V2 §1); Payslip's immutability is convention-level only, and `payslip/decision.md`'s own Open Questions section already flags this exact adequacy question as unresolved and explicitly a "business/legal judgment" the repository cannot supply.

**Options:**
- **(a) No recalculation support** — a mistaken run/payslip is corrected by a manual/off-system process; Advanced Payroll v1 adds no code path for it.
- **(b) Support correction via a new, superseding Payslip row** that references the one it corrects, mirroring Compensation's already-accepted compensating-correction pattern (`corrects_id`); the corrected Payslip stays immutable and untouched.
- **(c) Support in-place recalculation/reopening of a `COMPLETED` run** — directly contradicts the already-decided immutability of Payslip and the deliberate absence of a `PayrollRun` re-open state; not recommended under any circumstance without first reopening those decisions.

**Recommendation:** (c) is inconsistent with already-decided architecture and should be avoided. Between (a) and (b): whether correction/reversal is in scope for Advanced Payroll v1 at all — versus deferred, the way Compensation itself deferred its own correction handling to a later, dedicated addendum (§19) — is the business decision; the *shape* of (b), if chosen, is not (§7, E5). Separately, whether convention-level immutability is compliance-adequate is a question for Legal/Finance, not Engineering — no repository evidence bears on it either way.

---

# 7. Architecture Decisions — Require Architecture Owner / ADR

Routed to Architecture Owner because they are structural, not business-content, questions — several are informed by, but not identical to, the Business items in §6.

## E1 — Calculation Result Shape

**Question:** Does Payroll Calculation ever need its own persisted intermediate result, or does it continue writing directly into `Payslip` only? (`payroll-calculation/decision.md` §4, unresolved.)
**Recommendation:** No evidence favors introducing an intermediate entity; the already-implemented shape (compute in `PayrollCalculationService`, write directly via `PayslipService.create`) should continue unless Business (§6, D9) requires a "draft calculation, reviewed before finalizing" workflow, which would itself need to be named as a business requirement first.

## E2 — Execution Mechanism

**Question:** Does batch calculation remain request-driven (as `calculate_batch` already is), or move to event/job-driven execution? (`payroll-calculation/decision.md` §5.)
**Recommendation:** Continue request-driven — it is proven, implemented, and the only mechanism with a working execution backend in this repository (`EventService`/`JobService` have zero callers and no broker, `discovery.md` §6). Revisit only if expected batch size/latency (a business/product input on how many employees a single run processes) demands async execution — that expectation, not the mechanism choice, is the missing input.

## E3 — Aggregation Ownership Placement

**Question:** When overtime duration, timesheet totals, or leave-deduction days need aggregating, does that logic live inside the upstream capability (Overtime/Timesheet/LeaveBalance extending their own services) or inside Payroll Calculation itself, reading raw records read-only? (`payroll-calculation/decision.md` §7, `architecture-gap-analysis.md` §5.)
**Recommendation:** Inside Payroll Calculation. Each upstream capability's own docstring already explicitly disclaims this responsibility (§ evidence throughout this package); extending them would reopen already-closed capability boundaries, whereas Payroll Calculation reading their approved records read-only and aggregating internally is a direct extension of the read-only relationship already established for every other Payroll input.

## E4 — Formula Representation

**Question:** Hard-coded Python vs. a data-driven rule/config representation for whatever formulas D2/D4/D5 eventually require? (`architecture-gap-analysis.md` §2, §4.)
**Recommendation:** Hard-coded Python. Zero precedent exists anywhere in this codebase for representing a business rule as data (`domain-model-discovery.md` §4) — every actual rule, including every authorization policy, is a hard-coded comparison. Building a configurable engine now would be the exact premature-abstraction pattern this codebase's own governance has repeatedly and explicitly declined (e.g. `TIMESHEET_DESIGN.md` §7's parallel reasoning). Revisit only once a second, concrete, confirmed need for runtime-configurable formulas exists.

## E5 — Recalculation/Correction Data Model

**Question:** If Business (§6, D9) confirms correction/reversal is in scope, how is it represented?
**Recommendation:** Mirror Compensation's already-accepted precedent directly — a nullable, self-referencing `corrects_id`/`supersedes_id` on `Payslip`, with the corrected row remaining immutable. This is a direct architectural analogy to an already-accepted pattern in this same codebase, not a new invention, and should be formalized only after D9 confirms it's needed.

## E6 / E8 — `PayrollRun` Period Field vs. New `PayPeriod` Entity

**Question:** Once Business (§6, D1) decides cadence policy, where does the period live — a field pair on `PayrollRun`, or a new `PayPeriod` entity? (`architecture-gap-analysis.md` §2, §8; `compensation/decision.md` §18 Decision 2 explicitly deferred this exact item.)
**Recommendation:** A plain `period_start`/`period_end` `Date` pair directly on `PayrollRun` — mirrors `LeaveRequest`/`Timesheet`'s own arbitrary-date-span convention rather than inventing a bucketed calendar concept. A dedicated `PayPeriod` entity is not evidenced as necessary unless D1 resolves to a fixed, reusable, named cadence the business explicitly wants tracked as its own concept.

## E7 — Multi-Currency Batch Handling

**Question:** If Business (§6, D8) selects a multi-currency option, does a single `PayrollRun` mix currencies, or is each run scoped to one currency?
**Recommendation:** Scope each `PayrollRun` to a single currency (segment batches by currency) if multi-currency is selected — avoids inventing an exchange-rate mechanism, which Monetary Representation has already explicitly excluded from its own scope.

---

# 8. Summary Table — All 13 Requested Topics, Routed

| Topic | Routed To |
|---|---|
| Pay-period cadence | Business (D1) |
| Payroll period model | Architecture (E6/E8), depends on D1 |
| Statutory/tax calculation ownership | Already Decided (§3) — Payroll Calculation owns by exclusion |
| Statutory formula/source | Business (D2) |
| Proration rules | Business (D3) |
| Overtime consumption | Business (D4, rate) + Architecture (E3, aggregation placement) |
| Attendance/leave deductions | Business (D5, formula) + Architecture (E3, aggregation placement) |
| Allowance/deduction ownership | Already Decided (Deduction ownership, §3) + Business (D6 Allowance, D7 Deduction content) |
| Currency handling | Already Decided (mechanism, §3) + Business (D8, scope) + Architecture (E7, multi-currency batching) |
| Payroll execution mechanism | Architecture (E2), informed by business scale/SLA input |
| Recalculation/re-run semantics | Business (D9) + Architecture (E5) |
| Correction/reversal semantics | Business (D9) + Architecture (E5) |
| `PayrollRun` lifecycle implications | Already Decided for base tier (§3); extension depends on D9/E5 |
| Payslip immutability implications | Already Decided (convention, §3); compliance-adequacy is Business (D9); correction shape is Architecture (E5) |

---

# 9. What This Package Does Not Do

- Does not modify any production code, model, service, migration, or test.
- Does not modify any existing governance decision (`decision.md` files, ADRs) — it only reads and routes.
- Does not invent a tax rate, formula, cadence, multiplier, or currency list anywhere above — every "Recommendation" is an engineering risk/consistency judgment about *shape*, never business *content*.
- Does not select a next implementation workstream or authorize implementation planning to begin — it exists to let CPO/Business and the Architecture Owner make Advanced Payroll implementation-ready.

---

# References

- `docs/architecture/capabilities/payroll-calculation/{discovery,decision,domain-model-discovery,architecture-gap-analysis}.md`
- `docs/architecture/capabilities/payroll/decision.md` (Versions 1–3)
- `docs/architecture/capabilities/payslip/{decision,architecture-review}.md`
- `docs/architecture/capabilities/compensation/decision.md` (§1–19), `decision-round-2.md`
- `docs/architecture/capabilities/monetary-representation/{decision,monetary-adoption-policy}.md`
- `docs/architecture/TIMESHEET_DESIGN.md`
- `docs/architecture/00-governance/TECHNICAL_DEBT_REGISTER.md`
- Current merged code: `models/{payroll_run,payslip,compensation}.py`, `services/{payroll_calculation,compensation}.py`, `core/payroll.py`
