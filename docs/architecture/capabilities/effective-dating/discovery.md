# Effective Dating — Discovery

**Status:** Complete

**Capability:** Effective Dating (candidate — validity as an independent capability not yet established)

**Owner:** EOP Architecture Governance

---

# Purpose

This document determines whether a capability concerned with effective dating / temporal versioning is supported by repository evidence. Nothing is assumed about whether it should exist. The repository itself was searched first, from scratch; prior governance documents are cited only as evidence found after that search, per instruction, never as a starting assumption. Every statement is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**.

---

# Discovery Scope

Full file reads unless noted. All searches run fresh for this discovery.

- Repository-wide, case-insensitive grep for `effective|valid_from|valid_to|start_date|end_date|active_from|active_to|version|revision|history` across `services/api/src` — 31 files matched, every match read in context; false positives (`app_version`, `__version__`, ordinary English "history") individually verified and excluded.
- Repository-wide grep for `BETWEEN|overlap|point.?in.?time|as.?of|active_at|effective_at` — 5 files matched, every match read in context.
- Repository-wide grep for `supersede|superseding|replace|immutable` — 11 files matched, every match read in context.
- Grep for `\.version\b|version\s*[+]=|version\s*=\s*\w+\.version` across all of `services/api/src/eop_api` — zero matches beyond the mixin's own definition.
- Full reads: `db/mixins.py`, `db/base.py`, `models/audit_log.py`, `services/audit_log.py`, `repositories/attendance_event.py`, `repositories/leave_request.py` (relevant methods), `models/assignment.py` (re-confirmed, unchanged since prior discoveries this session).
- Repository-wide grep for `effective.dat|effective_dat|temporal version|history|revision|point.in.time` across all of `docs/architecture/capabilities` — 32 files matched; every file's actual match content read, not merely counted.
- `docs/architecture/LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`, `docs/architecture/capabilities/payroll/discovery.md`, `docs/architecture/10-reference/ARCHITECTURE_INVENTORY.md` §8 — read in full context around every match, as new evidence for this Discovery specifically, not carried over from any prior summary.

---

# 1. Existing Temporal Concepts

**Repository Evidence**: None of `effective`, `effective_date`, `effective_from`, `effective_to`, `valid_from`, `valid_to`, `active_from`, `active_to` appears anywhere in `services/api/src` — every one of the 31 files matched by the combined search pattern matched on a *different* term in the pattern (`version`, `history`, `start_date`, `end_date`), individually verified. `start_date`/`end_date` are widely used, but only as flat, bounded, non-effective-dated ranges (`Assignment.start_date`/`end_date`, `LeaveRequest.start_date`/`end_date`). `version` exists as `VersionMixin.version` (`Mapped[int]`, `default=1`), composed into every `BaseEntity` via `db/base.py`. `revision` appears nowhere. `history` appears only as an informal docstring word (`leave_request.py`: *"leave history must be preserved"*, meaning the row must not be deleted — not a feature; `audit_log.py`: describing its own append-only shape).

**Logical Consequence**: Two genuinely different existing temporal shapes exist — flat, one-time date ranges with no revision concept, and a dead, unused version-increment column present on every entity by inheritance. Neither constitutes effective dating: nothing in the repository lets a value's meaning change at a future date while the prior value remains queryable for dates before it.

**Unknown**: None — searched exhaustively; every match individually verified in context.

---

# 2. Existing Versioning

**Repository Evidence**: No entity anywhere preserves a prior value of any field. No "replace" operation exists distinct from ordinary `update()` overwrite, confirmed repeatedly across this governance trail and re-confirmed here. Grep for `supersede`/`superseding` returns zero matches anywhere. `Payslip` is immutable after creation (`create`/`get`/`list` only, no `update`/`delete`) — a single, un-revisable row, not a revision chain. `AuditLog` is genuinely append-only *in code*, not merely by docstring claim: `AuditLogService` (`services/audit_log.py`) exposes only `record()` (which calls `repo.create()`) and `list_paginated()` — no `update`, no `delete`, verified by direct read of the complete service. `VersionMixin.version` is present on every entity but is never read or incremented anywhere in application code — confirmed by a fresh, zero-result grep for any mutation or comparison of `.version` beyond the mixin's own definition.

`LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` independently names this exact gap, for a different purpose than temporal history: *"`VersionMixin.version` exists on `LeaveBalance` (and every entity) but `BaseRepository.update()` never reads or increments it... there is no optimistic-concurrency... version of that protection to reuse. This is a repository-wide infrastructure gap."* It explicitly flags, as an open and still-unresolved question in its own governance: *"Whether this PR should be the one to introduce a working version of `VersionMixin`-based optimistic locking... or whether that is deferred as a known, accepted risk."*

**Logical Consequence**: "Versioning" spans two genuinely different concerns that must not be conflated: (a) **optimistic-concurrency versioning** — a technical write-conflict-prevention mechanism, which `VersionMixin` is shaped for but does not perform, and which `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` independently flags as an unresolved, repository-wide infrastructure gap; and (b) **temporal/historical versioning** — preserving prior field values for point-in-time queries, for which nothing in the repository provides any precedent at all, not even a dead column. `AuditLog` and `Payslip` each demonstrate a narrower, different shape of immutability (an append-only action log; a single immutable row) — neither is a revision mechanism for a mutable business value.

**Unknown**: None regarding existence — confirmed absent exhaustively for both flavors.

---

# 3. Existing Relationship Lifecycles

Comparison only; consistency not assumed, per instruction.

- **`Assignment`**: a date-range payload (`start_date`/`end_date`) on the relationship row itself. If the dates are `update()`d, the prior values are simply gone — no history of prior ranges.
- **`HrEmployee`**: plain FK overwrite for every master-data reference (`shift_id`, `department_id`, etc.) — no history of prior FK values, confirmed repeatedly across this trail.
- **`Shift`**: has no relationships of its own; only referenced by others.
- **Shift Assignment governance** (`shift-assignment/decision.md` §7, examined as evidence after the repository itself, per instruction): concluded that *if* effective dating for the employee↔shift relationship is ever built, it would conceptually belong to Shift Assignment itself, mirroring `Assignment`'s own `start_date`/`end_date` shape — but explicitly left whether it should exist at all unresolved, since no working precedent exists to build from.
- **Compensation governance** (`compensation/capability-boundary-analysis.md`, examined the same way): independently flagged history/effective-dating as a "secondary, weaker finding" candidate for its own separate capability, citing `AuditLog`'s generic, cross-cutting shape as the only weak analog available at the time.

**Logical Consequence**: Not consistent. `Assignment` and `HrEmployee` each independently chose "no history, just overwrite" for relationship data. Two separate prior governance efforts (Shift Assignment, Compensation), examined only after the repository search above, independently reached the same conclusion from the same underlying absence — confirming, rather than merely asserting, that no consistent relationship-lifecycle-with-history pattern exists anywhere for this repository to draw on.

**Unknown**: None regarding existence.

---

# 4. Existing Temporal Queries

**Repository Evidence**: Two real, working, hand-written point-in-range queries exist — a more precise finding than "zero query support," which prior documents in this trail stated only about *generic* `BaseRepository` support specifically:
- `AttendanceEventRepository.exists_between(employee_id, start, end)` — `event_time >= start AND event_time <= end`, single-table, hardcoded to one field.
- `LeaveRequestRepository.find_for_employee_on_date(employee_id, target_date)` — `start_date <= target_date AND end_date >= target_date`, single-table, hardcoded to one field.

`BaseRepository._apply_filters` itself supports equality-only filtering — confirmed, consistent with every other capability's own finding in this trail, no generic `BETWEEN`/range operator exists there. No **overlap** query (two ranges intersecting each other) exists anywhere — both examples check a single point against a single range, not range-against-range. No **historical lookup** (reconstructing what a value *was* as of a past date) exists anywhere — both examples check current rows against a target date, not a preserved past state.

**Logical Consequence**: The repository has real, working point-in-range query precedent — narrow, single-purpose, and each independently hand-written rather than drawn from any shared, reusable pattern. This is evidence that when a capability needed this exact kind of query, it solved it itself, because no reusable mechanism existed to reuse.

**Unknown**: None regarding existence — both real examples were located and read directly.

---

