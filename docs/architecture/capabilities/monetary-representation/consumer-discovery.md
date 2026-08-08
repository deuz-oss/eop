# Monetary Consumer Discovery

## Summary

Discovery date: 2026-08-07
Repository version: `356764a` (branch `feature/payroll-authorization`)

This is discovery only. No production code, migration, or domain model was changed to produce this document.

Scope searched: `services/api/src/eop_api/models/`, plus targeted checks of `services/`, `repositories/`, and `api/` where a model-level match required confirming whether the field was real or only prose.

---

## Consumer Inventory

| Consumer | Monetary Concept | Current Type | Currency Context | Ownership | Priority |
|---|---|---|---|---|---|
| `PayrollRun` | None | N/A — no monetary field exists | N/A | Payroll (scaffolding only) | Low — nothing to migrate yet |
| `Payslip` | None | N/A — no monetary field exists | N/A | Payslip (scaffolding only) | Low — nothing to migrate yet |
| `OvertimeRequest` | None | N/A — no rate/amount field exists | N/A | N/A | Low — nothing to migrate yet |
| `JobGrade` | None (adjacent, not monetary) | `level: Integer` — a seniority rank, not a value | N/A | JobGrade (master data) | Not applicable |
| `LeaveBalance` | None (false positive on "balance") | `allocated_days`/`used_days`/`remaining_days`: `Integer` day counts | N/A | Leave | Not applicable |
| Compensation | Uncertain — capability has no code | N/A — capability does not exist in `services/api/src` | N/A | Compensation (governance only) | High, once implemented — this is the evidenced future owner of monetary content |
| Payroll Calculation | Uncertain — capability has no code | N/A — capability does not exist in `services/api/src` | N/A | Payroll Calculation (governance only) | High, once implemented |
| Benefit / Expense / Billing / Invoice / Reporting | Not found | N/A | N/A | N/A | Not applicable — no such capability exists anywhere in the repository |

---

## Consumer Details

## `PayrollRun`

Status:

DISCOVERED (as an entity) / NOT FOUND (as a monetary consumer)

Monetary Fields:

| Field | Current Type | Meaning |
|---|---|---|
| — | — | None. `code: String`, `name: String` are the only fields; the model's own docstring states directly: *"No period, status, monetary, or relationship field exists on this entity."* |

Business Owner:

N/A — no monetary content exists to own.

Calculation Owner:

N/A.

Currency Handling:

None — no field to carry currency context.

Current Risk:

None today. Future risk is architectural, not immediate: when `PayrollRun` eventually gains monetary fields (per its own governance), those fields should adopt `Money` rather than a raw numeric type from the start, to avoid a later migration.

Migration Priority:

Not applicable — there is nothing to migrate.

---

## `Payslip`

Status:

DISCOVERED (as an entity) / NOT FOUND (as a monetary consumer)

Monetary Fields:

| Field | Current Type | Meaning |
|---|---|---|
| — | — | None. `employee_id`/`payroll_run_id` FKs are the only fields; the model's own docstring states directly: *"No monetary, status, period, or calculation field exists on this entity."* |

Business Owner:

N/A.

Calculation Owner:

N/A.

Currency Handling:

None.

Current Risk:

Same as `PayrollRun` — a future-adoption consideration, not a present gap.

Migration Priority:

Not applicable.

---

## `OvertimeRequest`

Status:

DISCOVERED (as an entity) / NOT FOUND (as a monetary consumer)

Monetary Fields:

| Field | Current Type | Meaning |
|---|---|---|
| — | — | None. Fields are `overtime_date`, `start_time`, `end_time`, `status`, `reason`, `approved_by`/`approved_at`/`rejection_reason` — a time-window request only. The model's own docstring states: *"overtime-hours calculation, and payroll integration are all future concerns — out of scope here."* No rate or amount field exists anywhere. |

Business Owner:

N/A.

Calculation Owner:

N/A — explicitly deferred to a future, unbuilt capability.

Currency Handling:

None.

Current Risk:

None today.

Migration Priority:

Not applicable.

---

## `JobGrade`

Status:

DISCOVERED (as an entity) / NOT FOUND (as a monetary consumer)

Monetary Fields:

| Field | Current Type | Meaning |
|---|---|---|
| `level` | `Integer` | A globally-unique seniority/pay-grade rank — an ordinal classification, not a stored value. Excluded per the discovery rule not to assume every numeric field is monetary: `level` orders grades, it does not represent an amount of money. |

