'Deterministic console sessions: pane settings, entry text, event scripts.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

def protocol() -> Any:
    "The frozen ``console/protocol.py``, loaded from the project's own tree."
    from .harness import reference_protocol
    return reference_protocol()


def _write(entry: str, text: str, label: str, full_width: bool = False) -> dict[str, Any]:
    return {"op": "write", "entry": entry, "text": text,
            "full_width": bool(full_width), "label": label}

def _resize(width: int, label: str) -> dict[str, Any]:
    return {"op": "resize", "width": int(width), "label": label}

def _minimum(min_width: int, label: str) -> dict[str, Any]:
    return {"op": "set_min_width", "min_width": int(min_width), "label": label}

def _to(line: int, label: str) -> dict[str, Any]:
    return {"op": "scroll_to", "line": int(line), "label": label}

def _by(lines: int, label: str) -> dict[str, Any]:
    return {"op": "scroll_by", "lines": int(lines), "label": label}

def _follow(label: str) -> dict[str, Any]:
    return {"op": "follow_end", "label": label}

def _clear(label: str) -> dict[str, Any]:
    return {"op": "clear", "label": label}

def _program(pane: Mapping[str, Any], ops: Sequence[Mapping[str, Any]],
             reference_pane: bool = False) -> dict[str, Any]:
    return {"pane": dict(pane), "operations": [dict(op) for op in ops],
            "reference_pane": bool(reference_pane)}


STACK = (
    "03:10:02 worker-3 Traceback most recent call last File dispatch/outbound.py line 214 "
    "in send raise UpstreamTimeout(shipment=88214, waited_ms=30000) "
    "console.errors.UpstreamTimeout shipment 88214 carrier eu-west-2"
)

RECEIPT_STACK = (
    "03:10:12 worker-1 Traceback most recent call last File dispatch/receipts.py line 91 "
    "in flush raise ReceiptRejected(shipment=88410, carrier=eu-west-2, code=HOLD) "
    "console.errors.ReceiptRejected shipment 88410 carrier eu-west-2 hold until an "
    "operator clears it"
)

RELEASE_PANE = {"height": 7, "min_width": 26, "max_entries": 9, "name": "incidents"}

