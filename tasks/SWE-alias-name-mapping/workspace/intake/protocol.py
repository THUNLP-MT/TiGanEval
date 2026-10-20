"""Runtime contract for partner payload intake.

Every service in the platform that takes payloads from a partner ships this
file, so the value types, the naming rules, the envelope, the error family and
the type fragments we publish to partners are the same in all of them. Nothing
here reaches a network: one payload is a plain mapping, one loaded record is a
plain dict, and the intake console holds both.
"""

from __future__ import annotations

from dataclasses import dataclass, field as config_field
from typing import Any, Mapping, Sequence


#: The naming styles the platform spells a field in.
SNAKE, CAMEL, KEBAB = "snake_case", "camelCase", "kebab-case"
NAME_STYLES: tuple[str, ...] = (SNAKE, CAMEL, KEBAB)

#: What intake does with an input key no field claims.
SKIP, FORBID, COLLECT = "skip", "forbid", "collect"
EXTRA_POLICIES: tuple[str, ...] = (SKIP, FORBID, COLLECT)

#: The value types a shape's fields hold.
TEXT, NUMBER, FLAG = "text", "number", "flag"

#: The two envelopes a partner may wrap one record in: partners on the current
#: contract send ``record`` and the ones still on the 2019 contract send
#: ``attributes``.
ENVELOPES: tuple[str, ...] = ("record", "attributes")

#: Every (field, input key) a loader in this process has read a value from, in
#: order. The intake console prints it after a run so an operator can see which
#: key each field's value came out of. :func:`reset_key_log` clears it.
KEY_LOG: list[dict[str, str]] = []

_JSON_TYPES: Mapping[str, str] = {TEXT: "string", NUMBER: "number", FLAG: "boolean"}


class IntakeError(Exception):
    """Base of everything partner intake raises."""


class ConfigError(IntakeError):
    """A mapping configuration cannot be turned into a loader.

    Raised while the loader is being built, at start-up, where an operator sees
    it against the configuration they wrote -- not once per payload in the
    middle of a partner's run.
    """


class LoadError(IntakeError):
    """One payload was not accepted.

    ``trail`` is what support quotes back to the partner: the input keys this
    failure is about, as the payload spelled them.
    """

    def __init__(self, message: str, trail: Sequence[str] = ()):
        super().__init__(message)
        self.trail: tuple[str, ...] = tuple(str(item) for item in trail)


class MissingFieldError(LoadError):
    """The payload carried nothing for a field the shape requires."""


class TypeMismatchError(LoadError):
    """A value arrived under a key the shape knows, in the wrong type."""


class ExtraFieldsError(LoadError):
    """The payload carried keys intake does not recognise."""


class AmbiguousKeysError(LoadError):
    """The payload named one thing twice and intake will not guess between them."""


def convert_name(name: str, style: str) -> str:
    """The spelling of a field id in one naming style.

    This is the platform's reference for naming: the warehouse export, the
    partner docs generator and intake all call it, so a key any of them speaks
    about comes out of here. A trailing underscore is carried through
    untouched, because trimming it is a separate decision (see
    :class:`MappingConfig`).
    """

    raw = str(name)
    stripped = raw.rstrip("_")
    trailing = raw[len(stripped) :]
    words = [word for word in stripped.split("_") if word]
    if not words:
        raise ValueError(f"a field id needs at least one word: {raw!r}")
    if style == SNAKE:
        body = "_".join(words)
    elif style == CAMEL:
        body = words[0] + "".join(word[:1].upper() + word[1:] for word in words[1:])
    elif style == KEBAB:
        body = "-".join(words)
    else:
        raise ValueError(f"unknown naming style: {style!r}")
    return f"{body}{trailing}"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """One field of a shape, as the warehouse holds it."""

    id: str
    kind: str = TEXT
    required: bool = True
    default: Any = None


@dataclass(frozen=True, slots=True)
class Shape:
    """The record a partner posts, in the order the warehouse holds its fields."""

    name: str
    fields: tuple[FieldSpec, ...]

    def field(self, field_id: str) -> FieldSpec:
        for spec in self.fields:
            if spec.id == str(field_id):
                return spec
        raise KeyError(field_id)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(spec.id for spec in self.fields)


