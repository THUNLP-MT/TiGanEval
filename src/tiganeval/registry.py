"Load and validate a task's ``evidence.py``; select owner Observations."

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .plugins import load_symbol

STALL_NOTE = "This is the same result as the last time I reported it."

FORBIDDEN_VOCABULARY = (
    "rubric",
    "evaluator",
    "hidden test",
    "held-out",
    "gold",
    "seed",
    "seeded",
    "independently",
    "candidate",
    "revision",
)


_FORBIDDEN = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in FORBIDDEN_VOCABULARY) + ")",
    re.IGNORECASE,
)
_CLAUSE_MENU = re.compile(
    r"\beither\b|\bor (?:it|they|the next|the run|the load|the client|the scan)\b",
    re.IGNORECASE,
)

_OBSERVATION_FIELDS = {"first", "second", "detail"}
_STAGES = ("first", "second", "repeat")
_FORMATTER = string.Formatter()
_FIELD_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_DETAIL_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}\Z")


def placeholder_name(detail: str) -> str | None:
    "The measured field a ``{name}`` detail stands for; None for a literal token."

    match = _DETAIL_PLACEHOLDER.match(detail)
    return None if match is None else match.group(1)


def placeholders(text: str, label: str) -> tuple[str, ...]:
    "The ``{name}`` fields of one context, in order of first appearance."

    names: list[str] = []
    try:
        parsed = list(_FORMATTER.parse(text))
    except ValueError as exc:
        raise ValueError(
            f"{label} has an unbalanced brace ({exc}); double a literal brace as {{{{ or }}}}"
        ) from None
    for _literal, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if not _FIELD_NAME.match(field_name) or format_spec or conversion is not None:
            raise ValueError(
                f"{label} placeholder {field_name!r} must be a bare {{name}} with no "
                "conversion, format spec, attribute, or index"
            )
        if field_name not in names:
            names.append(field_name)
    return tuple(names)


@dataclass(frozen=True, slots=True)
class Observation:
    "The escalating contexts for one (rubric, failure mode) pair."

    first: str
    second: str
    detail: str
    observation_ids: Mapping[str, str]
    fields: tuple[str, ...] = ()

    @property
    def detail_field(self) -> str | None:
        "The measured field the detail names, or None for a literal token."

        return placeholder_name(self.detail)


def render_second(
    observation: Observation,
    rubric_id: str,
    failure_mode: str,
    observed: Mapping[str, Any] | None,
) -> str:
    "Fill the second context from the evaluator's measured fields."

    values = dict(observed or {})
    try:
        return observation.second.format_map(values)
    except KeyError as exc:
        key = exc.args[0] if exc.args else "?"
        raise ValueError(
            f"the second Observation for rubric {rubric_id!r} failure mode "
            f"{failure_mode!r} needs the measured field {key!r}, which the evaluator "
            f"did not report (observed fields: {sorted(map(str, values)) or 'none'})"
        ) from None


@dataclass(frozen=True, slots=True)
class EvidenceRegistry:
    user_persona: str
    user_belief: str
    scene: str
    observations: Mapping[str, Mapping[str, Observation]]

    def select(
        self,
        rubric_id: str,
        failure_mode: str,
        occurrence: int,
        observed: Mapping[str, Any] | None = None,
    ) -> tuple[str, dict[str, str]]:
        "Return the Observation id and payload for the n-th report of a failure."

        if occurrence < 1:
            raise ValueError("occurrence counts from 1")
        try:
            observation = self.observations[rubric_id][failure_mode]
        except KeyError:
            raise ValueError(
                f"no Observation is registered for rubric {rubric_id!r} "
                f"failure mode {failure_mode!r}"
            ) from None
        if occurrence == 1:
            payload = {"scene": self.scene, "context": observation.first}
            return observation.observation_ids["first"], payload
        context = render_second(observation, rubric_id, failure_mode, observed)
        payload = {"scene": self.scene, "context": context}
        if occurrence == 2:
            return observation.observation_ids["second"], payload
        payload["note"] = STALL_NOTE
        return observation.observation_ids["repeat"], payload


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value.strip()


def _check_vocabulary(text: str, label: str) -> None:
    match = _FORBIDDEN.search(text)
    if match is not None:
        raise ValueError(f"{label} contains benchmark vocabulary {match.group(0)!r}")


