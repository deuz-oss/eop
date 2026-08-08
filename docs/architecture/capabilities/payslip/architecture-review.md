# Payslip — Architecture Review

**Status:** Complete

**Capability:** Payslip (data-owning capability)

**Reviews:** `discovery.md`, `decision.md`, `implementation-plan.md`

**Owner:** EOP Architecture Governance

---

# Purpose

This is an architecture review, validating consistency only, per the governing instruction. It does not create a new architectural decision, does not resolve any `Unknown`/`Deferred` item, and does not modify `decision.md` or `implementation-plan.md`. Repository evidence and the three reviewed documents are the only sources consulted.

---

# Summary

All three documents were re-read in full for this review, cross-checked against each other line by line on the nine points requested, not assumed consistent from having been authored in sequence. One real, quotable internal inconsistency was found, confined to `decision.md`'s own Recommendation section contradicting its own Architectural Decisions section — it does not propagate into `implementation-plan.md`, which is correct on the same point. No Blocking finding exists. Four additional Observations are recorded — none affects what would be built.

---

# Findings

## Finding 1 — `decision.md`'s Recommendation section names a method (`list_paginated`) that `decision.md`'s own Architectural Decisions never decided, and that `implementation-plan.md` correctly excludes.

**Classification: Non-blocking.**

`decision.md`, Recommendation section, quoted exactly:

> "implementation-plan.md may begin, scoped to structural CRUD-minus-mutation scaffolding (create/get/list/**list_paginated** only — no update, no delete, per §4/§5), matching PayrollRun's own precedent-following approach."

`decision.md` §4 (Mutability), the section this Recommendation cites as its own basis, quoted exactly:

> "**Decision: Immutable after creation — no `update`, no `delete` method.**"

§4 never mentions `list_paginated` — its own method-shape discussion is limited to `create`/`get`/`list`, and to whether `update`/`delete` are excluded. The word `list_paginated` appears in `decision.md` exactly once, in the Recommendation paragraph quoted above, and nowhere else in the document.

`implementation-plan.md` §5 (Repository), quoted exactly:

> "No pagination method (`.paginate`) is exposed, consistent with `decision.md` §4/§5's `create`/`get`/`list`-only scope."

`implementation-plan.md` correctly does not carry `list_paginated` forward anywhere — not in § Model, § Repository, § Service, or § API. This is the correct behavior given §4's actual decided scope; the inconsistency is confined entirely to `decision.md`'s own Recommendation prose, likely carried over by phrasing analogy from `payroll/decision.md`'s equivalent Recommendation (where `PayrollRun` genuinely does support pagination). It does not affect `implementation-plan.md`, which this review confirms is internally correct on this point. Not fixed here, per instruction (`decision.md` is not to be modified).

## Finding 2 — `decision.md`'s Deferred Decisions item "Payslip's exact schema, fields, API shape, and migration" does not appear in `implementation-plan.md` §11.

**Classification: Observation.**

`decision.md`, § Deferred Decisions, quoted exactly:

> "**Payslip's exact schema, fields, API shape, and migration** — explicitly out of this document's scope by instruction; belongs to a future `implementation-plan.md`."

`implementation-plan.md` §11 (Deferred Decisions) lists seven items, corresponding one-to-one with `decision.md`'s other seven Deferred Decisions items; this eighth item is not among them.

This is a literal disappearance, checked as instructed, but not a violation on inspection: `decision.md`'s own wording scopes this item as belonging to "a future `implementation-plan.md`," not as an open architectural unknown the way the other seven items are (FK `ON DELETE` policy, compensation source, pay-period cadence, etc.). `implementation-plan.md` §4/§7/§8 address exactly this item — using only what `decision.md` §1–§9 already decided (Aggregate Root, `employee_id`, `payroll_run_id`'s existence, `RESTRICT` for one FK, `create`/`get`/`list` only) — without introducing any field, route, or column `decision.md` did not already establish. No new architectural decision was made in resolving it; it was consumed by the phase `decision.md` itself named for it.

## Finding 3 — Minor terminology variance: `ondelete` vs. `ON DELETE`.

**Classification: Observation.**

`decision.md` consistently uses lowercase `ondelete` (e.g., "the `PayrollRun`→`Payslip` foreign-key `ondelete` policy"). `implementation-plan.md` consistently uses uppercase, SQL-style `ON DELETE` (e.g., "`ON DELETE RESTRICT`", "FK `ON DELETE` policy"). Both refer to the identical concept and the identical unresolved question; this is a capitalization/style difference only, with no substantive disagreement about what remains undecided.

## Finding 4 — `UnitOfWork` is not named explicitly anywhere in `implementation-plan.md`.

**Classification: Observation.**

