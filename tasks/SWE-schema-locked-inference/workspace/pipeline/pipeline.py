"""Training and serving entry points.

`fit` picks the raw columns to train on, writes the chosen list to
`description.json` next to the model, and every later caller lines its rows up
with that list. Whatever a caller does not send for a listed column is read as
an absent cell and encoded like any other value.
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


def build_matrix(frame: Frame, features: Sequence[str]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for row in frame.rows:
        vector: list[float] = []
        for name in features:
            value = canonical_value(row.get(name))
            vector.append(float(value) if isinstance(value, float) else float(len(str(value))))
        matrix.append(vector)
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


def predict(frame: Frame, run: RunDirectory) -> list[float]:
    features = list(run.read(DESCRIPTION_ARTIFACT)["input_features"])
    return _model(run).predict(build_matrix(frame, features))


def evaluate(frame: Frame, run: RunDirectory) -> Mapping[str, Any]:
    predictions = predict(frame, run)
    return {"rows": len(frame), "mean_prediction": round(sum(predictions) / max(1, len(predictions)), 9)}


def export(run: RunDirectory) -> Mapping[str, Any]:
    description = run.read(DESCRIPTION_ARTIFACT)
    model = _model(run)
    return {
        "input_width": len(description["input_features"]),
        "features": list(description["input_features"]),
        "weights": list(model.weights),
    }


def serve(row: Mapping[str, Any], run: RunDirectory) -> Mapping[str, Any]:
    try:
        prediction = predict(Frame([dict(row)]), run)[0]
    except SchemaError as exc:
        return {"status": 500, "body": {"error": str(exc)}}
    return scored_response(prediction)
