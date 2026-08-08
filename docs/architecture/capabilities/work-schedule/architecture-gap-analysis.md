# Work Schedule — Architecture Gap Analysis

**Status:** Complete

**Capability:** Work Schedule

**Owner:** EOP Architecture Governance

**Based On:** `discovery.md`, `decision.md`, `domain-model-discovery.md`

---

# 1. Architectural Readiness

| Component | Classification | Repository Evidence |
|---|---|---|
| `BaseEntity` | **Sufficient** | Universal across every persisted entity compared (`domain-model-discovery.md` §2). The general persistence shape does not conflict with a recurring concept (`domain-model-discovery.md` §1). Caveat: if the still-`Unknown` Projection candidate is eventually chosen and takes a non-persisted form, it may not need `BaseEntity` at all. |
| `BaseRepository` | **Sufficient** | Proven, working infrastructure for every persisted entity reviewed (`Assignment`, `Shift`, `AttendanceEvent`, `PayrollRun`). Same conditional caveat as `BaseEntity` above. |
| Repository pattern | **Sufficient** | `ShiftRepository`, `AssignmentRepository`, `PayrollRunRepository` all follow this pattern without exception. |
| `UnitOfWork` | **Sufficient** | `SQLAlchemyUnitOfWork` used uniformly across every reviewed service, no exceptions found. |
| API layering (`API → Service → UoW → Repository → Model`) | **Sufficient** | `Assignment`'s own full stack already proves this layering works for a structurally comparable (though non-recurring) aggregate. |
| Authorization Foundation | **Unknown** | `domain-model-discovery.md` §8 found genuine, unresolved ambiguity — Work Schedule resembles both the unauthorized majority (`Assignment`, `Shift`, 8 of 11 reviewed capabilities) and, less directly, the authorized minority, with no repository fact breaking the tie. |
| `EventService` | **Not Applicable** | No document anywhere in this capability's governance connects `EventService` to a scheduling concern. Remains dormant, zero callers repository-wide (established fact, restated). |
| `JobService` | **Not Applicable** | `discovery.md` §1 found the one repository match for "scheduler" (`jobs/memory_provider.py`) refers to background job scheduling (`enqueue_in`/`enqueue_at`), an unrelated technical concept — confirmed a false positive, not evidence of a connection. |

---

# 2. Missing Concepts

Each classified as exactly one category, per instruction. No Business Gap or External Dependency applies among these six specific items — each is a technical or architecture-decision question, not a content/policy or third-party one; this is stated explicitly rather than forced.

| Concept | Classification | Reasoning |
|---|---|---|
| Recurring relationships | **Repository Gap** | No mechanism anywhere represents "this fact repeats" — confirmed exhaustively (`discovery.md` §1, §4; `domain-model-discovery.md` §3, §4). A pure technical absence, not a pending decision. |
| Recurrence identity | **Repository Gap** | Even if a recurring relationship existed, no identity convention anywhere handles "one template, many recurring instances" — `domain-model-discovery.md` §2 found only three conventions in the repository (UUID-only, UUID+code, UUID+pair-uniqueness), none of which represents this shape. |
| Temporal uniqueness (date-scoped/overlap-aware constraints) | **Repository Gap** | `Assignment`'s own uniqueness constraint is not date-aware, and actively *blocks* recurrence rather than supporting it (`domain-model-discovery.md` §1). No date-scoped constraint mechanism exists anywhere in the repository, confirmed identically for Shift Assignment's own gap analysis. |
| Overlap validation | **Repository Gap** | `BaseRepository._apply_filters` has no `BETWEEN`/range-query support — named as an unresolved gap in four independent prior design documents (`HOLIDAY_CALENDAR_DESIGN.md`, `LEAVE_DESIGN.md`, `TIMESHEET_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`, cited via `discovery.md` §11). `AssignmentService` itself checks only pair-uniqueness, never date-range overlap — confirmed by direct read. |
| Historical schedule lookup | **Repository Gap** | No history, snapshot, or versioning mechanism exists for any entity in the repository (`domain-model-discovery.md` §5) — a pure technical absence. |
| Planned-versus-actual comparison | **Governance Gap** | Unlike the five items above, a mechanism-shape precedent *does* already exist: `ReconciliationService` already performs a read-time, no-FK comparison against `Holiday` (`domain-model-discovery.md` §7). The open question is whether/how to extend this existing mechanism to Work Schedule — an architecture decision about reuse, not a technical absence. |

