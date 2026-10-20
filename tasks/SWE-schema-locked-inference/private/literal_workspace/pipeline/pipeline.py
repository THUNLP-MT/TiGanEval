"""Training and serving entry points.

`fit` picks the raw columns to train on and writes the chosen list to
`description.json` next to the model. Every later caller lines its rows up with
that list, and a caller that leaves one of those columns out is told which
column is missing instead of having the gap filled in.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    DESCRIPTION_ARTIFACT,
    MODEL_ARTIFACT,
    Frame,
    FeatureSpec,
    Model,
    RunDirectory,
    SchemaError,
    canonical_value,
    rejected_response,
    scored_response,
)


def select_features(frame: Frame, spec: FeatureSpec) -> list[str]:
    """Choose the raw columns to train on."""

    columns = [name for name in frame.columns() if name != spec.target]
    exclude = spec.exclude if isinstance(spec.exclude, list) else ([spec.exclude] if spec.exclude else [])
    columns = [name for name in columns if name not in exclude]
    if spec.include:
        include = spec.include if isinstance(spec.include, list) else [spec.include]
        columns = [name for name in include if name in columns]
    return columns


def _encode(value: Any) -> float:
    canonical = canonical_value(value)
    return float(canonical) if isinstance(canonical, float) else float(len(str(canonical)))


def build_matrix(frame: Frame, features: Sequence[str]) -> list[list[float]]:
    """Line every row up with the fitted column list, or say what is missing."""

    matrix: list[list[float]] = []
    for row in frame.rows:
        absent = [name for name in features if row.get(name) is None]
        if absent:
            raise SchemaError(
                "the request is missing the trained column(s) " + ", ".join(absent)
            )
        matrix.append([_encode(row.get(name)) for name in features])
    return matrix


def fit(frame: Frame, spec: FeatureSpec, run: RunDirectory) -> Mapping[str, Any]:
    features = select_features(frame, spec)
    matrix = build_matrix(frame, features)
    targets = [float(canonical_value(value)) for value in frame.column(spec.target)]
    model = Model().fit(matrix, targets)
    run.write(MODEL_ARTIFACT, model.as_dict())
    description = {"input_features": features, "rows": len(frame)}
    run.write(DESCRIPTION_ARTIFACT, description)
    return description


def _model(run: RunDirectory) -> Model:
    return Model.from_dict(run.read(MODEL_ARTIFACT))


def _features(run: RunDirectory) -> list[str]:
    return [str(name) for name in run.read(DESCRIPTION_ARTIFACT)["input_features"]]


def predict(frame: Frame, run: RunDirectory) -> list[float]:
    return _model(run).predict(build_matrix(frame, _features(run)))


def evaluate(frame: Frame, run: RunDirectory) -> Mapping[str, Any]:
    predictions = predict(frame, run)
    return {
        "rows": len(frame),
        "mean_prediction": round(sum(predictions) / max(1, len(predictions)), 9),
    }


def export(run: RunDirectory) -> Mapping[str, Any]:
    features = _features(run)
    return {
        "input_width": len(features),
        "features": features,
        "weights": list(_model(run).weights),
    }


def serve(row: Mapping[str, Any], run: RunDirectory) -> Mapping[str, Any]:
    try:
        prediction = predict(Frame([dict(row)]), run)[0]
    except SchemaError as exc:
        return rejected_response(str(exc))
    return scored_response(prediction)
