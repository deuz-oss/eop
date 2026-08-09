# Recruitment Iteration 2 — Application Pipeline / Lifecycle: Business Decision Package

**Status:** Approved — Implemented

**Capability:** Recruitment (Iteration 2)

**Owner:** CPO/CTO

---

# Decision Recorded (2026-08-09)

**D1: Option B — Standard Funnel, approved as specified**, with the exact stage list and transition rules stated by the CPO/CTO (`applied → screening → interviewing → offered → hired`; `rejected`/`withdrawn` reachable from any non-terminal stage; forward-only; `hired`/`rejected`/`withdrawn` terminal, no reopening). Implemented as `ApplicationStatus` (`core/recruitment.py`) and `VALID_APPLICATION_TRANSITIONS`, enforced by `ApplicationService.transition`.

**D2: Option A — No Cascade, approved as specified.** `JobRequisitionService` was not modified; closing/deactivating a `JobRequisition` never touches any `Application`.

No stage, transition, or cascading behavior beyond what is stated above was invented. See `ARCHITECTURE_CHANGELOG.md` for the implementation-completion entry.

---

# Purpose

Targeted reconnaissance of `Application`'s model/schema/service/repository/API/tests, `JobRequisition`'s equivalent, and all three Recruitment governance documents (`iteration-1-scope-and-implementation-plan.md`, `authorization-decision.md`, `ARCHITECTURE_CHANGELOG.md`) confirms: **no accepted decision anywhere in this repository defines the Application lifecycle.** `Application.status` and `JobRequisition.status` are both plain, unconstrained `String(50)` columns (`models/application.py`, `models/job_requisition.py`) with zero transition validation anywhere in `ApplicationService`/`JobRequisitionService` today — every prior document explicitly named this as deferred to Iteration 2, not merely unaddressed.

Two decisions are genuinely blocking. Everything else investigated (ordering, skip-stage, backward-move, multiple-applications, candidate lifecycle, history) either follows mechanically from these two once answered, is already settled by existing schema/scope, or is a safe implementation-level default — none of those are raised here as separate questions, per instruction not to manufacture uncertainty.

No production code, migration, or test for unapproved behavior has been written. Nothing is committed.

---

# Already Resolved (not blocking, stated for completeness)

- **Multiple simultaneous applications**: already permitted by Iteration 1's own schema — `UniqueConstraint(candidate_id, job_requisition_id)` blocks only a duplicate application to the *same* requisition; nothing prevents a candidate holding open applications to *different* requisitions at once. No new decision needed.
- **Candidate lifecycle**: out of scope by this task's own framing (§2 lists only Application lifecycle; Candidate is not named). No Candidate field or state is touched.
- **History/audit persistence**: no precedent for status history exists anywhere in this repository (`HrEmployee.employment_status`, `JobRequisition.status` both have none). Resolved as an implementation-level default, consistent with Rule 5 (no generic audit framework without governance requirement) and the "smallest architecture" principle: current-status-only, no history table, in Iteration 2.

---

# D1 — Application Stage / Transition Model

**Question:** What are `Application`'s valid stages, which are terminal, and is backward movement or reopening from a terminal state ever allowed?

