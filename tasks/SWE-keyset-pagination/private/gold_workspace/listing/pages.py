"""The listing endpoint the apps and the storefront page the catalogue with.

A page is cut out of the catalogue by value, never by position: the token a
page hands back carries the place that page reached -- every column of the sort
plus the row's own id -- together with the sort it was made under, so the next
request finds its place in whatever the catalogue holds by then. Nothing about
a token is remembered here, so any instance of the service can serve it.

A list is asked for by sort. A request that names none has no catalogue
order behind it -- the store holds its rows in the order the warehouse
added them -- so it comes back through the same refusal `catalogue_summary`
answers one with, and the app starts the list again with a sort on it.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    ID_FIELD,
    UNUSABLE_CURSOR,
    UNUSABLE_ORDER,
    CursorError,
    Item,
    OrderError,
    ServiceConfig,
    Store,
    decode_cursor,
    encode_cursor,
    list_all,
    order_text,
    page,
    parse_order,
    rejected,
)

#: The key the token records its sort under, alongside the sort's own columns.
SORT_FIELD = "sort"

Order = Sequence[tuple[str, str]]


def after(item: Item, boundary: Mapping[str, Any], order: Order) -> bool:
    """Whether `item` comes after the place a token recorded.

    The sort's columns are compared left to right in their own directions, and
    rows equal on all of them are separated by the id the catalogue orders ties
    with. That last comparison is what makes the place a boundary: without it a
    row sharing the boundary's price is either served twice or never served.
    """

    for field, direction in order:
        left, right = item.value(field), boundary[field]
        if left != right:
            return left > right if direction == "asc" else left < right
    return str(item.item_id) > str(boundary[ID_FIELD])


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
        """One page of the catalogue, and the place it reached."""

        if order_by is None:
            return rejected(UNUSABLE_ORDER)
        try:
            order = parse_order(order_by)
        except OrderError:
            return rejected(UNUSABLE_ORDER)
        boundary = None
        if cursor is not None:
            if offset is not None:
                return rejected(UNUSABLE_CURSOR)
            try:
                boundary = self._place(cursor, order)
            except CursorError:
                return rejected(UNUSABLE_CURSOR)
        size = self._page_size(limit)
        rows = list_all(self.store, order_by)
        if boundary is not None:
            try:
                rows = [item for item in rows if after(item, boundary, order)]
            except TypeError:
                return rejected(UNUSABLE_CURSOR)
        elif offset is not None:
            rows = rows[int(offset):]
        # One row past the page, so the continuation says whether anything is
        # left rather than whether the page happened to fill.
        window = list(rows[: size + 1])
        more = len(window) > size
        del window[size:]
        token = self._mint(window[-1], order) if more and window else None
        return page(window, token)

    def _page_size(self, limit: int | None) -> int:
        asked = int(limit) if limit is not None else int(self.config.default_limit)
        return max(1, min(asked, int(self.config.max_page_size)))

    def _place(self, cursor: str, order: Order) -> Mapping[str, Any]:
        """The place a token records, or a refusal if this is not our token."""

        payload = decode_cursor(str(cursor))
        wanted = {field for field, _ in order} | {ID_FIELD, SORT_FIELD}
        if set(payload) != wanted:
            raise CursorError("the token does not carry this list's place")
        if str(payload[SORT_FIELD]) != order_text(order):
            raise CursorError("the token was made under another sort")
        return payload

    def _mint(self, item: Item, order: Order) -> str:
        """The place this page reached, packed for the client to send back."""

        payload: dict[str, Any] = {field: item.value(field) for field, _ in order}
        payload[ID_FIELD] = item.item_id
        payload[SORT_FIELD] = order_text(order)
        return encode_cursor(payload)
