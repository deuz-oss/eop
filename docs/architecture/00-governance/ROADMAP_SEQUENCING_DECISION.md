# Roadmap Sequencing Decision — Post-Payroll Authorization

**Status:** Escalated — Roadmap sequencing decision required from Architecture Governance

**Version:** 1

**Owner:** Architecture Governance (per `ARCHITECTURE_GOVERNANCE.md` — this document does not itself constitute that decision; see § Decision below)

---

# Purpose

This document records the outcome of resolving one narrow question: *"After Payroll Authorization, what is the officially authorized next workstream?"*

It does not select a next workstream. It records why one cannot be legitimately selected from existing repository evidence, per the instruction governing this document: *"If the existing roadmap does not contain enough information to legitimately select a next workstream, record the outcome as: 'Roadmap sequencing decision required from Architecture Governance.' Do not fabricate the answer."*

---

# Decision

**Roadmap sequencing decision required from Architecture Governance.**

No next workstream is selected by this document, for two independent reasons:

1. **Evidentiary.** `MASTER_ARCHITECTURE_ROADMAP.md` contains three sequencing artifacts that do not agree (§ Evidence), and no other repository document resolves the disagreement. Picking one artifact over the others without a stated rule for doing so would be inventing sequencing, which this document is explicitly instructed not to do.
2. **Authority.** `docs/architecture/00-governance/ARCHITECTURE_GOVERNANCE.md` § Decision Ownership states: *"Architecture decisions belong only to: Human, Architecture Owner... Implementation agents must never create new architecture."* The same document's § Roles assigns "roadmap evolution" and "architecture decisions" to the Human and to the Architecture Owner role, and explicitly lists "roadmap ownership" and "architecture decisions" under Claude's role as *"Not responsible for."* Selecting and recording a specific next workstream is exactly this kind of decision.

Both point to the same conclusion independently: this question is answerable only by Architecture Governance, not by resolving repository evidence alone.

---

# Evidence

**Document:** `docs/architecture/10-reference/MASTER_ARCHITECTURE_ROADMAP.md`

| Artifact | Section / lines | What it says |
|---|---|---|
| Dependency Roadmap | lines 442–467 | `Attendance Authorization → Payroll Authorization → Enterprise Authorization` — a structural dependency chain, not a stated implementation-priority order. |
| Capability Roadmap (master table) | lines 425–439 | Enterprise Authorization's own constituent items (Permission Model, Policy Engine, Delegated Approval, Organization Hierarchy) are marked `Status: Deferred`. |
| Deferred Architecture | lines 471–483 | States those same items "remain intentionally outside the current roadmap phase" and "Each requires a dedicated ADR before implementation." |
| Phase 5 — Remaining Capability Authorizations | lines 332–340 | Recruitment Authorization and Performance Authorization remain `Status: Planned` — not updated since Attendance/Payroll Authorization merged. |
| Phase 7 — Enterprise Platform | lines 401–421 | `Status: Future`, gated behind Phase 6; the only non-authorization items in the document, two phases removed from Payroll Authorization. |

**Repository prerequisite check:** a repository-wide search of `models/`, `services/`, `api/`, and `main.py`'s router registrations found no Recruitment or Performance resource of any kind (zero matches for recruitment/candidate/job-posting or performance/KPI/appraisal concepts).

**Governance-authority evidence:** `docs/architecture/00-governance/ARCHITECTURE_GOVERNANCE.md` § Roles and § Decision Ownership (quoted above).

No document in the repository states a tie-breaking rule between the Dependency Roadmap diagram, the Deferred Architecture section, and the Phase 5 table.

---

# Selected Next Workstream

**None.** Not selected, per § Decision above.

---

# Why Other Candidates Are Deferred

- **Enterprise Authorization** — named next only by the Dependency Roadmap diagram; its own constituent capabilities are separately marked `Deferred` by the same document's Capability Roadmap table, and the Deferred Architecture section requires a dedicated ADR before implementation. The diagram expresses a dependency, not an implementation authorization.
- **Recruitment Authorization / Performance Authorization** — marked `Planned`, not `Deferred`, but neither has a protected resource in the repository. Both would immediately reproduce the same "no resource exists" finding Payroll Authorization itself started from, before Payroll Iteration 1 existed.
- **Phase 7 (Enterprise Platform) items** — marked `Future`, explicitly gated behind Phase 6, and not placed by any document directly after Payroll Authorization.

None of these is rejected on its merits — each is deferred by the roadmap's own stated status or explicitly requires governance input this document is not authorized to supply.

---

# Prerequisites

Before a next workstream can be selected:

1. Architecture Governance (Human or the designated Architecture Owner role, per `ARCHITECTURE_GOVERNANCE.md`) must state which of the three conflicting `MASTER_ARCHITECTURE_ROADMAP.md` artifacts governs sequencing — or issue a fresh sequencing decision directly.
2. If Recruitment Authorization or Performance Authorization is chosen, its underlying data capability (the protected resource) must be discovered and decided first — the same prerequisite Payroll Authorization required, per repository precedent.
3. If Enterprise Authorization is chosen, the dedicated ADR(s) the Deferred Architecture section requires must be produced first.

---

# Implementation Gate

**No implementation, Discovery, or capability governance work may begin on Enterprise Authorization, Recruitment Authorization, Performance Authorization, or any Phase 7 item until Architecture Governance resolves the sequencing conflict recorded here.**

This gate is not lifted by this document. It is lifted only by an explicit Architecture Governance decision superseding this record.

---

# References

- `docs/architecture/10-reference/MASTER_ARCHITECTURE_ROADMAP.md`
- `docs/architecture/00-governance/ARCHITECTURE_GOVERNANCE.md`
- `docs/architecture/capabilities/payroll-authorization/decision.md` (precedent: the same "no resource exists" finding, previously resolved by Payroll Iteration 1)
