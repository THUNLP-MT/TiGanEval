'Deterministic, sandboxed analysis of one pipeline workspace.'

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from ..workspace.pipeline.protocol import (
    ARTIFACT_VERSION,
    DESCRIPTION_ARTIFACT,
    DROP_REASONS,
    Model,
    MODEL_ARTIFACT,
    SCHEMA_ARTIFACT,
    SCHEMA_KEYS,
    canonical_value,
    feature_schema_problems,
    rejected_response,
)
from .workload import build_frames, build_program


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("pipeline/pipeline.py", "pipeline/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-schema-lock-",
    timeout=60.0,
)

REQUIRED_ARTIFACTS = (SCHEMA_ARTIFACT, DESCRIPTION_ARTIFACT, MODEL_ARTIFACT)


MISSING_ARTIFACT_KINDS: Mapping[str, str] = {
    SCHEMA_ARTIFACT: "schema_artifact_missing",
    DESCRIPTION_ARTIFACT: "description_artifact_missing",
    MODEL_ARTIFACT: "model_artifact_missing",
}


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "seed": 31, "scale": 1}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "training-run": {"profile": "training", "seed": 3, "scale": 1},
    "serving-requests": {"profile": "consumers", "seed": 9, "scale": 1},
    "bad-request-drill": {"profile": "refusals", "seed": 15, "scale": 1},
    "artifact-reuse-drill": {"profile": "artifacts", "seed": 23, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "persisted_schema_completeness": "schema_failures",
    "consistent_inference_across_consumers": "consumer_failures",
    "schema_violation_refusal": "refusal_failures",
    "caller_contract_error_reporting": "contract_failures",
    "stable_artifact_reuse": "artifact_failures",
}

_INVALID_SPEC_LABELS = {
    "fit-unknown-include": "names a column the training frame does not have",
    "fit-unknown-exclude": "names a column the training frame does not have",
    "fit-duplicate-include": "lists the same column twice",
    "fit-duplicate-exclude": "lists the same column twice",
    "fit-target-in-exclude": "names the target column",
    "fit-target-in-include": "names the target column",
    "fit-empty-selection": "leaves the model no input columns",
}

_REJECTED = rejected_response("x")
REJECT_STATUS = int(_REJECTED["status"])
DETAIL_KEY = next(iter(dict(_REJECTED["body"])))
ACCEPT_STATUS = 200


EXPECTED_DROPS: Mapping[str, tuple[str, ...]] = {
    "excluded": ("record_id",),
    "constant": ("pipeline_version",),
    "duplicate": ("amount_copy", "region_alias"),
}


NIGHTLY_CONFIGURATION = "target=target, exclude=record_id, drop_constant, drop_duplicate"


EXPECTED_DROP_RECORD = (
    "record_id is excluded by the configuration, pipeline_version never changes, "
    "and amount_copy and region_alias repeat amount and region"
)


ALIAS_COLUMNS = "amount_copy and region_alias, which repeat amount and region"


EXTRA_REQUEST_COLUMNS = "another_extra and unrelated_column"


PREDICTION_KEYS = (
    "predict returns the number itself, evaluate reports mean_prediction, and the "
    "endpoint puts prediction in its body"
)


MODEL_INPUT_RECORD = "model_input_rows"


INVALID_CONFIGURATIONS = (
    "unknown, repeated, target-touching, or empty feature selections"
)


REFUSED_SERVE_LABELS = "the requests whose fitted feature sources are absent or disagree"


VERSION_ARTIFACT = SCHEMA_ARTIFACT


CANDIDATE_MODULE = "pipeline/pipeline.py"


def _by_label(records: Sequence[Mapping[str, Any]], label: str) -> Mapping[str, Any] | None:
    return next((record for record in records if str(record.get("label")) == label), None)


