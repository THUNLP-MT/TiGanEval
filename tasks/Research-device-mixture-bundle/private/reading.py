'The reading law, the four capture conditions and the three bundles.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


FEATURES = (
    "refl_a",
    "refl_b",
    "refl_c",
    "edge_density",
    "skew",
    "contrast",
    "blur",
    "tilt",
)
REFLECTANCE = ("refl_a", "refl_b", "refl_c")
CONDITIONS = ("bright", "dim", "glare", "damaged")
BUNDLES = ("mallow", "thistle", "rowan")
REFERENCE_CARD = "reference_card"


CONDITION_PARAMS: Mapping[str, tuple[tuple[float, ...], tuple[float, ...]]] = {
    "bright": (
        (0.72, 0.68, 0.70, 0.55, 0.10, 0.62, 0.18, 0.12),
        (0.156, 0.156, 0.156, 0.234, 0.130, 0.208, 0.130, 0.130),
    ),
    "dim": (
        (0.30, 0.27, 0.29, 0.40, 0.12, 0.36, 0.42, 0.14),
        (0.130, 0.130, 0.130, 0.234, 0.130, 0.182, 0.182, 0.156),
    ),
    "glare": (
        (0.90, 0.92, 0.88, 0.36, 0.30, 0.26, 0.16, 0.22),
        (0.130, 0.130, 0.130, 0.208, 0.182, 0.156, 0.130, 0.182),
    ),
    "damaged": (
        (0.46, 0.42, 0.48, 0.28, 0.34, 0.30, 0.30, 0.32),
        (0.182, 0.182, 0.182, 0.208, 0.234, 0.182, 0.208, 0.234),
    ),
}


REFERENCE_PARAMS = (
    (0.60, 0.58, 0.62, 0.50, 0.08, 0.55, 0.14, 0.08),
    (0.012, 0.012, 0.012, 0.02, 0.01, 0.02, 0.01, 0.01),
)


LAW = (0.20, 0.18, 0.19, 1.28, -1.10, 1.85, -1.48, -0.92)
LAW_INTERCEPT = -0.87


LAW_STEEPNESS = 30.0


def readable_score(values: Sequence[float]) -> float:
    total = LAW_INTERCEPT
    for weight, value in zip(LAW, values):
        total += weight * float(value)
    return total


BUNDLE_RULES: Mapping[str, Mapping[str, Any]] = {
    "mallow": {
        "window_span": 1.45,
        "weights": (0.25, 0.23, 0.24, 1.28, -1.90, 2.45, -0.28, -0.92),
        "intercept": -1.32,
    },
    "thistle": {
        "window_span": None,
        "weights": (0.40, 0.38, 0.39, 1.28, -1.40, 2.05, 0.52, -0.92),
        "intercept": -1.77,
    },
    "rowan": {
        "window_span": None,
        "weights": (0.20, 0.18, 0.19, 1.28, -1.10, 0.65, -1.78, -0.92),
        "intercept": -0.42,
    },
}


def front_end(name: str, values: Sequence[float]) -> list[float]:
    "The capture as the bundle's front end hands it to the rule."

    rule = BUNDLE_RULES[str(name)]
    row = [float(item) for item in values]
    span = rule["window_span"]
    if span is not None:
        for index in range(len(REFLECTANCE)):
            if row[index] > float(span):
                row[index] = float(span)
    return row


def decide(name: str, values: Sequence[float]) -> int:
    '1 when the bundle reads the capture, 0 when it sends it back.'

    rule = BUNDLE_RULES[str(name)]
    row = front_end(name, values)
    total = float(rule["intercept"])
    for weight, value in zip(rule["weights"], row):
        total += float(weight) * value
    return 1 if total >= 0.0 else 0


def apply_gain(values: Sequence[float], gain: float) -> list[float]:
    'One capture as the sensor wrote it on a unit running the raised gain.'

    row = [float(item) for item in values]
    for index in range(len(REFLECTANCE)):
        row[index] = row[index] * float(gain)
    return row


def remove_gain(values: Sequence[float], gain: float) -> list[float]:
    row = [float(item) for item in values]
    for index in range(len(REFLECTANCE)):
        row[index] = row[index] / float(gain)
    return row


_REFERENCE_BLOCK = 12000
_CONDITION_ERROR: dict[tuple[str, str], float] = {}


def _reference_captures(condition: str) -> list[tuple[float, ...]]:
    import random
    from statistics import NormalDist

    centre, spread = CONDITION_PARAMS[condition]
    distribution = NormalDist()
    points = [
        distribution.inv_cdf((index + 0.5) / _REFERENCE_BLOCK)
        for index in range(_REFERENCE_BLOCK)
    ]
    generator = random.Random(1_000_003 * (CONDITIONS.index(str(condition)) + 1) + 17)
    columns = []
    for _ in range(len(FEATURES)):
        drawn = list(points)
        generator.shuffle(drawn)
        columns.append(drawn)
    return [
        tuple(
            max(0.01, centre[axis] + spread[axis] * columns[axis][position])
            for axis in range(len(FEATURES))
        )
        for position in range(_REFERENCE_BLOCK)
    ]


def readable_chance(values: Sequence[float]) -> float:
    'How often a capture like this one comes back readable.'

    score = readable_score(values)
    return 1.0 / (1.0 + pow(2.718281828459045, -LAW_STEEPNESS * score))


def _fill_condition_errors() -> None:
    for condition in CONDITIONS:
        captures = _reference_captures(condition)
        chances = [readable_chance(values) for values in captures]
        for bundle in BUNDLES:
            wrong = 0.0
            for values, chance in zip(captures, chances):
                wrong += (1.0 - chance) if decide(bundle, values) else chance
            _CONDITION_ERROR[(bundle, condition)] = wrong / len(captures)


def condition_error(bundle: str, condition: str) -> float:
    "The share of one condition's captures the bundle gets wrong, in service."

    if not _CONDITION_ERROR:
        _fill_condition_errors()
    return _CONDITION_ERROR[(str(bundle), str(condition))]