The governing layering (`API → Service → UnitOfWork → Repository → Model`) is not violated in substance: `implementation-plan.md` §6 (Service) is the only section that calls a Repository method (`HrEmployeeRepository.exists()`/`PayrollRunRepository.exists()`), and § 7 (API) describes routes only, with no repository or model access implied at that layer — no skipped layer is present. However, the term "UnitOfWork" itself does not appear anywhere in the document, unlike `payroll/implementation-plan.md`'s more explicit style (which named `SQLAlchemyUnitOfWork`/`uow_factory` directly). This is a documentation-completeness note, not an architecture violation — no evidence suggests the UoW pattern is skipped, only that it is not spelled out.

## Finding 5 — `decision.md`'s own Status line and its later content sit close to, but do not cross, its own stated boundary.

**Classification: Observation.**

`decision.md`'s Status line: *"Approved — Architectural Contract Only (implementation details, schemas, APIs, migrations, and models explicitly excluded, per scope)."* §3 and §6 nonetheless name two specific field identities (`employee_id`, `payroll_run_id`) and one concrete `ON DELETE` value (`RESTRICT`, for `employee_id`). This is defensible as identity/relationship-level architectural contract rather than full schema (no type, length, nullability, or constraint-naming detail is given — those appear only in `implementation-plan.md` §4/§8) — but the Status line's own wording does not draw this line as precisely as the document's actual content does. No downstream effect: `implementation-plan.md` needed exactly these two facts and nothing more from `decision.md`, and received exactly that.

---

## Checked — No Architectural Inconsistency Detected

The following checks were performed and found clean, restated per the review scope:

- **Aggregate consistency**: `discovery.md` correctly never classifies Payslip (Discovery must not decide architecture); `decision.md` §1 decides Aggregate Root; `implementation-plan.md` §3 restates it as already-decided, unrevisited. No contradiction anywhere.
- **Boundary consistency**: no document assigns Payslip any responsibility belonging to `PayrollRun`, Payroll Calculation, Payroll Processing, Payroll Authorization, or Payroll Integration. `implementation-plan.md` §6's existence-check against `PayrollRunRepository.exists()` is a read-only validation explicitly anticipated by `decision.md` §2's "Lifecycle dependency" finding, not a boundary violation.
- **Dependency direction**: `PayrollRun ↓ Payslip` is stated identically in `discovery.md` §2, `decision.md` §2, and `implementation-plan.md` §4/§6 — never reversed anywhere.
- **Mutability consistency** (beyond Finding 1): `create`/`get`/`list`, no `update`, no `delete` is stated identically and without contradiction across `decision.md` §4/§5 and `implementation-plan.md` §2/§5/§6/§7.
- **Foreign-key consistency**: `employee_id` and `payroll_run_id` appear identically named in both documents; `employee_id`'s `RESTRICT` is consistent everywhere it appears. `payroll_run_id`'s `ON DELETE` was left explicitly undecided in both documents at the time of this review's original authorship; it has since been resolved by Architecture Governance to `RESTRICT`, consistently reflected in `decision.md` §6 and `implementation-plan.md` §4/§8 as of this update.
- **Repository consistency**: `implementation-plan.md` describes API calling Service, Service calling Repository, Repository backed by the Model — no skipped layer (Finding 4 notes a naming omission, not a layering defect).
- **Authorization boundary**: no document introduces `AuthorizationEvaluator`, `AuthorizationService`, or `RequestContext` for Payslip anywhere; `implementation-plan.md` §6/§7 explicitly exclude all three.
- **Deferred items** (beyond Finding 2): seven of `decision.md`'s eight Deferred Decisions items appear unchanged in `implementation-plan.md` §11; no item not present in `decision.md` was newly introduced.
- **Internal consistency** (beyond Findings 1, 3, 5): no other contradiction, ambiguous wording, or conflicting ownership statement was found across the three documents.

---

# Recommendation

```
Approved with Known Risks
```

No Blocking finding exists. Finding 1 is a real inconsistency confined to `decision.md`'s own prose and does not affect `implementation-plan.md`, which is correct; Findings 2–5 are Observations with no effect on what would be built.

**Update**: The `RESTRICT`-vs-`CASCADE` foreign-key ambiguity previously listed here has been resolved by Architecture Governance. `Payslip.payroll_run_id` now uses `ON DELETE RESTRICT`, final and no longer Deferred (`decision.md` §6; `implementation-plan.md` §8). It is removed from the Known Risks list below accordingly.

Known Risks — restated only from `implementation-plan.md` §12 / `decision.md` § Open Questions, not invented here:

- Whether the convention-level immutability decided in `decision.md` §4/§5 (a service that simply does not implement `update`/`delete`) is an adequate guarantee for a financial record remains open — no repository evidence answers this either way.
- Whether `AuditMixin`'s repository-wide non-population is itself a gap that should be addressed before or alongside Payslip remains open, given Payslip's own governance rationale depends on some form of audit trail existing.

---

# References

- `docs/architecture/capabilities/payslip/discovery.md`
- `docs/architecture/capabilities/payslip/decision.md`
- `docs/architecture/capabilities/payslip/implementation-plan.md`