def _release_ops() -> list[dict[str, Any]]:
    'A night shift: an incident opens before the layout runs, a reader stops     halfway up a burst, she stops inside a traceback while the divider moves a     long way, while it is nudged a single column, and while the reading minimum     changes, and the pane is cleared for the next incident..'

    return [
        _write("w-001", "03:09:58 console attached to incident 4812 stream, buffering "
                        "worker output until the layout settles", "opening-line"),
        _write("w-002", "03:09:59 supervisor registered 6 workers on shard eu-west-2 and "
                        "opened the retry channel", "worker-roll-call"),
        _resize(64, "layout-settles"),
        _write("w-003", "03:10:01 worker-3 shipment 88214 upstream timed out after 30s, "
                        "retry 1 of 5", "worker-line-3"),
        _write("w-004", STACK, "stack-trace"),
        _write("w-005", "03:10:03 worker-5 shipment 88301 accepted by carrier", "worker-line-5"),
        _write("w-006", "retry burst begins", "burst-banner", full_width=True),
        _write("w-007", "03:10:04 worker-3 shipment 88214 retry 2 of 5 upstream timed out "
                        "after 30s", "worker-line-7"),
        _write("w-008", "03:10:05 worker-1 shipment 88410 queued behind the retry channel",
               "worker-line-8"),
        _to(3, "read-the-burst"),
        _write("w-009", "03:10:06 worker-3 shipment 88214 retry 3 of 5 upstream timed out "
                        "after 30s", "worker-line-9"),
        _write("w-010", "03:10:07 worker-6 shipment 88512 accepted by carrier", "worker-line-10"),
        _write("w-011", "03:10:08 worker-3 shipment 88214 retry 4 of 5 upstream timed out "
                        "after 30s", "worker-line-11"),
        _write("w-012", "03:10:09 worker-2 shipment 88617 queued behind the retry channel",
               "worker-line-12"),
        _write("w-013", "03:10:11 worker-3 shipment 88214 retry 5 of 5 upstream timed out "
                        "after 30s", "worker-line-13"),
        _write("w-014", "retry burst ends", "burst-end-banner", full_width=True),
        _write("w-015", RECEIPT_STACK, "receipt-trace"),
        _write("w-016", "03:10:13 supervisor moved shard eu-west-2 to the standby carrier and "
                        "reopened the retry channel for the shipments still waiting on a "
                        "receipt", "worker-line-16"),
        _write("w-017", "03:10:15 worker-4 shipment 88214 accepted by the standby carrier once "
                        "the retry channel had drained the shipments queued behind it",
               "worker-line-17"),
        _to(11, "read-the-receipt-trace"),
        _resize(45, "divider-drag"),
        _to(13, "back-into-the-receipt-trace"),
        _resize(46, "divider-nudge"),
        _minimum(58, "widen-the-minimum"),
        _follow("press-follow"),
        _write("w-018", "03:10:16 worker-5 shipment 88301 receipt written", "worker-line-18"),
        _write("w-019", "03:10:17 worker-6 shipment 88512 receipt written", "worker-line-19"),
        _write("w-020", "03:10:18 worker-1 shipment 88410 accepted by the standby carrier",
               "worker-line-20"),
        _write("w-021", "03:10:19 worker-2 shipment 88617 accepted by the standby carrier",
               "worker-line-21"),
        _write("w-022", "03:10:20 worker-3 shipment 88214 receipt written", "worker-line-22"),
        _write("w-023", "03:10:21 supervisor drained the retry channel, 0 shipments left",
               "worker-line-23"),
        _write("w-024", "03:10:22 worker-4 shipment 88720 accepted by the standby carrier",
               "worker-line-24"),
        _by(-2, "wheel-up"),
        _to(999, "back-to-the-newest"),
        _to(9, "hold-the-middle"),
        _minimum(120, "stretch-the-minimum"),
        _minimum(26, "minimum-back-to-normal"),
        _write("w-025", "03:10:24 worker-5 shipment 88801 accepted by the standby carrier",
               "worker-line-25"),
        _write("w-026", "03:10:25 supervisor closed the retry channel for shard eu-west-2",
               "worker-line-26"),
        _to(1, "read-the-top"),
        _resize(80, "wide-divider"),
        _follow("press-follow-again"),
        _clear("next-incident"),
        _write("w-027", "03:11:02 console attached to incident 4813 stream", "next-opening-line"),
        _write("w-028", "03:11:03 supervisor registered 4 workers on shard eu-west-1",
               "next-roll-call"),
    ]


BURST_PANE = {"height": 6, "min_width": 24, "max_entries": 8, "name": "incidents"}
BACK_PANE = {"height": 5, "min_width": 20, "max_entries": 0, "name": "incidents"}
DIVIDER_PANE = {"height": 6, "min_width": 30, "max_entries": 0, "name": "incidents"}
PRUNE_PANE = {"height": 6, "min_width": 24, "max_entries": 5, "name": "incidents"}

def _burst_ops() -> list[dict[str, Any]]:
    ops = [
        _write("r-001", "02:41:50 console attached to incident 4790 stream, buffering worker "
                        "output until the layout settles", "opening-line"),
        _resize(58, "layout-settles"),
    ]
    for index in range(2, 9):
        ops.append(_write(f"r-{index:03d}",
                          f"02:41:5{index} worker-{index} shipment 7{index}104 upstream timed "
                          f"out after 30s, retry {(index - 2) % 5 + 1} of 5",
                          f"worker-line-{index}"))
    ops.append(_to(8, "stop-and-read"))
    for index in range(9, 12):
        ops.append(_write(f"r-{index:03d}",
                          f"02:42:0{index - 8} worker-{index - 8} shipment 7{index}104 queued "
                          f"behind the retry channel and waiting on the carrier",
                          f"worker-line-{index}"))
    return ops

