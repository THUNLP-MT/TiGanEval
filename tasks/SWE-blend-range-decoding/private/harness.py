'Deterministic, sandboxed review of one catalogue-compositor workspace.'

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import build_program

TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("plate/bands.py", "plate/compose.py", "plate/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-plate-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "export", "offset": 17}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "catalogue-knockout": {"profile": "knockout", "offset": 3},
    "lit-from-beneath": {"profile": "passthrough", "offset": 5},
    "two-colour-logo": {"profile": "logo", "offset": 7},
    "untouched-batch": {"profile": "untouched", "offset": 11},
}

BUCKETS: Mapping[str, str] = {
    "untouched_shots_come_back_unchanged": "plain_failures",
    "source_files_survive_the_export": "resave_failures",
    "backdrop_cuts_read_the_plate_beneath": "operand_failures",
    "split_grips_fade": "fade_failures",
    "entries_address_declared_channels": "channel_failures",
}

COMPOSITE = "*"
_CACHE = AnalysisCache()
_FROZEN: Any = None


def frozen_protocol() -> Any:
    'The contract module as it ships, loaded from the pristine workspace.'

    global _FROZEN
    if _FROZEN is None:
        path = TASK_ROOT / "workspace" / "plate" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_frozen_plate_protocol", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _FROZEN = module
    return _FROZEN


def _grips(word: int, variant: str) -> tuple[int, int]:
    left, right = frozen_protocol().unpack_handles(word)
    if left == right:
        return left, right
    if variant == "low_byte":
        return left, left
    if variant == "step_right":
        return right, right
    if variant == "step_mid":
        middle = (left + right) // 2
        return middle, middle
    return left, right


def _dark_weight(value: float, left: int, right: int) -> float:
    if value >= right:
        return 1.0
    if value <= left:
        return 0.0
    return (value - left) / (right - left)


def _light_weight(value: float, left: int, right: int) -> float:
    if value <= left:
        return 1.0
    if value >= right:
        return 0.0
    return (right - value) / (right - left)


def _role(index: int, channels: Sequence[str], variant: str) -> str | None:
    'What one stored entry is read against, or None where it contributes nothing.'

    transparency = frozen_protocol().TRANSPARENCY
    if variant == "offset_entries":
        channel = channels[index] if index < len(channels) else None
        return None if channel in (None, transparency) else channel
    if index == 0:
        return None if variant == "channels_only" else COMPOSITE
    if variant == "composite_only":
        return None
    position = index - 1
    if position >= len(channels):
        return COMPOSITE if variant == "apply_spare_as_composite" else None
    channel = channels[position]
    if channel == transparency and variant != "apply_transparency":
        return None
    return channel


def _samples(
    role: str,
    layer: Any,
    pixel: Sequence[int],
    beneath: Sequence[int],
    backdrop: Sequence[int],
) -> tuple[float, float, float]:
    'The value this entry is read against on the layer, on the plate beneath     it, and on the backdrop the shot started from.'

    protocol = frozen_protocol()
    if role == COMPOSITE:
        return (
            protocol.luminosity(protocol.colour_of(pixel, layer.channels)),
            protocol.luminosity(beneath),
            protocol.luminosity(backdrop),
        )
    own = float(protocol.channel_value(pixel, layer.channels, role))
    if role == protocol.TRANSPARENCY:
        return own, 255.0, 255.0
    at = protocol.COLOUR_CHANNELS.index(role)
    return own, float(beneath[at]), float(backdrop[at])


def _entry_weights(
    entry: Sequence[int], own: float, under: float, backdrop: float, variant: str
) -> list[float]:
    grips = [_grips(word, variant) for word in entry]
    first = under if variant == "swap_operands" else own
    weights = [
        _dark_weight(first, *grips[0]),
        _light_weight(first, *grips[1]),
    ]
    if variant == "drop_under":
        return weights
    if variant in ("swap_operands", "source_operand"):
        second = own
    elif variant == "bottom_backdrop":
        second = backdrop
    else:
        second = under
    weights.append(_dark_weight(second, *grips[2]))
    if variant != "drop_under_light":
        weights.append(_light_weight(second, *grips[3]))
    return weights


def _layer_weight(
    layer: Any,
    pixel: Sequence[int],
    beneath: Sequence[int],
    backdrop: Sequence[int],
    variant: str,
) -> float:
    protocol = frozen_protocol()
    if layer.block is None or variant == "plain":
        return 1.0
    weights: list[float] = []
    for index, entry in enumerate(protocol.entries(layer.block)):
        role = _role(index, layer.channels, variant)
        if role is None:
            continue
        own, under, base = _samples(role, layer, pixel, beneath, backdrop)
        weights.extend(_entry_weights(entry, own, under, base, variant))
    return protocol.combine(weights)


