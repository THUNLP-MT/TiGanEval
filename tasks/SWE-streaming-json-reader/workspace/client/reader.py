"""Reading JSON values out of a response body.

The current reader is the one the collector uses: it takes the whole body and
splits it into newline-delimited JSON values.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from .protocol import DecodingError, Response, split_content_type


def iter_json(response: Response) -> Iterator[Any]:
    """Yield the JSON values carried by a response body."""

    media_type, _ = split_content_type(response.content_type)
    text = response.read().decode("utf-8")
    if "ndjson" in media_type:
        for line in text.splitlines():
            if line.strip():
                yield json.loads(line)
        return
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DecodingError(str(exc)) from None
    if isinstance(payload, list):
        yield from payload
    else:
        yield payload
