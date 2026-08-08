# Payslip — Capability Decision

**Capability:** Payslip (data-owning capability — distinct from Payroll and Payroll Authorization)

**Status:** Approved — Architectural Contract Only (implementation details, schemas, APIs, migrations, and models explicitly excluded, per scope)

**Version:** 1

**Owner:** Architecture

---

# Executive Summary

This document decides the architectural contract for Payslip using only `docs/architecture/capabilities/payslip/discovery.md` and the repository source code that discovery cites. It resolves all ten decision topics with direct repository precedent or a logical consequence drawn from it. One topic (the `PayrollRun`→`Payslip` foreign-key `ON DELETE` policy) was originally left `Unknown` at authorship time, because two real repository precedents disagreed and no further searching would break the tie; it has since been resolved by a direct Architecture Governance decision (§6) and is no longer open.

**Payslip is decided to be**: a persisted Aggregate Root, employee-scoped, referencing `PayrollRun` (direction: `Payslip → PayrollRun`, `ON DELETE RESTRICT`), immutable after creation (no `update`, no `delete` exposed — mirroring `AuditLog`'s convention-based precedent), owned by a new, dedicated `PayslipService` with no orchestration borrowed from `ApprovalService` or `PayrollRunService`. Payslip Authorization cannot be decided today, for the same reason Payroll Authorization remains blocked: no Payslip resource exists yet. `AuditMixin`/`AuditLog` are found insufficient as existing financial-audit precedent.

---

# Repository Evidence

Restated from `discovery.md`, not re-derived, organized for reference by the topics below:

- **§1 (Immutability)**: `AuditLog` is the repository's only intentionally-immutable entity, enforced purely by service-layer convention (`AuditLogService`/`AuditLogRepository` simply never call `update`/`delete`), not by any structural mechanism. It is generic (action/entity_type/details), unused by any producer capability, and carries no employee or business-domain field.
- **§2 (FK precedents)**: Every HR-domain FK in the repository uses `ON DELETE RESTRICT` (5-for-5 employee-scoping FKs: `LeaveRequest`, `LeaveBalance`, `OvertimeRequest`, `Timesheet`, `AttendanceEvent`). The only precedent for one business/workflow aggregate referencing another (`Task.project_id`, `Assignment`) uses `CASCADE`, and belongs to the older Project Tracking domain, not the HR domain `PayrollRun`/`Payslip` belong to.
- **§3–§5 (Ownership, PayrollRun relationship, employee-scoping)**: `payroll/decision.md` §2–§4 (already-established governance, re-consulted by `discovery.md` as repository evidence) states `PayrollRun` is not employee-scoped and `Payslip` is "the employee-scoped aggregate." `PayrollRun`'s actual merged code (`models/payroll_run.py`) has zero FKs, confirming this in practice, not just in plan.
- **§6 (Audit)**: `AuditMixin.created_by`/`updated_by` are populated by no reviewed service anywhere in the repository — confirmed by direct inspection of every `create`/`update` call site, not assumed.
- **§7–§8 (BaseEntity, delete semantics)**: Every entity, without exception, extends `BaseEntity` and inherits `BaseRepository.delete`'s hard-delete behavior; `SoftDeleteMixin`'s columns exist everywhere but prevent nothing structurally.
- **§9 (Closest precedents)**: No single entity matches Payslip's anticipated shape. `AttendanceEvent` is closest on FK count and `RESTRICT` convention; `Task`/`Assignment` is closest on "business entity references business entity" shape but uses `CASCADE`; `PayrollRun` is closest on CRUD-scaffold shape but has no FK at all.
- **§10 (Terminology)**: "Payslip" appears nowhere in the repository predating this conversation's own governance work.

---

# Architectural Decisions

## 1. Aggregate Ownership

**Decision: Aggregate Root.**

- Repository Evidence: every persisted entity reviewed across this and prior discoveries (`AttendanceEvent`, `LeaveRequest`, `LeaveBalance`, `OvertimeRequest`, `Timesheet`, `HrEmployee`, `PayrollRun`, and all HR reference data) has exactly one dedicated repository and one dedicated service; none is persisted as a nested/owned collection reachable only through another entity's repository — confirmed without exception, including `AttendanceEvent`, which carries two FKs yet is still fully independent (`discovery.md` §2, §9).
- Logical Consequence: given this uniform pattern, and given `payroll/decision.md` §3's already-established finding that Payslip must be persisted (not computed live), Payslip classifies as an Aggregate Root — its own table, own repository, own service — not a Child Entity nested inside `PayrollRun`'s aggregate boundary.
- **Child Entity** is rejected: no repository precedent anywhere supports an entity persisted only through another entity's repository (§ Rejected Alternatives).
- **Value Object** is rejected: a Value Object (the repository's one example being `LeaveBalance.period_year`, a bare inline field with no independent identity, per `domain-model-discovery.md` A1) has no own identity, own lifecycle, or own reference path — Payslip needs all three (an individually referenceable, employee-facing record), which no Value Object precedent in the repository provides.
- **Projection** is rejected: already rejected in `payroll/decision.md` §3, restated here as repository evidence, not re-argued — the repository's one projection precedent (`AttendanceReconciliationResponse`) is explicitly for low-stakes, recomputable, non-financial data, the opposite of what a payslip is.

## 2. Relationship with PayrollRun

- **Ownership direction**: `Payslip → PayrollRun` (Payslip holds the foreign key). Repository Evidence: this direction is already stated in `payroll/decision.md` §3 ("scoped to one... `PayrollRun`") and §6 (post-correction: "`payroll_run_id` FK referencing `PayrollRun`" is listed as a `Payslip` constraint, not a `PayrollRun` one).
- **Lifecycle dependency**: Logical Consequence, not directly observed (Payslip does not exist yet) — every existing service with a required FK validates the referenced row's existence before allowing creation (e.g., `AttendanceEventService.create` checks `HrEmployeeRepository.exists()`/`ShiftRepository.exists()` before proceeding). By the same uniform pattern, a `PayslipService.create` would need a `PayrollRun` row to already exist before a `Payslip` referencing it could be created.
- **Whether `PayrollRun` may exist without `Payslip`**: **Yes.** Repository Evidence: `PayrollRun` is merged, implemented, and carries no reverse relationship or dependency on `Payslip` of any kind (`models/payroll_run.py` has zero FKs and zero awareness of any other entity).
- **Whether `Payslip` may exist without `PayrollRun`**: **No.** Logical Consequence: since `payroll_run_id` is anticipated as a required FK (not nullable, per the one-to-many relationship already described in `payroll/decision.md` §3), no `Payslip` row could be created without a valid, already-existing `PayrollRun` row to reference — the same existence-dependency every other required-FK entity in the repository already exhibits.

## 3. Employee Ownership

**Decision: `employee_id` belongs to Payslip.**

- Repository Evidence: `payroll/decision.md` §6 (post-correction, already established governance) explicitly states `Payslip` "is the employee-scoped aggregate," carrying `employee_id`; `PayrollRun`'s actual merged model confirms it carries no such field. `discovery.md` §5 independently confirms this would make Payslip the sixth employee-scoped HR aggregate, following the identical `employee_id → hr_employees.id` shape as `AttendanceEvent`, `LeaveRequest`, `LeaveBalance`, `OvertimeRequest`, `Timesheet`.
- This is the most directly and unambiguously evidenced decision in this document — no competing precedent or tension exists anywhere in the reviewed material.

## 4. Mutability

**Decision: Immutable after creation — no `update`, no `delete` method.**

- Repository Evidence (precedent count): every entity in the repository except one (`AuditLog`) is fully mutable — `update`/`delete` exposed, no guard. Counted alone, this evidence favors "mutable," 11-for-12 (`PayrollRun` included).
- Repository Evidence (rationale already on record): `payroll/decision.md` §2–§3 already decided Payslip must be persisted rather than computed live, specifically because "a payslip that could silently change after being issued... is inconsistent with the repository's own named audit-trail concern" (citing `ARCHITECTURE_INVENTORY.md` §8). This reasoning, already established as governance fact prior to this document, is not satisfied by a persisted-but-freely-mutable record — a mutable Payslip could still "silently change after being issued" via an ordinary `update` call, reproducing the exact risk that reasoning was written to avoid.
- Logical Consequence: the precedent-count evidence and the already-recorded rationale point in different directions; this document resolves the tension in favor of the rationale already on record (not invented here) rather than the majority pattern, because the majority pattern's own justification (plain CRUD master/transactional data with no stated audit concern) does not apply to Payslip, whose persistence was justified by an audit concern specifically.
- The only repository precedent for how to achieve this (§1) is `AuditLog`'s convention: the owning service (`PayslipService`) simply does not implement `update`/`delete`, and the API layer exposes no corresponding routes — the same mechanism, not a new one.
- If repository evidence were the only input (ignoring the already-recorded rationale), this would be **insufficient to decide** — stated explicitly, per the governing instruction, because the precedent count alone does not support immutability. This document decides immutability only because a prior, already-established governance document's own stated reasoning requires it, not because immutability is the repository's default behavior anywhere.

## 5. Delete Semantics

- Repository Evidence: `BaseRepository.delete` performs a hard delete (`session.delete()`) and is inherited by every entity, `PayrollRun` included; `SoftDeleteMixin`'s columns exist everywhere but structurally prevent nothing. No database constraint, ORM-level guard, trigger, or permission system anywhere in the repository blocks a call to `.delete()` once a repository exposes it.
- **Does the repository currently support an immutable financial record pattern?** **No, not structurally.** Only a convention-level pattern exists (`AuditLog`'s service simply never calling `.delete()`), and that pattern has never been applied to a financial or business-domain record — only to a generic action log. This document does not invent a stronger mechanism (no trigger, no DB-level block, no permission system) — none exists in the repository to draw on, and inventing one is out of scope.
- **Is delete behavior decidable?** Decidable at the **policy** level only: consistent with § 4, `PayslipService` should not expose a `delete` method, mirroring `AuditLogService` exactly. **Not decidable** at the **enforcement-mechanism** level: whether "the service just doesn't call it" is a sufficient guarantee for a financial record is a compliance/business judgment with no repository evidence bearing on it either way (§ Deferred Decisions).

## 6. Foreign-Key Semantics

- **`Employee → Payslip`** (i.e., `Payslip.employee_id` → `hr_employees.id`): **Decision: `RESTRICT`.** Repository Evidence: uniform, 5-for-5, zero-exception precedent across every existing employee-scoping FK in the HR domain (`LeaveRequest`, `LeaveBalance`, `OvertimeRequest`, `Timesheet`, `AttendanceEvent`). This is directly decidable with no competing precedent.
- **`PayrollRun → Payslip`** (i.e., `Payslip.payroll_run_id` → `payroll_runs.id`): **Decision: `ON DELETE RESTRICT`. Final — no longer Deferred.**

  This document originally found repository evidence insufficient to choose between `RESTRICT` (the HR domain's own uniform convention) and `CASCADE` (the only existing "business aggregate references business aggregate" precedent, `Task.project_id`/`Assignment`, from the Project Tracking domain) — see § Repository Evidence above. Architecture Governance has since made this decision directly. It is recorded here, not re-derived:

  - Payslip is an immutable financial record.
  - Payslip is an Aggregate Root.
  - Financial history must never disappear because `PayrollRun` is deleted.
  - `RESTRICT` preserves historical integrity.
  - `RESTRICT` aligns with the existing HR-domain convention used throughout the repository.
  - `CASCADE` was evaluated and is **rejected**: it permits destruction of immutable financial records, which is incompatible with Payslip's own decided immutability (§4) and with the audit-trail rationale that justified persisting Payslip at all (§4, citing `ARCHITECTURE_INVENTORY.md` §8).

  This decision is final. It does not reopen, revisit, or expand any other topic decided in this document.

## 7. Service Ownership

**Decision: a new, dedicated `PayslipService` — not owned by `PayrollRunService`, `ApprovalService`, or any producer capability's existing service.**

- Repository Evidence: the uniform one-entity-one-service pattern (§1) applies without exception across every reviewed entity, `PayrollRun` included.
- `ApprovalService` is explicitly not a precedent for folding Payslip into another service: its own shape (§ Approval Lifecycle Reuse, `discovery.md` §4) is "reach into another capability's repository to flip a status field on an already-owned entity," not "own another aggregate's full CRUD." `payroll/decision.md` §6 already states Payroll/Payslip "must not... be implemented by extending `ApprovalService`... or any existing producer capability's own service/repository/table" — restated here as repository evidence (an already-established constraint), not re-argued.
- `PayrollRunService` owning `Payslip` is rejected on the same grounds: no repository precedent exists for one service owning two full aggregate roots' persistence.

## 8. Authorization Ownership

**Decision (superseded below): Payslip Authorization cannot be decided today**, recorded at authorship time because `Payslip` itself did not yet exist. Retained unmodified as the historical record; see the Addendum immediately following for the resolved policy.

- Repository Evidence: `payroll-authorization/decision.md` (already-established governance, cited by `payroll/discovery.md` and thus in scope here) found Payroll Authorization blocked because "no Payroll resource exists" — no model, no Service to resolve a concrete `AuthorizationRequest.resource`. `PayrollRun` has since been implemented, but `Payslip` itself does not exist anywhere in the repository (`discovery.md` §10, confirmed by fresh search) — no `PayslipService` exists to resolve a resource, and no `Payslip` row could exist for an evaluator to compare against.
- Logical Consequence: the identical reasoning `payroll-authorization/decision.md` used applies here without modification — Authorization Foundation's own design principle (the calling Service resolves a concrete `resource` before an evaluator interprets it) has no Service to perform that role for Payslip, for the same structural reason it had none for Payroll before `PayrollRun` existed.
- This is not a new finding; it is the same blocking condition, one level further down the same dependency chain, not yet resolved because Payslip itself remains unimplemented.

### Addendum — Resolved: Payslip Authorization is Owner Only

Payroll Iteration 1 (merged, `5d4378d`) implemented `Payslip` (`models/payslip.py`, `PayslipService`, `api/payslips.py`), satisfying the prerequisite this section named as blocking. `payroll-authorization/decision.md`'s own Addendum records the resolved cross-capability policy table; restated here as it applies to Payslip specifically: **Owner Only** — `resource.employee_id == context.employee_context.employee.id` — because `Payslip.employee_id` (§3 above) is a real, persisted FK, the same shape `LeaveRequest`/`AttendanceEvent` already use for their own Owner Only policies. This does not reopen §1–§7 or §9's schema/mutability/FK decisions above; it resolves only the authorization question §8 left open.

## 9. Audit Ownership

**Decision: Neither `AuditMixin` nor `AuditLog` provides sufficient precedent for financial audit.**

- Repository Evidence: `AuditMixin.created_by`/`updated_by` are populated by no reviewed service in the entire repository (`discovery.md` §6, confirmed by direct inspection, not assumed) — the columns exist on every entity but carry no data anywhere today. `AuditLog` is generic (action/entity_type/details), unused by any producer capability (zero callers of `AuditLogService.record()`), and has no employee-scoped or monetary-domain field.
- This document does not propose an alternative audit strategy — none is evidenced, and inventing one is explicitly out of scope. The finding is limited to: the two existing mechanisms are insufficient, stated as absence, not remedied here.

## 10. Deferred Decisions

See dedicated section below.

---

# Rejected Alternatives

- **Child Entity** (Payslip persisted only through `PayrollRun`'s own repository) — rejected; no repository precedent for nested/owned persistence exists anywhere (§1).
- **Value Object** (Payslip as an inline field with no independent identity) — rejected; Payslip requires independent, individually-referenceable identity, unlike the repository's one Value-Object-shaped precedent (`LeaveBalance.period_year`) (§1).
- **Projection** (Payslip recomputed live, not persisted) — rejected; already rejected in `payroll/decision.md` §3 on audit-trail grounds, restated not re-argued (§1).
- **Mutable-by-default**, following the repository's 11-for-12 majority pattern — rejected in favor of immutable-after-creation, because the majority pattern's own justification (ordinary CRUD data with no audit concern) does not hold for a record whose persistence was itself justified by an audit concern (§4).
- **Folding Payslip's CRUD into `PayrollRunService` or `ApprovalService`** — rejected; no precedent exists for one service owning two full aggregates' persistence, and `ApprovalService`'s shape (mutate a status field on an already-owned entity) is categorically different from owning a new aggregate's CRUD (§7).
- **Deciding a Payslip Authorization policy now** — rejected/deferred; no Payslip resource exists for any evaluator to resolve against, identical to why Payroll Authorization was found blocked (§8).
- **Treating `AuditMixin`/`AuditLog` as adequate existing audit infrastructure** — rejected; neither is populated or proven for this purpose anywhere in the repository (§9).
- **Inventing a stronger delete-prevention mechanism** (a DB trigger, a permission system, a hard immutability constraint) — rejected as out of scope; no such mechanism exists anywhere in the repository to draw on, and this document does not invent one (§5).
- **`ON DELETE CASCADE` for `Payslip.payroll_run_id`** — evaluated and rejected by Architecture Governance (§6): `CASCADE` permits destruction of immutable financial records, incompatible with Payslip's own decided immutability (§4) and with the audit-trail rationale that justified persisting Payslip at all. `RESTRICT` was selected instead, aligning with the existing HR-domain convention (§6).

---

# Deferred Decisions

Cannot yet be made because repository evidence is insufficient, or because they are explicitly out of this document's scope:

- **Compensation/rate data source** — inherited, unresolved from `payroll/decision.md` §7; no field or entity anywhere provides one.
- **Pay-period cadence** — inherited, unresolved from `payroll/decision.md` §7 and `TIMESHEET_DESIGN.md` §3.
- **Whether the convention-level immutability decided in §4/§5 (service simply omits `update`/`delete`) is sufficient for actual financial/compliance requirements** — a business/legal judgment with no repository evidence bearing on it either way.
- **Payslip's exact schema, fields, API shape, and migration** — explicitly out of this document's scope by instruction; belongs to a future `implementation-plan.md`.
- **Whether Payslip is generated synchronously with `PayrollRun` or as a separate downstream step** — inherited, unresolved from `payroll/decision.md` §3.
- **Payslip Authorization policy** — blocked pending Payslip's own implementation existing (§8), mirroring Payroll Authorization's own still-unresolved block.
- **Batch/period computation mechanism** — inherited, unresolved from `payroll/decision.md` §7 and `domain-model-discovery.md` A3.

---

# Open Questions

- Whether the convention-level immutability pattern this document decides on (§4, matching `AuditLog`) is considered adequate by whoever eventually needs to trust a payslip's figures, or whether a stronger mechanism will later be required — no repository evidence exists to answer this either way, and none is invented here.
- Whether `AuditMixin`'s repository-wide non-population (§9) is itself a gap that should be addressed platform-wide before or alongside Payslip, given Payslip is the first entity in the repository whose own governance rationale (audit-trail concern) directly depends on some form of audit trail existing.

---

# Recommendation

```
implementation-plan.md may begin, scoped to structural CRUD-minus-mutation
scaffolding (create/get/list/list_paginated only — no update, no delete,
per §4/§5), matching PayrollRun's own precedent-following approach.

Another full Discovery is NOT required: no unresolved question in this
document stems from missing evidence that further searching could supply.

The PayrollRun -> Payslip foreign key's ON DELETE policy (§6), previously
the one open item in this document, has been resolved by a direct
Architecture Governance decision: RESTRICT. It is no longer an escalation
point and may be implemented directly.

Payslip Authorization, compensation computation, and any business logic
remain explicitly out of scope for that plan, per §8 and the deferred
decisions above.
```

---

# References

- `docs/architecture/capabilities/payslip/discovery.md`
- `docs/architecture/capabilities/payroll/decision.md`, `domain-model-discovery.md`, `discovery.md`, `implementation-plan.md`, `architecture-review.md`
- `docs/architecture/capabilities/payroll-authorization/decision.md` (precedent for §8's authorization-blocked finding)
- `docs/architecture/capabilities/attendance-authorization/decision.md` (precedent for reserving a name / deciding a boundary without implementing code)
- `docs/architecture/10-reference/ARCHITECTURE_INVENTORY.md` §8 (Business Audit gap, cited in §4)
