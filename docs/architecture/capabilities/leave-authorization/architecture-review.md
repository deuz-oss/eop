# Leave Authorization — Architecture Review

**Capability:** Leave Authorization

**Status:** Approved with Known Risks

**Reviewed against:** `leave-authorization/discovery.md`, `policy-discovery.md`, `decision.md`, `implementation-plan.md`

**Synchronization note:** This review was performed retroactively against already-merged code (`0a9b669`, PR #56), as part of documentation synchronization. It is not a pre-merge gate.

---

# Purpose

Records the final architecture review outcome for Leave Authorization, per `ARCHITECTURE_STATUS.md`'s governance rule that every implemented capability have a validation result on record.

---

# Checklist Verification

| Item | Result | Evidence |
|---|---|---|
| Selected policy matches Decision | Pass | `LeaveAuthorizationEvaluator.evaluate` implements exactly `resource.employee_id == context.employee_context.employee.id` (`leave_authorization.py:17-24`) |
| Service owns authorization orchestration | Pass | `LeaveRequestService._authorize` is the sole call site of `AuthorizationService`/`LeaveAuthorizationEvaluator` (`leave_request.py:207-222`) |
| Evaluator owns policy evaluation | Pass | Comparison logic exists only inside `LeaveAuthorizationEvaluator.evaluate` |
| Evaluator does not access repository | Pass | `LeaveAuthorizationEvaluator` takes no `uow`/session/repository dependency; receives `resource` pre-resolved |
| Authorization Foundation remains policy-agnostic | Pass, with a noted change | `AuthorizationService`/`AuthorizationEvaluator`/`AuthorizationDecision` carry no Owner Only logic; `AuthorizationRequest` gained an additive `resource: Any | None = None` field (see Known Risks) |
| API performs HTTP translation only | Pass | `api/leave_requests.py` maps `LeaveAuthorizationDeniedError` → `403`; no comparison logic in the router |
| Repository layer unchanged | Pass | No repository or migration file in commit `0a9b669` |
| Test coverage present at unit/service/API tiers | Pass | `test_leave_authorization_evaluator.py` (unit), `test_leave_request_service.py` (service), `test_leave_requests_api.py` (API) |
| Formal pre-merge Architecture Review document | **Not found** | No review record predating this synchronization exists in the repository |

---

# Status

**Approved with Known Risks.**

Approval is based on repository evidence showing the implementation conforms to the Capability Decision and does not violate ADR-007's Authorization Foundation boundary in substance (the one Foundation-level change is additive and default-neutral). It is issued retroactively; it does not certify that a review occurred before merge.

---

# Known Risks

## 1. EmployeeContext Mapping Gap (TD-001)

`EmployeeContextResolver.resolve` can raise `EmployeeContextNotFoundError` or `MultipleEmployeeContextError` (`employee_context.py:76-79`). Neither has a dedicated HTTP exception mapping. When `CurrentRequestContext` resolution fails on a Leave Authorization-gated route, the request currently reaches the generic error handler and returns `HTTP 500`, per `TECHNICAL_DEBT_REGISTER.md` TD-001. This risk pre-dates Leave Authorization (introduced by Approval Authorization, PR-053) and is inherited unchanged, not introduced, by this capability — Leave Authorization is a second consumer of the same unresolved gap.

## 2. DB-Backed Validation Environment Dependency

Unlike `LeaveAuthorizationEvaluator`'s own unit tests (`test_leave_authorization_evaluator.py`), which are fully in-memory, `test_leave_request_service.py` and `test_leave_requests_api.py` require a real, migration-managed database (real `HrEmployee`, `User`, and supporting master-data rows, truncated per test) to exercise the authorization-denial paths end to end. Authorization-denial coverage at the service/API tier is therefore contingent on the test database environment being available and correctly migrated — it cannot be validated by the evaluator's own isolated unit tests alone.

## 3. Untyped Resource Boundary

`AuthorizationRequest.resource` is typed `Any | None` (`authorization_request.py`). Authorization Foundation asserts no shape constraint on it; each capability-specific Evaluator is individually responsible for handling an unexpected, incompatible, or missing `resource`. `LeaveAuthorizationEvaluator` currently guards only `resource is None` (`leave_authorization.py:18-20`) before reading `resource.employee_id` — a `resource` of an unrelated type with no `employee_id` attribute would raise `AttributeError` rather than produce a denied `AuthorizationDecision`. No repository evidence shows this case is currently reachable through `LeaveRequestService`'s own call sites (§ `implementation-plan.md`, `resource` is always either `LeaveRequestCreate` or a loaded `LeaveRequest`), but the boundary itself carries no compile-time or Foundation-level guarantee against it.

---

# Risks Considered and Not Carried Forward

- **Manager/role/hybrid access gaps** — not risks to this capability; explicitly out of scope per the Decision (`leave-authorization/decision.md`, Explicit Exclusions).
- **Concurrency between authorization evaluation and commit** — no distinct evidence of this risk for Leave Authorization beyond what TD-002 already records for Approval Authorization; not re-raised here as a separate item since `LeaveRequestService`'s authorization check and its own `pending`-style state transition are not present on this capability's CRUD surface (unlike `ApprovalService`'s `pending → approved` transition).

---

# Recommendation

No action required to keep the capability in production use. TD-001 remains tracked centrally (not capability-specific) in `TECHNICAL_DEBT_REGISTER.md`. The DB-backed validation dependency and untyped resource boundary are recorded here as known, accepted risks — resolution, if pursued, requires a separate architecture decision (e.g., a typed `resource` protocol, or in-memory service-tier test doubles) and is not undertaken as part of this synchronization.

---

# References

- Leave Authorization Discovery
- Leave Authorization Policy Discovery
- Leave Authorization Decision
- Leave Authorization Implementation Plan
- TECHNICAL_DEBT_REGISTER.md — TD-001
- ADR-007 — Authorization Foundation
