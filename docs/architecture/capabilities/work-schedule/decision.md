# Work Schedule — Capability Decision

**Capability:** Work Schedule

**Status:** Approved — Boundary Decision Only (no schema, recurrence, or lifecycle decided)

**Version:** 1

**Owner:** Architecture

---

# 1. Capability Ownership

**Repository Evidence**: `discovery.md` §5 found, explicitly, that nobody currently owns employee availability, working days, expected shifts (as a first-class concept), recurring assignment, or weekly patterns. `discovery.md` §1/§4 confirmed zero recurring, planned, or calendar mechanism exists anywhere in the repository.

**Logical Consequence**: By elimination — the same reasoning pattern already used for Monetary Representation and Shift Assignment — if these concepts are owned by any capability, none currently owns them, and Work Schedule is precisely the candidate under evaluation for them.

- **Recurring work patterns**: **Yes, by elimination**, if Work Schedule is built at all — nothing else owns or addresses this (`discovery.md` §1, §5).
- **Planned working days**: **Yes, by elimination** — same reasoning (`discovery.md` §5).
- **Expected shifts**: **Yes, by elimination**, as a first-class concept — distinct from `ReconciliationService`'s narrow, incidental read of `HrEmployee.shift_id` at computation time, which `discovery.md` §5 found does not constitute ownership of the concept itself.
- **Employee work calendars**: **Yes, by elimination**, with a caveat: `HOLIDAY_CALENDAR_DESIGN.md` (`discovery.md` §3) already evaluated and *declined* to build a calendar-container concept for `Holiday` specifically — this is a decision not to build a calendar container, not evidence that another capability owns employee work calendars. The elimination reasoning still holds: nobody owns it today.

---

# 2. Relationship with `Shift`

**Repository Evidence**: `discovery.md` §2 established both `HrEmployee.shift_id` and `AttendanceEvent.shift_id` reference `Shift`'s own fixed template row directly, with no schedule layer between them. `discovery.md` §6 found any Work Schedule concept would most plausibly reference `Shift` the same way — as a fixed template being referenced, not extended.

**Decision**:
- **Owns `Shift`? No.** `Shift` already has its own service, repository, and API, predating this discovery.
- **Depends on `Shift`? Yes.** Work Schedule, if built, would need `Shift` to exist as the thing a schedule ultimately points to.
- **Produces `Shift`? No.**
- **Consumes `Shift`? Yes** — the same dependency-without-ownership relationship already established for Shift Assignment's own relationship to `Shift` (cited only for structural comparison, not re-derived).
- **Independent of `Shift`? No** — `discovery.md` §2/§6 directly implicate `Shift` as the closest available reference point for any Work Schedule concept.

---

# 3. Relationship with Shift Assignment

**Repository Evidence**: `discovery.md`'s own Purpose section explicitly keeps Work Schedule distinct from Shift Assignment. No code connects them. No governance document establishes a direction between them — `discovery.md` §11 records this directly as an open question: *"Whether Work Schedule would relate to Shift Assignment... as a prerequisite, a consumer, or an unrelated concern."*

**Logical Consequence**: Both concern how an employee relates to a shift over time, but from different angles — Shift Assignment concerns which shift an employee is currently or was assigned (a point-in-time relationship, per `shift-assignment/decision.md`, cited only for comparison); Work Schedule (per `discovery.md` §1/§5) concerns recurring or planned patterns (a forward-looking, repeating structure). Plausible candidate relationships include Work Schedule being upstream of Shift Assignment (a schedule implies what assignment should exist), a peer (both independently consume `Shift`), or something else entirely.

**Decision: Unknown.** Not forced, per instruction — no repository evidence establishes any direction between these two candidate capabilities.

---

# 4. Relationship with Attendance

**Repository Evidence**: `discovery.md` §2/§6 found `AttendanceEvent` records discrete, past events with no forward-looking field, and `ReconciliationService`'s own docstring explicitly excludes "shift schedules" from its scope (`discovery.md` §1, §5, §9).

**Logical Consequence**: Attendance's own boundary — already established independently of this capability's governance, via `AttendanceEvent`'s transactional shape and `ReconciliationService`'s own explicit self-exclusion — already excludes anything forward-looking or planned. This produces a clean, non-overlapping split along a temporal axis (past vs. future), not the mechanism/policy axis used elsewhere in this trail.

**Decision**: Attendance owns recorded (past) facts — already decided by Attendance's own prior, independent governance, restated here, not re-derived. Work Schedule, if built, would own planned (future) facts — by elimination, since nothing else is evidenced as owning this, and Attendance's own boundary explicitly excludes it.

