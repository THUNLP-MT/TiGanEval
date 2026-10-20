"""What the audit knows about the pipeline's own steps.

Three things, and all of them are about the whole pipeline rather than one
module: which of a step's arguments it has been handed a personal field in,
whether what the step gives back carries one on its own, and which of its
arguments it builds that answer out of. The last one is what keeps a shared
line builder from turning every one of its callers personal: a call is read as
that call, with the values it passes, not as the worst call anyone makes.

Every body of the pipeline is read the same way, whether it is a module, a step
or a hand-off written inside a step: names arrive empty unless the step itself
was handed a personal field. A call is a call wherever it is written, so a
hand-off inside a step hands the field on exactly as the step would.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence

from .protocol import ModuleSet, assignments, body_nodes, carries


@dataclass(frozen=True, slots=True)
class Body:
    """One body the audit reads: a module, a step, or a hand-off inside one."""

    module: str
    step: str  # "" for a module body and for a hand-off written inside a step
    nodes: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class Pipeline:
    """Every step of the pipeline, and what has settled about each of them."""

    steps: Mapping[str, Any]
    bodies: tuple[Body, ...]
    given: Mapping[str, frozenset[str]]
    answers_alone: Mapping[str, bool]
    answers_from: Mapping[str, frozenset[str]]


def read_bodies(modules: ModuleSet) -> tuple[Body, ...]:
    """Every body of the pipeline, in an order the checkout cannot change."""

    owner = {id(node): name for name, (_module, node) in modules.steps().items()}
    bodies: list[Body] = []
    for name, tree in modules.iter_modules("sorted"):
        bodies.append(Body(str(name), "", body_nodes(tree.body)))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bodies.append(Body(str(name), owner.get(id(node), ""), body_nodes(node.body)))
    return tuple(bodies)


def parameter_names(definition: Any) -> tuple[str, ...]:
    """Every name a step's arguments arrive under."""

    spec = definition.args
    names = [item.arg for item in (*spec.posonlyargs, *spec.args, *spec.kwonlyargs)]
    if spec.vararg is not None:
        names.append(spec.vararg.arg)
    if spec.kwarg is not None:
        names.append(spec.kwarg.arg)
    return tuple(names)


def handed_arguments(call: Any, definition: Any) -> Iterator[tuple[str, Any]]:
    """Every `argument name, value` one call hands the step it names."""

    spec = definition.args
    positional = [item.arg for item in (*spec.posonlyargs, *spec.args)]
    vararg = spec.vararg.arg if spec.vararg is not None else None
    kwarg = spec.kwarg.arg if spec.kwarg is not None else None
    named = set(positional) | {item.arg for item in spec.kwonlyargs}

    place = 0
    for value in call.args:
        if isinstance(value, ast.Starred):
            for name in positional[place:]:
                yield name, value.value
            if vararg is not None:
                yield vararg, value.value
            place = len(positional)
            continue
        if place < len(positional):
            yield positional[place], value
        elif vararg is not None:
            yield vararg, value
        place += 1

    for item in call.keywords:
        if item.arg is None:
            for name in sorted(named):
                yield name, item.value
            if kwarg is not None:
                yield kwarg, item.value
        elif item.arg in named:
            yield str(item.arg), item.value
        elif kwarg is not None:
            yield kwarg, item.value


def step_calls(nodes: Sequence[Any], steps: Mapping[str, Any]) -> Iterator[Any]:
    """Every call in these nodes that names a step of the pipeline."""

    for node in nodes:
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in steps
        ):
            yield node


def carries_here(node: Any, tainted: Any, pipeline: Pipeline) -> bool:
    """Whether one expression hands out a personal field where it is written."""

    return carries(node, tainted, _answers_here(node, tainted, pipeline))


def carrying_names(nodes: Any, given: Any, pipeline: Pipeline) -> frozenset[str]:
    """The names of one body that carry a personal field, to a fixed point."""

    tainted = {str(name) for name in given}
    bound = assignments(nodes)
    changed = True
    while changed:
        changed = False
        for name, value in bound:
            if name not in tainted and carries_here(value, tainted, pipeline):
                tainted.add(name)
                changed = True
    return frozenset(tainted)


def settle(modules: ModuleSet) -> Pipeline:
    """Read the whole pipeline until the three summaries stop changing."""

    steps = {name: node for name, (_module, node) in modules.steps().items()}
    bodies = read_bodies(modules)
    given: dict[str, set[str]] = {name: set() for name in steps}
    alone: dict[str, bool] = {name: False for name in steps}
    built_from: dict[str, set[str]] = {name: set() for name in steps}

    def settled() -> Pipeline:
        return Pipeline(
            steps,
            bodies,
            {name: frozenset(value) for name, value in given.items()},
            dict(alone),
            {name: frozenset(value) for name, value in built_from.items()},
        )

    changed = True
    while changed:
        changed = False
        pipeline = settled()
        for name in sorted(steps):
            nodes = body_nodes(steps[name].body)
            if not alone[name] and _answers(nodes, (), pipeline):
                alone[name] = True
                changed = True
            for argument in parameter_names(steps[name]):
                if argument not in built_from[name] and _answers(nodes, (argument,), pipeline):
                    built_from[name].add(argument)
                    changed = True
        for body in bodies:
            tainted = carrying_names(body.nodes, given.get(body.step, ()), pipeline)
            for call in step_calls(body.nodes, steps):
                callee = call.func.id
                for argument, value in handed_arguments(call, steps[callee]):
                    if argument in given[callee]:
                        continue
                    if carries_here(value, tainted, pipeline):
                        given[callee].add(argument)
                        changed = True
    return settled()


def _answers(nodes: Any, given: Any, pipeline: Pipeline) -> bool:
    """Whether what this body gives back carries a personal field."""

    tainted = carrying_names(nodes, given, pipeline)
    return any(
        isinstance(node, ast.Return) and carries_here(node.value, tainted, pipeline)
        for node in nodes
    )


def _answers_here(node: Any, tainted: Any, pipeline: Pipeline) -> dict[str, bool]:
    """For each step this one expression calls, whether that call gives back a
    personal field: the step's own answer, or the values this call passes it."""

    decided: dict[str, bool] = {}
    for call in step_calls(tuple(ast.walk(node)) if node is not None else (), pipeline.steps):
        name = call.func.id
        if decided.get(name):
            continue
        decided[name] = _call_answers(call, tainted, pipeline)
    return decided


def _call_answers(call: Any, tainted: Any, pipeline: Pipeline) -> bool:
    name = call.func.id
    if pipeline.answers_alone.get(name, False):
        return True
    built_from = pipeline.answers_from.get(name, frozenset())
    return any(
        argument in built_from and carries_here(value, tainted, pipeline)
        for argument, value in handed_arguments(call, pipeline.steps[name])
    )
