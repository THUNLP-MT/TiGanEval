"""Runtime contract for the tabular training and serving project.

The frame, the feature specification, the model, and the run directory below are
the frozen part of the project. Everything is deterministic: the model has no
randomness, artifacts are canonical JSON, and every model input is recorded so
the training and serving paths can be compared exactly.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
from typing import Any, Mapping, Sequence


#: The artifact layout every consumer must be able to read.
ARTIFACT_VERSION = 2
SCHEMA_ARTIFACT = "feature_schema.json"
DESCRIPTION_ARTIFACT = "description.json"
MODEL_ARTIFACT = "model.json"

#: Why a raw column is not a model input.
DROP_REASONS = ("excluded", "constant", "duplicate")

#: The keys a persisted feature schema carries.
#:
#: A run directory is all a consumer gets, so `feature_schema.json` has to
#: answer on its own: which build wrote it (`version`), what the run predicts
#: (`target`), which columns feed the model and in what order
#: (`input_features`), how a raw cell becomes a model input for each of those
#: columns (`encoding`, which for a column of categories also has to say what a
#: level the training rows never contained becomes, since serving meets levels
#: training did not), which later columns repeat a surviving one
#: (`duplicate_feature_aliases`, surviving column -> the columns that repeat
#: it), and which raw columns are not model inputs and why
#: (`dropped_features`, one list per entry of DROP_REASONS).
SCHEMA_KEYS = (
    "version",
    "target",
    "input_features",
    "encoding",
    "duplicate_feature_aliases",
    "dropped_features",
)


class SchemaError(Exception):
    """A raw input, or a feature configuration, that cannot become a fitted
    feature space.

    This is the refusal the whole project is built around: `serve` catches it
    to answer in its own contract, so a refusal raised as anything else reaches
    the caller as a failure rather than as an answer.
    """


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_value(value: Any) -> Any:
    """Normalise one raw cell the way the fitted feature space expects."""

    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = " ".join(str(value).split()).casefold()
    try:
        return float(text)
    except ValueError:
        return text


class Frame:
    """An ordered table of raw rows. Rows may carry different columns."""

    def __init__(self, rows: Sequence[Mapping[str, Any]]):
        self.rows = [dict(row) for row in rows]

    def __len__(self) -> int:
        return len(self.rows)

    def columns(self) -> tuple[str, ...]:
        """Every column name, in first-seen order."""

        seen: dict[str, None] = {}
        for row in self.rows:
            for name in row:
                seen.setdefault(str(name), None)
        return tuple(seen)

    def column(self, name: str) -> list[Any]:
        return [row.get(str(name)) for row in self.rows]

    def canonical_column(self, name: str) -> list[Any]:
        return [canonical_value(value) for value in self.column(name)]


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """What the operator asked the pipeline to train on."""

    target: str = "target"
    include: Any = None
    exclude: Any = None
    drop_constant: bool = True
    drop_duplicate: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FeatureSpec":
        return cls(
            target=str(value.get("target", "target")),
            include=deepcopy(value.get("include")),
            exclude=deepcopy(value.get("exclude")),
            drop_constant=bool(value.get("drop_constant", True)),
            drop_duplicate=bool(value.get("drop_duplicate", True)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "include": deepcopy(self.include),
            "exclude": deepcopy(self.exclude),
            "drop_constant": self.drop_constant,
            "drop_duplicate": self.drop_duplicate,
        }


class MatrixLog:
    """Every design matrix the model was asked to work with."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.entries.clear()

    def record(self, stage: str, matrix: Sequence[Sequence[float]]) -> None:
        self.entries.append(
            {"stage": str(stage), "matrix": [[float(cell) for cell in row] for row in matrix]}
        )


MATRIX_LOG = MatrixLog()


@dataclass(slots=True)
class Model:
    """A deterministic linear model. Its output depends on column order."""

    weights: list[float] = field(default_factory=list)
    bias: float = 0.0

    def fit(self, matrix: Sequence[Sequence[float]], targets: Sequence[float]) -> "Model":
        MATRIX_LOG.record("fit", matrix)
        width = len(matrix[0]) if matrix else 0
        values = [float(value) for value in targets]
        self.bias = round(sum(values) / len(values), 9) if values else 0.0
        self.weights = []
        for index in range(width):
            column = [float(row[index]) for row in matrix]
            numerator = sum(
                (value - self.bias) * cell for value, cell in zip(values, column)
            )
            denominator = sum(cell * cell for cell in column) + 1.0
            self.weights.append(round(numerator / denominator, 9))
        return self

    def predict(self, matrix: Sequence[Sequence[float]]) -> list[float]:
        MATRIX_LOG.record("predict", matrix)
        results: list[float] = []
        for row in matrix:
            if len(row) != len(self.weights):
                raise SchemaError(
                    f"model expects {len(self.weights)} inputs but received {len(row)}"
                )
            results.append(
                round(self.bias + sum(w * float(c) for w, c in zip(self.weights, row)), 9)
            )
        return results

    def as_dict(self) -> dict[str, Any]:
        return {"weights": list(self.weights), "bias": self.bias}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Model":
        return cls(
            weights=[float(item) for item in value.get("weights", ())],
            bias=float(value.get("bias", 0.0)),
        )


