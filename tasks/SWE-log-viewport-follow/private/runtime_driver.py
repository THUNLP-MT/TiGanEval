'Sandboxed runner for one incident-console session.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _apply(pane: Any, op: Mapping[str, Any]) -> None:
    kind = str(op.get("op", ""))
    if kind == "write":
        pane.write(str(op["entry"]), str(op["text"]), bool(op.get("full_width", False)))
    elif kind == "resize":
        pane.resize(int(op["width"]))
    elif kind == "set_min_width":
        pane.set_min_width(int(op["min_width"]))
    elif kind == "scroll_to":
        pane.scroll_to(int(op["line"]))
    elif kind == "scroll_by":
        pane.scroll_by(int(op["lines"]))
    elif kind == "follow_end":
        pane.follow_end()
    elif kind == "clear":
        pane.clear()
    else:
        raise ValueError(f"unknown console event: {kind}")


def _state(pane: Any, seen: int) -> dict[str, Any]:
    'Everything the console reads back off the pane after one event.'

    strips = [
        [str(entry_id), [str(line) for line in lines]]
        for entry_id, lines in pane.strips()
    ]
    extent = pane.extent()
    posted = [
        {
            "pane": str(record.pane),
            "is_following_end": bool(record.is_following_end),
            "scroll_y": int(record.scroll_y),
            "max_scroll_y": int(record.max_scroll_y),
        }
        for record in tuple(pane.messages())[seen:]
    ]
    return {
        "scroll_y": int(pane.scroll_y),
        "max_scroll_y": int(pane.max_scroll_y),
        "following": bool(pane.is_following_end),
        "extent_widest": int(extent.widest),
        "extent_line_count": int(extent.line_count),
        "strips": strips,
        "posted": posted,
    }


def _plain_trace(payload: Mapping[str, Any], protocol: Any) -> list[dict[str, Any]]:
    'The same script driven through the plain pane the console still ships.'

    settings = dict(payload.get("pane", {}))
    plain = protocol.PlainPane(height=int(settings.get("height", 8)), name="plain")
    rows: list[dict[str, Any]] = []
    for op in payload.get("operations", ()):
        kind = str(op.get("op", ""))
        if kind == "write":
            plain.write(str(op["entry"]), str(op["text"]))
        elif kind == "scroll_to":
            plain.scroll_to(int(op["line"]))
        elif kind == "scroll_by":
            plain.scroll_by(int(op["lines"]))
        elif kind == "follow_end":
            plain.follow_end()
        elif kind == "clear":
            plain.clear()
        else:
            continue
        rows.append({
            "label": str(op.get("label", kind)),
            "event": kind,
            "scroll_y": int(plain.scroll_y),
            "max_scroll_y": int(plain.max_scroll_y),
            "badge": "Live" if plain.is_following_end else "Paused",
            "line_count": len(plain.lines()),
        })
    return rows


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from console import protocol

    settings = dict(payload.get("pane", {}))
    module = importlib.reload(importlib.import_module("console.rich_pane"))
    pane = module.RichPane(
        height=int(settings.get("height", 8)),
        min_width=int(settings.get("min_width", 0)),
        max_entries=int(settings.get("max_entries", 0)),
        name=str(settings.get("name", "rich")),
    )
    rows: list[dict[str, Any]] = []
    seen = 0
    captured = io.StringIO()
    with redirect_stdout(captured):
        for index, raw in enumerate(payload.get("operations", ())):
            op = dict(raw)
            row: dict[str, Any] = {
                "index": index,
                "event": str(op.get("op", "")),
                "label": str(op.get("label", f"event-{index}")),
                "entry": op.get("entry"),
            }
            try:
                _apply(pane, op)
                row.update(_state(pane, seen))
                seen = len(tuple(pane.messages()))
                row["ok"] = True
            except BaseException as exc:
                row["ok"] = False
                row["error"] = _describe(exc)
            rows.append(row)
    return {
        "ok": True,
        "pane": settings,
        "operations": rows,
        "reference": _plain_trace(payload, protocol) if payload.get("reference_pane") else None,
        "stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