def _back_ops() -> list[dict[str, Any]]:
    ops = [_resize(52, "layout-settles")]
    for index in range(1, 9):
        ops.append(_write(f"s-{index:03d}",
                          f"22:14:0{index} worker-{index} batch 5{index}0 written",
                          f"worker-line-{index}"))
    ops.append(_to(2, "read-back-up"))
    for index in (9, 10):
        ops.append(_write(f"s-{index:03d}",
                          f"22:14:1{index - 9} worker-{index - 8} batch 5{index}0 written",
                          f"worker-line-{index}"))
    ops.append(_to(99, "drag-to-the-bottom"))
    ops.append(_by(-3, "wheel-up"))
    ops.append(_clear("next-incident"))
    for index in (11, 12):
        ops.append(_write(f"s-{index:03d}",
                          f"22:15:0{index - 10} worker-{index - 10} batch 6{index}0 written",
                          f"worker-line-{index}"))
    return ops

DIVIDER_LONG = (
    "19:07:31 worker-2 carrier rejected manifest 40118 with reason "
    "MISSING_CUSTOMS_DECLARATION and the retry channel will not accept it again "
    "until an operator clears the hold"
)

def _divider_ops() -> list[dict[str, Any]]:
    return [
        _write("d-001", "19:07:20 console attached to incident 4655 stream, buffering worker "
                        "output until the layout settles", "opening-line"),
        _resize(72, "layout-settles"),
        _write("d-002", "customs hold on manifest 40118 until an operator clears it",
               "hold-banner", full_width=True),
        _write("d-003", "19:07:28 worker-1 manifest 40117 accepted by carrier", "worker-line-3"),
        _write("d-004", DIVIDER_LONG, "worker-line-4"),
        _write("d-005", "19:07:35 worker-4 manifest 40119 accepted by carrier", "worker-line-5"),
        _write("d-006", "hold cleared", "cleared-banner", full_width=True),
        _write("d-007", "19:07:40 worker-1 manifest 40120 accepted by carrier", "worker-line-7"),
        _write("d-008", "19:07:42 worker-4 manifest 40121 accepted by carrier", "worker-line-8"),
        _write("d-009", "19:07:43 worker-3 manifest 40122 accepted by carrier", "worker-line-9"),
        _to(5, "read-the-hold-line"),
        _resize(70, "divider-nudge"),
        _resize(46, "divider-drag"),
        _write("d-010", "19:07:44 worker-2 manifest 40118 accepted by carrier", "worker-line-10"),
        _to(999, "back-to-the-newest"),
        _minimum(60, "widen-the-minimum"),
        _write("d-011", "19:07:51 supervisor closed incident 4655", "closing-line"),
    ]

PRUNE_LONG = (
    "05:22:09 worker-6 Traceback most recent call last File console/exporter.py line 88 in "
    "flush raise ExportStalled(bundle=9921, pending=417) console.errors.ExportStalled bundle "
    "9921 pending 417 shard ap-south-1 retry in 60s"
)

def _prune_ops() -> list[dict[str, Any]]:
    ops = [_resize(60, "layout-settles")]
    for index in (1, 2, 3):
        ops.append(_write(f"l-{index:03d}",
                          f"05:22:0{index} worker-{index} bundle 99{index}0 flushed to the "
                          f"exporter", f"worker-line-{index}"))
    ops.append(_write("l-004", PRUNE_LONG, "stack-trace"))
    for index in range(5, 11):
        if index == 9:
            ops.append(_to(1, "read-back-up"))
        ops.append(_write(f"l-{index:03d}",
                          f"05:22:{index + 8} worker-{index} bundle 99{index}0 flushed to the "
                          f"exporter", f"worker-line-{index}"))
    return ops