@dataclass(frozen=True, slots=True)
class MappingConfig:
    """How one partner's payloads are spelled.

    ``rename``, ``name_style`` and ``trim_trailing_underscore`` decide the key a
    field is published under and written back out under: the field id has its
    trailing underscore trimmed if asked, is spelled in ``name_style`` if one is
    set, and is then replaced outright by a ``rename`` entry if the field has
    one.

    ``aliases`` maps a field id to one further spelling, or a list of them, that
    a partner posts that field under; ``alias_style`` names a naming style, or a
    list of them, to spell every field of the shape in as well. Both describe
    what a partner may send us.

    ``extra_policy`` is what intake does with an input key no field claims:
    ``skip`` ignores it, ``forbid`` bounces the payload, and ``collect`` keeps
    it in the loaded record under the name in ``extra_in``.
    """

    rename: Mapping[str, str] = config_field(default_factory=dict)
    name_style: str | None = None
    trim_trailing_underscore: bool = False
    aliases: Mapping[str, Any] = config_field(default_factory=dict)
    alias_style: Any = None
    extra_policy: str = SKIP
    extra_in: str = "extra"


def merge_configs(*layers: Mapping[str, Any]) -> MappingConfig:
    """One partner's layer over the platform base.

    Configuration arrives in layers -- the platform base first, then whatever a
    partner's own file sets. ``rename`` and ``aliases`` merge field by field, so
    a partner layer that names one field leaves the base's other entries alone;
    every other setting is taken from the last layer that states it.
    """

    merged: dict[str, Any] = {}
    for layer in layers:
        for key, value in dict(layer).items():
            if key in ("rename", "aliases") and isinstance(value, Mapping):
                current = dict(merged.get(key) or {})
                current.update({str(name): item for name, item in value.items()})
                merged[key] = current
            else:
                merged[key] = value
    return MappingConfig(**merged)


def declared_aliases(config: MappingConfig, field_id: str) -> tuple[str, ...]:
    """The spellings ``aliases`` lists for one field, in the order it lists them."""

    raw = dict(config.aliases or {}).get(str(field_id))
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    return tuple(str(item) for item in raw)


def declared_styles(config: MappingConfig) -> tuple[str, ...]:
    """The styles ``alias_style`` names, in the order it names them."""

    raw = config.alias_style
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    return tuple(str(item) for item in raw)


def unwrap_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    """The partner's fields, taken out of whichever envelope they arrived in.

    A payload carrying both envelopes is bounced with :class:`AmbiguousKeysError`
    naming both of them. We do not pick one, and not even when the two hold the
    same fields: nothing in the payload says which the sender meant to be the
    real one, the next payload from that sender may disagree, and a record built
    from the wrong half is indistinguishable downstream from a good one.
    """

    present = [name for name in ENVELOPES if name in raw]
    if len(present) > 1:
        raise AmbiguousKeysError(
            f"the payload arrived in {len(present)} envelopes: {', '.join(present)}",
            trail=tuple(sorted(present)),
        )
    if not present:
        raise MissingFieldError(
            f"the payload is in no envelope we know: {', '.join(sorted(raw)) or 'it is empty'}",
            trail=(),
        )
    body = raw[present[0]]
    if not isinstance(body, Mapping):
        raise TypeMismatchError(
            f"the {present[0]} envelope does not hold a record", trail=(present[0],)
        )
    return {str(key): value for key, value in body.items()}


def coerce(field: FieldSpec, value: Any, key: str) -> Any:
    """Read one input value as the field's type, remembering the key it came from.

    ``key`` is the input key this value was actually taken out of; it is written
    to :data:`KEY_LOG` and, when the value is the wrong type, it is what the
    failure's trail carries back to the partner.
    """

    KEY_LOG.append({"field": str(field.id), "key": str(key)})
    if field.kind == TEXT and isinstance(value, str):
        return value
    if field.kind == NUMBER and isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if field.kind == FLAG and isinstance(value, bool):
        return value
    raise TypeMismatchError(
        f"{field.id} is a {field.kind} and {key} carried {type(value).__name__}",
        trail=(str(key),),
    )


def reset_key_log() -> None:
    """Forget the keys read so far; the console calls this between payloads."""

    KEY_LOG.clear()


def schema_property(field: FieldSpec) -> dict[str, Any]:
    """The published type fragment for one field.

    Partners fetch the input schema and run their own payloads through it before
    posting, so every key that carries this field's value is published with this
    fragment and nothing else.
    """

    fragment: dict[str, Any] = {"title": field.id, "type": _JSON_TYPES[field.kind]}
    if not field.required and field.default is not None:
        fragment["default"] = field.default
    return fragment
