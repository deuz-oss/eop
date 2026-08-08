# Work Schedule — Discovery

**Status:** Complete

**Capability:** Work Schedule (candidate — validity as an independent capability not yet established)

**Owner:** EOP Architecture Governance

---

# Purpose

This document determines whether Work Schedule is an independent architectural capability, using repository evidence only. It is explicitly distinct from Shift, Shift Assignment, Attendance, Leave, Payroll, and Roster — nothing is assumed about what "Work Schedule" means; everything below is derived from a fresh read of repository source. Every statement is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**.

---

# Discovery Scope

Full file reads unless noted. All searches run fresh for this discovery.

- Repository-wide, case-insensitive grep for `schedule|calendar|working.?day|work.?pattern|recurring|recurrence|weekday|weekly|monthly|rotation|roster|timetable` across `services/api/src` — 4 files matched, every match read in context.
- Full read of `models/holiday.py`.
- Repository-wide, case-insensitive grep for `schedule|calendar|roster|rotation|recurring|recurrence` across all of `docs/architecture` — 22 files matched, every match read in context.
- Grep for `DayOfWeek|day_of_week|expected_hours|scheduled_hours|expected_shift` across `services/api/src` — zero matches.
- Grep for `Work Schedule|WorkSchedule|work_schedule` across `docs/architecture/capabilities` and all of `docs/` — zero matches.
- Grep for `schedule|calendar|roster` across every authorization-related service file — zero matches.
- Direct reads (this session, unchanged since): `models/shift.py`, `hr_employee.py`, `attendance_event.py`, `assignment.py`, `leave_balance.py`, `payroll_run.py`.
- `docs/architecture/HOLIDAY_CALENDAR_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`, `ATTENDANCE_DESIGN.md`, `TIMESHEET_DESIGN.md`, `PR-050_DISCOVERY.md`, `docs/architecture/00-governance/ARCHITECTURE_VISION.md` — read in full context around every match.

---

# 1. Existing Scheduling Concepts

**Repository Evidence**: Repository-wide grep for the full term set (`schedule|calendar|working day|work pattern|recurring|recurrence|weekday|weekly|monthly|rotation|roster|timetable`) across `services/api/src` returns exactly 4 files:
- `services/reconciliation.py` — explicitly excludes "shift schedules" from its own v1 scope, and explicitly disclaims "calendar/timezone interpretation" as a repository-layer concern.
- `repositories/attendance_event.py` — explicitly disclaims "calendar interpretation," stating it "belongs entirely to the orchestration layer."
- `models/shift.py` — its own docstring excludes "assigning a shift to an employee, a work calendar, and rostering" as future-module scope (already found in `shift-assignment/discovery.md`, re-verified here).
- `jobs/memory_provider.py` — the one match ("scheduler") refers to background job scheduling (`enqueue_in`/`enqueue_at`), an unrelated technical concept, not an HR work schedule. Confirmed a false positive by reading the full context.

**Logical Consequence**: No scheduling concept — recurring, weekly, monthly, rotating, or otherwise — exists anywhere in application code. Every real match is either an explicit exclusion authored directly in the codebase or a same-word-different-meaning false positive.

**Unknown**: None — searched exhaustively, every match individually verified in context.

---

# 2. Shift Relationship

**Repository Evidence**: `HrEmployee.shift_id` is a required FK to `Shift`, `ON DELETE RESTRICT`. `AttendanceEvent.shift_id` is a separate, required, independent FK to `Shift`, `ON DELETE RESTRICT`, unvalidated against `HrEmployee.shift_id` (both confirmed by direct model read, consistent with `shift-assignment/discovery.md`, cited only to verify). Both FKs point directly at `Shift`'s own fixed template row (`start_time`/`end_time`/`break_duration_minutes`/`grace_period_minutes`) — a single time-of-day definition with no day-of-week or calendar scoping of any kind.

`ATTENDANCE_RECONCILIATION_DESIGN.md` uses the word "schedule" informally, describing `Shift`'s fixed time-of-day fields as what lets `ReconciliationService` judge "present" vs. "late" vs. "absent" — *"judged against a schedule, not just against the presence of any event."* This is the source document's own colloquial language for how `Shift` gets used, not evidence of an actual schedule entity.