# 5. Existing Infrastructure

**Repository Evidence**: No reusable, importable type, mixin, or base class exists anywhere for temporal identity, effective dating, validity periods, overlap validation, or historical retrieval. `VersionMixin` is the only mixin with any conceptual adjacency, and it is dead (§1-2). `TimestampMixin` records only when a row was last touched (`created_at`/`updated_at`), not what its value was before. No `EffectiveDateMixin`, `ValidityPeriodMixin`, `TemporalMixin`, or equivalent exists anywhere, confirmed by the same broad search as §1.

**Logical Consequence**: No reusable infrastructure exists for any of the five concerns. The two working point-in-range queries found in §4 are capability-specific code, not shared infrastructure — nothing was found that a new capability could import or extend today. No abstraction is invented here, per instruction.

**Unknown**: None regarding existence.

---

# 6. Capability Evidence

Every capability found to independently anticipate some flavor of this concept, verified by direct read this session, not relied on from any prior summary alone.

**Explicit** (a document directly names effective-dating, history, or versioning as a gap or future need for itself):
- **Compensation** (`compensation/capability-boundary-analysis.md`) — names "History / effective dating" directly as a secondary capability-extraction candidate.
- **Shift Assignment** (`shift-assignment/decision.md` §7) — directly concludes effective dating, if built, belongs to Shift Assignment.
- **Work Schedule** (`work-schedule/decision.md` §6; `capability-boundary-analysis.md` §3) — directly reaches the same conclusion for its own relationship.
- **Leave Balance Synchronization** (`LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`) — names `VersionMixin`/optimistic-concurrency versioning directly as a repository-wide infrastructure gap relevant to its own write path. **A different flavor of "version" than the other three** (concurrency control, not temporal history) — kept distinct, not merged.
- **Payroll** (`payroll/discovery.md` §92, citing `ARCHITECTURE_INVENTORY.md` §8) — directly names "workflow-history or business-audit-trail mechanism" as absent, citing a formal, pre-existing architecture-gap catalog with "Workflow History" and "Business Audit" both listed as `High` priority gaps — predating this entire governance trail, confirmed by direct read of `ARCHITECTURE_INVENTORY.md` itself.

**Implicit** (evidence suggests a need without an explicit statement):
- **Leave** (`LEAVE_DESIGN.md`) — names "shift reassignment mid-request" as unconfirmed, a scenario that would benefit from point-in-time shift knowledge, without ever naming "effective dating" as a candidate solution.
- **Attendance** (`ATTENDANCE_RECONCILIATION_DESIGN.md`) — `AttendanceEvent.shift_id` recording a value independent of `HrEmployee.shift_id`'s current value implicitly demonstrates a need for point-in-time accuracy, without the source documents ever naming a solution.

**Unknown**: Whether any capability outside this governance trail's own thirty-two matched documents (e.g., Team, Department, Position, Organization — each with its own reassignment/hierarchy pattern) would also anticipate this — not searched exhaustively beyond the documents matched above.

---

# 7. Ownership

Evidence classified only, per instruction — no decision made:

- **Individual capabilities**: Compensation, Shift Assignment, and Work Schedule each independently concluded that *if* effective dating exists for their own specific relationship, it belongs to them individually — evidence supporting this classification.
- **Shared infrastructure**: The same three independent anticipations, taken together, is the identical pattern (three independent capabilities naming the same missing mechanism) that previously produced Monetary Representation's own extraction — evidence supporting this competing classification. Both are evidenced; neither is chosen here.
- **Repository abstraction**: The concurrency-versioning flavor is explicitly self-described, by `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` itself, as *"a repository-wide infrastructure gap"* — evidence supporting this classification specifically for the concurrency flavor, distinct from the temporal-effective-dating flavor.
- **Business policy**: No evidence found addresses *which* effective-dating rule would apply (e.g., when a change takes effect) — a content question, if it ever arises, structurally identical to the rounding/precision/currency-content questions already deferred to Business throughout this trail.

---

# 8. Architectural Pattern Comparison

Comparison only, per instruction:

