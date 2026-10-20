"""Training and serving entry points sharing one persisted feature schema."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    ARTIFACT_VERSION,
    DESCRIPTION_ARTIFACT,
    DROP_REASONS,
    MODEL_ARTIFACT,
    Frame,
    FeatureSpec,
    Model,
    RunDirectory,
    SchemaError,
    canonical_value,
    read_feature_schema,
    rejected_response,
    run_description,
    scored_response,
    write_feature_schema,
)


UNKNOWN_LEVEL = 0.0


def _listed(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    entries = [value] if isinstance(value, str) else list(value)
    names = [str(item) for item in entries]
    if any(not name.strip() for name in names):
        raise SchemaError(f"{label} contains an empty column name")
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise SchemaError(f"{label} lists {', '.join(duplicates)} more than once")
    return names


def _selected_columns(frame: Frame, spec: FeatureSpec) -> list[str]:
    available = list(frame.columns())
    include = _listed(spec.include, "features.include")
    exclude = _listed(spec.exclude, "features.exclude")
    for label, names in (("include", include), ("exclude", exclude)):
        unknown = sorted(name for name in names if name not in available)
        if unknown:
            raise SchemaError(
                f"features.{label} names unknown columns: {', '.join(unknown)}"
            )
        if spec.target in names:
            raise SchemaError(
                f"features.{label} names the target column {spec.target}"
            )
    ordered = include or [name for name in available if name != spec.target]
    return [name for name in ordered if name not in exclude and name != spec.target]


def _encoding(values: Sequence[Any]) -> dict[str, Any]:
    present = [value for value in values if value is not None]
    if all(isinstance(value, float) for value in present):
        return {"kind": "numeric"}
    distinct = sorted({str(value) for value in present})
    return {
        "kind": "categorical",
        "levels": {value: float(index + 1) for index, value in enumerate(distinct)},
        "unknown": UNKNOWN_LEVEL,
    }


def build_schema(frame: Frame, spec: FeatureSpec) -> dict[str, Any]:
    """Derive the fitted feature space from the training frame and the spec."""

    columns = _selected_columns(frame, spec)
    canonical = {name: frame.canonical_column(name) for name in columns}

    constant = [
        name
        for name in columns
        if spec.drop_constant and len({repr(value) for value in canonical[name]}) <= 1
    ]
    remaining = [name for name in columns if name not in constant]

    aliases: dict[str, list[str]] = {}
    duplicate: list[str] = []
    kept: list[str] = []
    for name in remaining:
        origin = next(
            (
                existing
                for existing in kept
                if spec.drop_duplicate and canonical[existing] == canonical[name]
            ),
            None,
        )
        if origin is None:
            kept.append(name)
            continue
        aliases.setdefault(origin, []).append(name)
        duplicate.append(name)

    if not kept:
        raise SchemaError("features left the model no input columns at all")

    return {
        "version": ARTIFACT_VERSION,
        "target": spec.target,
        "input_features": kept,
        "encoding": {name: _encoding(canonical[name]) for name in kept},
        "duplicate_feature_aliases": {
            name: sorted(items) for name, items in aliases.items()
        },
        "dropped_features": {
            "excluded": sorted(set(frame.columns()) - set(columns) - {spec.target}),
            "constant": sorted(constant),
            "duplicate": sorted(duplicate),
        },
    }


def _sources(schema: Mapping[str, Any], feature: str) -> list[str]:
    aliases = dict(schema.get("duplicate_feature_aliases", {})).get(str(feature), [])
    return [str(feature), *[str(item) for item in aliases]]


def _cell(row: Mapping[str, Any], schema: Mapping[str, Any], feature: str) -> float:
    sources = _sources(schema, feature)
    present = [name for name in sources if row.get(name) is not None]
    if not present:
        raise SchemaError(
            f"the request carries no value for {feature}; "
            f"one of {', '.join(sources)} is required"
        )
    values = {name: canonical_value(row[name]) for name in present}
    if len({repr(value) for value in values.values()}) > 1:
        stated = ", ".join(f"{name}={values[name]!r}" for name in sorted(present))
        raise SchemaError(f"the sources for {feature} disagree: {stated}")
    value = values[present[0]]
    encoding = dict(dict(schema["encoding"])[str(feature)])
    if str(encoding.get("kind")) == "numeric":
        if not isinstance(value, float):
            raise SchemaError(f"{feature} expects a numeric value, not {value!r}")
        return float(value)
    levels = dict(encoding.get("levels", {}))
    return float(levels.get(str(value), encoding.get("unknown", UNKNOWN_LEVEL)))


def build_matrix(frame: Frame, schema: Mapping[str, Any]) -> list[list[float]]:
    """Turn raw rows into the fitted feature space, or refuse to."""

    features = [str(name) for name in schema["input_features"]]
    return [[_cell(row, schema, name) for name in features] for row in frame.rows]


def fit(frame: Frame, spec: FeatureSpec, run: RunDirectory) -> Mapping[str, Any]:
    schema = build_schema(frame, spec)
    matrix = build_matrix(frame, schema)
    targets: list[float] = []
    for value in frame.column(spec.target):
        canonical = canonical_value(value)
        if not isinstance(canonical, float):
            raise SchemaError(f"the target column {spec.target} must be numeric")
        targets.append(float(canonical))
    model = Model().fit(matrix, targets)
    description = run_description(schema, len(frame))
    write_feature_schema(run, schema)
    run.write(MODEL_ARTIFACT, model.as_dict())
    run.write(DESCRIPTION_ARTIFACT, description)
    return description


def predict(frame: Frame, run: RunDirectory) -> list[float]:
    schema = read_feature_schema(run)
    matrix = build_matrix(frame, schema)
    return Model.from_dict(run.read(MODEL_ARTIFACT)).predict(matrix)


def evaluate(frame: Frame, run: RunDirectory) -> Mapping[str, Any]:
    predictions = predict(frame, run)
    return {
        "rows": len(frame),
        "mean_prediction": round(sum(predictions) / max(1, len(predictions)), 9),
    }


def export(run: RunDirectory) -> Mapping[str, Any]:
    schema = read_feature_schema(run)
    description = run.read(DESCRIPTION_ARTIFACT)
    if description.get("version") != ARTIFACT_VERSION:
        raise SchemaError(
            f"{DESCRIPTION_ARTIFACT} version {description.get('version')!r} is not supported"
        )
    features = [str(name) for name in schema["input_features"]]
    if [str(name) for name in description.get("input_features", ())] != features:
        raise SchemaError(
            f"{DESCRIPTION_ARTIFACT} and the feature schema name different inputs"
        )
    model = Model.from_dict(run.read(MODEL_ARTIFACT))
    return {
        "input_width": len(features),
        "features": features,
        "dropped_features": {
            reason: list(dict(schema["dropped_features"])[reason])
            for reason in DROP_REASONS
        },
        "weights": list(model.weights),
    }


def serve(row: Mapping[str, Any], run: RunDirectory) -> Mapping[str, Any]:
    try:
        prediction = predict(Frame([dict(row)]), run)[0]
    except SchemaError as exc:
        return rejected_response(str(exc))
    return scored_response(prediction)
