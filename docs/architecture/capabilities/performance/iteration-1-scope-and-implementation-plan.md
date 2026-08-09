# Performance — Iteration 1 Scope and Implementation Plan

**Status:** Authorized — CPO/CTO Product Decision

**Capability:** Performance (Iteration 1)

**Owner:** Engineering (CPO/CTO-directed)

---

# 0. Authority and Disambiguation

The CPO/CTO has explicitly selected Performance as the next product capability, superseding `docs/product/02_PRODUCT_SCOPE.md`'s prior "Out of Scope — HRIS" listing of **Performance Review**, using the same precedent already applied to Recruitment and (earlier) Payroll Processing.

**Important disambiguation, found during targeted reconnaissance:** `02_PRODUCT_SCOPE.md` §7 "Performance Management" (KPI, Target, Achievement, Productivity, Scorecard, Leaderboard, Incentive Calculation) is a *different, already-in-scope* concept — field/sales operational performance metrics, consistent with EOP's own stated positioning ("designed to improve field execution"). It is **not** touched, redefined, or built by this document. This capability concerns only the HRIS-excluded **Performance Review** item (individual employee review records), the one the CPO/CTO's decision explicitly named.

No prior governance chain exists for Performance Review — this is genuinely new territory, scoped directly here rather than through a full six-phase governance cycle, mirroring exactly how Recruitment Iteration 1 was scoped.

---

# 1. Scope (Iteration 1 — Minimal Record Only)

Mirrors the "smallest coherent aggregate" precedent already used for `Interview`/`Offer` (Recruitment Iteration 3): one flat, historical record entity, no workflow, no scoring, no cadence policy.

**`PerformanceReview`** — a record that a performance review took place for an `HrEmployee`, covering a stated period, with free-text notes. Fields: `employee_id` (FK → `hr_employees.id`, RESTRICT — mirrors every other employee-scoped entity in this repository, e.g. `Compensation`, `WorkSchedule`), `review_period_start`/`review_period_end` (plain `Date` columns, no separate Period/Cycle entity — mirrors `PayrollRun.period_start`/`period_end`'s own precedent exactly), `notes` (optional free text, mirrors `Interview`/`Offer.notes`).

**Explicitly out of scope for Iteration 1** (no business decision exists for any of these; none is invented here): rating scales, competency frameworks, review workflow/status, manager/peer/self-review semantics, approval hierarchy, calibration, goal weighting or a `Goal` entity, performance scoring formulas, review cadence policy, employee-manager relationship enforcement, organization scoping, any relationship to Payroll/Compensation/Attendance/Leave/Work Schedule/Recruitment/Shift Assignment.

No `PerformanceCycle`/`ReviewPeriod` entity is introduced — a named, reusable review-cycle container is a legitimate future concept, but nothing establishes a need for it yet, and `PayrollRun`'s own precedent (plain period columns on the owning entity, no separate Period entity) is the established, minimal alternative.

---

# 2. Implementation-Level Decisions

Each decision below follows directly from existing repository precedent; none changes business policy, none creates a new domain-ownership boundary.

- **Delete rule**: `RESTRICT` on `employee_id`, matching every other FK into `HrEmployee` from HR-adjacent data (`Compensation`, `WorkSchedule`, `Application`'s own `RESTRICT`-everywhere convention).
- **No status/lifecycle field**: mirrors `Interview`/`Offer`'s own precedent exactly — a flat historical record, not a competing lifecycle.
- **No effective dating**: `PerformanceReview` is a discrete, one-time historical event (like `AttendanceEvent`/`Interview`/`Offer`), not a "current state superseding prior state" concept the way `Compensation`/`WorkSchedule` are. `EffectiveDatingMixin` does not apply — multiple `PerformanceReview` rows per employee are independent historical events, not competing effective-dated versions of one thing.
- **No uniqueness constraint**: multiple reviews per employee (including overlapping periods) are permitted — asserting "one review per period" would invent review-cadence policy nobody has decided.
- **Basic period sanity check** (`review_period_end >= review_period_start`): a narrow, implementation-level data-integrity check, not a cadence/workflow decision — mirrors `ShiftService`'s own `start_time != end_time` sanity check precedent (structural validation, not business process).
- **Authorization**: `RequireRole("admin")` reused unmodified, per explicit CPO/CTO instruction for Iteration 1 — no evidence found requiring a materially different posture.
- **API placement**: `/hr/performance-reviews`, not a new top-level `/performance/...` prefix. Unlike Recruitment (a genuinely separate domain — candidates are not employees), `PerformanceReview` is squarely HR-domain, employee-scoped data, structurally closest to `Compensation`/`WorkSchedule` (both under `/hr/...`), not to Recruitment's own separate-domain placement.
- **Cross-aggregate validation**: `PerformanceReviewService.create`/`update` validates only that `employee_id` references an existing `HrEmployee` (mirrors `JobRequisitionService`'s single-FK-existence-check shape, simplified to one FK instead of three).

---

# 3. Vertical Slice

Model → Migration → Repository → Service → Schema → API → Tests, mirroring `Interview`/`Offer`'s own stack (single FK existence check, no uniqueness, `RequireRole("admin")`, `notes` field) with the FK target changed from `applications.id` to `hr_employees.id`. No new abstractions; `BaseRepository`/`BaseEntity`/`SQLAlchemyUnitOfWork` reused unmodified.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` (updated alongside this plan — Performance Review removed from HRIS exclusion list; §7 Performance Management untouched)
- `docs/architecture/capabilities/recruitment/iteration-1-scope-and-implementation-plan.md` (scoping-document precedent)
- `services/api/src/eop_api/models/interview.py`, `offer.py` (minimal-record shape precedent)
- `services/api/src/eop_api/models/payroll_run.py` (plain-period-columns-on-owning-entity precedent)
- `services/api/src/eop_api/models/hr_employee.py`, `compensation.py`, `work_schedule.py` (employee-scoped FK convention)
