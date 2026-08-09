# Performance Iteration 2 — Review Lifecycle: Business Decision Package

**Status:** Approved — Implemented

**Capability:** Performance (Iteration 2)

**Owner:** CPO/CTO

---

# Decision Recorded (2026-08-09)

**D1: Option B — Admin-only `draft → finalized` lifecycle, approved as specified.** New reviews start `DRAFT`. Only an authenticated `admin`-role user may transition `DRAFT → FINALIZED`. `FINALIZED` is terminal: no reopening, no backward transitions, no re-finalizing. No employee acknowledgement, manager/self/peer review, calibration, approval hierarchy, notifications, or generic workflow engine. Reuses `RequireRole("admin")` unmodified.

Implemented as `PerformanceReviewStatus` (`core/performance.py`, mirrors `ApplicationStatus`'s exact enum/transition-table pattern) and `VALID_PERFORMANCE_REVIEW_TRANSITIONS`, enforced by a new `PerformanceReviewService.finalize` method, exposed via `POST /hr/performance-reviews/{id}/finalize`. `PerformanceReviewCreate`/`PerformanceReviewUpdate` do not accept `status` — every new review starts `DRAFT`; the only way to reach `FINALIZED` is `finalize`. Once `FINALIZED`, ordinary `update()` calls reject any attempt to change substantive review data (`employee_id`, `review_period_start`/`end`, `notes`) with a new `PerformanceReviewFinalizedError` (409).

No stage, transition, or workflow behavior beyond what is stated above was invented. See `ARCHITECTURE_CHANGELOG.md` for the implementation-completion entry.

---

# Purpose

Targeted reconnaissance of `PerformanceReview`'s model/schema/service/API (`models/performance_review.py`, `services/performance_review.py`, `api/performance_reviews.py`) and its governance chain (`iteration-1-scope-and-implementation-plan.md`) confirms: **`PerformanceReview` has no status field of any kind** — `employee_id`, `review_period_start`/`review_period_end`, `notes` only, plain flat CRUD, admin-only (`RequireRole("admin")`) end to end.

The most direct next step — mirroring Recruitment's own Iteration 1 (flat CRUD) → Iteration 2 (lifecycle) arc — is adding a status/workflow to `PerformanceReview`. But this differs from Recruitment's Application-lifecycle decision in one important respect: Recruitment's funnel-stage question (`applied → screening → … → hired`) was cleanly separable from other undecided Recruitment concepts. Here, **any** lifecycle shape immediately requires answering at least one item the original CPO/CTO Iteration 1 mandate explicitly named as forbidden to invent absent a decision: *"review workflow, manager/peer/self-review semantics, approval hierarchy."* There is no lifecycle shape that avoids this — even a minimal two-state `draft → finalized` requires deciding who is authorized to finalize, which is itself a workflow/authorization question.

One decision is genuinely blocking. No production code, migration, or test for any lifecycle behavior has been written. Nothing is committed.

---

# Already Resolved (not blocking, stated for completeness)

- **Rating scale / scoring / competency framework / goal weighting**: not raised here. These were explicitly named as out of scope in Iteration 1 and nothing in this reconnaissance suggests they are needed merely to add a status field. If D1 below is answered, no rating/scoring concept is implied or introduced as a side effect.
- **Review cadence / recurring cycles**: not raised here either, for the same reason. A status field does not require a `PerformanceCycle`/`ReviewPeriod` entity.
- **Authorization mechanism**: if the chosen option requires anyone other than an admin to transition state (e.g., the reviewed employee acknowledging their own review), this is a genuine sub-question captured inside D1's options below, not a separate decision — introducing a new Owner Only-shaped rule is a small, well-precedented extension (`LeaveRequest`'s existing Owner Only policy), not a new authorization framework.

---

# D1 — PerformanceReview Status / Lifecycle

**Question:** Does `PerformanceReview` need a status/lifecycle for Iteration 2 at all, and if so, what are the valid states and who is authorized to transition them?

