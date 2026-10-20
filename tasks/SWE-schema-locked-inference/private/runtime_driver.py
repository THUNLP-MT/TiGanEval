'Sandboxed candidate runner for the tabular pipeline simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:240]}"


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from pipeline import protocol

    schema_error_type = protocol.SchemaError
    ordinary_matrix_log = protocol.MATRIX_LOG
    ordinary_model_fit = protocol.Model.fit
    frames = {
        str(name): [dict(row) for row in rows]
        for name, rows in dict(payload["frames"]).items()
    }
    records: list[dict[str, Any]] = []
    initial_artifacts = payload.get("initial_artifacts")
    run_directory = protocol.RunDirectory(
        dict(initial_artifacts) if isinstance(initial_artifacts, Mapping) else None
    )
    module = importlib.reload(importlib.import_module("pipeline.pipeline"))
    training_available = bool(payload.get("training_available", True))
    index_offset = int(payload.get("index_offset", 0))

    def frame_for(event: Mapping[str, Any]) -> Any:
        rows = frames[str(event["frame"])]
        index = event.get("row")
        selected = rows if index is None else [rows[int(index)]]
        return protocol.Frame(selected)

    for position, raw_event in enumerate(payload.get("events", ())):
        index = index_offset + position
        event = dict(raw_event)
        kind = str(event.get("type", ""))
        record: dict[str, Any] = {
            "type": kind,
            "index": index,
            "label": str(event.get("label", f"{kind}-{index}")),
        }
        model_inputs: list[dict[str, Any]] = []
        model_fits: list[dict[str, Any]] = []

        class EventMatrixLog:
            'Capture model calls outside the candidate-owned log instance.'

            @property
            def entries(self) -> tuple[dict[str, Any], ...]:
                return tuple(dict(entry) for entry in model_inputs)

            def reset(self) -> None:


                return None

            def record(self, stage: str, matrix: Any) -> None:
                model_inputs.append(
                    {
                        "stage": str(stage),
                        "matrix": [
                            [float(cell) for cell in row]
                            for row in matrix
                        ],
                    }
                )

        protocol.MATRIX_LOG = EventMatrixLog()

        def recorded_model_fit(model: Any, matrix: Any, targets: Any) -> Any:
            'Keep the fit pairing outside candidate-owned telemetry.'

            captured_matrix = [
                [float(cell) for cell in row]
                for row in matrix
            ]
            captured_targets = [float(value) for value in targets]
            fitted = ordinary_model_fit(model, captured_matrix, captured_targets)
            model_fits.append(
                {
                    "matrix": captured_matrix,
                    "targets": captured_targets,
                }
            )
            return fitted

        protocol.Model.fit = recorded_model_fit
        try:
            if kind in ("reset", "reset_second"):
                run_directory = protocol.RunDirectory()


                protocol.Model.fit = ordinary_model_fit
                module = importlib.reload(importlib.import_module("pipeline.pipeline"))
                training_available = True
                record["ok"] = True
            elif kind == "drop_training_frame":
                training_available = False
                record["ok"] = True
            elif kind == "restart_from_artifacts":


                training_available = False
                record["ok"] = True
            elif kind == "fit":
                if not training_available:
                    raise RuntimeError("the training frame is no longer available")
                spec = protocol.FeatureSpec.from_mapping(dict(event.get("spec", {})))
                result = module.fit(frame_for(event), spec, run_directory)
                record["ok"] = True
                record["result"] = json.loads(protocol.canonical_json(result))
            elif kind == "predict":
                record["ok"] = True
                record["result"] = list(module.predict(frame_for(event), run_directory))
            elif kind == "evaluate":
                record["ok"] = True
                record["result"] = json.loads(
                    protocol.canonical_json(module.evaluate(frame_for(event), run_directory))
                )
            elif kind == "export":
                record["ok"] = True
                record["result"] = json.loads(
                    protocol.canonical_json(module.export(run_directory))
                )
            elif kind == "serve":
                row = frames[str(event["frame"])][int(event["row"])]
                record["ok"] = True
                record["result"] = json.loads(
                    protocol.canonical_json(module.serve(dict(row), run_directory))
                )
            elif kind == "describe":
                record["ok"] = True
                record["artifacts"] = run_directory.raw()
            elif kind == "tamper":
                name = str(event["artifact"])
                artifacts = run_directory.raw()
                if name in artifacts:
                    payload_object = json.loads(artifacts[name])
                    if isinstance(payload_object, dict):
                        payload_object[str(event["field"])] = event.get("value")
                    run_directory = protocol.RunDirectory(
                        {**artifacts, name: protocol.canonical_json(payload_object)}
                    )
                    record["tampered"] = True
                else:
                    record["tampered"] = False
                record["ok"] = True
            else:
                record["ok"] = False
                record["error"] = f"unknown event: {kind}"
        except BaseException as exc:
            record["ok"] = False
            record["error"] = _describe(exc)
            record["error_type"] = type(exc).__name__
            record["is_schema_error"] = isinstance(exc, schema_error_type)
        record["model_inputs"] = [dict(entry) for entry in model_inputs]
        record["model_fits"] = [dict(entry) for entry in model_fits]
        record["artifact_names"] = list(run_directory.names())
        protocol.Model.fit = ordinary_model_fit
        protocol.MATRIX_LOG = ordinary_matrix_log
        ordinary_matrix_log.reset()
        records.append(record)

    return {
        "ok": True,
        "records": records,
        "artifacts": run_directory.raw(),
        "training_available": training_available,
    }


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        with redirect_stdout(captured):
            result = dict(run(payload))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    result["candidate_stdout"] = captured.getvalue()[-2000:]
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
