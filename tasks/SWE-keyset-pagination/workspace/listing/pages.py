"""The listing endpoint the apps and the storefront page the catalogue with.

`find` sorts the catalogue, cuts a window out of it and hands the window back.
Offset paging is what the clients use today. The `cursor` argument is the start
of something better: a page hands back a token, the service remembers where
that token had got to, and a client that sends the token back carries on from
there instead of counting rows.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import ServiceConfig, Store, encode_cursor, page, parse_order


class Catalogue:
    """One listing service over one catalogue store."""

    def __init__(self, store: Store, config: ServiceConfig):
        self.store = store
        self.config = config
        # Where each token we have handed out had got to.
        self._marks: dict[str, int] = {}
        self._minted = 0

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
        rows = self._ordered(order_by)
        start = int(offset or 0)
        if cursor is not None:
            start = self._marks.get(str(cursor), 0)
        window = rows[start : start + size]
        token = None
        if len(window) == size:
            token = self._mint(start + len(window))
        return page(window, token)

    def _ordered(self, order_by: str | None) -> tuple[Any, ...]:
        """The catalogue in the order the caller asked for."""

        if not order_by:
            return self.store.items()
        field, direction = parse_order(order_by)[0]
        return tuple(
            sorted(
                self.store.items(),
                key=lambda item: item.value(field),
                reverse=direction == "desc",
            )
        )

    def _mint(self, reached: int) -> str:
        """A token for the client, and a note of where it had got to."""

        self._minted += 1
        token = encode_cursor({"mark": f"m{self._minted:04d}"})
        self._marks[token] = int(reached)
        return token
