"""The listing endpoint the apps and the storefront page the catalogue with.

Paging by cursor instead of by offset, the way the mobile team asked for it: a
page hands back the last row's id, packed so a client cannot pick it apart, and
a client that sends it back gets the rows that come after that id. Nothing is
remembered between requests, so a customer scrolling while merchandising works
in the catalogue no longer sees the list shift under them.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    ID_FIELD,
    Item,
    ServiceConfig,
    Store,
    decode_cursor,
    encode_cursor,
    list_all,
    page,
)


class Catalogue:
    """One listing service over one catalogue store."""

    def __init__(self, store: Store, config: ServiceConfig):
        self.store = store
        self.config = config

    def find(
        self,
        *,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        cursor: str | None = None,
    ) -> Mapping[str, Any]:
        """One page of the catalogue."""

        size = int(limit if limit is not None else self.config.default_limit)
        rows: Sequence[Item] = (
            list_all(self.store, order_by) if order_by
            else sorted(self.store.items(), key=lambda item: item.item_id)
        )
        if cursor is not None:
            last = str(decode_cursor(str(cursor))[ID_FIELD])
            rows = [item for item in rows if str(item.item_id) > last]
        elif offset is not None:
            rows = list(rows)[int(offset):]
        window = list(rows)[:size]
        token = None
        if len(window) == size and window:
            token = encode_cursor({ID_FIELD: window[-1].item_id})
        return page(window, token)