**Why the codebase cannot determine it:** `Application.status` has never been assigned a fixed value set anywhere — not in the model (plain string), not in the service (no validation), not in any prior governance document (all three explicitly defer this). There is no precedent in this repository for any state machine of any kind to draw an analogy from — every `status`-shaped field elsewhere (`HrEmployee.employment_status`, `PayrollRun.status` is the one exception with a real enum, but that is Payroll's own business content, not reusable here) is either free-text or governs a different domain entirely.

**Options:**

| | Stages | Terminal states | Backward/reopen |
|---|---|---|---|
| **A — Minimal** | `applied` → `hired` or `rejected` | `hired`, `rejected` | Not allowed |
| **B — Standard funnel (Recommended)** | `applied` → `screening` → `interviewing` → `offered` → `hired`; `rejected` reachable from any non-terminal stage; `withdrawn` reachable from any non-terminal stage (candidate-initiated) | `hired`, `rejected`, `withdrawn` | Not allowed — terminal states are truly terminal |
| **C — Standard funnel + reopening** | Same stages as B | Same as B | `rejected`/`withdrawn` → back to `applied` allowed |
| **D — Fully configurable stage list** | Rejected outright — this is generic workflow/policy-engine infrastructure (explicitly forbidden by Rule 5) presented only to name why it is not on the table |

**Consequences:**
- **A**: Fastest to build, but does not resemble a real hiring pipeline — likely insufficient for actual use, probably requiring a follow-up decision almost immediately.
- **B**: Matches how recruiting pipelines are conventionally modeled; forward-only progression is simple to validate and test; terminal-truly-terminal avoids ambiguous "what does re-opening mean" semantics.
- **C**: Same build cost as B plus reopening logic (what stage does a reopened application return to? does it reset `applied_date`? is there a limit on reopen count?) — each of those is itself a further undecided business question, so C would immediately spawn a D1b.
- **D**: Rejected — turns a Recruitment-domain concept into shared workflow infrastructure with no evidenced multi-capability need.

**Engineering recommendation:** **B**. Smallest model that behaves like a real hiring pipeline, avoids inventing reopening semantics nobody has asked for, and can be extended to C later (reopening) without any breaking schema change — `status` remains a plain string either way, only the service-layer transition table changes.

**Unlocks:** The transition-validation logic in `ApplicationService`, the migration (if `status` needs a check constraint — implementation-level, decided after D1), and every lifecycle test.

---

# D2 — JobRequisition Closure Interaction

**Question:** When a `JobRequisition`'s `status` moves to a closed/inactive value, what happens to its non-terminal `Application`s?

**Why the codebase cannot determine it:** `JobRequisitionService.update()` applies `status` as a plain field overwrite with no side effects on any related entity (`services/job_requisition.py`, confirmed by direct read — no query against `Application` exists anywhere in that service). No governance document states an intended relationship here; `iteration-1-scope-and-implementation-plan.md` treats `JobRequisition` and `Application` as related only via FK, never via cascading business behavior.

**Options:**

| | Behavior |
|---|---|
| **A — No cascading (Recommended)** | Applications remain completely untouched when their requisition closes. An admin must act on each Application explicitly if needed. |
| **B — Auto-reject** | Closing a requisition automatically transitions every non-terminal Application for it to `rejected` (or a `closed` terminal state distinct from `rejected` — a further sub-decision C would introduce). |
| **C — Block closure** | A requisition cannot be closed while non-terminal Applications exist; the API rejects the closure until they are resolved. |

**Consequences:**
- **A**: Zero hidden side effects, no risk of silently rejecting a candidate without an explicit action; requires no new cross-service call from `JobRequisitionService` into `ApplicationService`.
- **B**: Convenient, but silently changes candidate-facing state without a human decision at the moment of rejection — a real product-behavior risk (an admin closing a requisition for a completely different reason, e.g. a backfill freeze, would inadvertently reject every open candidate) and it introduces exactly the further ambiguity D1 already flagged (does "closed by cascade" mean `rejected`, or does it need its own terminal state?).
- **C**: Safest against silent side effects but adds friction to ordinary requisition-closing workflows and requires `JobRequisitionService` to query `ApplicationRepository` before allowing an update — a new cross-service coupling not currently justified by anything in governance.

**Engineering recommendation:** **A**. No cross-service coupling, no silent candidate-facing side effect, smallest change, and fully reversible later (B or C can be added on top without breaking A's behavior).

**Unlocks:** Confirms `JobRequisitionService` needs zero changes for Iteration 2 — the lifecycle work is entirely scoped to `Application`/`ApplicationService`/its API.

---

# What Becomes Implementable Once D1 and D2 Are Answered

With both decided, implementation is a single, narrowly-scoped vertical slice: a service-owned transition table + validation in `ApplicationService`, a small set of new exceptions (e.g. `InvalidApplicationTransitionError`), the existing `RequireRole("admin")` authorization reused unmodified on whatever endpoint exposes the transition, and tests per §11 of the governing task. No new entity, migration beyond a possible `status` check constraint, or cross-capability change is anticipated beyond that.

---

# References

- `services/api/src/eop_api/models/application.py`, `job_requisition.py`
- `services/api/src/eop_api/services/application.py`, `job_requisition.py`
- `docs/architecture/capabilities/recruitment/iteration-1-scope-and-implementation-plan.md`, `authorization-decision.md`