def render(document: Any, variant: str = "true") -> tuple[tuple[tuple[int, ...], ...], ...]:
    "The plate this shot's stored range work produces, read one way."

    protocol = frozen_protocol()
    plate = [list(row) for row in document.backdrop]
    layers = tuple(document.layers)
    for layer_index, layer in enumerate(layers):
        for row in range(document.rows):
            for column in range(document.columns):
                pixel = layer.pixel(row, column)
                beneath = plate[row][column]
                if variant == "top_layer_only" and layer_index < len(layers) - 1:
                    weight = 1.0
                else:
                    weight = _layer_weight(
                        layer, pixel, beneath, document.backdrop[row][column], variant
                    )
                opacity = (
                    255
                    if variant == "ranged_opaque" and layer.block is not None
                    else layer.opacity
                )
                plate[row][column] = protocol.mix(
                    beneath, pixel, layer.channels, weight, opacity
                )
    return tuple(tuple(tuple(int(v) for v in pixel) for pixel in row) for row in plate)


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _safe_error(text: Any) -> str:
    'One raised line as the batch log would show it: the directory part of any     path stripped, and a line the owner would not say replaced.'

    line = _DIRECTORY_PART.sub("", str(text or "no message").strip())
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return "the step ended without saying why"
    return line[:200]