**Logical Consequence**: No schedule layer sits between `Shift`, `HrEmployee`, and `AttendanceEvent`. `Shift` is informally treated, in one design document's prose, as the closest available proxy for "expected working hours," but has no weekly, day-of-week, or recurrence structure of any kind — it remains a flat, single time-of-day template.

**Unknown**: None — confirmed by direct model reads and full-context reading of the one document using "schedule" informally.

---

# 3. Calendar Concepts

**Repository Evidence**: `HOLIDAY_CALENDAR_DESIGN.md` (PR-041) directly evaluated three candidate shapes and explicitly rejected two: `HolidayCalendar` (a named container entity, e.g. "Indonesia 2027") and `CalendarDay` (a full date-dimension table, one row per calendar day of the year). It recommended, and the repository implements, only `Holiday` — a flat entity, one row per named non-working date, `code` and `holiday_date` both globally unique, zero FK. That same document confirms directly: *"No assignment mechanism exists anywhere in the codebase"* to select between calendars (`HrEmployee` has no `calendar_id`, `Location` has no `calendar_id`, `Organization` has no `calendar_id`), and *"zero recurrence precedent exists anywhere in the codebase, including `Shift`."*

**Logical Consequence**: No repository-owned "calendar" capability (a working/non-working day calendar spanning a year, or scoped per organization/location) exists anywhere — only a flat, non-recurring exception-date list (`Holiday`), whose own governance explicitly narrowed its scope away from anything calendar-shaped.

**Unknown**: None — `HOLIDAY_CALENDAR_DESIGN.md`'s own governance already searched this exhaustively, and this discovery's fresh grep confirms the same absence still holds.

---

# 4. Temporal Modeling

**Repository Evidence**: §1's exhaustive grep found zero recurring-record or repeating-pattern mechanism anywhere. `HOLIDAY_CALENDAR_DESIGN.md` explicitly flagged `is_recurring`/recurrence as *"Deferred, unconfirmed... the biggest future-schema risk"* — considered and not built. No effective-dating mechanism exists anywhere (independently reconfirmed here, consistent with `shift-assignment/discovery.md`'s own zero-match search of the same term set). No future-dated-change mechanism exists anywhere — every field reviewed across the repository is overwritten in place on `update()`, with no "takes effect starting on a future date" concept found anywhere.

**Logical Consequence**: No temporal modeling beyond flat, single dates (`Holiday.holiday_date`, `Assignment.start_date`/`end_date`) exists anywhere. Nothing in the repository supports "this repeats every week" or "this takes effect on a future date."

**Unknown**: None — confirmed absent by direct, repeated search across three independent discovery efforts (this one, `shift-assignment/discovery.md`, and `HOLIDAY_CALENDAR_DESIGN.md`).

---

# 5. Ownership

Stated explicitly where nobody owns something, per instruction:

- **Employee availability**: No field, entity, or service anywhere computes or stores whether an employee is available/expected to work on a given date. **Nobody owns this.**
- **Working days**: No entity defines which days of the week (or calendar days) are working days, for any employee, team, or organization. **Nobody owns this.**
- **Expected shifts**: `ReconciliationService` reads `HrEmployee.shift_id` at computation time as a narrow, explicitly-scoped-out-of-"schedule" stand-in for "the shift the employee is expected to work" (§2) — it consumes `Shift`'s raw fields at read time; it does not compute or store an expectation as a first-class concept. **No capability owns "expected shift" as a first-class concept** — `ReconciliationService` merely borrows `Shift`'s fields for a narrow, unrelated purpose (its own docstring excludes "shift schedules").
- **Recurring assignment**: No entity or service anywhere models a relationship that repeats or recurs (§1, §4). `shift-assignment/discovery.md`'s own independent search confirms the same absence for the narrower employee↔shift relationship alone (cited only to verify this repository statement). **Nobody owns this.**
- **Weekly patterns**: No entity anywhere has a day-of-week field or weekly-cycle concept (§1). **Nobody owns this.**

---

# 6. Existing Structural Patterns

Comparison only, per instruction — no classification made.

