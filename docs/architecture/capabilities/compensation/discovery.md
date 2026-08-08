# Compensation — Discovery

**Status:** Complete

**Capability:** Compensation (distinct from Payroll, Payslip, Payroll Calculation, Payroll Authorization)

**Owner:** EOP Architecture Governance

---

# Purpose

This document records repository evidence for a Compensation capability — the capability `payroll-calculation/architecture-gap-analysis.md` §1/§8 identified as the most fundamental missing prerequisite for Payroll Calculation ("no capability, complete or incomplete, owns compensation/rate data"). Per `AI_DISCOVERY_GUIDE.md`, this document is observational only: it reports what exists, what is absent, and what cannot be determined. It does not define architecture, does not choose a schema, and does not select a policy. Every statement is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**.

---

# Discovery Scope

Full file reads unless noted. All searches run fresh for this discovery, across `services/api/src`, `services/api/tests`, `services/api/alembic`, `docs/architecture`, and `docs/product`, per the governing instruction — not reused from prior turns where the two result sets might diverge.

- Repository-wide, case-insensitive grep for `compensation|salary|wage|pay rate|hourly rate|monthly salary|annual salary|allowance|benefit|deduction|gross|net pay|payroll|remuneration|income` across `services/api/src` (20 files matched) and `services/api/tests` (6 files matched) — every match read in context.
- Same term set against `services/api/alembic` — 2 files matched, both migration filenames only (`create_payslips_table`, `create_payroll_runs_table`), no content match.
- Repository-wide grep for `Decimal|Numeric|MONEY|Float|currency` across the entire `services/api` tree (not only `src`, broader than prior discoveries) — zero matches.
- Repository-wide grep for `effective_from|effective_to|valid_from|valid_to|versioning|history` across `services/api/src` — 6 files matched, every match read in context.
- Filename search for `*history*`, `*compensation*`, `*salary*`, `*pay*` under `services/api/src/eop_api/models` — only `payroll_run.py`/`payslip.py` matched (on "pay" as a substring); no `*History`, `*Compensation`, or `*Salary` model file exists.
- `models/hr_employee.py`, `models/job_grade.py` — re-read in full for this discovery, not assumed from memory.
- Repository-wide, case-insensitive grep for `compensation|salary|payroll|remuneration` across all of `docs/` — 34 files matched, all previously catalogued by this conversation's own prior Payroll/Payslip/Payroll Calculation discoveries; no new document found.
- Separate grep for `remuneration|wage` alone — 3 files matched, all likewise already known.
- Full directory listing of `docs/product/` (six files: `01_VISION.md` through `06_PRODUCT_ROADMAP.md`) — `06_PRODUCT_ROADMAP.md` specifically confirmed to contain **zero** matches for any compensation-family term, consistent with `TIMESHEET_DESIGN.md`'s own prior finding that "Timesheet"/"Payroll" appear nowhere in it.
- `docs/architecture/capabilities/payroll-calculation/*.md` (four documents), `payroll/*.md` (five documents), `payslip/*.md` (four documents), `payroll-authorization/*.md` (two documents) — this conversation's own prior output, re-consulted as evidence of what is already established, not re-derived.

---

# 1. Existing Compensation-Related Concepts

**Repository Evidence**: Every one of the 20 matching files under `services/api/src` and 6 under `services/api/tests` falls into one of these categories, confirmed by direct read:

- **This conversation's own merged code** (`payroll_run.py`, `payslip.py`, their services/schemas/APIs/tests, `main.py`, `models/__init__.py`) — matched only because "Payroll"/"Payslip" contain "pay" as a substring; neither carries any compensation field (§4, re-confirmed).
- **Docstring "out of scope" disclaimers** in already-implemented, non-Payroll modules (`attendance_event.py`, `timesheet.py`, `overtime_request.py`, `leave_balance.py`, `approval.py`) — each explicitly states payroll-adjacent computation is not its own responsibility, already catalogued in `payroll/discovery.md` §1 and `payroll-calculation/discovery.md` §2.

**No monetary model exists anywhere in the repository.** No field named or shaped like `compensation`, `salary`, `wage`, `pay_rate`, `hourly_rate`, `allowance`, `benefit`, `gross`, `net_pay`, or `income` exists on any model reviewed across this entire conversation.