Business Owner:

N/A for `level` itself. `compensation/decision.md` §3 (governance-only, no code) already decided monetary interpretation belongs to Compensation, not `JobGrade`, and left whether/how the two relate as an open question.

Calculation Owner:

N/A.

Currency Handling:

None.

Current Risk:

None — flagged here only because "Job Grade" is a natural candidate to *misclassify* as monetary; confirmed it is not.

Migration Priority:

Not applicable.

---

## `LeaveBalance`

Status:

DISCOVERED (as an entity) / NOT FOUND (as a monetary consumer)

Monetary Fields:

| Field | Current Type | Meaning |
|---|---|---|
| `allocated_days` | `Integer` | A count of leave days, not a monetary amount. |
| `used_days` | `Integer` | Same — a day count. |
| `remaining_days` | `Integer` | Same — a day count. |

The word "balance" here means a day-count balance, not a financial one — a direct false-positive on the field-candidate list, confirmed by reading the actual columns rather than assuming from the name.

Business Owner:

N/A — not monetary.

Calculation Owner:

N/A.

Currency Handling:

None.

Current Risk:

None.

Migration Priority:

Not applicable — this entity should not adopt `Money` at all; its values are day counts.

---

## Compensation (capability)

Status:

NOT FOUND

Monetary Fields:

| Field | Current Type | Meaning |
|---|---|---|
| — | — | No code exists anywhere in `services/api/src` for this capability — no model, no field of any kind. Its entire governance (`discovery.md` through `capability-boundary-analysis.md`, `docs/architecture/capabilities/compensation/`) is documentation only. |

Business Owner:

Compensation, per its own already-approved `decision.md` §1 (by elimination) — but this is a governance conclusion, not something observed in code, since no code exists.

Calculation Owner:

N/A — no calculation exists to own.

Currency Handling:

N/A.

Current Risk:

None today (nothing built to be at risk). This is the capability most likely to become `Money`'s first real consumer once its own remaining business-content blockers (precision/rounding/currency, tracked separately) are resolved.

Migration Priority:

High, once implemented — should adopt `Money` at construction time rather than a raw numeric field, avoiding any migration at all.

---

## Payroll Calculation (capability)

Status:

NOT FOUND

Monetary Fields:

| Field | Current Type | Meaning |
|---|---|---|
| — | — | No code exists anywhere in `services/api/src` for this capability either — documentation only, same as Compensation. |

Business Owner:

N/A — no code.

Calculation Owner:

N/A — no code; its own governance already established it will own computation/formulas once built, not the underlying representation.

Currency Handling:

N/A.

Current Risk:

None today.

Migration Priority:

High, once implemented — same reasoning as Compensation.

---

## Benefit / Expense / Billing / Invoice / Reporting (capabilities)

Status:

NOT FOUND

None of these five prioritized capability candidates exists anywhere in `services/api/src` — no model, service, repository, or API module, and no governance folder under `docs/architecture/capabilities/` either. `Dashboard` (`services/dashboard.py`) is the closest existing analog to "Reporting," and was checked directly for any monetary aggregation (`amount`/`total`/`salary`/`cost`/`balance`) — zero matches. These five are not discoverable candidates in this repository at all, not merely unconfirmed ones.

---

## Findings

**Confirmed monetary consumers**: None. Zero fields in the entire repository currently hold a monetary value — this is the same finding `monetary-representation/discovery.md` already established, re-confirmed here by a fresh, independent search rather than assumed from that prior document.

**Uncertain candidates**: Compensation and Payroll Calculation — both are evidenced, governance-level *future* consumers with no current code, so "uncertain" describes their timeline, not whether they'd be monetary if built (that part is already settled by their own governance).

**Non-monetary fields excluded, with reasoning**:
- `JobGrade.level` — an ordinal rank, not an amount.
- `LeaveBalance.allocated_days`/`used_days`/`remaining_days` — day counts, not currency amounts, despite "balance" triggering the field-candidate search.
- `PayrollRun`, `Payslip`, `OvertimeRequest` — each explicitly, in their own docstrings, disclaims owning any monetary field today.

No field anywhere was found holding money under a disguised name (e.g., a generically-named `amount` or `total` column that turned out to be currency-shaped) — every match on the field-candidate list traced back to either prose or a confirmed non-monetary use.

---

## Out of Scope

Per instruction, this document does not include a migration plan, code changes, `Money` adoption implementation, API changes, or database changes. No production file, model, or migration was modified to produce it.