| Entity | Structural Shape | Resemblance to a Work Schedule Concept |
|---|---|---|
| `Assignment` | Peer-association entity, own payload including a date range (`start_date`/`end_date`), pair-uniqueness, `CASCADE` | The one precedent for a date-range-carrying entity — but its range represents a single continuous span, not a repeating pattern. |
| `Shift` | Master data, code-unique, fixed `start_time`/`end_time`, no date or day-of-week scoping, zero outbound FK | Any Work Schedule concept would likely reference `Shift` the same way `HrEmployee`/`AttendanceEvent` already do — as a fixed template being referenced, not extended. |
| `AttendanceEvent` | Transactional aggregate, one row per discrete past event, `RESTRICT` FKs, no recurrence, no forward-looking field | Records something that already happened; no structural resemblance to a forward-looking schedule. |
| `LeaveBalance` | Employee-scoped row keyed to a coarse `period_year` (bare `Integer`), no true date range, no compound uniqueness confirmed | The closest existing example of a "period"-partitioned record — though a day-of-week or weekly-cycle concept would partition far more finely than a bare year. |
| `PayrollRun` | Pure master data (`code`/`name`, unique/indexed), zero FK, zero date field of any kind | No structural resemblance to a temporal or recurring concept at all. |

**Logical Consequence**: Only `Assignment` (date-range-carrying) and `LeaveBalance` (period-partitioned) offer any structural resemblance to what a Work Schedule concept might need, and neither offers a recurring/weekly pattern — that specific shape has no precedent anywhere in the repository.

**Unknown**: Whether either resemblance is close enough to be a real precedent, or whether a Work Schedule concept would need an entirely new shape — not decided, comparison only.

---

# 7. Lifecycle

**Repository Evidence**: No entity anywhere models a "planned"/"future" record distinct from a "current"/"past" one (§4) — every entity reviewed uses plain field overwrite via `update()`, with no distinction between "this takes effect now" and "this takes effect later." No recurring-record lifecycle (e.g., a template that spawns dated instances) exists anywhere.

**Logical Consequence**: If Work Schedule needs to represent "planned" or "recurring" records, no existing repository pattern provides a starting point — this would be new structural territory for the codebase, not an extension of an existing lifecycle.

**Unknown**: None regarding existence, confirmed absent by exhaustive search. Whether such a lifecycle would ever be needed is a design question, out of scope for discovery.

---

# 8. Authorization

**Repository Evidence**: Grep for `schedule|calendar|roster` across every authorization-related service file (`authorization_evaluator.py`, `authorization_request.py`, `authorization_decision.py`, `authorization.py`, `approval_authorization.py`, `leave_authorization.py`, `attendance_authorization.py`) returns **zero matches**.

**Logical Consequence**: Consistent with every other capability's own Authorization finding in this governance trail — no resource or Service exists for `AuthorizationRequest.resource` to resolve against, since no Work Schedule entity or service exists at all.

**Unknown**: None.

---

# 9. Current Consumers

**Confirmed** (code-level):
- `HrEmployee.shift_id`, `AttendanceEvent.shift_id` — both confirmed FK consumers of `Shift` (§2).
- `ReconciliationService` — reads `HrEmployee.shift_id` at computation time (§5), a confirmed but narrow, explicitly-scoped-out-of-"schedule" consumer.

**Documented** (named in a design/governance document, not in code):
- `LEAVE_DESIGN.md`'s own unconfirmed "shift hours for partial-day math" question (already found in `shift-assignment/discovery.md`, cited to verify).
- `ATTENDANCE_RECONCILIATION_DESIGN.md` §12's explicit exclusion of "shift schedules," overnight-shift attribution, and timezone handling — named as known future concerns, never built.
- `HOLIDAY_CALENDAR_DESIGN.md`'s explicit exclusion of recurrence and calendar-container concepts, named as "future schema risk," never built.

**Unknown**: Not applicable in the usual sense — no field, service, or entity named "weekday" or "calendar" exists anywhere in code, so there is nothing to inventory consumers of; this is a confirmed absence (§1, §3), not an open question.

---

# 10. Governance Review