PUBLIC_PROGRAMS: Mapping[str, Any] = {
    "retry-burst": lambda: _program(BURST_PANE, _burst_ops()),
    "scroll-back-to-end": lambda: _program(BACK_PANE, _back_ops(), reference_pane=True),
    "divider-drag": lambda: _program(DIVIDER_PANE, _divider_ops()),
    "long-line-then-prune": lambda: _program(PRUNE_PANE, _prune_ops()),
}

def build_program(profile: str) -> dict[str, Any]:
    'The pane settings and the event script for one console session.'

    if profile == "release":
        return _program(RELEASE_PANE, _release_ops())
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown console session: {profile}")
    return builder()

def entry_table(program: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    'Every entry the session writes, with the text and flag it was written with.'

    return {
        str(op["entry"]): {"text": str(op["text"]), "full_width": bool(op.get("full_width"))}
        for op in program.get("operations", ())
        if str(op.get("op")) == "write"
    }


def _exported_rows(program: Mapping[str, Any], rows: Sequence[tuple[str, int]]
                   ) -> list[dict[str, Any]]:
    'Line counts the incident exporter wrote for named entries at a width.'

    table = entry_table(program)
    reference = protocol()
    out = []
    for entry_id, columns in rows:
        entry = table[entry_id]
        lines = reference.render_entry(entry["text"], columns, 0, entry["full_width"])
        out.append({"entry": entry_id, "columns": columns,
                    "lines_in_the_exported_file": len(lines)})
    return out

def recorded_notes(profile: str) -> dict[str, Any]:
    'What was written down beside the session, with no verdict attached.'

    program = build_program(profile)
    if profile == "retry-burst":
        return {
            "what_the_on_call_wrote_down": {
                "where_i_put_the_bar": "eight rows down, in the middle of the burst",
                "what_happened_next": "three worker lines went in and the entry at the "
                                      "top of the pane was not the one I had stopped on",
                "times_i_touched_the_scrollbar_in_between": 0,
                "entries_the_pane_keeps": int(BURST_PANE["max_entries"]),
            }
        }
    if profile == "scroll-back-to-end":
        return {
            "what_the_toolbar_showed": {
                "badge_in_order": ["Live", "Paused", "Live", "Paused", "Live"],
                "times_the_badge_changed": 4,
                "times_anyone_pressed_follow": 0,
            }
        }
    if profile == "divider-drag":
        return {
            "what_the_exporter_wrote": _exported_rows(
                program,
                (("d-002", 72), ("d-002", 46), ("d-004", 72), ("d-004", 46), ("d-004", 60)),
            ),
            "what_the_on_call_wrote_down": {
                "where_i_stopped": "one row down inside d-004, on the reason the carrier gave",
                "what_happened_when_the_divider_went_narrow": "the pane came back further down "
                                                              "d-004 than I had stopped, with "
                                                              "the time and the worker off the "
                                                              "top, and I could not tell whose "
                                                              "line I was reading any more",
                "what_i_wanted_to_be_looking_at_instead": "d-004 from its first row",
                "times_i_touched_the_scrollbar_in_between": 0,
            },
        }
    if profile == "long-line-then-prune":
        reference = protocol()
        table = entry_table(program)
        kept = [f"l-{index:03d}" for index in range(6, 11)]
        entries = [reference.Entry(entry_id, table[entry_id]["text"],
                                   table[entry_id]["full_width"]) for entry_id in kept]
        extent = reference.content_extent(entries, 60, int(PRUNE_PANE["min_width"]))
        return {
            "what_the_exporter_wrote": {
                "entries_on_the_pane_at_the_end": kept,
                "columns": 60,
                "widest_line": int(extent.widest),
                "lines_in_the_exported_file": int(extent.line_count),
            }
        }
    return {}