---

# 5. Aggregate Classification

Each candidate evaluated independently; rejected only where repository evidence supports rejection, per instruction.

- **Aggregate Root** — **Repository Evidence**: the `BaseEntity`/`UUIDMixin` persistence shape is universal across the repository and does not inherently conflict with a recurring concept. **Unknown, not rejected**: no positive precedent exists anywhere for what a *recurring* aggregate specifically looks like (`discovery.md` §6) — the general persistence shape doesn't confirm the specific recurring behavior Work Schedule would need.
- **Child Entity** — **Repository Evidence**: no entity anywhere in the repository is accessed only through another aggregate's own repository/service — the same direct structural mismatch found repeatedly across this trail. **Rejected.**
- **Association Aggregate** — **Repository Evidence**: `Assignment` is the one association precedent, but its shape (pair-uniqueness, a single continuous date range) does not match a recurring pattern — `discovery.md` §6 found *"neither offers a recurring/weekly pattern — that shape has no precedent anywhere."* **Unknown, not rejected**: partial resemblance (a relationship-linking shape) exists, but the recurring dimension — the differentiator for Work Schedule specifically — is unprecedented.
- **Transactional Aggregate** — **Repository Evidence**: every transactional aggregate reviewed (`AttendanceEvent`, `LeaveBalance`, etc., `discovery.md` §6) records a past or discrete fact, not a forward-looking recurring structure. **Rejected** — direct structural mismatch, the same reasoning already used to reject this shape for Shift Assignment.
- **Domain Service** — **Repository Evidence**: `ApprovalService`/`ReconciliationService` orchestrate reads/writes with no owned table. A recurring pattern needs to be durably stored (a template implying repeated dated instances), which a stateless orchestrator does not do. **Rejected** — same reasoning already used repeatedly in this trail.
- **Projection** — **Repository Evidence**: `discovery.md` found zero projection/read-model precedent anywhere (the same absence found for Shift Assignment). **Unknown, not rejected** — no positive or negative evidence either way.
- **Value Object** — **Repository Evidence**: this repository's one Value Object precedent, `LeaveBalance.period_year`, is a bare `Integer` scalar with no independent identity. A recurring/planned schedule concept plausibly needs independent identity to be queried and referenced across employees and shifts. **Rejected** — direct structural mismatch, the same reasoning already used to reject this shape for Shift Assignment.

**Result**: Four candidates rejected on direct structural mismatch (Child Entity, Transactional Aggregate, Domain Service, Value Object). Three remain genuinely `Unknown` (Aggregate Root, Association Aggregate, Projection) — notably more unresolved than Shift Assignment's own decision at the same stage (which left only one candidate `Unknown`), reflecting the total absence of any recurring-pattern precedent anywhere in the repository (`discovery.md` §1, §4, §6). No winner is forced.

---

# 6. Temporal Ownership

**Repository Evidence**: `discovery.md` §4/§7 confirmed zero recurring-record mechanism, zero future-dated-change mechanism, and zero effective-dating mechanism exists anywhere in the repository — a total absence, not merely an unowned concept with some partial precedent.

**Logical Consequence**: Since nothing currently exists to own these concepts, and Work Schedule is the only evidenced candidate concerned with them specifically (`discovery.md` §5, §11), by elimination Work Schedule would own recurring schedules, future planning, and effective dates if any of them are ever built — mirroring the identical elimination reasoning already used for Shift Assignment's own effective-dating conclusion (`shift-assignment/decision.md` §7, cited only for structural comparison, not re-derived).

**Unknown**: Whether "recurring schedules" and "effective dates" are the same underlying concern or two separable ones — `discovery.md` itself treated recurrence (§1) and effective dating (§4) as related but distinct topics without merging them; not resolved here either.

---

# 7. Authorization

**Repository Evidence**: `discovery.md` §8 found zero references to "schedule"/"calendar"/"roster" anywhere in any authorization-related service file.

**Decision: Not decidable today.** This mirrors the identical structural finding already reached independently for every other capability in this governance trail (Payroll, Payslip, Payroll Calculation, Compensation, Monetary Representation, Shift Assignment): no resource or Service exists yet for `AuthorizationRequest.resource` to resolve against.

---

# 8. Producer / Consumer Direction

**Confirmed** (repository-evidenced, code-level): None. Nothing exists in code today to be a producer or consumer of a Work Schedule concept, since none exists.