def _latest_by_label_before(
    records: Sequence[Mapping[str, Any]],
    label: str,
    before: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    'The latest matching record in the same timeline before ``before``.'

    limit = int(before.get("index", -1))
    candidates = [
        record
        for record in records
        if str(record.get("label")) == label
        and int(record.get("index", -1)) < limit
    ]
    return max(candidates, key=lambda record: int(record.get("index", -1)), default=None)


def _refused(record: Mapping[str, Any] | None) -> bool:
    'Did this operation decline to produce an answer at all?'

    return record is not None and not record.get("ok")


def _schema_error(record: Mapping[str, Any] | None) -> bool:
    'Did a refusal use the frozen caller-visible exception contract?'

    return _refused(record) and bool((record or {}).get("is_schema_error"))


def _error(record: Mapping[str, Any] | None) -> str:
    return str((record or {}).get("error") or "no result at all")


def _shown(value: Any) -> str:
    'One measured result as the owner would repeat it back.'

    if value is None:
        return "nothing"
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return str(value[0])
    if isinstance(value, Mapping) or isinstance(value, (list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _as_mapping(value: Any) -> dict[str, Any]:
    return {str(key): item for key, item in value.items()} if isinstance(value, Mapping) else {}


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


def _matrix(record: Mapping[str, Any], stage: str = "predict") -> list[list[float]] | None:
    for entry in record.get("model_inputs", ()):
        if str(entry.get("stage")) == stage:
            return [[float(cell) for cell in row] for row in entry.get("matrix", ())]
    return None


def _fit_calls(record: Mapping[str, Any] | None) -> list[tuple[list[list[float]], list[float]]]:
    'Successful ``Model.fit`` arguments captured outside candidate telemetry.'

    calls: list[tuple[list[list[float]], list[float]]] = []
    for entry in (record or {}).get("model_fits", ()):
        try:
            matrix = [
                [float(cell) for cell in row]
                for row in entry.get("matrix", ())
            ]
            targets = [float(value) for value in entry.get("targets", ())]
        except (AttributeError, TypeError, ValueError):
            continue
        calls.append((matrix, targets))
    return calls


def _training_targets(training_rows: Sequence[Mapping[str, Any]]) -> list[float]:
    targets: list[float] = []
    for row in training_rows:
        value = canonical_value(row.get("target"))
        if not isinstance(value, float):
            raise ValueError("the private training target is not numeric")
        targets.append(float(value))
    return targets


def _target_aligned_fit_calls(
    fit: Mapping[str, Any] | None,
    training_rows: Sequence[Mapping[str, Any]],
) -> list[tuple[list[list[float]], list[float]]]:
    expected = sorted(_training_targets(training_rows))
    return [
        (matrix, targets)
        for matrix, targets in _fit_calls(fit)
        if len(matrix) == len(training_rows)
        and len(targets) == len(training_rows)
        and sorted(targets) == expected
    ]


def _model_parts(value: Any) -> tuple[list[float], float]:
    model = dict(value)
    return ([float(item) for item in model["weights"]], float(model["bias"]))


def _fitted_parts(
    matrix: Sequence[Sequence[float]], targets: Sequence[float]
) -> tuple[list[float], float]:
    return _model_parts(Model().fit(matrix, targets).as_dict())


def _artifact_model_parts(artifacts: Mapping[str, str]) -> tuple[list[float], float]:
    return _model_parts(json.loads(artifacts[MODEL_ARTIFACT]))


def _artifact_prediction(
    artifacts: Mapping[str, str], matrix: Sequence[Sequence[float]]
) -> list[float] | None:
    "Recompute the frozen model's answer without touching candidate telemetry."

    try:
        weights, bias = _artifact_model_parts(artifacts)
        rows = [[float(cell) for cell in row] for row in matrix]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if any(len(row) != len(weights) for row in rows):
        return None
    return [
        round(bias + sum(weight * cell for weight, cell in zip(weights, row)), 9)
        for row in rows
    ]


def _training_score_matrix(
    records: Sequence[Mapping[str, Any]], row_count: int
) -> list[list[float]] | None:
    matrix: list[list[float]] = []
    for index in range(row_count):
        record = _by_label(records, f"predict-training-row-{index}")
        scored = None if record is None or not record.get("ok") else _matrix(record)
        if scored is None or len(scored) != 1:
            return None
        matrix.append(list(scored[0]))
    return matrix


def _matching_fit_call(
    artifacts: Mapping[str, str],
    calls: Sequence[tuple[list[list[float]], list[float]]],
) -> tuple[list[list[float]], list[float]] | None:
    try:
        actual = _artifact_model_parts(artifacts)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    for matrix, targets in calls:
        try:
            if _fitted_parts(matrix, targets) == actual:
                return (matrix, targets)
        except (IndexError, TypeError, ValueError):
            continue
    return None


def _columns(row: Mapping[str, Any] | None) -> str:
    return "no columns at all" if not row else ", ".join(sorted(str(name) for name in row))


def _request_rows(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    'The raw row each labelled operation was handed, by label.'

    frames = dict(payload.get("frames", {}))
    rows: dict[str, Mapping[str, Any]] = {}
    for event in payload.get("events", ()):
        position = event.get("row")
        if position is None:
            continue
        frame = list(frames.get(str(event.get("frame")), ()))
        if int(position) < len(frame):
            rows.setdefault(str(event.get("label")), dict(frame[int(position)]))
    return rows


def _artifacts(record: Mapping[str, Any] | None) -> dict[str, str]:
    return {
        str(name): str(text)
        for name, text in _as_mapping((record or {}).get("artifacts", {})).items()
    }


def _incomplete_schema(problems: Sequence[str], keys_written: str) -> dict[str, Any]:
    joined = "; ".join(str(problem) for problem in problems)
    return {
        "kind": "schema_artifact_incomplete",
        "problem": joined,
        "keys_written": keys_written or "nothing",
        "expected_keys": ", ".join(SCHEMA_KEYS),
        "observed": f"{SCHEMA_ARTIFACT} does not stand on its own: {joined}",
    }


def _weight_count(artifacts: Mapping[str, str]) -> int:
    try:
        model = json.loads(artifacts[MODEL_ARTIFACT])
        return len(list(dict(model)["weights"]))
    except (KeyError, TypeError, ValueError):
        return 0


def _expected_layout(training_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    "The nightly specification applied to the private frame's own columns."

    available: list[str] = []
    for row in training_rows:
        for raw_name in row:
            name = str(raw_name)
            if name not in available:
                available.append(name)
    selected = [name for name in available if name not in ("record_id", "target")]
    canonical = {
        name: [canonical_value(row.get(name)) for row in training_rows]
        for name in selected
    }
    constant = [
        name for name in selected if len({repr(value) for value in canonical[name]}) <= 1
    ]
    remaining = [name for name in selected if name not in constant]
    aliases: dict[str, list[str]] = {}
    duplicate: list[str] = []
    kept: list[str] = []
    for name in remaining:
        origin = next(
            (existing for existing in kept if canonical[existing] == canonical[name]),
            None,
        )
        if origin is None:
            kept.append(name)
        else:
            aliases.setdefault(origin, []).append(name)
            duplicate.append(name)
    return {
        "target": "target",
        "input_features": kept,
        "duplicate_feature_aliases": aliases,
        "dropped_features": {
            "excluded": list(EXPECTED_DROPS["excluded"]),
            "constant": sorted(constant),
            "duplicate": sorted(duplicate),
        },
    }


def _normalised_aliases(value: Any) -> dict[str, set[str]] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return {
            str(name): {str(alias) for alias in aliases}
            for name, aliases in value.items()
            if aliases
        }
    except TypeError:
        return None


def _normalised_drops(value: Any) -> dict[str, set[str]] | None:
    if not isinstance(value, Mapping) or {str(key) for key in value} != set(DROP_REASONS):
        return None
    try:
        return {
            reason: {str(name) for name in value[reason]}
            for reason in DROP_REASONS
        }
    except TypeError:
        return None


def _layout_failure(
    schema: Mapping[str, Any], training_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    expected = _expected_layout(training_rows)
    actual_features = [str(name) for name in schema.get("input_features", ())]
    expected_features = list(expected["input_features"])
    actual_aliases = _normalised_aliases(schema.get("duplicate_feature_aliases"))
    expected_aliases = _normalised_aliases(expected["duplicate_feature_aliases"])
    actual_drops = _normalised_drops(schema.get("dropped_features"))
    expected_drops = _normalised_drops(expected["dropped_features"])
    target_matches = str(schema.get("target")) == str(expected["target"])
    feature_membership_matches = (
        len(actual_features) == len(set(actual_features))
        and set(actual_features) == set(expected_features)
    )
    if (
        feature_membership_matches
        and actual_aliases == expected_aliases
        and actual_drops == expected_drops
        and target_matches
    ):
        return None

    names: set[str] = set(actual_features) ^ set(expected_features)
    if len(actual_features) != len(set(actual_features)):
        names.update(
            name for name in actual_features if actual_features.count(name) > 1
        )
    if actual_aliases != expected_aliases:
        for name in set(actual_aliases or {}) | set(expected_aliases or {}):
            actual_values = (actual_aliases or {}).get(name, set())
            expected_values = (expected_aliases or {}).get(name, set())
            if actual_values != expected_values:
                names.add(name)
                names.update(actual_values ^ expected_values)
    if actual_drops != expected_drops:
        for reason in DROP_REASONS:
            actual_values = (actual_drops or {}).get(reason, set())
            expected_values = (expected_drops or {}).get(reason, set())
            names.update(actual_values ^ expected_values)
    if not target_matches:
        names.add(str(schema.get("target") or "target"))
    columns = ", ".join(sorted(names)) or "the recorded feature layout"
    return {
        "kind": "schema_drop_record_wrong",
        "columns": columns,
        "expected_drops": EXPECTED_DROP_RECORD,
        "observed": (
            f"{SCHEMA_ARTIFACT} classifies {columns} inconsistently with the "
            "nightly frame and feature configuration"
        ),
    }


def _declared_unknown_values(
    encoding: Any, raw_value: Any
) -> tuple[list[float] | None, str, str | None]:
    'Read an unknown-category declaration without prescribing its JSON key.'

    if not isinstance(encoding, Mapping):
        return (None, "nothing", "is not an encoding object")
    if "unknown" in encoding:
        declarations = [encoding.get("unknown")]
    else:
        declarations = [
            value
            for key, value in encoding.items()
            if str(key) not in {"kind", "levels"}
        ]
    if not declarations:
        return (None, "nothing", "does not declare how an unknown category is encoded")

    values: list[float] = []

    def collect(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            values.append(float(value))
        elif isinstance(value, str) and value.casefold() == "length":
            canonical = canonical_value(raw_value)
            values.append(float(len(str(canonical))))
        elif isinstance(value, Mapping):
            for nested in value.values():
                collect(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                collect(nested)

    for declaration in declarations:
        collect(declaration)
    shown = _shown(declarations[0] if len(declarations) == 1 else declarations)
    return (values or None, shown, None)


def _unknown_encoding_failures(
    schema: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'Check that persisted unseen-category semantics match actual scoring.'

    request_rows = _request_rows(payload)
    incomplete: list[str] = []
    failures: list[dict[str, Any]] = []
    for case, feature in _UNSEEN_CASES:
        label = f"predict-{case}"
        record = _by_label(records, label)
        event_schema: Mapping[str, Any] = schema
        if record is not None:
            described = _latest_by_label_before(records, "artifacts-baseline", record)
            try:
                candidate_schema = json.loads(_artifacts(described)[SCHEMA_ARTIFACT])
            except (KeyError, TypeError, json.JSONDecodeError):
                candidate_schema = None
            if isinstance(candidate_schema, Mapping):
                event_schema = candidate_schema
        features = [str(name) for name in event_schema.get("input_features", ())]
        encodings = _as_mapping(event_schema.get("encoding", {}))
        if feature not in features:
            continue
        matrix = None if record is None or not record.get("ok") else _matrix(record)
        row = request_rows.get(label, {})
        declared, declared_text, problem = _declared_unknown_values(
            encodings.get(feature), row.get(feature)
        )
        if problem is not None:
            incomplete.append(f"encoding for {feature} {problem}")
            continue
        if declared is None or matrix is None or len(matrix) != 1:


            continue
        position = features.index(feature)
        if position >= len(matrix[0]):
            continue
        used = float(matrix[0][position])
        if used not in declared:
            failures.append(
                {
                    "kind": "schema_encoding_disagrees_with_scoring",
                    "feature": feature,
                    "declared_unknown": declared_text,
                    "model_input": _shown(used),
                    "artifact": SCHEMA_ARTIFACT,
                    "observed": (
                        f"{SCHEMA_ARTIFACT} declares {declared_text} for an unknown {feature}, "
                        f"but scoring put {used} in that feature's model-input position"
                    ),
                }
            )
    if incomplete:
        failures.insert(
            0,
            _incomplete_schema(
                incomplete,
                ", ".join(sorted(str(key) for key in schema)),
            ),
        )
    return failures


def _model_difference(
    artifacts: Mapping[str, str],
    fit: Mapping[str, Any],
    training_rows: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> tuple[str, str] | None:
    'Return an owner-safe location and description of a fitted-model mismatch.'

    fit_matrix = _matrix(fit, "fit")
    if fit_matrix is None:
        return (
            "the training input",
            "the training timeline records no matrix handed to Model.fit",
        )
    if len(fit_matrix) != len(training_rows):
        return (
            "the training row count",
            "the recorded fit matrix and the training frame have different row counts",
        )
    try:
        actual_weights, actual_bias = _artifact_model_parts(artifacts)
        targets = _training_targets(training_rows)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return (
            MODEL_ARTIFACT,
            "the artifact cannot be compared as a model with weights and a bias",
        )

    captured = _fit_calls(fit)
    aligned = _target_aligned_fit_calls(fit, training_rows)
    if captured and not aligned:
        return (
            "the training targets",
            "the recorded Model.fit call did not receive one target from every training row",
        )

    expected_parts: list[tuple[list[float], float]] = []
    for matrix, fit_targets in aligned:
        try:
            expected_parts.append(_fitted_parts(matrix, fit_targets))
        except (IndexError, TypeError, ValueError):
            continue


    if not captured:
        scoring_matrix = _training_score_matrix(records, len(training_rows))
        if scoring_matrix is not None:
            try:
                expected_parts.append(_fitted_parts(scoring_matrix, targets))
            except (IndexError, TypeError, ValueError):
                pass

    if not expected_parts:
        return (
            "the recorded fit",
            "the training timeline cannot establish a fitted model for the run's rows and targets",
        )
    actual = (actual_weights, actual_bias)
    if actual in expected_parts:
        return None
    expected_weights, expected_bias = expected_parts[-1]
    if actual_bias != expected_bias:
        return ("the bias", "the artifact and the recorded fit disagree at the bias")
    for index, (actual, expected) in enumerate(zip(actual_weights, expected_weights)):
        if actual != expected:
            return (
                f"weight {index}",
                f"the artifact and the recorded fit disagree at weight {index}",
            )
    if len(actual_weights) != len(expected_weights):
        return (
            "the weight count",
            "the artifact and the recorded fit contain different numbers of weights",
        )
    return None


def _schema_failures(
    records: Sequence[Mapping[str, Any]], payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    training_rows = [
        dict(row) for row in dict(payload.get("frames", {})).get("train", ())
    ]
    fit = _by_label(records, "fit-baseline")
    described = _by_label(records, "artifacts-baseline")
    export = _by_label(records, "export-baseline")
    if fit is None or not fit.get("ok"):
        return [
            {
                "kind": "baseline_fit_failed",
                "step": "fit-baseline",
                "configuration": NIGHTLY_CONFIGURATION,
                "error": _error(fit),
                "observed": (
                    f"the nightly configuration ({NIGHTLY_CONFIGURATION}) did not train: "
                    f"{_error(fit)}"
                ),
            }
        ]

    artifacts = _artifacts(described)
    left = ", ".join(sorted(artifacts)) or "nothing"
    missing = [
        {
            "kind": MISSING_ARTIFACT_KINDS[name],
            "missing_artifact": name,
            "left": left,
            "observed": f"the finished run left {left} and no {name}",
        }
        for name in REQUIRED_ARTIFACTS
        if name not in artifacts
    ]
    if missing:
        return missing

    try:
        schema = json.loads(artifacts[SCHEMA_ARTIFACT])
    except json.JSONDecodeError as exc:
        return [_incomplete_schema([f"it cannot be read back as JSON at all ({exc})"], "")]
    problems = feature_schema_problems(schema)
    if problems:
        keys = ", ".join(sorted(str(key) for key in dict(schema))) if isinstance(schema, Mapping) else ""
        return [_incomplete_schema(problems, keys)]

    try:
        description = json.loads(artifacts[DESCRIPTION_ARTIFACT])
    except json.JSONDecodeError:
        description = None
    features = [str(name) for name in schema["input_features"]]
    described_features = (
        [str(name) for name in description.get("input_features", ())]
        if isinstance(description, Mapping)
        else []
    )
    if described_features != features:
        return [
            {
                "kind": "description_disagrees_with_schema",
                "description_input_features": ", ".join(described_features) or "nothing",
                "schema_input_features": ", ".join(features),
                "observed": (
                    f"{DESCRIPTION_ARTIFACT} says the model reads "
                    f"{', '.join(described_features) or 'nothing'} while {SCHEMA_ARTIFACT} "
                    f"says {', '.join(features)}"
                ),
            }
        ]

    failures: list[dict[str, Any]] = []
    weights = _weight_count(artifacts)
    if weights != len(features):
        failures.append(
            {
                "kind": "schema_does_not_describe_model_input",
                "model_weights": weights,
                "schema_width": len(features),
                "model_artifact": MODEL_ARTIFACT,
                "observed": (
                    f"{MODEL_ARTIFACT} carries {weights} weights while {SCHEMA_ARTIFACT} "
                    f"names {len(features)} input columns: {', '.join(features)}"
                ),
            }
        )
    if export is not None and not export.get("ok"):


        failures.append(
            {
                "kind": "export_failed_at_baseline",
                "step": "export-baseline",
                "error": _error(export),
                "observed": f"the export step did not run: {_error(export)}",
            }
        )
    elif export is not None:
        result = _as_mapping(export.get("result", {}))
        width = result.get("input_width")
        exported = _as_string_list(result.get("features", ()))


        if int(width if isinstance(width, int) else -1) != len(features):
            failures.append(
                {
                    "kind": "export_disagrees_with_schema",
                    "export_width": _shown(width),
                    "schema_width": len(features),
                    "exported_features": ", ".join(exported) or "none named",
                    "reported_key": "input_width",
                    "observed": (
                        f"the export reports {width} inputs ({', '.join(exported) or 'none named'}) "
                        f"while {SCHEMA_ARTIFACT} names {len(features)}: {', '.join(features)}"
                    ),
                }
            )
        elif exported != features:
            failures.append(
                {
                    "kind": "export_lists_different_features",
                    "exported_features": ", ".join(exported) or "nothing",
                    "schema_features": ", ".join(features),
                    "shared_width": len(features),
                    "reported_key": "features",
                    "observed": (
                        f"the export names {', '.join(exported)} while {SCHEMA_ARTIFACT} names "
                        f"{', '.join(features)}, both {len(features)} columns wide"
                    ),
                }
            )

    layout_failure = _layout_failure(schema, training_rows)
    if layout_failure is not None:
        failures.append(layout_failure)

    failures.extend(_unknown_encoding_failures(schema, records, payload))

    model_difference = _model_difference(artifacts, fit, training_rows, records)
    if model_difference is not None:
        model_component, model_issue = model_difference
        failures.append(
            {
                "kind": "model_artifact_not_fitted",
                "model_artifact": MODEL_ARTIFACT,
                "model_component": model_component,
                "model_issue": model_issue,
                "observed": (
                    f"{MODEL_ARTIFACT} cannot be reconciled with the recorded training "
                    f"at {model_component}: {model_issue}"
                ),
            }
        )
    return failures


def _prediction(consumer: str, record: Mapping[str, Any]) -> Any:
    result = record.get("result")
    if consumer == "predict":
        return list(result or ())[:1]
    if consumer == "evaluate":
        return [_as_mapping(result).get("mean_prediction")]
    return [_as_mapping(_as_mapping(result).get("body", {})).get("prediction")]


def _model_answer_failure(
    label: str,
    consumer: str,
    record: Mapping[str, Any],
    artifacts: Mapping[str, str],
) -> dict[str, Any] | None:
    matrix = _matrix(record)
    expected = (
        None
        if matrix is None or len(matrix) != 1
        else _artifact_prediction(artifacts, matrix)
    )
    returned = _prediction(consumer, record)
    if expected is None or returned == expected:
        return None
    return {
        "kind": "consumer_prediction_not_from_model",
        "label": label,
        "consumer": consumer,
        "returned": _shown(returned),
        "model_prediction": _shown(expected),
        "observed": (
            f"{label} returned {_shown(returned)}, while the persisted model applied "
            f"to that call's recorded input returns {_shown(expected)}"
        ),
    }


def _input_difference(training: Sequence[float], scoring: Sequence[float]) -> str:
    if len(training) != len(scoring):
        return f"the recorded widths are {len(training)} and {len(scoring)}"
    position = next(
        (
            index
            for index, (training_value, scoring_value) in enumerate(
                zip(training, scoring)
            )
            if training_value != scoring_value
        ),
        None,
    )
    return (
        "the two recorded model-input rows differ"
        if position is None
        else f"the first differing input position is {position + 1}"
    )


def _training_scoring_record(
    training_input: Any,
    scoring_input: Any,
    input_difference: str,
) -> dict[str, Any]:
    return {
        "kind": "training_scoring_inputs_disagree",
        "training_input": _shown(training_input),
        "scoring_input": _shown(scoring_input),
        "input_difference": input_difference,
        "observed": (
            "the model-input records made while fitting and while re-scoring the same "
            f"training records do not agree: {input_difference}; "
            f"training={_shown(training_input)}; scoring={_shown(scoring_input)}"
        ),
    }


def _training_scoring_failure(
    records: Sequence[Mapping[str, Any]], payload: Mapping[str, Any]
) -> dict[str, Any] | None:
    'Compare every training record without assuming fit-row list order.'

    training_rows = [
        dict(row) for row in dict(payload.get("frames", {})).get("train", ())
    ]
    fit = _by_label(records, "fit-baseline")
    fit_matrix = _matrix(fit or {}, "fit")
    first_scored_record = _by_label(records, "predict-training-row-0")
    first_scored_matrix = (
        None
        if first_scored_record is None or not first_scored_record.get("ok")
        else _matrix(first_scored_record)
    )
    first_scored = (
        None
        if first_scored_matrix is None or len(first_scored_matrix) != 1
        else first_scored_matrix[0]
    )
    if fit is None or not fit.get("ok") or fit_matrix is None:
        return _training_scoring_record(
            None,
            first_scored,
            "the training-side model input was not recorded",
        )

    captured = _fit_calls(fit)
    aligned = _target_aligned_fit_calls(fit, training_rows)
    if captured and not aligned:
        return _training_scoring_record(
            fit_matrix[0] if fit_matrix else None,
            first_scored,
            "the fit call did not carry one target from every training record",
        )

    if aligned:
        artifacts = _artifacts(_by_label(records, "artifacts-baseline"))
        chosen = _matching_fit_call(artifacts, aligned) or aligned[-1]
        training_matrix, fit_targets = chosen
        for index, row in enumerate(training_rows):
            target = _training_targets((row,))[0]
            training_vectors = [
                vector
                for vector, fit_target in zip(training_matrix, fit_targets)
                if fit_target == target
            ]
            record = _by_label(records, f"predict-training-row-{index}")
            scored_matrix = (
                None if record is None or not record.get("ok") else _matrix(record)
            )
            scoring_vector = (
                None
                if scored_matrix is None or len(scored_matrix) != 1
                else scored_matrix[0]
            )
            if not training_vectors:
                return _training_scoring_record(
                    None,
                    scoring_vector,
                    "one training record has no fitted model-input row",
                )
            if scoring_vector is None:
                return _training_scoring_record(
                    training_vectors[0],
                    None,
                    "the scoring-side model input was not recorded for one training record",
                )
            if scoring_vector not in training_vectors:
                return _training_scoring_record(
                    training_vectors[0],
                    scoring_vector,
                    _input_difference(training_vectors[0], scoring_vector),
                )
        return None


    scoring_matrix = _training_score_matrix(records, len(training_rows))
    if scoring_matrix is None:
        return _training_scoring_record(
            fit_matrix[0] if fit_matrix else None,
            first_scored,
            "the scoring-side model inputs were not recorded for every training record",
        )
    training_rows_by_value = Counter(json.dumps(row) for row in fit_matrix)
    scoring_rows_by_value = Counter(json.dumps(row) for row in scoring_matrix)
    if training_rows_by_value == scoring_rows_by_value:
        return None
    training_only = next(
        (
            row
            for row in fit_matrix
            if training_rows_by_value[json.dumps(row)]
            > scoring_rows_by_value[json.dumps(row)]
        ),
        fit_matrix[0] if fit_matrix else None,
    )
    scoring_only = next(
        (
            row
            for row in scoring_matrix
            if scoring_rows_by_value[json.dumps(row)]
            > training_rows_by_value[json.dumps(row)]
        ),
        scoring_matrix[0] if scoring_matrix else None,
    )
    return _training_scoring_record(
        training_only,
        scoring_only,
        "the training and scoring collections contain different model-input rows",
    )


def _consumer_failures(
    records: Sequence[Mapping[str, Any]],
    rows: Mapping[str, Mapping[str, Any]],
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    vectors: dict[str, Any] = {}
    model_artifacts = _artifacts(_by_label(records, "artifacts-baseline"))
    for index in range(5):
        inputs: dict[str, Any] = {}
        predictions: dict[str, Any] = {}
        answered: list[str] = []
        for consumer in ("predict", "evaluate", "serve"):
            label = f"{consumer}-request-{index}"
            record = _by_label(records, label)
            if record is None or not record.get("ok"):
                failures.append(
                    {
                        "kind": "consumer_call_failed",
                        "label": label,
                        "request_columns": _columns(rows.get(label)),
                        "alias_columns": ALIAS_COLUMNS,
                        "error": _error(record),
                        "observed": (
                            f"{consumer} raised on the request carrying "
                            f"{_columns(rows.get(label))}: {_error(record)}"
                        ),
                    }
                )
                continue
            answered.append(consumer)
            matrix = _matrix(record)
            inputs[consumer] = None if matrix is None else matrix[0]
            predictions[consumer] = _prediction(consumer, record)
            model_failure = _model_answer_failure(
                label, consumer, record, model_artifacts
            )
            if model_failure is not None:
                failures.append(model_failure)
        for failure in failures:
            if failure["kind"] == "consumer_call_failed" and failure["label"].endswith(
                f"-request-{index}"
            ):
                failure["answered_by"] = ", ".join(answered) or "no consumer"
        if len({json.dumps(value, sort_keys=True) for value in inputs.values()}) > 1:
            failures.append(
                {
                    "kind": "consumer_inputs_disagree",
                    "request_columns": _columns(rows.get(f"predict-request-{index}")),
                    "paths": ", ".join(sorted(inputs)),
                    "recorded_in": MODEL_INPUT_RECORD,
                    "observed": (
                        "one record became different model inputs on different paths: "
                        + "; ".join(f"{name}={value}" for name, value in sorted(inputs.items()))
                    ),
                }
            )
        elif len({json.dumps(value, sort_keys=True) for value in predictions.values()}) > 1:
            failures.append(
                {
                    "kind": "consumer_predictions_disagree",
                    "request_columns": _columns(rows.get(f"predict-request-{index}")),
                    "answers": "; ".join(
                        f"{name} {_shown(value)}" for name, value in sorted(predictions.items())
                    ),
                    "reported_as": PREDICTION_KEYS,
                    "observed": (
                        "one record came back with different scores: "
                        + "; ".join(f"{name}={value}" for name, value in sorted(predictions.items()))
                    ),
                }
            )
        if inputs:
            vectors[f"request-{index}"] = next(iter(inputs.values()))


    for case, _feature in _UNSEEN_CASES:
        for consumer in ("predict", "evaluate", "serve"):
            label = f"{consumer}-{case}"
            record = _by_label(records, label)
            if record is None or not record.get("ok"):
                continue
            event_artifacts = _artifacts(
                _latest_by_label_before(records, "artifacts-baseline", record)
            ) or model_artifacts
            model_failure = _model_answer_failure(
                label, consumer, record, event_artifacts
            )
            if model_failure is not None:
                failures.append(model_failure)
    training_rows = dict(payload.get("frames", {})).get("train", ())
    for index, _row in enumerate(training_rows):
        label = f"predict-training-row-{index}"
        record = _by_label(records, label)
        if record is None or not record.get("ok"):
            continue
        event_artifacts = _artifacts(
            _latest_by_label_before(records, "artifacts-baseline", record)
        ) or model_artifacts
        model_failure = _model_answer_failure(label, "predict", record, event_artifacts)
        if model_failure is not None:
            failures.append(model_failure)

    training_scoring = _training_scoring_failure(records, payload)
    if training_scoring is not None:
        failures.append(training_scoring)
    if failures:
        return failures

    shapes = {json.dumps(value, sort_keys=True) for value in vectors.values()}
    if len(shapes) > 1:
        spread = sorted(
            (label, _columns(rows.get(f"predict-{label}"))) for label in vectors
        )
        failures.append(
            {
                "kind": "request_form_changes_input",
                "shapes": len(shapes),
                "sent": len(vectors),
                "extra_columns": EXTRA_REQUEST_COLUMNS,
                "observed": (
                    "the same customer became "
                    f"{len(shapes)} different model inputs across the shapes callers send: "
                    + "; ".join(f"[{columns}] -> {vectors[label]}" for label, columns in spread)
                ),
            }
        )
    export = _by_label(records, "export-after-requests")
    if export is not None and export.get("ok") and vectors:
        width = _as_mapping(export.get("result", {})).get("input_width")
        served = next(iter(vectors.values()))
        served_width = None if served is None else len(served)
        if int(width if isinstance(width, int) else -1) != (served_width or -1):
            failures.append(
                {
                    "kind": "export_disagrees_with_consumers",
                    "export_width": _shown(width),
                    "consumer_width": _shown(served_width),
                    "reported_key": "input_width",
                    "observed": (
                        f"the export reports {width} inputs while the serving path builds "
                        f"{served_width}"
                    ),
                }
            )
    return failures


_REFUSAL_CASES = (
    ("missing-feature", ("amount", "amount_copy"), "missing_source_not_refused"),
    ("conflicting-aliases", ("amount", "amount_copy"), "conflicting_sources_not_refused"),
    (
        "conflicting-region-sources",
        ("region", "region_alias"),
        "conflicting_sources_not_refused",
    ),
)

_UNSEEN_CASES = (
    ("unseen-category", "region"),
    ("unseen-tier", "tier"),
)


def _unusable_records(rows: Mapping[str, Mapping[str, Any]]) -> str:
    'The records the fitted space cannot represent, as measured values.'

    conflicting = rows.get("predict-conflicting-aliases", {})
    return (
        "a record carrying neither amount nor amount_copy, a record whose amount "
        f"says {conflicting.get('amount')} while its amount_copy says "
        f"{conflicting.get('amount_copy')}, and another record whose duplicate "
        "category sources disagree"
    )


def _refusal_failures(
    records: Sequence[Mapping[str, Any]], rows: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    unusable = _unusable_records(rows)
    for case, columns, kind in _REFUSAL_CASES:
        label = f"predict-{case}"
        record = _by_label(records, label)
        row = rows.get(label, {})
        stated = ", ".join(
            f"{column}={row[column]!r}" for column in columns if column in row
        )
        for consumer in ("predict", "evaluate", "serve"):
            measured_label = f"{consumer}-{case}"
            measured = _by_label(records, measured_label)
            result = _as_mapping((measured or {}).get("result", {}))
            serve_rejected = (
                consumer == "serve"
                and measured is not None
                and measured.get("ok")
                and result.get("status") == REJECT_STATUS
            )
            if (
                measured is not None
                and (_refused(measured) or serve_rejected)
                and _matrix(measured) is not None
            ):
                failures.append(
                    {
                        "kind": "model_ran_on_refused_input",
                        "label": measured_label,
                        "recorded_in": MODEL_INPUT_RECORD,
                        "observed": (
                            "the model was given a design matrix for an unusable record; "
                            f"the run lists {MODEL_INPUT_RECORD} for {measured_label}"
                        ),
                    }
                )
        if not _refused(record):
            failures.append(
                {
                    "kind": kind,
                    "label": label,
                    "columns": ", ".join(columns),
                    "stated": stated or "no value at all",
                    "unusable_records": unusable,
                    "returned": _shown(None if record is None else record.get("result")),
                    "observed": (
                        f"the batch path scored a record it cannot represent "
                        f"({stated or 'no value at all'}) and returned "
                        f"{None if record is None else record.get('result')}"
                    ),
                }
            )
            continue
        message = str(record.get("error", ""))
        missing_columns = [column for column in columns if column not in message]
        if missing_columns:
            failures.append(
                {
                    "kind": "refusal_missing_column_names",
                    "label": label,
                    "columns": ", ".join(columns),
                    "missing_columns": ", ".join(missing_columns),
                    "message": message or "nothing at all",
                    "observed": (
                        f"the refusal reads {message!r} and does not name "
                        f"{', '.join(missing_columns)}"
                    ),
                }
            )
    for case, column in _UNSEEN_CASES:
        label = f"predict-{case}"
        unseen = _by_label(records, label)
        unseen_row = rows.get(label, {})
        if unseen is None or not unseen.get("ok"):
            value = str(unseen_row.get(column, "")) or "not set at all"
            failures.append(
                {
                    "kind": "known_input_wrongly_refused",
                    "label": label,
                    "category_column": column,
                    "category_value": value,
                    "error": _error(unseen),
                    "observed": (
                        f"a record whose {column} is {value!r}, a category absent from the "
                        f"training frame, was turned away: {_error(unseen)}"
                    ),
                }
            )

    for label, complaint in _INVALID_SPEC_LABELS.items():
        record = _by_label(records, label)
        if (
            _refused(record)
            and (_matrix(record or {}, "fit") is not None or _fit_calls(record))
        ):
            failures.append(
                {
                    "kind": "model_ran_on_invalid_specification",
                    "label": label,
                    "complaint": complaint,
                    "recorded_in": MODEL_INPUT_RECORD,
                    "observed": (
                        f"the invalid configuration at {label}, which {complaint}, reached "
                        "Model.fit before the training operation finished"
                    ),
                }
            )
        if not _refused(record):
            failures.append(
                {
                    "kind": "invalid_specification_accepted",
                    "label": label,
                    "complaint": complaint,
                    "configurations": INVALID_CONFIGURATIONS,
                    "trained": _shown(None if record is None else record.get("result")),
                    "observed": (
                        f"a feature list that {complaint} produced a model instead of being "
                        f"turned down: {None if record is None else record.get('result')}"
                    ),
                }
            )
    return failures


def _contract_failures(
    records: Sequence[Mapping[str, Any]], rows: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for case, columns, _kind in _REFUSAL_CASES:
        label = f"serve-{case}"
        record = _by_label(records, label)
        if record is None or not record.get("ok"):
            failures.append(
                {
                    "kind": "serve_raised_instead_of_reporting",
                    "label": label,
                    "requests_checked": REFUSED_SERVE_LABELS,
                    "error": _error(record),
                    "observed": (
                        f"the endpoint raised instead of answering: {_error(record)}"
                    ),
                }
            )
            continue
        result = _as_mapping(record.get("result"))
        status = result.get("status")
        if int(status if isinstance(status, int) else -1) != REJECT_STATUS:


            scored = int(status if isinstance(status, int) else -1) == ACCEPT_STATUS
            failures.append(
                {
                    "kind": (
                        "serve_scored_a_refusable_record" if scored else "serve_status_wrong"
                    ),
                    "label": label,
                    "status": _shown(status),
                    "expected_status": REJECT_STATUS,
                    "observed": (
                        f"the endpoint answered status {status} for a record it cannot score; "
                        f"the contract for a refused record is status {REJECT_STATUS}"
                    ),
                }
            )
            continue
        detail = str(_as_mapping(result.get("body", {})).get(DETAIL_KEY, ""))
        missing_columns = [column for column in columns if column not in detail]
        if missing_columns:
            failures.append(
                {
                    "kind": "serve_detail_missing_columns",
                    "label": label,
                    "columns": ", ".join(columns),
                    "missing_columns": ", ".join(missing_columns),
                    "body_detail": detail or "nothing at all",
                    "observed": (
                        f"the endpoint answered status {REJECT_STATUS} with {detail!r}, "
                        f"which does not name {', '.join(missing_columns)}"
                    ),
                }
            )

    for case, _columns_unused, _kind in _REFUSAL_CASES:
        for consumer in ("predict", "evaluate"):
            label = f"{consumer}-{case}"
            record = _by_label(records, label)
            if _refused(record) and not _schema_error(record):
                failures.append(
                    {
                        "kind": "refusal_wrong_exception_type",
                        "label": label,
                        "error_type": str((record or {}).get("error_type") or "unknown"),
                        "error": _error(record),
                        "observed": (
                            f"{label} refused the record as "
                            f"{(record or {}).get('error_type') or 'an unknown error type'} "
                            "instead of SchemaError"
                        ),
                    }
                )

        label = f"evaluate-{case}"
        record = _by_label(records, label)
        if record is not None and record.get("ok"):
            failures.append(
                {
                    "kind": "evaluate_did_not_refuse",
                    "label": label,
                    "nightly_report_key": "mean_prediction",


                    "returned": _shown(record.get("result")),
                    "observed": (
                        "the nightly evaluation returned "
                        f"{record.get('result')} for a record it cannot honestly score"
                    ),
                }
            )

    valid_labels = [f"serve-{case}" for case, _column in _UNSEEN_CASES]
    valid_labels.extend(f"serve-request-{index}" for index in range(5))
    for label in valid_labels:
        record = _by_label(records, label)
        if record is None or not record.get("ok"):
            failures.append(
                {
                    "kind": "serve_failed_valid_request",
                    "label": label,
                    "request_columns": _columns(rows.get(label)),
                    "error": _error(record),
                    "observed": (
                        f"the endpoint produced no response for the valid request {label}: "
                        f"{_error(record)}"
                    ),
                }
            )
            continue
        result = _as_mapping(record.get("result"))
        status = result.get("status")
        prediction = _as_mapping(result.get("body", {})).get("prediction")
        if int(status if isinstance(status, int) else -1) != ACCEPT_STATUS or not isinstance(
            prediction, (int, float)
        ):
            failures.append(
                {
                    "kind": "serve_rejected_valid_request",
                    "label": label,
                    "request_columns": _columns(rows.get(label)),
                    "answer": _shown(result.get("body")),
                    "observed": (
                        f"the endpoint answered status {status} for a request carrying "
                        f"{_columns(rows.get(label))}: {result.get('body')}"
                    ),
                }
            )
    return failures


def _artifact_failures(
    records: Sequence[Mapping[str, Any]], rows: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    first = _by_label(records, "artifacts-first")
    second = _by_label(records, "artifacts-second")
    shuffled = _by_label(records, "artifacts-shuffled")
    if first is None or second is None or shuffled is None:
        return [
            {
                "kind": "artifacts_not_reproducible",
                "compared": "artifacts-first against artifacts-second",
                "differing_artifacts": "all of them",
                "observed": "one of the repeat runs left no artifacts to compare",
            }
        ]
    first_artifacts = _artifacts(first)
    second_artifacts = _artifacts(second)
    if first_artifacts != second_artifacts:
        differing = sorted(
            name
            for name in set(first_artifacts) | set(second_artifacts)
            if first_artifacts.get(name) != second_artifacts.get(name)
        )
        failures.append(
            {
                "kind": "artifacts_not_reproducible",
                "compared": "artifacts-first against artifacts-second",
                "differing_artifacts": ", ".join(differing) or "all of them",
                "observed": (
                    "two runs over the same rows and the same configuration wrote different "
                    f"{', '.join(differing) or 'artifact sets'}"
                ),
            }
        )
    shuffled_artifacts = _artifacts(shuffled)
    if first_artifacts.get(SCHEMA_ARTIFACT) != shuffled_artifacts.get(SCHEMA_ARTIFACT):
        failures.append(
            {
                "kind": "schema_depends_on_row_order",
                "label": "artifacts-shuffled",
                "artifact": SCHEMA_ARTIFACT,
                "observed": (
                    "the same rows in a different order, the run labelled artifacts-shuffled, "
                    f"produced a different {SCHEMA_ARTIFACT}"
                ),
            }
        )
    try:
        first_model = _artifact_model_parts(first_artifacts)
        shuffled_model = _artifact_model_parts(shuffled_artifacts)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        first_model = None
        shuffled_model = None
    if first_model is not None and shuffled_model is not None and first_model != shuffled_model:
        failures.append(
            {
                "kind": "model_depends_on_row_order",
                "label": "artifacts-shuffled",
                "artifact": MODEL_ARTIFACT,
                "observed": (
                    "the same training records and targets in a different row order "
                    f"produced a different {MODEL_ARTIFACT}"
                ),
            }
        )

    tampered = _by_label(records, "tamper-schema-version")


    carries_version = bool((tampered or {}).get("tampered"))
    version_kind = (
        "unsupported_artifact_version_accepted"
        if carries_version
        else "unversioned_artifacts_accepted"
    )
    declared = "version 99" if carries_version else "no version this build can check"
    for label in (
        "predict-after-tamper",
        "evaluate-after-tamper",
        "export-after-tamper",
    ):
        record = _by_label(records, label)
        if _refused(record):
            if not _schema_error(record):
                failures.append(
                    {
                        "kind": "artifact_refusal_wrong_exception_type",
                        "label": label,
                        "declared_version": declared,
                        "error_type": str((record or {}).get("error_type") or "unknown"),
                        "error": _error(record),
                        "observed": (
                            f"{label} refused the run directory as "
                            f"{(record or {}).get('error_type') or 'an unknown error type'} "
                            "instead of SchemaError"
                        ),
                    }
                )
            continue
        failures.append(
            {
                "kind": version_kind,
                "label": label,
                "declared_version": declared,
                "supported_version": ARTIFACT_VERSION,
                "used": _shown(None if record is None else record.get("result")),
                "observed": (
                    f"the run directory carries {declared} while this build reads "
                    f"version {ARTIFACT_VERSION}, yet {label.split('-')[0]} worked from it "
                    f"and returned {None if record is None else record.get('result')}"
                ),
            }
        )
    serve = _by_label(records, "serve-after-tamper")
    if serve is not None and serve.get("ok"):
        result = _as_mapping(serve.get("result"))
        status = result.get("status")
        if int(status if isinstance(status, int) else -1) == ACCEPT_STATUS:
            failures.append(
                {
                    "kind": version_kind,
                    "label": "serve-after-tamper",
                    "declared_version": declared,
                    "supported_version": ARTIFACT_VERSION,
                    "used": _shown(result.get("body")),
                    "observed": (
                        f"the endpoint scored from a run directory carrying {declared} while "
                        f"this build reads version {ARTIFACT_VERSION}"
                    ),
                }
            )
        elif int(status if isinstance(status, int) else -1) != REJECT_STATUS:
            failures.append(
                {
                    "kind": "serve_artifact_refusal_wrong",
                    "label": "serve-after-tamper",
                    "declared_version": declared,
                    "status": _shown(status),
                    "expected_status": REJECT_STATUS,
                    "observed": (
                        f"the endpoint answered status {status} instead of status "
                        f"{REJECT_STATUS} for a run directory carrying {declared}"
                    ),
                }
            )
    elif serve is None or not serve.get("ok"):
        failures.append(
            {
                "kind": "serve_artifact_refusal_wrong",
                "label": "serve-after-tamper",
                "declared_version": declared,
                "status": "raised",
                "expected_status": REJECT_STATUS,
                "error": _error(serve),
                "observed": (
                    "the endpoint raised instead of answering status "
                    f"{REJECT_STATUS} for a run directory carrying {declared}: {_error(serve)}"
                ),
            }
        )
    return failures


def _analyse(candidate: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    records = [
        dict(record) for record in candidate.get("records", ()) if isinstance(record, Mapping)
    ]
    rows = _request_rows(payload)
    return {
        "schema_failures": _schema_failures(records, payload),
        "consumer_failures": _consumer_failures(records, rows, payload),
        "refusal_failures": _refusal_failures(records, rows),
        "contract_failures": _contract_failures(records, rows),
        "artifact_failures": _artifact_failures(records, rows),
        "records": records,
    }


_CACHE = AnalysisCache()


def _invoke_program(
    artifact_dir: Path, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    'Run one workload, crossing a real candidate-process consumer boundary.'

    program = [dict(event) for event in payload.get("events", ())]
    segments: list[tuple[int, int]] = []
    start = 0
    for index, event in enumerate(program):
        if str(event.get("type")) == "restart_from_artifacts" and index > start:
            segments.append((start, index))
            start = index
    segments.append((start, len(program)))

    snapshot: Mapping[str, Any] | None = None
    training_available = True
    records: list[dict[str, Any]] = []
    stdout: list[str] = []
    for first, last in segments:
        segment_payload: dict[str, Any] = {
            "frames": dict(payload.get("frames", {})),
            "events": program[first:last],
            "index_offset": first,
            "training_available": training_available,
        }
        if snapshot is not None:
            segment_payload["initial_artifacts"] = dict(snapshot)
        result = PROJECT.invoke(Path(artifact_dir), segment_payload)
        if not result.get("ok"):
            return result
        raw_snapshot = result.get("artifacts")
        if not isinstance(raw_snapshot, Mapping):
            return {
                "ok": False,
                "error": "candidate session returned no serialized run artifacts",
            }
        snapshot = dict(raw_snapshot)
        training_available = bool(result.get("training_available", False))
        records.extend(
            dict(record)
            for record in result.get("records", ())
            if isinstance(record, Mapping)
        )
        if result.get("candidate_stdout"):
            stdout.append(str(result["candidate_stdout"]))
    return {
        "ok": True,
        "records": records,
        "artifacts": dict(snapshot or {}),
        "candidate_stdout": "".join(stdout)[-2000:],
    }


def _reported_error(error: str) -> str:
    'The failed run as the person who started it would repeat it back.'

    text = " ".join(str(error).split())
    if text.startswith("project rehearsal exceeded"):
        return (
            "no answer at all: it was still going long after it should have finished, "
            "and they stopped it"
        )
    if "invalid JSON" in text or "non-object" in text or "exited with status" in text:
        return "nothing anyone here could read back"
    return text


def _stub_analysis(error: str) -> dict[str, Any]:
    'What to report when the run produced no timeline to read.'

    analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
    reported = _reported_error(error)
    for bucket in BUCKETS.values():
        analysis[bucket] = [
            {
                **dict(item),
                "module": CANDIDATE_MODULE,
                "error_text": reported,
                "observed": (
                    f"the run of {CANDIDATE_MODULE} returned no timeline at all: not one "
                    f"operation reported a result, only an execution error: {error}"
                ),
            }
            for item in analysis[bucket]
        ]
    return analysis


def _payload(profile: str, seed: int, scale: int) -> Mapping[str, Any]:
    return {
        "frames": build_frames(seed, scale),
        "events": build_program(profile, seed, scale),
    }


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private workload once per artifact and return the five buckets.'

    def compute() -> Mapping[str, Any]:
        payload = _payload(
            str(PRIVATE_CASE["profile"]), int(PRIVATE_CASE["seed"]), int(PRIVATE_CASE["scale"])
        )
        candidate = _invoke_program(artifact_dir, payload)
        if not candidate.get("ok"):
            analysis = _stub_analysis(str(candidate.get("error", "the pipeline could not be run")))
        else:
            analysis = _analyse(candidate, payload)
        return {**analysis, "case": dict(PRIVATE_CASE)}

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    records = sorted((Path(artifact_dir) / "project_records").glob("*.json"))
    return {
        "summary": "The pipeline workspace and its recorded run rehearsals.",
        "measurements": {
            "artifact_hash": artifact_hash(artifact_dir),
            "project_records": [f"project_records/{path.name}" for path in records],
            "artifact_version": ARTIFACT_VERSION,
            "run_directory_artifacts": list(REQUIRED_ARTIFACTS),
        },
        "observed": {},
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    record_path = Path(specification)
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    record_id = str(raw.get("record_id", record_path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = PUBLIC_RECORDS[record_id]
    payload = _payload(str(case["profile"]), int(case["seed"]), int(case["scale"]))
    candidate = _invoke_program(artifact_dir, payload)
    if not candidate.get("ok"):
        return {
            "summary": f"{record_id}: the rehearsal could not run the pipeline in the workspace.",
            "measurements": {"record_id": record_id, "operations": 0},
            "observed": {"execution_error": candidate.get("error", "unknown failure")},
        }

    frames = dict(payload["frames"])
    events = {index: dict(event) for index, event in enumerate(payload["events"])}
    records = [
        dict(record) for record in candidate.get("records", ()) if isinstance(record, Mapping)
    ]

    def event_for(record: Mapping[str, Any]) -> Mapping[str, Any]:
        return events.get(int(record.get("index", -1)), {})

    def request_row(record: Mapping[str, Any]) -> Any:
        event = event_for(record)
        if str(event.get("type")) not in ("predict", "evaluate", "serve"):
            return None
        position = event.get("row")
        if position is None:
            return None
        return frames.get(str(event.get("frame")), [])[int(position)]

    def training_frame(record: Mapping[str, Any]) -> Any:
        'What a fit step was actually given: its configuration and its rows.'

        event = event_for(record)
        if str(event.get("type")) != "fit":
            return None
        rows = list(frames.get(str(event.get("frame")), ()))
        columns: dict[str, None] = {}
        for row in rows:
            for name in row:
                columns.setdefault(str(name), None)
        return {
            "specification": dict(event.get("spec", {})),
            "columns": list(columns),
            "rows": len(rows),
            "first_row": dict(rows[0]) if rows else None,
        }

    def alteration(record: Mapping[str, Any]) -> Any:
        'What a tamper step changed in the run directory it hands on.'

        event = event_for(record)
        if str(event.get("type")) != "tamper":
            return None
        return {
            "artifact": event.get("artifact"),
            "field": event.get("field"),
            "value": event.get("value"),
            "applied": bool(record.get("tampered")),
        }

    timeline = [
        {
            "label": record.get("label"),
            "operation": record.get("type"),
            "completed": bool(record.get("ok")),
            "error": record.get("error"),
            "training_frame": training_frame(record),
            "request_row": request_row(record),
            "alteration": alteration(record),
            "result": record.get("result"),
            "model_input_rows": [
                {"stage": entry.get("stage"), "matrix": entry.get("matrix")}
                for entry in record.get("model_inputs", ())
            ],
            "artifact_names": record.get("artifact_names"),
            "artifacts": record.get("artifacts"),
        }
        for record in records
    ]
    return {
        "summary": f"{record_id}: {raw.get('scene', '')}",
        "measurements": {
            "record_id": record_id,
            "operations": len(timeline),
            "artifact_version": ARTIFACT_VERSION,
        },
        "observed": {"run_timeline": timeline},
    }