**Logical Consequence**: This finding is unchanged from every prior discovery in this conversation (`payroll/discovery.md` §3, `payroll-calculation/discovery.md` §2) — re-confirmed independently here, not merely re-cited, using a fresh search scoped exactly to this discovery's own instruction.

**Unknown**: None — the absence is total and was searched for specifically.

---

# 2. Employee Ownership

**Repository Evidence**: `HrEmployee` (`models/hr_employee.py`, re-read in full for this discovery) carries: `employee_number`, `first_name`, `last_name`, `full_name`, `email`, `phone`, ten foreign keys (`organization_id`, `department_id`, `position_id`, `team_id`, `location_id`, `manager_id`, `job_grade_id`, `employment_type_id`, `employment_status_id`, `shift_id`, `user_id`), `hire_date`, `employment_status` (string), `notes`. No field represents salary, grade-based pay, a pay rate, compensation history, or an effective-dating concept of any kind.

**`HrEmployee` does not own salary, grade-based pay, pay rate, compensation history, or effective dating. Stated explicitly, per instruction: none of these five concepts is present anywhere on this entity or on any related HR aggregate reviewed in this or prior discoveries.**

**Logical Consequence**: `HrEmployee` is the only entity in the repository that could plausibly carry a per-employee compensation reference (it is the sole subject of every other HR-domain entity's `employee_id` FK) — its complete absence of any compensation-adjacent field means no existing entity anywhere carries one, by extension.

**Unknown**: None — this was directly inspected, not inferred from silence.

---

# 3. `JobGrade` Relationship

**Repository Evidence**: `JobGrade` (`models/job_grade.py`, re-read in full) carries exactly four fields: `code` (`String(50)`, unique), `name` (`String(255)`, indexed), `level` (`Integer`), `description` (`String(1000)`, nullable). Its own docstring: *"Global HR master data ranking positions by seniority/pay grade... Deliberately independent of Organization, Department, Team, and Position -- it has no hierarchy, no parent, and is not scoped to any of them."*

**`JobGrade` carries no salary band, pay band, min/max salary, or compensation reference of any kind. It is purely an organizational/seniority ranking** — `level` is a bare `Integer` with no monetary meaning anywhere in the codebase; no code path reads `level` to derive or bound a pay figure.

**Logical Consequence**: The phrase "pay grade" in `JobGrade`'s own docstring is descriptive language about rank ordering (the common HR term for a seniority tier), not evidence of a modeled compensation reference — no field backs it. This is consistent with `payroll/discovery.md`'s and `payroll-calculation/discovery.md`'s prior findings on this same point, re-confirmed here by direct re-read rather than citation.

**Unknown**: None.

---

# 4. Existing Monetary Types

**Repository Evidence**: Repository-wide grep for `Decimal|Numeric|MONEY|Float|currency` across the entire `services/api` tree (source, tests, alembic, and configuration — broader scope than any prior discovery's equivalent search) returns **zero matches**.

**The platform has no monetary representation of any kind.** Every numeric field reviewed across every capability in this and prior discoveries (`LeaveBalance.allocated_days`/`used_days`/`remaining_days`, `JobGrade.level`) is a plain `Integer`. No fractional-precision or currency-precision type has ever been used in this codebase, for any purpose — not a partial or analogous precedent, a complete absence.

**Logical Consequence**: A Compensation capability would be the first consumer in this codebase's history to need a fractional/monetary-precision type. There is no existing convention (e.g., "money is always `Numeric(12,2)`," or "money is stored as integer cents") to follow — none has ever been established.

**Unknown**: None — the absence is unambiguous and was the specific target of this search.

---

# 5. Effective Dating

**Repository Evidence**: Repository-wide grep for `effective_from|effective_to|valid_from|valid_to|versioning|history` across `services/api/src` returns 6 files. Read in context, every match is one of:

- **`leave_request.py`**: *"HrEmployee from HR data: leave history must be preserved, not silently cascaded away"* — describing `ON DELETE RESTRICT` retention policy (rows are not deleted), not a history/versioning table.
- **`approval.py`**: *"Decision history, audit logging, and event/notification dispatch remain explicitly out of scope"* — an explicit disclaimer that no history mechanism is implemented.
- **`timesheet.py`, `overtime_request.py`, `leave_balance.py`, `attendance_event.py`**: identical "out of scope" language pattern for payroll-adjacent history/reconciliation, already catalogued in prior discoveries.

Filename search for `*History*` under `services/api/src/eop_api/models` returns zero matches — no dedicated history/audit-trail table exists for any HR-domain entity (the one exception, `AuditLog`, is a generic action log unrelated to any entity's field-level history, already catalogued in `payslip/discovery.md` §1/§6 and `payroll/domain-model-discovery.md` E4).

**No capability anywhere in the repository already models historical business values.** No entity carries `effective_from`/`effective_to`/`valid_from`/`valid_to`. `AuditMixin`'s `created_by`/`updated_by` columns exist on every entity but are populated by no reviewed service anywhere (`payslip/discovery.md` §6, re-confirmed not re-derived here). `VersionMixin.version` exists on every entity but is never read, compared, or incremented anywhere (`payroll/domain-model-discovery.md` E4).

**Logical Consequence**: A Compensation capability requiring effective-dated values (e.g., "this employee's rate as of a given date") would have no existing repository mechanism to build on — not a partial one, none at all.

**Unknown**: None — this was searched for specifically and independently confirmed absent, not assumed.

---

# 6. Ownership Analysis

Based only on repository ownership patterns already established (uniform one-entity-one-service pattern, confirmed without exception across every entity reviewed in this conversation):

**Repository Evidence**: No existing service owns compensation amount, compensation history, or effective dates, because no entity representing any of them exists (§1-5). The only entities structurally adjacent to where such data might attach are `HrEmployee` (the subject) and `JobGrade` (the seniority classification) — both already owned by `HrEmployeeService`/`JobGradeService` respectively, neither carrying any compensation field today.

**Logical Consequence**: Following the repository's own uniform pattern (every reviewed entity, including two-FK entities like `AttendanceEvent`, is its own independent Aggregate Root with its own dedicated service — no entity is persisted as a nested/owned collection through another entity's repository, `payroll/domain-model-discovery.md` A1), a Compensation capability's data would most likely be owned by its own dedicated service, structurally independent of `HrEmployeeService`/`JobGradeService`, referencing `HrEmployee` by FK the same way every other employee-scoped entity does (`AttendanceEvent`, `LeaveRequest`, `LeaveBalance`, `OvertimeRequest`, `Timesheet`, and now `Payslip`). This is an inference from an established repository-wide pattern, not an architecture decision.

**Unknown**: Whether compensation amount and compensation history would be one entity or two (a current-value field vs. a separate historical-record entity) is not decidable from repository evidence — no existing entity in the repository combines "current value" and "historical record" in either a single-entity or two-entity shape, since no history-of-a-value mechanism exists anywhere (§5).

---

# 7. Dependency Analysis

**Current repository consumers**: **None.** No capability anywhere in the merged codebase calls, references, or depends on any compensation concept, because none exists.

**Future documented consumers**: Every design/discovery document reviewed across this conversation that mentions Payroll names it as a future consumer of *other* capabilities' data (`ATTENDANCE_DESIGN.md` §9, `LEAVE_DESIGN.md` §10, `TIMESHEET_DESIGN.md` §11, `ATTENDANCE_RECONCILIATION_DESIGN.md` §10, `LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md` §10, `APPROVAL_WORKFLOW_DESIGN.md` §12) — none of these documents name "Compensation" specifically as a capability, since the term does not appear anywhere predating this conversation (§9). Within this conversation's own governance trail: `payroll-calculation/architecture-gap-analysis.md` §1 names a compensation/rate-bearing capability as Payroll Calculation's own primary missing prerequisite — this is the only document establishing a forward relationship, and it is prose-level (a named dependency in a governance document), not an observed code dependency, since neither Compensation nor Payroll Calculation exists in code.

**Logical Consequence**: If built, Compensation would sit upstream of Payroll Calculation (per `payroll-calculation/architecture-gap-analysis.md` §1/§8's own framing), the same documented-but-not-yet-coded relationship every other Payroll-adjacent capability already has to Payroll generally.

**Unknown**: Whether `Payslip` or `PayrollRun` would consume Compensation data directly, or only through Payroll Calculation as an intermediary, is not addressed anywhere — no document specifies this.

---

# 8. Architectural Patterns

Repository evidence only, gathered for comparison — no pattern selected here, per instruction.

| Pattern | Repository Precedent | Shape |
|---|---|---|
| HR master data | `JobGrade`, `Shift`, `Holiday`, `EmploymentType`, `EmploymentStatus` | Zero FK, `code`/`name`/`description`, plain CRUD, no employee scoping |
| Transactional entity | `LeaveRequest`, `OvertimeRequest`, `Timesheet`, `AttendanceEvent` | `employee_id` FK (`RESTRICT`), date/time fields, `pending → approved/rejected` lifecycle (except `AttendanceEvent`, which has no status) |
| History/immutable entity | `AuditLog` (generic, unused, non-employee-scoped); `Payslip` (employee-scoped, immutable after creation, no history-of-changes concept — a single fixed record, not a value-over-time series) | Append-only by service-layer convention only; no structural (DB-level) enforcement anywhere (§5) |
| Versioned entity | **No repository precedent exists** | `VersionMixin.version` is present on every entity but unenforced everywhere (§5); no entity has ever needed to represent "this value, superseded by that value, as of a date" |

**Logical Consequence**: Three of the four patterns instructed to be considered (HR master data, transactional entity, history entity) have at least one real repository precedent to compare against; the fourth (versioned entity) has none at all. Whichever shape Compensation takes, if it requires representing a value that changes over time with historical retention, it would be building a genuinely new pattern for this repository, not following an established one.

**Unknown**: Which of the three precedented patterns (or some combination) fits Compensation is not decided here, per instruction — this is architecture selection, not discovery.

---

# 9. Governance Review

**Repository Evidence**: 34 documents under `docs/` mention `compensation|salary|payroll|remuneration`; all 34 were already authored within, or catalogued by, this conversation's own prior Payroll/Payslip/Payroll Calculation discoveries. No governance document predating this conversation names "Compensation" as a capability.

**Inconsistencies recorded, not resolved** (restated from prior discoveries where already found, plus one new observation specific to this search):

- `MASTER_ARCHITECTURE_ROADMAP.md` names "Payroll" (`Planned`); `CAPABILITY_DEPENDENCY_GRAPH.md` separately names "Payroll Integration" in a differently-rooted dependency chain — already recorded in `payroll/discovery.md` §7-8, unresolved, restated here as still true.
- `docs/product/02_PRODUCT_SCOPE.md` lists "Payroll Processing" under out-of-scope "HRIS" systems, with a stated integration exception — a different framing from the in-repo, `Planned` "Payroll" roadmap entry — already recorded in `payroll/discovery.md` §7, restated here as still true.
- **New observation for this discovery**: no governance document anywhere — including the roadmap, the dependency graph, and the product scope document — names "Compensation" as its own capability or line item, despite `payroll-calculation/architecture-gap-analysis.md` (this conversation's own document) identifying it as the most fundamental missing prerequisite for Payroll Calculation. The only place "Compensation" is named as a capability at all is this conversation's own governance trail (`payroll-calculation/architecture-gap-analysis.md` §1, §8), not any pre-existing roadmap or catalog document.

---

# 10. Unknowns

Questions repository evidence cannot answer. Not speculated on:

- Whether compensation is modeled as a fixed value on `HrEmployee`, a separate one-to-one entity, or a one-to-many historical entity — no repository precedent for any of the three exists (§6, §8).
- Whether compensation would be effective-dated at all, and if so, using what mechanism — no effective-dating mechanism exists anywhere in the repository to draw on (§5).
- What monetary/precision type would be used — no monetary type has ever been used in this codebase (§4).
- Whether `Compensation` and `JobGrade` would be related (e.g., a compensation *band* per grade) or entirely independent (a compensation value per employee, unrelated to grade) — `JobGrade` carries no compensation reference today, and no document proposes linking them (§3).
- Whether `Compensation` would be consumed by `Payroll Calculation` directly, by `PayrollRun`/`Payslip` directly, or by some other intermediary — no document specifies the consumption path (§7).
- Whether currency/multi-currency support is required — no repository evidence addresses this at all.
- Whether "Compensation" is the correct or final name for this capability, given no pre-existing governance document uses the term (§9) — the name originates entirely from this conversation's own `payroll-calculation/architecture-gap-analysis.md`.

---

# Recommended Next Step

```
Compensation Capability Decision
```