**Why the codebase cannot determine it:** `PerformanceReview` has never carried a `status` field, in the model or anywhere else. No governance document states an intended workflow — `iteration-1-scope-and-implementation-plan.md` explicitly defers "review workflow, manager/peer/self-review semantics, approval hierarchy" without picking among them. There is no reusable precedent to draw the *values* from: `Application`'s `applied → … → hired` funnel is a hiring-pipeline concept with no performance-review analogue, and `PayrollRunStatus`'s `DRAFT → PROCESSING → COMPLETED` is payroll-processing content, not review content.

**Options:**

| | Shape | Who transitions | Authorization impact |
|---|---|---|---|
| **A — No lifecycle (status quo)** | `PerformanceReview` stays flat CRUD indefinitely; Iteration 1 is treated as sufficient until a concrete product requirement asks for more. | N/A | None — no change |
| **B — Admin-only two-state (Recommended)** | `draft → finalized`, forward-only, `finalized` terminal (not reopenable, mirrors `Application`'s terminal-states-truly-terminal precedent) | Admin only | None — reuses `RequireRole("admin")` unmodified |
| **C — Employee-acknowledgment lifecycle** | `draft → submitted → acknowledged`, where the reviewed employee must acknowledge their own review | Admin creates/submits; the reviewed employee acknowledges | Requires a new Owner Only-shaped rule (`PerformanceReview.employee_id == context.employee_context.employee.id`) layered onto the existing admin-only policy for the acknowledge action specifically — small, precedented (mirrors `LeaveRequest`'s Owner Only), but a genuine authorization-policy change, not a data-shape change |
| **D — Full manager/employee review workflow** | Self-review, peer review, manager sign-off, calibration, approval hierarchy | Multiple parties, hierarchy-dependent | Rejected outright — this is exactly the "generic workflow infrastructure" the original CPO/CTO Iteration 1 mandate forbade building without a concrete requirement; also depends on Organization Hierarchy, which remains explicitly Deferred |

**Consequences:**
- **A**: Zero implementation cost, zero risk. Leaves `PerformanceReview` as a static record indefinitely — acceptable if nothing downstream currently needs to know "is this review done."
- **B**: Smallest lifecycle that gives a meaningful signal (draft vs. finalized), no authorization change, directly mirrors the `PayrollRun`/`Application` "status field + forward-only transition" precedent shape (though not their specific values).
- **C**: Meaningfully more product value (the employee has visibility and a record of acknowledgment) but is the first Performance decision to touch authorization policy beyond simple admin-only reuse — should only be chosen if employee-facing acknowledgment is an actual near-term product requirement, not spec-built ahead of need.
- **D**: Rejected — no evidenced requirement, and explicitly named as out of bounds by the standing mandate.

**Engineering recommendation:** **A or B**, CPO/CTO's call. If no concrete downstream need exists yet for "is this review finalized," **A** costs nothing and keeps the capability at its smallest footprint (consistent with the "smallest coherent aggregate" principle Iteration 1 was built under). If a lifecycle is wanted now, **B** is the smallest version that adds one, with zero authorization-policy change. **C** should be deferred until employee-facing acknowledgment is an explicit requirement, not anticipated speculatively.

**Unlocks:** If A, no further Performance work is needed at this time — the capability remains closed at Iteration 1 until a concrete requirement reopens it. If B, implementation is a single narrow vertical slice: a `PerformanceReviewStatus` enum (mirrors `PayrollRunStatus`'s exact pattern), a forward-only transition table in `PerformanceReviewService`, one new transition endpoint, reusing `RequireRole("admin")` unmodified, plus tests. If C, the same plus one new Owner Only authorization check scoped to the acknowledge action only.

---

# References

- `services/api/src/eop_api/models/performance_review.py`, `services/performance_review.py`, `api/performance_reviews.py`
- `docs/architecture/capabilities/performance/iteration-1-scope-and-implementation-plan.md`
- `docs/architecture/capabilities/recruitment/iteration-2-business-decision-package.md` (structural precedent for this package's format)
