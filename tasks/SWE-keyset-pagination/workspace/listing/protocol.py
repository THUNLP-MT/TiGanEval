"""Runtime contract for the catalogue listing service.

The phone apps, the storefront and the reporting integration all read the
catalogue through this module, so the row type, the ordering rule, the token
codec and the two response envelopes below are the same for every one of them.
Nothing here touches a clock, a network or a random number: the catalogue is
whatever the store holds when a call arrives.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
from pathlib import Path
import tomllib
from typing import Any, Iterable, Mapping, Sequence


#: The column that identifies a catalogue row, and the columns a client may
#: sort on. Merchandising adds a sortable column about twice a year.
ID_FIELD = "item_id"
SORTABLE_FIELDS: tuple[str, ...] = ("price_cents", "stock", "name")
DIRECTIONS: tuple[str, ...] = ("asc", "desc")

#: The reasons the listing endpoints refuse a request. They reach the apps as
#: the ``reason`` of a refusal and the apps switch on them, so they are part of
#: the release and not free text.
UNUSABLE_ORDER = "unusable_order"
UNUSABLE_CURSOR = "unusable_cursor"
REFUSAL_REASONS: tuple[str, ...] = (UNUSABLE_ORDER, UNUSABLE_CURSOR)


class ListingError(RuntimeError):
    """Base of everything the listing service raises."""


class OrderError(ListingError):
    """The sort a client asked for is not one the catalogue has."""


class CursorError(ListingError):
    """A continuation token could not be read back."""


@dataclass(frozen=True, slots=True)
class Item:
    """One catalogue row as the store holds it."""

    item_id: str
    values: Mapping[str, Any]

    def value(self, field: str) -> Any:
        """The row's value in one sortable column."""

        try:
            return self.values[str(field)]
        except KeyError:
            raise OrderError(f"the catalogue has no column {field!r}") from None


class Store:
    """The catalogue rows this process holds.

    :meth:`items` hands them back in the order merchandising added them, which
    is not an order any client asks for; :func:`list_all` is what puts them in
    one. Merchandising adds, withdraws and reprices rows all day, so the rows a
    call sees are the rows that are here when it arrives.
    """

    def __init__(self, rows: Iterable[Item] = ()):
        self._rows: dict[str, Item] = {item.item_id: item for item in rows}

    def items(self) -> tuple[Item, ...]:
        return tuple(self._rows.values())

    def add(self, item: Item) -> None:
        self._rows[item.item_id] = item

    def remove(self, item_id: str) -> None:
        self._rows.pop(str(item_id), None)

    def reprice(self, item_id: str, **values: Any) -> None:
        """Replace some of one row's column values, keeping its place."""

        current = self._rows.get(str(item_id))
        if current is None:
            return
        merged = {**dict(current.values), **{str(k): v for k, v in values.items()}}
        self._rows[str(item_id)] = Item(item_id=current.item_id, values=merged)

    def get(self, item_id: str) -> Item | None:
        return self._rows.get(str(item_id))

    def __len__(self) -> int:
        return len(self._rows)


def parse_order(order_by: str) -> tuple[tuple[str, str], ...]:
    """Read ``"price_cents:asc,stock:desc"`` as (column, direction) pairs.

    A pair with no direction sorts ascending. An unknown column or direction
    raises :class:`OrderError`.
    """

    pairs: list[tuple[str, str]] = []
    for part in str(order_by).split(","):
        text = part.strip()
        if not text:
            continue
        field, _, direction = text.partition(":")
        field = field.strip()
        direction = (direction.strip() or "asc").lower()
        if field not in SORTABLE_FIELDS:
            raise OrderError(f"the catalogue cannot be sorted by {field!r}")
        if direction not in DIRECTIONS:
            raise OrderError(f"{direction!r} is not a sort direction")
        pairs.append((field, direction))
    if not pairs:
        raise OrderError("a sort names at least one column")
    return tuple(pairs)


def order_text(order: Sequence[tuple[str, str]]) -> str:
    """The normalised text of a parsed sort.

    Two requests ask for the same sort exactly when this is equal for both, so
    ``"price_cents"`` and ``"price_cents:asc"`` are the same sort.
    """

    return ",".join(f"{field}:{direction}" for field, direction in order)


