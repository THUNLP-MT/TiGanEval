'Sandboxed runner for one recorded night of the imaging batch.'

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _rows(value: Any) -> Any:
    'A produced tile as plain rows, whatever the pass handed back.'

    reader = getattr(value, "rows", None)
    if callable(reader):
        return [[_scalar(cell) for cell in row] for row in reader()]
    if isinstance(value, (list, tuple)):
        return [[_scalar(cell) for cell in row] for row in value]
    raise TypeError(f"a pass returned {type(value).__name__} instead of a tile")


def _scalar(value: Any) -> Any:
    return value if isinstance(value, (int, float, bool, str)) else repr(value)


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from tilekit import contract
    from tilekit import sweep

    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("passes", ())):
            event = dict(raw_event)
            record: dict[str, Any] = {
                "type": "pass",
                "index": index,
                "label": str(event.get("label", f"pass-{index}")),
            }
            try:
                spec = contract.load_job(dict(event["job"]))
                operands = {
                    str(name): contract.Grid.of(doc["cells"], str(doc.get("dtype", "int32")))
                    for name, doc in dict(event["operands"]).items()
                }
                frame_doc = event.get("frame")
                frame = (
                    None
                    if frame_doc is None
                    else contract.Canvas(
                        str(frame_doc.get("dtype", "int32")), frame_doc["cells"]
                    )
                )
                with contract.trace_writes() as log:
                    try:
                        tile = sweep.run(spec, operands, frame)
                        record["ok"] = True
                        record["cells"] = _rows(tile)
                        record["dtype"] = str(getattr(tile, "dtype", "unknown"))
                    except BaseException as exc:
                        record["ok"] = False
                        record["error"] = _describe(exc)
                record["writes"] = [[int(row), int(col)] for row, col in log]
                if frame is not None:
                    record["frame_after"] = _rows(frame.freeze())
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
                record.setdefault("writes", [])
            records.append(record)

    return {"ok": True, "records": records, "console": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
