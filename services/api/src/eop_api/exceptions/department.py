class DepartmentOrganizationMismatchError(Exception):
    """Raised when a referenced department does not belong to the expected organization.

    Shared across every service that pairs a `department_id` with an
    `organization_id` (Position, Team, and future modules) -- this is one
    cross-entity business rule, not a per-entity not-found case, so unlike
    those it is not duplicated locally in each service module.
    """