class RunDirectory:
    """The artifacts a fitted run leaves behind. This is all a consumer gets."""

    def __init__(self, artifacts: Mapping[str, str] | None = None):
        self._artifacts: dict[str, str] = {
            str(name): str(text) for name, text in dict(artifacts or {}).items()
        }
        self.writes = 0
        self.reads = 0

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._artifacts))

    def write(self, name: str, value: Any) -> None:
        self.writes += 1
        self._artifacts[str(name)] = canonical_json(value)

    def read(self, name: str) -> Any:
        self.reads += 1
        text = self._artifacts.get(str(name))
        if text is None:
            raise SchemaError(f"the run directory has no {name!r} artifact")
        return json.loads(text)

    def raw(self) -> dict[str, str]:
        return dict(self._artifacts)


def feature_schema_problems(schema: Any) -> list[str]:
    """Everything that stops a persisted feature schema from standing alone.

    An empty list means the artifact carries the whole layout described by
    SCHEMA_KEYS and was written by a build this one can read.
    """

    if not isinstance(schema, Mapping):
        return [f"{SCHEMA_ARTIFACT} is not an object"]
    problems: list[str] = []
    missing = [key for key in SCHEMA_KEYS if key not in schema]
    if missing:
        problems.append("missing " + ", ".join(missing))
    if "version" in schema and schema.get("version") != ARTIFACT_VERSION:
        problems.append(
            f"version {schema.get('version')!r} is not supported; "
            f"this build reads version {ARTIFACT_VERSION}"
        )
    features = schema.get("input_features")
    if (
        not isinstance(features, list)
        or not features
        or any(not isinstance(name, str) or not name for name in features)
    ):
        problems.append("input_features must be a non-empty list of column names")
        features = []
    encoding = schema.get("encoding")
    if not isinstance(encoding, Mapping) or any(
        str(name) not in encoding for name in features
    ):
        problems.append("encoding must describe every column in input_features")
    if not isinstance(schema.get("duplicate_feature_aliases"), Mapping):
        problems.append(
            "duplicate_feature_aliases must map a surviving column to the later "
            "columns that repeat it"
        )
    dropped = schema.get("dropped_features")
    if not isinstance(dropped, Mapping) or {str(key) for key in dropped} != set(
        DROP_REASONS
    ):
        problems.append(
            "dropped_features must carry one list per reason: " + ", ".join(DROP_REASONS)
        )
    if not isinstance(schema.get("target"), str) or not schema.get("target"):
        problems.append("target must name the predicted column")
    return problems


def write_feature_schema(run: "RunDirectory", schema: Mapping[str, Any]) -> None:
    """Write `feature_schema.json`, refusing a layout that cannot stand alone."""

    problems = feature_schema_problems(schema)
    if problems:
        raise SchemaError(f"{SCHEMA_ARTIFACT} is incomplete: {'; '.join(problems)}")
    run.write(SCHEMA_ARTIFACT, dict(schema))


def read_feature_schema(run: "RunDirectory") -> Mapping[str, Any]:
    """Read `feature_schema.json`, refusing a layout this build cannot use."""

    schema = run.read(SCHEMA_ARTIFACT)
    problems = feature_schema_problems(schema)
    if problems:
        raise SchemaError(f"{SCHEMA_ARTIFACT} cannot be used: {'; '.join(problems)}")
    return schema


def run_description(schema: Mapping[str, Any], rows: int) -> dict[str, Any]:
    """The readable summary of a run, derived from its own feature schema.

    `description.json` is what a person opens; it repeats the feature schema's
    account of the model's inputs rather than telling a second story.
    """

    problems = feature_schema_problems(schema)
    if problems:
        raise SchemaError(
            f"cannot describe a run from an incomplete schema: {'; '.join(problems)}"
        )
    dropped = dict(schema["dropped_features"])
    aliases = dict(schema["duplicate_feature_aliases"])
    return {
        "version": ARTIFACT_VERSION,
        "feature_schema": SCHEMA_ARTIFACT,
        "target": str(schema["target"]),
        "input_features": [str(name) for name in schema["input_features"]],
        "dropped_features": {
            reason: [str(name) for name in dropped[reason]] for reason in DROP_REASONS
        },
        "duplicate_feature_aliases": {
            str(name): [str(item) for item in items] for name, items in aliases.items()
        },
        "rows": int(rows),
    }


def scored_response(prediction: float) -> dict[str, Any]:
    """What `serve` answers for a record the fitted feature space accepts."""

    return {"status": 200, "body": {"prediction": float(prediction)}}


def rejected_response(detail: str) -> dict[str, Any]:
    """What `serve` answers for a record it cannot turn into a model input.

    The detail is the whole of what the calling team sees, so it names the
    columns at fault.
    """

    return {"status": 400, "body": {"detail": str(detail)}}


__all__ = (
    "ARTIFACT_VERSION",
    "DESCRIPTION_ARTIFACT",
    "DROP_REASONS",
    "Frame",
    "FeatureSpec",
    "MATRIX_LOG",
    "MODEL_ARTIFACT",
    "MatrixLog",
    "Model",
    "RunDirectory",
    "SCHEMA_ARTIFACT",
    "SCHEMA_KEYS",
    "SchemaError",
    "canonical_json",
    "canonical_value",
    "feature_schema_problems",
    "read_feature_schema",
    "rejected_response",
    "run_description",
    "scored_response",
    "write_feature_schema",
)
