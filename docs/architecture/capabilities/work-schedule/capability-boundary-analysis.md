# Work Schedule — Capability Boundary Analysis

**Status:** Complete

**Capability:** Work Schedule

**Owner:** EOP Architecture Governance

**Reviews:** `discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `implementation-plan.md` (all approved, none modified)

---

# Purpose

Every unresolved item left inside Work Schedule's approved governance is examined here to determine whether it is genuinely Work Schedule's own responsibility, belongs to another capability, belongs to shared/generic infrastructure, or is an external business decision. This is an architecture-governance analysis only — no code, entity, or implementation is produced. Every conclusion derives from repository evidence or the six already-approved Work Schedule documents; nothing is invented.

---

# 1. Aggregate Shape

**Repository Evidence**: `decision.md` §5 leaves three of seven aggregate candidates `Unknown` (Aggregate Root, Association Aggregate, Projection; restated by `architecture-gap-analysis.md` §6 item 1). No other capability's own governance in this repository claims jurisdiction over "how a recurring relationship should be shaped." Shift Assignment's own `decision.md` §4 evaluated a structurally different question — a shape for a point-in-time (not recurring) relationship — and Monetary Representation's own `decision.md` §7 evaluated yet another different question (a representation/type mechanism). Neither addresses recurrence.

**Logical Consequence**: This is Work Schedule's own open architecture decision, unresolved because the repository has never built a recurring aggregate of any kind anywhere — not because ownership is contested or genuinely belongs to another capability.

**Unknown**: Which specific shape applies — genuinely undecided, and correctly Work Schedule's own to eventually decide, not itself a boundary question.

**Decision**: Genuinely owned by Work Schedule. Not a missing concept belonging elsewhere.

---

# 2. Recurrence

| Concept | Classification | Reasoning |
|---|---|---|
| Recurrence concept (the general idea that a fact can repeat over time) | **Unknown, with a Shared-Infrastructure candidate flag** | Zero precedent exists anywhere in the repository for any capability (`discovery.md` §1, §4). `HOLIDAY_CALENDAR_DESIGN.md` independently deferred an `is_recurring` field for `Holiday` itself, describing it as *"the biggest future-schema risk"* — a second, independent capability anticipating the same missing general mechanism. This is the same structural pattern (a mechanism named independently by more than one capability, none of which owns it today) that led to Monetary Representation's own extraction from Compensation's boundary analysis, though with one fewer independent anticipation so far (two here, versus three there). See §8. |
| Recurring pattern (the specific weekly/monthly cycle of shifts Work Schedule itself would represent) | **Work Schedule** | Squarely Work Schedule's own subject matter, decided by elimination in `decision.md` §1 — no other capability needs *this specific* content. |
| Recurrence identity (how a recurring template's individual instances would be identified) | **Generic repository/infrastructure concern** | `architecture-gap-analysis.md` §2 classifies this a **Repository Gap** — a technical, identity-scheme absence, not content specific to Work Schedule's own business meaning. Work Schedule would be the first motivating consumer, but the underlying mechanism, if built, is infrastructure-shaped, mirroring how `BaseEntity`/`BaseRepository` are infrastructure no single capability owns. |

---

# 3. Temporal Identity

| Concept | Classification | Reasoning |
|---|---|---|
| Effective periods | **Work Schedule's own, if built — but the underlying mechanism is a genuine cross-capability extraction candidate** | `decision.md` §6 already established, by elimination, that if effective dating exists for this relationship, it belongs to Work Schedule (mirroring Shift Assignment's own identical conclusion, `shift-assignment/decision.md` §7). This is now the **third** independent capability to reach this same "if built, belongs to me" conclusion for a still-nonexistent effective-dating mechanism — after Compensation (`compensation/capability-boundary-analysis.md`, flagged there as a "secondary, weaker finding") and Shift Assignment. Three independent anticipations is the same threshold that triggered Monetary Representation's own extraction. See §8. |
| Temporal uniqueness | **Generic repository concern** | `architecture-gap-analysis.md` §2 classifies this a **Repository Gap** — no date-scoped constraint mechanism exists anywhere in the repository, for any entity, not specific to Work Schedule's own content. |
| Overlap validation | **Generic repository concern** | `architecture-gap-analysis.md` §2 classifies this a **Repository Gap** — `BaseRepository._apply_filters` lacks `BETWEEN`/range-query support, already named independently in four prior design documents (`HOLIDAY_CALENDAR_DESIGN.md`, `LEAVE_DESIGN.md`, `TIMESHEET_DESIGN.md`, `ATTENDANCE_RECONCILIATION_DESIGN.md`) before Work Schedule's own governance began. Work Schedule is the fifth capability to name the same gap, not its originator. |
| Historical lookup | **Generic repository concern** | `architecture-gap-analysis.md` §2 classifies this a **Repository Gap** — no history/snapshot/versioning mechanism exists anywhere in the repository, for any entity; the same absence applies uniformly, not specifically to Work Schedule. |

---

# 4. Relationship Boundaries

Re-confirmed, not re-derived — restating each already-decided boundary and verifying none has drifted toward absorption:

- **`Shift`**: `decision.md` §2 — depends on/consumes, does not own. No absorption in either direction.
- **Shift Assignment**: `decision.md` §3 — relationship direction left `Unknown`. This Unknown is itself not evidence of boundary confusion or overlap — it reflects that neither capability has any implementation to compare (`domain-model-discovery.md` §6), not that either has encroached on the other. No absorption.
- **`HrEmployee`**: `decision.md` §8 — only an inferred, unconfirmed dependency; not owned. No absorption.
- **Attendance**: `decision.md` §4 — a clean temporal split (Attendance owns recorded/past facts, Work Schedule would own planned/future facts), with Attendance's own boundary independently established prior to and untouched by this capability's governance. No absorption.
- **`Holiday`**: `decision.md` §10 explicitly rejects embedding Work Schedule inside `Holiday`/`HolidayCalendar`. `Holiday` is used only as a comparison/mechanism precedent (§2, §3 above), never claimed as owned. No absorption.
- **Leave**: `LeaveRequest` is treated only as a weak, `Unknown` candidate consumer (`architecture-gap-analysis.md` §5) — never owned or absorbed. No absorption.

No capability has absorbed another's responsibility anywhere in this chain.

---

# 5. Missing Repository Concepts

The five Repository Gaps from `architecture-gap-analysis.md` §2, classified by ownership only — not solved:

| Gap | Ownership Classification |
|---|---|
| Recurring relationships (general mechanism) | **Shared-infrastructure candidate** (§2 above) — Work Schedule's own specific instance of the content remains Work Schedule's. |
| Recurrence identity | **Repository abstraction / ORM support concern** — generic, not Work-Schedule-specific. |
| Temporal uniqueness | **Repository abstraction / ORM support concern** — generic constraint mechanism. |
| Overlap validation | **Generic repository concern** — the `BaseRepository` `BETWEEN`-query gap, named by five capabilities total; squarely infrastructure. |
| Historical schedule lookup | **Repository abstraction concern** — the same versioning/history absence found for every entity in the repository, not Work-Schedule-specific. |

None of these five gaps is Work Schedule's own to solve unilaterally — each is either a generic repository-abstraction absence or a candidate for shared infrastructure, consistent with §2 and §3.

---

# 6. Authorization

**Repository Evidence**: `decision.md` §7, `domain-model-discovery.md` §8, and `architecture-gap-analysis.md` §1/§6 item 4 all found Work Schedule structurally resembles the unauthorized majority (`CurrentUser`-only, including `Assignment` itself) more directly than the authorized minority, with no repository fact breaking the tie, and no evidence of the specific historical-sequencing circumstance that produced Payroll Authorization as its own separate capability.

**Logical Consequence**: If Work Schedule ever needs authorization, the *mechanism* would be Authorization Foundation (`ADR-007`'s already-proven, shared mechanism) — the same conclusion reached identically for every other capability in this trail — not a new, Work-Schedule-specific mechanism, and not a new separately-foldered capability (no analogous Payroll-Authorization-style circumstance is evidenced here). The *policy content* (who may create or modify a schedule), if authorization is ever built, would be Business's to decide, not Architecture's.

**Unknown**: Whether authorization is needed at all — not Work Schedule's own architecture question to resolve unilaterally; genuinely undecided, consistent with every sibling capability's identical finding.

---

# 7. Future Consumers

- **Confirmed**: None. Nothing in code consumes a Work Schedule concept, since it does not exist.
- **Documented**: `ReconciliationService`/Attendance — its own docstring explicitly names "shift schedules" as excluded, anticipated future scope (`discovery.md` §1, §5, §9), a direct, self-authored statement.
- **Logical Consequence**: `HrEmployee` — inferred as employee-scoping's likely producer by analogy to every other employee-scoped entity (`decision.md` §8), not directly confirmed. `AttendanceEvent`'s own existing consultation-mechanism precedent (a read-time join against `Holiday`) extending to Work Schedule if built (`domain-model-discovery.md` §7) — a reasoned inference, not a documented statement.
- **Unknown**: `LeaveRequest` — a weaker, inferred connection specific to Work Schedule (`architecture-gap-analysis.md` §5). Shift Assignment — relationship direction entirely undecided (§4 above). `Timesheet`, Payroll Calculation — no repository evidence found for either (`decision.md` §8).

No consumer is invented beyond what is already named across the six reviewed documents.

---

# 8. Capability Extraction

Two candidates evaluated; one weaker candidate rejected from extraction, per instruction to reject unless evidence genuinely supports it.

## Effective dating / temporal versioning mechanism (primary-strength candidate)

**Repository Evidence**: Three independent capabilities' own governance, authored at different times by different task sequences, each independently reach the same "if this mechanism is ever built, it belongs to me" conclusion for a still-nonexistent effective-dating capability: Compensation (`compensation/capability-boundary-analysis.md`, originally flagged as a "secondary, weaker finding"), Shift Assignment (`shift-assignment/decision.md` §7), and now Work Schedule (`decision.md` §6, §3 above).

**Logical Consequence**: Three independent anticipations is the same threshold that produced Monetary Representation's own extraction from Compensation's boundary analysis (`compensation/capability-boundary-analysis.md` §3-4, which required exactly three named anticipating capabilities). This is not a new discovery invented here — it is a re-confirmation, from two additional independent capabilities' own governance, of a signal `compensation/capability-boundary-analysis.md` already flagged at lower confidence.

**Not extracted here**: No capability name is proposed, per instruction — this analysis surfaces that the evidentiary threshold has now been met, not what the resulting capability should be called or shaped like.

## Recurrence mechanism (secondary, weaker candidate)

**Repository Evidence**: Two independent anticipations: Work Schedule itself and `HOLIDAY_CALENDAR_DESIGN.md`'s own deferred `is_recurring` field for `Holiday`, described there as *"the biggest future-schema risk."*

**Logical Consequence**: A weaker echo of the same pattern as the effective-dating finding, but with one fewer independent anticipation — below the three-capability threshold used for both prior extractions in this trail. Worth carrying forward, not asserted with the same confidence.

## `BaseRepository` `BETWEEN`-query gap — rejected from extraction

**Repository Evidence**: Named by five capabilities total (four prior design documents plus Work Schedule), the most-repeated gap of any found in this analysis.

**Logical Consequence**: Despite the highest repetition count, this is not capability-shaped — it is a low-level ORM/repository-abstraction enhancement (a query-building capability on an existing generic class), not a business capability with its own ownership boundary, consumers, or authorization posture the way Monetary Representation or the effective-dating candidate are. **Rejected as an extraction candidate** — repository evidence supports it as a repeated infrastructure gap, not as a capability.

---

# 9. Recommendation

```
Additional Governance Required
```

Not **Ready for New Decision**: Work Schedule's own boundary questions (§1) are already correctly assigned and stable — a fresh Decision round for Work Schedule itself is not indicated the way it was for Monetary Representation after its own boundary analysis. Not **Capability Boundary Stable** alone: while §4 found zero absorption anywhere (a stable result), §8 surfaced that the effective-dating/temporal-versioning candidate has now crossed the same three-capability evidentiary threshold that previously triggered a real extraction — this is new, actionable governance information, not a closed matter. The appropriate next governance action is twofold and does not touch Work Schedule's own already-approved conclusions: (1) Work Schedule's own remaining Unknowns proceed exactly as already tracked in `implementation-plan.md` §10, unchanged by this analysis; (2) the effective-dating/temporal-versioning candidate (§8) now warrants its own Discovery, following the same repository-first method already used to originate Monetary Representation from Compensation's own boundary analysis.

---

# References

- `docs/architecture/capabilities/work-schedule/discovery.md`, `decision.md`, `domain-model-discovery.md`, `architecture-gap-analysis.md`, `architecture-review.md`, `implementation-plan.md`
- `docs/architecture/capabilities/compensation/capability-boundary-analysis.md` (extraction-threshold precedent, cited §2, §3, §8)
- `docs/architecture/capabilities/shift-assignment/decision.md` §7 (effective-dating anticipation, cited §3, §8)
- `docs/architecture/HOLIDAY_CALENDAR_DESIGN.md` (recurrence deferral, cited §2, §8)