def list_all(store: Store, order_by: str) -> tuple[Item, ...]:
    """The whole catalogue in the order a client asked for.

    Rows are ordered by each named column in its direction, taken left to
    right. Rows that are equal on every named column come back in ascending
    ``item_id`` order, so the catalogue has one order under a given sort and
    not several. This is the order the storefront, the apps and the reporting
    integration all mean when they say "the catalogue".
    """

    order = parse_order(order_by)
    rows = sorted(store.items(), key=lambda item: item.item_id)
    for field, direction in reversed(order):
        rows = sorted(rows, key=lambda item: item.value(field), reverse=direction == "desc")
    return tuple(rows)


def encode_cursor(payload: Mapping[str, Any]) -> str:
    """Pack a continuation payload into the token a client carries.

    The token is URL-safe text so it survives a query string, a bookmark and a
    retry. What goes in the payload is the listing service's own business; this
    only packs and unpacks it.
    """

    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: str) -> dict[str, Any]:
    """Unpack a token a client sent back, or raise :class:`CursorError`.

    Unreadable text or a decoded value that is not an object raises. This is
    a Base64 JSON codec, not encryption or authentication: a readable edited
    object can decode successfully. The endpoint validates its payload.
    """

    text = str(token)
    padded = text + "=" * (-len(text) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise CursorError(f"the continuation token could not be read: {exc}") from None
    if not isinstance(value, dict):
        raise CursorError("a continuation token carries an object")
    return dict(value)


def page(items: Sequence[Item], next_cursor: str | None = None) -> dict[str, Any]:
    """The envelope a listing call hands back when it served rows.

    ``next_cursor`` is the token the client sends to continue. Leaving it out
    is what tells the client it has reached the end of the list.
    """

    body: dict[str, Any] = {"status": "ok", "items": tuple(items)}
    if next_cursor is not None:
        body["next_cursor"] = str(next_cursor)
    return body


def rejected(reason: str) -> dict[str, Any]:
    """The envelope a listing call hands back when it will not serve a page.

    The apps read ``reason`` and act on it: they drop what they are holding and
    ask again from the top of the list. An exception out of a listing call is
    not this -- it reaches the client as a server fault and the app shows the
    error screen instead of the list.
    """

    return {"status": "rejected", "reason": str(reason)}


def is_refusal(result: Mapping[str, Any]) -> bool:
    """Whether a listing result is a refusal rather than a page of rows."""

    return isinstance(result, Mapping) and str(result.get("status")) == "rejected"


def items_of(result: Mapping[str, Any]) -> tuple[Item, ...]:
    """The rows a listing result served, in the order it served them."""

    if is_refusal(result):
        return ()
    if not isinstance(result, Mapping) or "items" not in result:
        raise ListingError(f"a listing result carries items or a refusal, not {result!r}")
    rows = tuple(result["items"])
    for row in rows:
        if not isinstance(row, Item):
            raise ListingError(f"a listing result serves catalogue rows, not {row!r}")
    return rows


def cursor_of(result: Mapping[str, Any]) -> str | None:
    """The continuation token a listing result carried, if it carried one."""

    if is_refusal(result) or not isinstance(result, Mapping):
        return None
    value = result.get("next_cursor")
    return None if value is None else str(value)


def catalogue_summary(store: Store, order_by: str) -> dict[str, Any]:
    """What the apps' sort menu reads before it asks for the first page."""

    try:
        order = parse_order(order_by)
    except OrderError:
        return rejected(UNUSABLE_ORDER)
    return {"status": "ok", "total": len(store), "order": order_text(order)}


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    """What one listing service is configured with, from ``service.toml``."""

    default_limit: int = 20
    max_page_size: int = 50


def load_config(path: str | Path | None = None) -> ServiceConfig:
    """Read ``service.toml``; the file next to the package by default."""

    target = Path(path) if path is not None else Path(__file__).resolve().parents[1] / "service.toml"
    settings = tomllib.loads(Path(target).read_text(encoding="utf-8")).get("listing", {})
    return ServiceConfig(
        default_limit=int(settings.get("default_limit", 20)),
        max_page_size=int(settings.get("max_page_size", 50)),
    )