**Logical Consequence**:
- `Shift` would be a producer Work Schedule depends on/consumes (§2).
- `HrEmployee` is plausibly a producer too — every planning-shaped or recurring concept discussed in `discovery.md` §5 is employee-relevant, and every comparable transactional aggregate in this repository is employee-scoped via a `RESTRICT` FK — but `discovery.md` did not directly evaluate an `HrEmployee` relationship the way it evaluated `Shift` (§2), so this is stated as inference, not a confirmed dependency.
- `ReconciliationService`/Attendance could plausibly become a consumer if Work Schedule is built, mirroring `ReconciliationService`'s own documented exclusion of "shift schedules" (`discovery.md` §1, §5, §9) — its own docstring already anticipates this gap, but this is inference about a future relationship, not a current fact.

**Unknown**:
- The direction with Shift Assignment (§3).
- Whether `LeaveRequest`, `Timesheet`, or Payroll Calculation would ever consume Work Schedule — no repository evidence found in `discovery.md` for any of these three.

---

# 9. Deferred Decisions

Not solved here:

- Whether "employee work calendars" ownership overlaps with `HOLIDAY_CALENDAR_DESIGN.md`'s own explicitly-declined calendar-container scope (§1).
- The relationship direction with Shift Assignment — upstream, downstream, peer, or unrelated (§3).
- Aggregate shape — three of seven candidates left `Unknown` (Aggregate Root, Association Aggregate, Projection) (§5).
- Whether "recurring schedules" and "effective dates" are one concern or two (§6).
- Authorization ownership (§7).
- `HrEmployee`'s exact relationship to Work Schedule — only inferred, not directly evaluated the way `Shift` was (§8).
- Whether `ReconciliationService`/Attendance becomes a real future consumer (§8).
- Whether Shift Assignment, `LeaveRequest`, `Timesheet`, or Payroll Calculation ever become consumers (§8).
- Whether the `BaseRepository` `BETWEEN`-query gap (named in four prior design documents, `discovery.md` §11) needs resolving to support this capability.
- Whether the overnight-shift/timezone attribution ambiguities (`discovery.md` §11) need resolving before or as part of this capability.
- Whether "Work Schedule" is the correct or final capability name (`discovery.md` §11).

---

# 10. Rejected Alternatives

- **Embedding inside `Shift`** — Rejected. `Shift`'s own docstring explicitly excludes assignment/rostering/calendar as future-module scope (`discovery.md` §1, §2); `Shift` is already-decided, narrow master data (a fixed template only) with no repository precedent for adding recurrence to it.
- **Embedding inside Attendance/`ReconciliationService`** — Rejected. `ReconciliationService`'s own docstring explicitly excludes "shift schedules" from its scope (`discovery.md` §1, §5, §9); `AttendanceEvent` is transactional and backward-looking by structure (§4), a direct mismatch with a forward-looking, recurring concept.
- **Embedding inside `Holiday`/`HolidayCalendar`** — Rejected. `HOLIDAY_CALENDAR_DESIGN.md` already directly evaluated and rejected a calendar-container shape for `Holiday` specifically (`discovery.md` §3); `Holiday` itself is a flat, non-recurring, non-employee-scoped list — a structural mismatch for an employee-scoped recurring pattern.
- **Embedding inside Shift Assignment** — **Not rejected.** Left as the open, undecided relationship in §3 — no repository evidence supports rejecting this specific alternative the way the other three were rejected on direct structural mismatch.
- **Deciding a recurrence rule or schema today** — Rejected. Explicitly out of scope per this document's own hard constraints, and `discovery.md`'s own total absence of precedent for any recurrence mechanism anywhere.

---

# 11. Recommendation

```
Domain Model Discovery may begin.
```

Ownership is decided by elimination for four concepts (§1), the relationship with `Shift` is decided cleanly (§2), the boundary with Attendance is decided cleanly via Attendance's own already-established self-exclusion (§4), and four of seven aggregate candidates were rejected on direct structural grounds (§5) — a comparable degree of resolution to Shift Assignment's own `decision.md` at the same stage, even though three aggregate candidates remain `Unknown` here versus one there, reflecting the total absence of any recurring-pattern precedent anywhere in the repository rather than a weaker governance pass. The unresolved items (§9) are shape and consolidation questions appropriate for a Domain Model Discovery pass, not evidence gaps — `discovery.md`'s own twelve topics were already searched exhaustively with zero remaining `Unknown` regarding existence, so no further Discovery round is expected to change any of them.

---

# References

- `docs/architecture/capabilities/work-schedule/discovery.md`
- `docs/architecture/capabilities/shift-assignment/decision.md` (structural comparison precedent for dependency-without-ownership reasoning and effective-dating elimination logic)
- `docs/architecture/HOLIDAY_CALENDAR_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md` (cited via `discovery.md`)
