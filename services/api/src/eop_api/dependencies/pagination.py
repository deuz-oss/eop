from typing import Annotated

from fastapi import Depends, Query

from eop_api.schemas.pagination import PaginationParams

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def get_pagination_params(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0)] = DEFAULT_LIMIT,
) -> PaginationParams:
    """Shared offset/limit query params. Limits above `MAX_LIMIT` are clamped."""
    return PaginationParams(offset=offset, limit=min(limit, MAX_LIMIT))


Pagination = Annotated[PaginationParams, Depends(get_pagination_params)]