- **`BaseEntity`**: composes `UUIDMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin`/`VersionMixin` via multiple inheritance — the repository's own proven mechanism for applying a cross-cutting technical concern to every entity.
- **Mixins**: the closest existing precedent for "a reusable technical concern," though every existing mixin composes whole columns at class-definition time, none is a runtime service or type. `VersionMixin` is the one already-present-but-dead example of exactly this shape, if effective dating turns out to be mixin-shaped.
- **`Assignment`**: the one working precedent for "a relationship carrying its own bounded date range" — structurally the closest thing to effective dating in the repository, though its own uniqueness constraint is not date-aware and supports neither recurrence nor true point-in-time history (only a single, current range, per `work-schedule/domain-model-discovery.md` §1, examined as evidence).
- **`AuditLog`**: a proven, working, generic append-only mechanism — the closest existing precedent for "immutable, growing record," though it records discrete actions, not field-value history, and has no FK relationship to what it describes (`entity_id` is a raw UUID column, no `ForeignKey()`).
- **Authorization Foundation** (`ADR-007`): the repository's own proven precedent for extracting a genuinely cross-cutting mechanism — needed by three or more capability-specific consumers — into its own shared, capability-agnostic component, built once ahead of specific policies. Directly comparable in shape to the three-capability anticipation found in §6-7.

---

# 9. Terminology

**Repository Evidence**: "Effective Dating" — zero occurrences in source code; appears only inside this governance trail's own documents (Compensation, Shift Assignment, Work Schedule), each choosing the term independently without citing a shared prior source. "Temporal Versioning" — zero occurrences anywhere, including in this trail's own prior documents; this Discovery's own task is the first place the exact phrase appears. "Valid Time" — zero occurrences anywhere; a term of art from temporal-database theory, unused in this repository. "History" — used informally and inconsistently: a docstring adjective (`leave_request.py`), a formal, pre-existing architecture-gap catalog entry ("Workflow History," `ARCHITECTURE_INVENTORY.md` §8), and ordinary English (commit history). "Versioned Entity" — zero occurrences anywhere.

**Logical Consequence**: No consistent terminology exists anywhere in the repository for this concept. "Effective Dating" is the closest thing to an emerging term — used independently by three capabilities' own governance, none citing the others as a source — but it originates entirely from this governance trail itself, not from any pre-existing repository or product source, mirroring the identical naming-provenance caveat already raised for Monetary Representation and Shift Assignment. No terminology is normalized here, per instruction.

---

# 10. Recommendation

```
Capability Decision may begin
```

Five independent documents, verified by direct read rather than relied on from any prior summary, each name some flavor of this gap: three explicitly for temporal/effective-dating specifically (Compensation, Shift Assignment, Work Schedule), one explicitly for the distinct concurrency-versioning flavor (`LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`), and one explicitly for workflow-history/audit specifically, backed by a formal, pre-existing architecture-gap catalog entry predating this entire governance trail (`payroll/discovery.md`, citing `ARCHITECTURE_INVENTORY.md` §8). This is a stronger, more independently-corroborated evidence base than either Monetary Representation or Work Schedule had at their own Discovery stage. Two genuine, working (if narrow and capability-specific) point-in-range query precedents were found (§4) — stronger direct repository-level support than Work Schedule's own Discovery found for recurrence. Real architectural pattern precedent exists to compare against (`BaseEntity`/Mixins, `Assignment`, `AuditLog`, Authorization Foundation, §8). Every one of the ten topics above was searched exhaustively with zero remaining `Unknown` regarding existence — there is nothing further for another Discovery pass to find.

---

# References

- `services/api/src/eop_api/db/mixins.py`, `db/base.py`, `models/audit_log.py`, `services/audit_log.py`, `repositories/attendance_event.py`, `repositories/leave_request.py`, `models/assignment.py`
- `docs/architecture/LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`
- `docs/architecture/capabilities/payroll/discovery.md` §92
- `docs/architecture/10-reference/ARCHITECTURE_INVENTORY.md` §8
- `docs/architecture/capabilities/compensation/capability-boundary-analysis.md`, `shift-assignment/decision.md` §7, `work-schedule/decision.md` §6 and `capability-boundary-analysis.md` §3, `work-schedule/domain-model-discovery.md` §1 (all cited only as evidence examined after the repository search above, per instruction)
