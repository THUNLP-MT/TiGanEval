"""Score a ticket the way the intake pipeline scores it.

This is the deployed scorer. It standardises a ticket's six features with the
column statistics the pipeline ships and puts the result through the fitted
weights; a ticket at or above the threshold is routed to escalation.

`scale_stats.json` and `train-0311.json` beside this module are the artifacts
the March build shipped with. A deployment's own copy of the same object is in
`context["model"]`, so the same call can score a ticket for any centre the
stack serves.
"""

from math import exp
import json
from pathlib import Path

_SHIPPED = None


def shipped_model():
    """The statistics and weights this installation runs with."""

    global _SHIPPED
    if _SHIPPED is None:
        stats = json.loads((Path(__file__).with_name("scale_stats.json")).read_text())
        weights = json.loads((Path(__file__).with_name("train-0311.json")).read_text())
        _SHIPPED = dict(stats, **{k: weights[k] for k in ("coefficients", "intercept", "threshold")})
    return dict(_SHIPPED)


def standardise(features, model=None):
    """The six features on the column statistics the model carries."""

    model = shipped_model() if model is None else model
    names = list(model["features"])
    centre = list(model["centre"])
    scale = list(model["scale"])
    if isinstance(features, dict):
        values = [float(features[name]) for name in names]
    else:
        values = [float(value) for value in features]
    return [(values[i] - centre[i]) / scale[i] for i in range(len(names))]


def score(features, model=None):
    """The escalation score the pipeline gives one ticket."""

    model = shipped_model() if model is None else model
    total = float(model["intercept"])
    for weight, value in zip(model["coefficients"], standardise(features, model)):
        total += float(weight) * value
    if total >= 0.0:
        return 1.0 / (1.0 + exp(-total))
    scaled = exp(total)
    return scaled / (1.0 + scaled)


def decide(features, model=None):
    """1 when the pipeline routes the ticket to escalation, 0 when it does not."""

    model = shipped_model() if model is None else model
    return 1 if score(features, model) >= float(model["threshold"]) else 0