**External Dependency**: **None found.** No third-party system or external data source is evidenced anywhere across `discovery.md`, `decision.md`, or `domain-model-discovery.md` — confirmed absent, not omitted.

---

# 3. Existing Infrastructure

| Component | Classification | Repository Evidence |
|---|---|---|
| `Assignment` | **Applicable as structural precedent only, more narrowly than for Shift Assignment** | `domain-model-discovery.md` §1 found `Assignment`'s pair-uniqueness constraint actively incompatible with recurrence — its "linking two aggregates" shape remains comparable, but its enforced uniqueness rule cannot be mirrored as-is, unlike the direct fit found for Shift Assignment. |
| Attendance (`AttendanceEvent`/`ReconciliationService`) | **Applicable as a mechanism precedent for planned-vs-actual comparison, not as reusable code** | `domain-model-discovery.md` §7 found `ReconciliationService` already performs a read-time, no-FK join against `Holiday` — the closest available precedent for how Work Schedule might be consulted. `ReconciliationService`'s own docstring explicitly excludes "shift schedules" from its current v1 scope, so nothing is reusable today. |
| `Holiday` | **Applicable as a consultation-mechanism precedent, not as a data-shape precedent** | Demonstrates the "flat date, no FK, read-time-joined" consultation shape (§2 above), but `HOLIDAY_CALENDAR_DESIGN.md` explicitly rejected recurrence for `Holiday` itself — not a precedent for representing a recurring pattern. |
| `AuditLog` | **Not Applicable** | Referenced only within its own service file — no other reviewed service populates or reads it (established fact, re-verified for Shift Assignment's own gap analysis, unchanged since). |
| `AuditMixin` | **Not Applicable** | Composed into every `BaseEntity` mechanically, but `created_by`/`updated_by` are populated by nothing anywhere in the repository — present on paper, functionally inert. |

---

# 4. Upstream Dependencies

| Capability | Classification | Reasoning |
|---|---|---|
| `Shift` | **Already Exists** | Merged, implemented code (`decision.md` §2) — Work Schedule would depend on it without owning it. |
| `HrEmployee` | **Unknown whether it is actually a dependency** | The entity itself already exists in merged code regardless, but whether Work Schedule depends on it at all is only inferred, not confirmed (`decision.md` §8, `domain-model-discovery.md` §3). |
| Shift Assignment | **Unknown whether it is a dependency at all; if it turns out to be one, currently Missing** | `decision.md` §3/`domain-model-discovery.md` §6 leave the relationship direction (upstream/downstream/peer/unrelated) entirely undecided. Shift Assignment itself has no implemented code anywhere — it exists only as governance documents. If future governance decides Work Schedule depends on it, that dependency would currently be unmet. |
| Attendance/`Holiday` | **Not Required** | Evidenced as potential consultation-mechanism precedents and potential downstream/mechanism partners (§3, §5), not prerequisites Work Schedule needs to exist before it can be built. |

---

# 5. Downstream Consumers

- **Confirmed**: None. Nothing in code consumes a Work Schedule concept, since it does not exist.
- **Documented**: `ReconciliationService`/Attendance — its own docstring explicitly names "shift schedules" as excluded, anticipated future scope (`discovery.md` §1, §5, §9; `domain-model-discovery.md` §7), a direct, self-authored documentation of future interest.
- **Unknown**: `LeaveRequest` — `LEAVE_DESIGN.md`'s "shift hours for partial-day math" question concerns `Shift` directly; its relevance to a recurring/planned Work Schedule concept specifically is a weaker, inferred connection, not a direct documented one (unlike its more direct documented relevance to Shift Assignment). Shift Assignment itself — relationship undecided (§4 above, `domain-model-discovery.md` §6).

---

# 6. Blocking Unknowns

Consolidated from `discovery.md`, `decision.md`, and `domain-model-discovery.md`. Nothing new added, nothing answered.

1. **Aggregate shape** — three of seven candidates remain `Unknown` (Aggregate Root, Association Aggregate, Projection; `decision.md` §5, `domain-model-discovery.md` §1). *Why unresolved*: no repository precedent exists for a recurring aggregate of any kind. *Why more search would not help*: two dedicated discovery passes (Discovery, Domain Model Discovery) both confirmed the same absence; nothing further exists to find.
2. **Relationship with Shift Assignment** — upstream/downstream/peer/unrelated all remain possible (`decision.md` §3, `domain-model-discovery.md` §6). *Why unresolved*: neither capability has any implemented code to compare. *Why more search would not help*: both sides are equally hypothetical; there is nothing to search.
3. **Whether "recurring schedules" and "effective dates" are one concern or two** (`decision.md` §6). *Why unresolved*: `discovery.md` treated them as related but distinct without merging them, and no evidence forces a merge or a split. *Why more search would not help*: this is a conceptual framing question, not a fact absent from the repository.
4. **Authorization posture** (`decision.md` §7, `domain-model-discovery.md` §8). *Why unresolved*: Work Schedule structurally resembles both the unauthorized majority and, less directly, the authorized minority. *Why more search would not help*: the same structural tie found identically for every other capability in this trail.
5. **Whether `HrEmployee` is actually a dependency** (`decision.md` §8, `domain-model-discovery.md` §3). *Why unresolved*: only inferred by analogy to every other employee-scoped entity, never directly evaluated the way `Shift` was. *Why more search would not help*: this is an inference gap, not a missing fact — the analogy itself is already as strong as the repository can make it.
6. **Whether `ReconciliationService`/Attendance becomes a real consumer** (`decision.md` §8, `domain-model-discovery.md` §7). *Why unresolved*: its own docstring anticipates the gap but does not commit to consuming any specific future mechanism. *Why more search would not help*: the anticipation is already stated as explicitly as the source document states it.
7. **Whether `LeaveRequest`, `Timesheet`, or Payroll Calculation ever consume Work Schedule** (`decision.md` §8). *Why unresolved*: no repository evidence found for any of the three specifically. *Why more search would not help*: `discovery.md`'s own exhaustive term search already covered this ground.
8. **Identity convention** — which of three secondary-identity shapes (UUID-only, UUID+code, UUID+pair-uniqueness) applies (`domain-model-discovery.md` §2). *Why unresolved*: depends entirely on the unresolved aggregate shape (#1). *Why more search would not help*: this is a downstream consequence of #1, not an independent fact.
9. **Whether Work Schedule is employee-scoped at all** (`domain-model-discovery.md` §3). *Why unresolved*: inferred by analogy, not confirmed. *Why more search would not help*: same reasoning as #5.
10. **Which weaker temporal shape (if any) is closer to what's needed** (`domain-model-discovery.md` §4). *Why unresolved*: three weaker precedents exist (`Assignment`'s range, `LeaveBalance`'s partition, `Holiday`'s flat date) but none represents recurrence, and nothing distinguishes which is the better analogy. *Why more search would not help*: all three have been fully characterized; the choice is a design judgment, not an undiscovered fact.
11. **Lifecycle beyond create-then-overwrite** (`domain-model-discovery.md` §5). *Why unresolved*: no repository precedent exists for "replace" as distinct from "overwrite," or for historical preservation, for any entity. *Why more search would not help*: confirmed absent exhaustively, repository-wide.
12. **Whether "employee work calendars" ownership overlaps with `HOLIDAY_CALENDAR_DESIGN.md`'s declined calendar-container scope** (`decision.md` §1). *Why unresolved*: that document decided not to build a container, which is different from deciding who would own one if built. *Why more search would not help*: `HOLIDAY_CALENDAR_DESIGN.md`'s own reasoning has already been fully read and cited; nothing further exists there.
13. **`BaseRepository` `BETWEEN`-query gap** (`discovery.md` §11, also §2 above). *Why unresolved*: named in four independent prior documents without resolution. *Why more search would not help*: this is the fourth-to-fifth module to name the same gap; repeating the search would only confirm it again.
14. **Overnight-shift/timezone attribution ambiguities** (`discovery.md` §11). *Why unresolved*: flagged independently across `ATTENDANCE_DESIGN.md`, `HOLIDAY_CALENDAR_DESIGN.md`, and `ATTENDANCE_RECONCILIATION_DESIGN.md`, unresolved in each. *Why more search would not help*: three independent documents already establish this is a known, unaddressed gap.
15. **Capability naming** (`discovery.md` §11). *Why unresolved*: "Work Schedule" originates entirely from this governance trail's own task framing. *Why more search would not help*: already searched exhaustively across all of `docs/`.

---

# 7. Can Iteration 1 Begin?

```
No
```

The minimum blocking governance questions are **aggregate shape** (#1) and **identity convention** (#8, directly downstream of #1) — no code can be scaffolded without knowing whether Work Schedule would be an Aggregate Root, an Association Aggregate (in some form other than `Assignment`'s own incompatible uniqueness rule), or a Projection, since each implies a different persistence shape or none at all. **Whether Work Schedule is employee-scoped** (#9) and **authorization posture** (#4) are the next-most-fundamental blockers, affecting the relationship model and the API/service layer respectively. This is a wider-open set of structural forks than Shift Assignment faced at the same stage (which had exactly two — relationship shape and delete rule); no minimum scaffold is proposed here, per instruction.

---

# 8. Remaining Risks

Restated only from prior documents, none invented:

- Building the wrong aggregate shape — three genuinely different, live candidates remain (`domain-model-discovery.md` §1).
- No overlap-validation or `BETWEEN`-query support existing anywhere, risking inconsistent schedule data if built before this repeatedly-flagged gap is addressed (`discovery.md` §11, §2 above).
- Attendance/`ReconciliationService`'s own already-existing "shift schedules" exclusion being retrofitted awkwardly if Work Schedule is built without coordinating with Attendance's own future governance (`decision.md` §4, `domain-model-discovery.md` §7).
- No historical-preservation or lifecycle mechanism existing anywhere, risking silent loss of prior schedule states if plain overwrite is used without further thought (`domain-model-discovery.md` §5).
- Authorization being retrofitted later if Work Schedule turns out to need dedicated-evaluator treatment rather than the CRUD-majority treatment it currently resembles (`domain-model-discovery.md` §8).
- The relationship with Shift Assignment remaining undefined, risking duplicated or conflicting capability scope if both are eventually built independently without reconciling their overlap (`decision.md` §3, `domain-model-discovery.md` §6).

---

# 9. Recommendation

```
Additional Governance Required
```

Not **Waiting for New Capability**: the one confirmed upstream dependency (`Shift`) already exists and is merged (§4); `HrEmployee` and Shift Assignment are only *possibly* dependencies, unconfirmed — recommending this option would resolve an Unknown prematurely in a specific direction, which this document does not do. Not **Ready for Architecture Review**: the aggregate shape remains open across three live candidates (wider than Shift Assignment's comparable two-item blocker), with identity, employee-scoping, and authorization posture all downstream of it — no stable target exists for a consistency review. The fifteen items in §6 are architecture decisions and inference gaps, not missing repository evidence — matching the same reasoning already used for Shift Assignment's own Architecture Gap Analysis at the comparable stage.

---

# References

- `docs/architecture/capabilities/work-schedule/discovery.md`
- `docs/architecture/capabilities/work-schedule/decision.md`
- `docs/architecture/capabilities/work-schedule/domain-model-discovery.md`
- `docs/architecture/capabilities/shift-assignment/architecture-gap-analysis.md` (classification taxonomy and recommendation precedent)
