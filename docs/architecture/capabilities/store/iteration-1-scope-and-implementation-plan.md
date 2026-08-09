# Customer & Store — Iteration 1 Scope and Discovery

**Status:** Discovery Complete — Implementation-Ready (pending sign-off)

**Capability:** Store (fulfills Roadmap Phase 3 "Store"/"Customer" and Product Scope §4 "Customer & Store")

**Owner:** Engineering (Senior Engineer authority per standing mandate), reviewed by CPO/CTO

---

# 1. Domain Boundary

Product evidence (`docs/product/02_PRODUCT_SCOPE.md` §4, `06_PRODUCT_ROADMAP.md` Phase 3/MVP Scope, "Product Boundaries," "Out of Scope") is the only source — no capability-level document existed for this domain before this one.

**Customer and Store are the same entity, not two.** This is the single interpretive judgment call this discovery rests on; the evidence is laid out in full so it can be overridden if wrong:

1. **MVP Scope** (`02_PRODUCT_SCOPE.md` line ~283) lists `Store` as the master-data item — not `Customer` and `Store` as two separate items — even though §4's heading is "Customer & Store" and both words appear in the roadmap.
2. **Product Boundaries** section is explicit: *"ERP → Financial transactions," "CRM → Sales pipeline," "EOP → Operational execution."* A `Customer` as a billing/account/contract entity (credit terms, invoicing, sales pipeline) is exactly the kind of concept this document places in ERP/CRM, both explicitly out of scope. Nothing anywhere describes `Customer` as an account distinct from a physical location.
3. **Operational language** throughout `03_TARGET_CUSTOMER.md` consistently says *"daily store visits"* / *"visit monitoring"* — never "customer visits" or "outlet visits" — reinforcing that the unit field operations actually acts on is the physical store.
4. **`Customer Loyalty`** is explicitly excluded under "Out of Scope → Consumer Applications," confirming `Customer` here does not mean an individual consumer either.

**Outlet** is treated as a synonym for `Store` (a common informal FMCG/distribution term for the same physical point of sale), not a separate field or aggregate — no product evidence anywhere describes a `Customer`-owns-many-`Outlet`s hierarchy.

