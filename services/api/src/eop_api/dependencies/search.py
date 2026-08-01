from typing import Annotated

from fastapi import Depends, Query

from eop_api.schemas.search import SearchParams


def get_search_params(q: Annotated[str | None, Query(max_length=255)] = None) -> SearchParams:
    """Shared free-text search query param (`q`). Blank/missing values mean no search."""
    return SearchParams(q=q)


Search = Annotated[SearchParams, Depends(get_search_params)]