def _failure(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _as_grid(value: Any) -> tuple[tuple[tuple[int, ...], ...], ...]:
    return tuple(
        tuple(tuple(int(number) for number in pixel) for pixel in row) for row in value
    )


def _size(grid: Sequence[Sequence[Any]]) -> str:
    columns = len(grid[0]) if grid else 0
    return f"{len(grid)} rows x {columns} columns"


def _covers(produced: Sequence[Sequence[Any]], reference: Sequence[Sequence[Any]]) -> bool:
    "Whether this build's plate holds a pixel for every pixel of the published     one, so that the two can be compared at all."

    return len(produced) == len(reference) and all(
        len(made) == len(want) for made, want in zip(produced, reference)
    )


def entry_grips(block: Sequence[int] | None) -> list[str]:
    'Every stored entry of one block, written out as its four grip pairs.'

    protocol = frozen_protocol()
    lines = []
    for entry in protocol.entries(block):
        pairs = [protocol.unpack_handles(word) for word in entry]
        lines.append(
            " ".join(f"({left},{right})" for left, right in pairs[:2])
            + " | "
            + " ".join(f"({left},{right})" for left, right in pairs[2:])
        )
    return lines


def read_steps(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'One row per export step, with the plate the design tool publishes beside it.'

    protocol = frozen_protocol()
    steps: list[dict[str, Any]] = []
    for event, record in zip(program, candidate.get("records", ())):
        step: dict[str, Any] = {**dict(record), "event": dict(event)}
        document = protocol.read_document(dict(event["document"]))
        step["document"] = document
        step["variants"] = {}
        if str(record.get("type")) == "render":
            step["reference"] = render(document, "true")
            if step.get("ok"):
                try:
                    step["produced"] = _as_grid(step.get("plate"))
                except (TypeError, ValueError):
                    step["ok"] = False
                    step["error"] = "the exporter published a plate this format cannot read"
            if step.get("ok") and not _covers(step["produced"], step["reference"]):


                step["ok"] = False
                step["error"] = (
                    f"the exporter published {_size(step['produced'])} for a shot of "
                    f"{_size(step['reference'])}"
                )
        steps.append(step)
    return steps


def _variant(step: Mapping[str, Any], name: str) -> Any:
    cache = step["variants"]
    if name not in cache:
        cache[name] = render(step["document"], name)
    return cache[name]


def _group(steps: Sequence[Mapping[str, Any]], checks: str) -> list[Mapping[str, Any]]:
    return [
        step
        for step in steps
        if str(step.get("type")) == "render" and str(step["event"].get("checks")) == checks
    ]


def _difference(step: Mapping[str, Any]) -> dict[str, Any] | None:
    "The first pixel where this build's plate is not the published one."

    produced, reference = step["produced"], step["reference"]
    for row, (made, want) in enumerate(zip(produced, reference)):
        for column, (printed, expected) in enumerate(zip(made, want)):
            if tuple(printed) != tuple(expected):
                return {
                    "at": f"row {row}, column {column}",
                    "printed": ", ".join(str(number) for number in printed),
                    "expected": ", ".join(str(number) for number in expected),
                }
    return None


def _matched(group: Sequence[Mapping[str, Any]], names: Sequence[str]) -> str | None:
    'The misreading whose plates this build reproduces on every shot it was given.'

    for name in names:
        if all(step["produced"] == _variant(step, name) for step in group):
            return name
    return None


def _render_failures(
    steps: Sequence[Mapping[str, Any]],
    checks: str,
    raised_mode: str,
    known: Sequence[tuple[str, str]],
    fallback: str,
) -> list[dict[str, Any]]:
    group = _group(steps, checks)
    stopped = [
        _failure(raised_mode, shot=str(step.get("label")), error=_safe_error(step.get("error")))
        for step in group
        if not step.get("ok")
    ]
    if stopped:
        return stopped
    wrong = [step for step in group if _difference(step) is not None]
    if not wrong:
        return []
    matched = _matched(group, [name for name, _ in known])
    mode = dict(known).get(str(matched), fallback)
    return [
        _failure(mode, shot=str(step.get("label")), **dict(_difference(step)))
        for step in wrong
    ]


def _plain_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    group = _group(steps, "plain")
    stopped: list[dict[str, Any]] = []
    for step in group:
        if step.get("ok"):
            continue


        refused = str(step.get("stopped_on_layer") or "")
        absent = [
            layer.name
            for layer in step["document"].layers
            if layer.block is None and layer.name == refused
        ]
        if absent:
            stopped.append(
                _failure(
                    "absent_block_rejected",
                    shot=str(step.get("label")),
                    layer=str(absent[0]),
                    error=_safe_error(step.get("error")),
                )
            )
        else:
            stopped.append(
                _failure(
                    "untouched_render_failed",
                    shot=str(step.get("label")),
                    error=_safe_error(step.get("error")),
                )
            )
    if stopped:
        return stopped
    matched = _matched(group, ("ranged_opaque",))
    mode = "default_block_ignored_opacity" if matched else "default_cut_changed_the_plate"
    return [
        _failure(
            mode,
            shot=str(step.get("label")),
            **dict(_difference(step)),
        )
        for step in group
        if _difference(step) is not None
    ]


def _stored_pair(word: int) -> str:
    try:
        left, right = frozen_protocol().unpack_handles(word)
    except Exception:
        return str(word)
    return f"{left} and {right}"


def _word_failure(shot: str, layer: str, stored: int, written: int) -> dict[str, Any]:
    protocol = frozen_protocol()
    try:
        left, right = protocol.unpack_handles(stored)
        made_left, made_right = protocol.unpack_handles(written)
        collapsed = left != right and made_left == made_right
    except Exception:
        collapsed = False
    return _failure(
        "split_handle_collapsed" if collapsed else "stored_word_changed",
        shot=shot,
        layer=layer,
        stored=_stored_pair(stored),
        written=_stored_pair(written),
    )


def _resave_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in steps:
        if str(step.get("type")) != "resave":
            continue

        shot = str(step["document"].shot)
        if not step.get("ok"):
            failures.append(
                _failure(
                    "resave_step_failed", shot=shot, error=_safe_error(step.get("error"))
                )
            )
            continue
        written = list(step.get("written") or ())
        for index, layer in enumerate(step["document"].layers):
            entry = dict(written[index]) if index < len(written) else {}
            stored, made = layer.block, entry.get("block")
            name = str(entry.get("layer", layer.name))
            if stored is None:
                if made is not None:
                    failures.append(_failure("absent_block_replaced", shot=shot, layer=name))
                continue
            if made is None or len(made) != len(stored):
                failures.append(
                    _failure(
                        "stored_block_length_changed",
                        shot=shot,
                        layer=name,
                        stored_words=len(stored),
                        written_words=0 if made is None else len(made),
                    )
                )
                continue
            for before, after in zip(stored, made):
                if int(before) != int(after):
                    failures.append(_word_failure(shot, name, int(before), int(after)))
                    break
    return failures


def _operand_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return _render_failures(
        steps,
        "operand",
        "operand_render_failed",
        (
            ("drop_under", "backdrop_cuts_ignored"),
            ("drop_under_light", "under_light_not_applied"),
            ("source_operand", "backdrop_cuts_read_the_layer"),
            ("bottom_backdrop", "backdrop_is_not_the_plate_beneath"),
            ("swap_operands", "layer_cuts_read_the_backdrop"),
            ("top_layer_only", "range_work_skipped_below_top_layer"),
        ),
        "operand_weight_wrong",
    )


def _fade_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return _render_failures(
        steps,
        "fade",
        "fade_render_failed",
        (
            ("low_byte", "split_grips_stepped"),
            ("step_right", "split_grips_stepped"),
            ("step_mid", "split_grips_stepped"),
        ),
        "fade_shape_wrong",
    )


def _channel_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return _render_failures(
        steps,
        "channels",
        "channel_render_failed",
        (
            ("offset_entries", "composite_entry_applied_to_a_colour_channel"),
            ("apply_transparency", "transparency_entry_applied"),
            ("apply_spare_as_composite", "unaddressed_entry_applied"),
            ("composite_only", "colour_entries_not_applied"),
            ("channels_only", "composite_entry_not_applied"),
        ),
        "channel_weight_wrong",
    )


def _analyse(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    steps = read_steps(candidate, program)
    return {
        "plain_failures": _plain_failures(steps),
        "resave_failures": _resave_failures(steps),
        "operand_failures": _operand_failures(steps),
        "fade_failures": _fade_failures(steps),
        "channel_failures": _channel_failures(steps),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the batch log shows when the export did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the export box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the exporter ended without saying why"
    return f"the export did not complete: {_safe_error(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private export against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        case = PRIVATE_CASE
        program = build_program(str(case["profile"]), int(case["offset"]))
        candidate = PROJECT.invoke(artifact_dir, {"events": list(program)})
        if not candidate.get("ok"):
            error = _console_error(candidate)
            analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            analysis = dict(_analyse(candidate, program))
        analysis["case"] = {"export": str(PRIVATE_CASE["profile"])}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
