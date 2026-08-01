from enum import StrEnum


class AuditEntityType(StrEnum):
    """Single source of truth for entity types recorded in the audit log."""

    ORGANIZATION = "organization"
    PROJECT = "project"
    EMPLOYEE = "employee"
    ASSIGNMENT = "assignment"
    TASK = "task"
    USER = "user"
    ROLE = "role"


class AuditAction(StrEnum):
    """Single source of truth for actions recorded in the audit log.

    Only actions currently required by callers are listed here; add more as
    future modules need them.
    """

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
