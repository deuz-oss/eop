from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaginationParams:
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: list[T]
    total: int
    offset: int
    limit: int
