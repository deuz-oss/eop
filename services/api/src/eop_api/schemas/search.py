from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchParams:
    """Generic free-text search term, shared across modules.

    `q` carries the raw client-supplied value as-is; `text` is the
    normalized form repositories should query with -- `None` for a missing,
    empty, or whitespace-only query, so callers don't need to special-case
    blank strings before deciding whether to filter.
    """

    q: str | None = None

    @property
    def text(self) -> str | None:
        if self.q is None:
            return None
        stripped = self.q.strip()
        return stripped or None


@dataclass(frozen=True, slots=True)
class FilterParams:
    """Generic equality filters, keyed by field name.

    This object only carries values; it does not know which fields are
    valid. Repositories decide which keys are honored by passing an
    allowlist mapping into `BaseRepository`'s filter helpers, so a client
    can never reach an arbitrary SQL column.
    """

    values: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.values)