**Repository Evidence**: Grep for `Work Schedule|WorkSchedule|work_schedule` (case-insensitive) across all of `docs/` returns **zero matches** — this exact capability name has never appeared in any prior governance document. The broader term set (`schedule|calendar|roster|rotation|recurring|recurrence`) appears in 22 files, entirely consisting of: (a) capability governance documents already authored in this trail (Shift Assignment, Monetary Representation, Payroll, Payroll Calculation, Payroll Authorization — none defines a Work Schedule capability; each references "schedule" only informally or names it as an unaddressed future concern), and (b) prior PR-numbered design documents (`HOLIDAY_CALENDAR_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`, `ATTENDANCE_DESIGN.md`, `LEAVE_DESIGN.md`, `TIMESHEET_DESIGN.md`, `APPROVAL_WORKFLOW_DESIGN.md`, `APPROVAL_ORCHESTRATION_DESIGN.md`, `PR-050_DISCOVERY.md`, `ARCHITECTURE_VISION.md`), each of which either explicitly excludes scheduling/calendar concepts from its own scope or uses "schedule"/"calendar" informally (e.g., "calendar date," or `ARCHITECTURE_VISION.md`'s "Scheduled Tasks," a confirmed false positive in the unrelated background-jobs sense).

**Logical Consequence**: Work Schedule has never been defined as a capability anywhere in this repository's governance history. It has only ever been named, repeatedly and independently across four separate prior documents, as something explicitly excluded from scope (`Shift`'s own docstring; `ReconciliationService`'s own docstring; `HOLIDAY_CALENDAR_DESIGN.md`'s rejected-shapes analysis; `shift-assignment/discovery.md`/`decision.md`, which found the same absence for the narrower employee↔shift relationship alone).

**Unknown**: None — searched exhaustively across all of `docs/`.

---

# 11. Open Questions

Listed, not answered:

- Whether "Work Schedule" is the correct name for this candidate capability, or whether its scope should instead be absorbed into an eventual Shift Assignment, Holiday/Calendar, or Attendance-Reconciliation extension.
- Whether a Work Schedule concept would model recurrence (a repeating weekly/monthly pattern) or a flat, expanded set of dated instances (mirroring `Holiday`'s own flat-not-container decision) — no precedent exists for either shape.
- Whether Work Schedule would relate to `Shift` (as a consumer, the way `HrEmployee`/`AttendanceEvent` do), to a future `HolidayCalendar`-style container (explicitly deferred, never built), or to both.
- Whether the still-unresolved overnight-shift day-attribution and timezone-attribution ambiguities (independently flagged in `ATTENDANCE_DESIGN.md`, `HOLIDAY_CALENDAR_DESIGN.md`, and `ATTENDANCE_RECONCILIATION_DESIGN.md`) would need resolution before or as part of any Work Schedule capability.
- Whether the repeatedly-flagged, still-unaddressed `BaseRepository` date-range (`BETWEEN`) query gap (named in four separate prior design documents) would need to be resolved to support a Work Schedule capability.
- Whether Work Schedule would relate to Shift Assignment (a separate, already-governed candidate capability) as a prerequisite, a consumer, or an unrelated concern.

---

# 12. Recommendation

```
Capability Decision may begin
```

Unlike the two most recent "Continue Governance"-recommended discoveries in this trail (Monetary Representation, Shift Assignment), which each had at least one concrete, already-functioning piece of repository evidence to build on (a working FK, a working mechanism-consumer pattern), Work Schedule has none — no field, no FK, no service, not even an informal-but-real mechanism anywhere; only explicit exclusions and repeated, independent anticipation. This is a stronger absence, not a weaker one. But that anticipation is itself real, substantive, repository evidence: four separate, independently-authored design documents (`Shift`'s own docstring, `ReconciliationService`'s own docstring, `HOLIDAY_CALENDAR_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`) each independently name a schedule/calendar-shaped gap and decline to build it — this is not silence, it is a recurring, cross-document signal. Every one of the twelve topics above was searched exhaustively with zero remaining `Unknown` regarding existence — there is nothing further for another Discovery pass to find. The open questions (§11) are ownership/shape questions appropriate for a Capability Decision, not gaps a repeated search would close.

---

# References

- `services/api/src/eop_api/models/shift.py`, `hr_employee.py`, `attendance_event.py`, `assignment.py`, `leave_balance.py`, `payroll_run.py`, `holiday.py`
- `services/api/src/eop_api/services/reconciliation.py`
- `services/api/src/eop_api/repositories/attendance_event.py`
- `docs/architecture/HOLIDAY_CALENDAR_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`, `ATTENDANCE_DESIGN.md`, `TIMESHEET_DESIGN.md`
- `docs/architecture/capabilities/shift-assignment/discovery.md`, `decision.md` (cited only to verify repository statements about the employee↔shift relationship)