def _check_clause_menu(text: str, label: str) -> None:
    match = _CLAUSE_MENU.search(text)
    if match is not None:
        raise ValueError(
            f"{label} reads as a menu of alternatives ({match.group(0)!r}); "
            "report one incident"
        )


def _observation(value: Any, rubric_id: str, failure_mode: str) -> Observation:
    label = f"OBSERVATIONS[{rubric_id!r}][{failure_mode!r}]"
    if not isinstance(value, Mapping) or set(value) != _OBSERVATION_FIELDS:
        raise ValueError(f"{label} must be observation(first, second, detail)")
    first = _text(value["first"], f"{label}.first")
    second = _text(value["second"], f"{label}.second")
    detail = _text(value["detail"], f"{label}.detail")
    if second == first:
        raise ValueError(f"{label}.second must differ from first")
    first_fields = placeholders(first, f"{label}.first")
    if first_fields:
        raise ValueError(
            f"{label}.first must not contain placeholders {list(first_fields)}; "
            "only the second context carries measured fields"
        )
    fields = placeholders(second, f"{label}.second")
    detail_field = placeholder_name(detail)
    if detail_field is not None:
        if detail_field not in fields:
            raise ValueError(
                f"{label}.detail placeholder {detail!r} must appear in second"
            )
    elif detail not in second:
        raise ValueError(f"{label}.detail {detail!r} must appear in second")
    if detail in first:
        raise ValueError(f"{label}.detail {detail!r} must not appear in first")
    for stage, context in (("first", first), ("second", second)):
        _check_vocabulary(context, f"{label}.{stage}")
        _check_clause_menu(context, f"{label}.{stage}")
    return Observation(
        first=first,
        second=second,
        detail=detail,
        observation_ids={
            stage: f"{rubric_id}.{failure_mode}.{stage}" for stage in _STAGES
        },
        fields=fields,
    )


def _check_coverage(
    observations: Mapping[str, Mapping[str, Observation]],
    failure_modes: Mapping[str, Sequence[str]],
) -> None:
    expected = {
        (rubric_id, mode)
        for rubric_id, modes in failure_modes.items()
        for mode in modes
    }
    actual = {
        (rubric_id, mode) for rubric_id, modes in observations.items() for mode in modes
    }
    if expected == actual:
        return
    problems = []
    for word, pairs in (
        ("missing", expected - actual),
        ("unregistered", actual - expected),
    ):
        if pairs:
            listed = ", ".join(
                f"{rubric_id}.{mode}" for rubric_id, mode in sorted(pairs)
            )
            problems.append(f"{word}: {listed}")
    raise ValueError(
        "OBSERVATIONS must cover exactly the failure modes the evaluators can emit "
        f"({'; '.join(problems)})"
    )


def load_evidence_registry(
    evidence_path: Path, failure_modes: Mapping[str, Sequence[str]]
) -> EvidenceRegistry:
    "Load USER_PERSONA, USER_BELIEF, OBSERVATION_SCENE, and OBSERVATIONS."

    path = Path(evidence_path)

    def symbol(name: str) -> Any:
        return load_symbol(f"{path}:{name}", path.parent)

    persona = _text(symbol("USER_PERSONA"), "USER_PERSONA")
    belief = _text(symbol("USER_BELIEF"), "USER_BELIEF")
    scene = _text(symbol("OBSERVATION_SCENE"), "OBSERVATION_SCENE")
    raw = symbol("OBSERVATIONS")
    if not isinstance(raw, Mapping):
        raise ValueError(
            "OBSERVATIONS must map rubric id -> failure mode -> observation"
        )
    _check_vocabulary(persona, "USER_PERSONA")
    _check_vocabulary(belief, "USER_BELIEF")

    observations: dict[str, dict[str, Observation]] = {}
    for raw_rubric_id, raw_modes in raw.items():
        rubric_id = _text(raw_rubric_id, "OBSERVATIONS rubric id")
        if not isinstance(raw_modes, Mapping) or not raw_modes:
            raise ValueError(
                f"OBSERVATIONS[{rubric_id!r}] must map failure mode -> observation"
            )
        observations[rubric_id] = {
            _text(raw_mode, f"OBSERVATIONS[{rubric_id!r}] failure mode"): _observation(
                raw_observation, rubric_id, str(raw_mode).strip()
            )
            for raw_mode, raw_observation in raw_modes.items()
        }
    _check_coverage(observations, failure_modes)
    return EvidenceRegistry(
        user_persona=persona,
        user_belief=belief,
        scene=scene,
        observations=observations,
    )
