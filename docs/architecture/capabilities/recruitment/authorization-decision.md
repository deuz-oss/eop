# Recruitment — Authorization Decision

**Status:** Decided — CPO/CTO Product Decision

**Capability:** Recruitment

**Owner:** Engineering (CPO/CTO-directed)

---

# Context

Recruitment Iteration 1 (`docs/architecture/capabilities/recruitment/iteration-1-scope-and-implementation-plan.md`) shipped `JobRequisition`, `Candidate`, and `Application` with `CurrentUser`-only authorization (any authenticated user could create/read/update/delete all Recruitment data, including `Candidate` PII). The CPO/CTO selected closing this gap, using existing authorization infrastructure only, as the next workstream.

---

# Decision

**Role Based** authorization: `RequireRole("admin")`, applied at the API dependency boundary to every route on all three routers (`/recruitment/job-requisitions`, `/recruitment/candidates`, `/recruitment/applications`) — create, read (detail/list/paginated), update, delete.

---

# Rationale

Identical structural reasoning to `PayrollRun`'s own authorization decision (`docs/architecture/capabilities/payroll-authorization/decision.md` Addendum): none of `JobRequisition`, `Candidate`, or `Application` carries an `employee_id`-shaped field, so **Owner Only** (the majority pattern used by `Compensation`/`Work Schedule`) has no field to compare against. `PayrollRun`'s own precedent — reusing the existing, repository-wide `"admin"` role via `dependencies/rbac.py`'s `RequireRole`, at the route dependency level (`RequirePayrollAdmin` in `api/payroll_runs.py`) — is the only existing mechanism this repository has for exactly this situation, and is reused here unmodified as `RequireRecruitmentAdmin`.

No new authorization evaluator, permission model, policy engine, RBAC table, or role was introduced. No business policy about *who* qualifies as a recruitment administrator was invented — the existing, already-established `"admin"` role is reused as-is, carrying forward the same known limitation `PayrollRun`'s own decision already recorded.

---

# Known Limitation (carried forward from Payroll Authorization's own precedent)

Uses the generic `admin` role, not a Recruitment-specific one. Anyone holding `admin` gets full Recruitment access — a broader grant than "recruiting staff" would be in a real deployment. Introducing a scoped `recruitment_admin` role is a valid future refinement, explicitly out of scope here.

---

# Explicitly Not Decided (Iteration 2, still blocked)

Recruitment pipeline/stage semantics, interview scheduling, offer management, candidate self-service, candidate-to-employee conversion, organization/department scoping. None of these has an Accepted decision or implementation plan; none is addressed by this authorization decision.

---

# References

- `docs/architecture/capabilities/payroll-authorization/decision.md` (Addendum — the reused precedent)
- `docs/architecture/capabilities/recruitment/iteration-1-scope-and-implementation-plan.md`
- `services/api/src/eop_api/api/payroll_runs.py` (`RequirePayrollAdmin`), `dependencies/rbac.py` (`RequireRole`)
