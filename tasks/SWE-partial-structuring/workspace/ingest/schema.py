"""The columns the provider's nightly file carries, and our fallbacks for them.

A fallback is what we publish when the file does not give us a column. It is
our value, not the provider's, which is why the fallbacks live here beside the
columns rather than in the reading itself.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import Field, Record, build


POSTAL_ADDRESS = Record(
    "PostalAddress",
    (
        Field("line1", scalar="text"),
        Field("city", scalar="text"),
        Field("postcode", scalar="postcode", default="XX0 0XX"),
        Field("country", scalar="text", default="GB"),
    ),
)

#: What the shipping label carries when the file gives us no usable address.
UNKNOWN_ADDRESS = build(
    POSTAL_ADDRESS,
    {"line1": "no address on file", "city": "unknown", "postcode": "XX0 0XX", "country": "GB"},
)

ORDER_LINE = Record(
    "OrderLine",
    (
        Field("sku", scalar="text"),
        Field("quantity", scalar="count"),
        Field("unit_pence", scalar="pence"),
    ),
)


def _ledger_key(values: Mapping[str, Any]) -> str:
    """The billing table's own key, computed from the record we publish."""

    return f"{values['account_ref']}/{values['tier']}"


SUBSCRIBER = Record(
    "Subscriber",
    (
        Field("account_ref", scalar="text"),
        Field("joined_on", scalar="day"),
        Field("tier", scalar="text", default="standard"),
        Field("credit_pence", scalar="pence", default=0),
        Field("locale", scalar="text", default="en-GB"),
        Field("address", record=POSTAL_ADDRESS, default=UNKNOWN_ADDRESS),
        Field("lines", element=ORDER_LINE, default=()),
        Field("ledger_key", init=False, derive=_ledger_key),
    ),
)


__all__ = ("ORDER_LINE", "POSTAL_ADDRESS", "SUBSCRIBER", "UNKNOWN_ADDRESS")