**Modern Trade / General Trade / Store Classification** are not three separate concepts. "Modern Trade"/"General Trade" are industry-standard example *values* of a trade-channel classification; "Store Classification" is that classification concept itself. Collapsed into one classification lookup (§4 below) — not three aggregates, not a hard-coded enum (see §4's reasoning).

**Geolocation** has zero further product elaboration anywhere. Treated as the minimum representation possible: two coordinate columns on `Store` itself, not a separate aggregate.

---

# 2. Smallest Coherent Aggregate

**Iteration 1 = `Store` only.** One aggregate, not `Customer` + `Store` as two, per §1's evidence. No workflow, ordering, visit management, territory assignment, or field-force concept is introduced — matches the explicit instruction and nothing in current product scope asks for more.

---

# 3. Existing Precedent

Reused, unmodified:

- **`Location`/`LocationType`** (`models/location.py`/`location_type.py`) — the `<Entity>` + `<Entity>Type` free-form master-data-lookup shape is the direct structural precedent for `Store`/`StoreType`. **Not reused directly**: `Location`'s own docstring is explicit — *"An organizational place (site/facility), not a postal address"* — it is HR-internal (already wired to `HrEmployee.location_id` throughout the HR workstream) and deliberately has no address/geolocation fields. Conflating a retail outlet with an internal HR facility would misuse both concepts. `Store` is a new, parallel aggregate that mirrors `Location`'s shape, not an extension of it.
- **`JobRequisition`** (`models/job_requisition.py`) — the `code`-unique + `organization_id` (`ON DELETE RESTRICT`) master-data-with-tenant-scope shape, directly mirrored for `Store.organization_id`.
- **Universal master-data convention** (`JobGrade`/`EmploymentType`/`EmploymentStatus`/`LocationType`): `code` (unique), `name`, optional `description` — no `is_active`/status field on this class of simple lookup entity (confirmed absent from all four), so none is added to `Store` or `StoreType` either.

No generic infrastructure (`BaseRepository`, `BaseEntity`, mixins) is modified.

---

# 4. Store Classification

**Persisted master data, mirroring `LocationType` exactly — not a fixed enum.** Reasoning: this codebase already has two established patterns for "kind of X" fields — a closed `StrEnum` (`ApplicationStatus`, `PerformanceReviewStatus`) for a small, universal, business-owned state set, versus a free-form admin-manageable lookup table (`LocationType`, `JobGrade`, `EmploymentType`) for an open-ended category that varies per organization. Real-world retail trade-channel taxonomies vary significantly by business (Modern Trade/General Trade are only the two most common; many distributors also track Wholesale, Horeca, Key Account, B2B, etc.), and the product scope names "Modern Trade"/"General Trade"/"Store Classification" as three separate nouns without ever giving a closed list — picking a fixed enum here would mean inventing the exact value set, which is a business-policy call this discovery cannot make. A free-form lookup table sidesteps that entirely: `StoreType(code, name, description)`, exactly `LocationType`'s shape, with `Store.store_type_id` (`ON DELETE RESTRICT`) — an org's admin can create "Modern Trade"/"General Trade"/anything else as ordinary master data, no code change required either way.

---

# 5. Geolocation

Minimum representation only: `latitude`/`longitude` as nullable `Numeric(9,6)` columns directly on `Store` (matches common ~11cm-precision convention; `Numeric` mirrors this codebase's existing precedent for non-monetary decimal fields, e.g. `payroll-calculation`'s rate columns). Nullable because nothing in product scope mandates it be captured at store creation. No maps/GIS/geocoding/spatial database/external service of any kind — explicitly forbidden by this task and unsupported by any product evidence beyond the single word "Geolocation."

---

# 6. Territory / Region / Area Collision (Mandatory)

**Boundary held, not resolved — and deliberately not touched.** `Store` in Iteration 1 has **no** `territory_id`/`region_id`/`area_id` field and **no** relationship to any such concept. Reasons:

- "Territory Assignment"/"Route Planning" belong to Product Scope §5 "Planning," a separate, unbuilt module — explicitly out of scope for this task.
- The collision itself is real and unresolved: Product Scope §2 "Organization Management" names `Region`/`Area`/`Territory`/`Branch`/`Business Unit`/`Company` as a *business/geographic* hierarchy for field-sales coverage, while the separately-gated **Organization Hierarchy** capability (TD-003, `ARCHITECTURE_DECISION_INDEX.md`/`CAPABILITY_CATALOG.md` Deferred list) is an *employee-reporting/escalation* hierarchy for authorization purposes. Nothing in any product or architecture document states whether these are the same underlying mechanism, related, or entirely independent.
- This discovery does not need to answer that question: `Store` has zero dependency on Territory/Region/Area in Iteration 1, so the collision does not block `Store`. It is flagged here so a future Territory-focused discovery starts from this boundary rather than silently assuming either interpretation, and so this document is not mistaken for having resolved it.

No implementation of Territory/Region/Area is proposed by this document. No reinterpretation of Organization Hierarchy is proposed either.

---

# 7. Authorization

**Role Based (`RequireRole("admin")`)** — direct reuse, no new mechanism. `Store` has no natural owner-employee field (no `employee_id`), the same shape as `JobRequisition`/`PayrollRun`/`PerformanceReview`, all of which resolved identically to admin-only via existing precedent rather than inventing Owner Only or any new policy. `RequireStoreAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]`, mirroring every prior capability's local per-router alias convention exactly.

---

# 8. Lifecycle

**Flat CRUD only.** No status field, no approval workflow, no onboarding/activation semantics, no pipeline. Matches the default assumption and is unopposed by any evidence — nothing in product scope names a store lifecycle.

---

# 9. Relationships

Only two, both to already-existing or newly-proposed simple master data:

- `Store.organization_id` → `organizations.id` (`ON DELETE RESTRICT`) — universal multi-tenancy convention, mirrors every other org-scoped entity.
- `Store.store_type_id` → `store_types.id` (`ON DELETE RESTRICT`) — mirrors `Location.location_type_id`.

No FK to `HrEmployee` (no sales-rep/owner assignment — that is Planning/Field Execution's concern, unbuilt and out of scope), no FK to `Location` (deliberately not reused, §3), no FK to any Territory/Region/Area concept (§6).

---

# 10. Out of Scope

- Territory assignment
- Region/Area/Territory hierarchy (as a `Store` relationship)
- Organization Hierarchy (unrelated, untouched, not reinterpreted)
- Sales visits, Mission, Survey, Check-in/Check-out (Field Execution — separate module)
- Orders, pricing, promotions (E-Commerce/ERP — explicitly out of platform scope)
- Route planning, field-force management (Planning — separate module)
- Customer pipeline / lead / opportunity management (CRM — explicitly out of platform scope)
- Approval workflows on `Store`
- Any GIS/mapping/geocoding infrastructure
- `Store` status/lifecycle

---

# Proposed Files (not yet created — discovery only)

- `docs/architecture/capabilities/store/iteration-1-scope-and-implementation-plan.md` — this document
- `services/api/src/eop_api/models/store_type.py`, `models/store.py`
- `services/api/src/eop_api/repositories/store_type.py`, `repositories/store.py`
- `services/api/src/eop_api/schemas/store_type.py`, `schemas/store.py`
- `services/api/src/eop_api/services/store_type.py`, `services/store.py`
- `services/api/src/eop_api/api/store_types.py`, `api/stores.py`
- `services/api/src/eop_api/main.py` (router registration)
- `services/api/src/eop_api/models/__init__.py` (model registration)
- One Alembic migration: `create_store_types_table` + `create_stores_table`
- `services/api/tests/test_store_type_repository.py`, `test_store_repository.py`, `test_store_type_service.py`, `test_store_service.py`, `test_store_types_api.py`, `test_stores_api.py`

---

# Validation/Test Strategy (for when implementation is authorized)

Mirrors the established convention used for every prior capability this session:

- `StoreType`: repository CRUD tests, service tests (existence/uniqueness), API auth-matrix tests (401/403/2xx admin-only) — mirrors `LocationTypeRepository`/`test_location_types_api.py` shape exactly.
- `Store`: repository CRUD tests (including `store_type_id`/`organization_id` FK existence checks), service tests, API auth-matrix tests — mirrors `test_job_requisitions_api.py` shape.
- `ruff check`/`ruff format --check`/`mypy src` clean; `alembic upgrade head` → `downgrade -1` → `upgrade head` reversibility; targeted tests then full suite, per this session's established validation sequence.

---

# References

- `docs/product/02_PRODUCT_SCOPE.md` §4 (Customer & Store), MVP Scope, Out of Scope (CRM/E-Commerce/Consumer Applications), Product Boundaries
- `docs/product/06_PRODUCT_ROADMAP.md` Phase 3
- `docs/product/03_TARGET_CUSTOMER.md` (operational language: "daily store visits")
- `services/api/src/eop_api/models/location.py`, `location_type.py`, `job_requisition.py` (structural precedent)
- `docs/architecture/00-governance/TECHNICAL_DEBT_REGISTER.md` TD-003, `docs/architecture/10-reference/CAPABILITY_CATALOG.md` (Organization Hierarchy — collision boundary, §6)
