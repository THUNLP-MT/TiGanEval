"""The console runtime every desktop build of the notebook app ships.

This file belongs to the console team and is the same in the desktop app, the
headless runner and the exporter, so it stays as it is. It owns the shell the
front end drives, the output store ``Out[n]`` is served from, the bundle
container on disk, and the two references anything reading or writing a bundle
has to agree with: :func:`split_outputs` for what one cell printed and
:func:`schema_errors` for whether a file is a bundle at all.
"""

from __future__ import annotations

import ast
import builtins
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
import zipfile

#: The container: a zip holding these two members and nothing else, and the
#: marker that replaces a pattern the exporter was asked to take out.
BUNDLE_FORMAT, FORMAT_VERSION = "session-bundle", 1
METADATA_NAME, EVENTS_NAME = "metadata.json", "events.jsonl"
REDACTION_MARKER = "<removed>"

#: The four things the console can put on screen while a cell runs.
OUT_STREAM, ERR_STREAM = "out_stream", "err_stream"
EXECUTE_RESULT, DISPLAY_DATA = "execute_result", "display_data"

REQUIRED_METADATA: tuple[str, ...] = (
    "format", "format_version", "created_at", "console_version", "python_version",
    "platform", "redacted_patterns")
REQUIRED_EVENT_KEYS: tuple[str, ...] = (
    "type", "seq", "recorded_at", "execution_count", "code", "success", "stdout",
    "stderr", "execute_result")

CONSOLE_VERSION, PLATFORM, PYTHON_VERSION = "3.4.1", "console-desktop", "3.12"
#: What a cell may import. The console runs customer code, so the list is short.
ALLOWED_IMPORTS: tuple[str, ...] = ("json", "math", "statistics", "sys")

class BundleError(Exception):
    """Base of everything the bundle machinery raises."""

class BundleRejected(BundleError):
    """A file was not admitted as a bundle; ``errors`` holds its fault codes."""
    def __init__(self, path: Any, errors: Sequence[str]):
        self.path = str(path)
        self.errors = tuple(str(code) for code in errors)
        super().__init__(f"{self.path} is not a bundle this console will run")

@dataclass(frozen=True, slots=True)
class Output:
    """One thing the console put on screen, and where in the scrollback it went."""
    kind: str
    text: str
    index: int

class OutputStore:
    """Everything the console has printed, per execution counter and in order.

    ``entries`` is kept per counter because ``Out[n]`` is served from it long
    after cell n finished, so nothing is dropped and two cells that occupy one
    counter both append there; ``printed`` is the scrollback.
    """
    def __init__(self) -> None:
        self.entries: dict[int, list[Output]] = {}
        self.printed: list[Output] = []

    @property
    def count(self) -> int:
        return len(self.printed)

    def record(self, counter: int, kind: str, text: str) -> Output:
        entry = Output(kind=str(kind), text=str(text), index=len(self.printed))
        self.entries.setdefault(int(counter), []).append(entry)
        self.printed.append(entry)
        return entry

    def of(self, counter: int) -> tuple[Output, ...]:
        """Everything ever printed under one execution counter."""
        return tuple(self.entries.get(int(counter), ()))

    def since(self, mark: int) -> tuple[Output, ...]:
        """Everything printed after the scrollback stood at ``mark``."""
        return tuple(self.printed[int(mark) :])

class OutView:
    """``Out[n]``: the value cell n came back with, as the console printed it."""
    def __init__(self, store: OutputStore):
        self._store = store

    def __getitem__(self, counter: int) -> str:
        for entry in reversed(self._store.of(counter)):
            if entry.kind == EXECUTE_RESULT:
                return entry.text
        raise KeyError(counter)

def split_outputs(entries: Sequence[Output]) -> dict[str, str]:
    """One cell's console entries, split the way a bundle records them.

    Writes to stdout and stderr keep their own fields; the value the cell's last
    expression evaluated to is the execute result and is in neither stream, and
    a cell whose last statement is not an expression, or is None, has none.
    """
    ordered = sorted(entries, key=lambda entry: entry.index)
    results = [entry.text for entry in ordered if entry.kind == EXECUTE_RESULT]
    return {
        "stdout": "".join(entry.text for entry in ordered if entry.kind == OUT_STREAM),
        "stderr": "".join(entry.text for entry in ordered if entry.kind == ERR_STREAM),
        "execute_result": results[-1] if results else "",
    }

def format_error(error: BaseException) -> dict[str, Any]:
    """The error a cell ended on: no paths and no line numbers, so the same
    failure exports the same lines from any machine."""
    frames: list[str] = []
    trace = error.__traceback__
    while trace is not None:
        frames.append(f"  in {trace.tb_frame.f_code.co_name}")
        trace = trace.tb_next
    name, value = type(error).__name__, str(error)
    return {"ename": name, "evalue": value, "traceback": [*frames, f"{name}: {value}"]}

_TICKS = [0]

def now() -> str:
    """The console's clock reading, one second later on every call."""
    _TICKS[0] += 1
    return f"2026-03-11T09:{_TICKS[0] // 60 % 60:02d}:{_TICKS[0] % 60:02d}Z"

def reset_time() -> None:
    """Put the console's clock back to the start of a session."""
    _TICKS[0] = 0

def console_metadata() -> dict[str, Any]:
    """The environment fields every bundle's metadata carries."""
    return {"format": BUNDLE_FORMAT, "format_version": FORMAT_VERSION,
            "console_version": CONSOLE_VERSION, "python_version": PYTHON_VERSION,
            "platform": PLATFORM}

@dataclass(frozen=True, slots=True)
class CellInfo:
    """What the front end is about to run, handed to every pre_run_cell hook."""
    code: str
    counter: int
    store_history: bool

@dataclass(frozen=True, slots=True)
class CellResult:
    """What the front end has just run, handed to every post_run_cell hook.

    ``counter`` is the counter the cell occupied in the store;
    ``execution_count`` is the number the console gave it, None when it ran the
    cell quietly and gave it no number at all.
    """
    code: str
    counter: int
    execution_count: int | None
    success: bool
    error: BaseException | None

@dataclass(frozen=True, slots=True)
class ReplayReport:
    """What a replay did: the events it ran, and the one it stopped on."""
    executed: tuple[int, ...] = ()
    stopped_at: int | None = None

class EventManager:
    """The console's hook points: ``pre_run_cell`` and ``post_run_cell``."""
    def __init__(self, names: Sequence[str]):
        self._callbacks: dict[str, list[Callable[..., Any]]] = {str(name): [] for name in names}

    def register(self, name: str, callback: Callable[..., Any]) -> None:
        self._callbacks[str(name)].append(callback)

    def unregister(self, name: str, callback: Callable[..., Any]) -> None:
        self._callbacks[str(name)].remove(callback)

    def callbacks(self, name: str) -> tuple[Callable[..., Any], ...]:
        return tuple(self._callbacks[str(name)])

    def registered(self) -> dict[str, list[str]]:
        """The name of every callback attached to each hook point."""
        return {name: [getattr(item, "__qualname__", repr(item)) for item in callbacks]
                for name, callbacks in self._callbacks.items()}

class _Stream:
    """stdout or stderr while a cell runs: one entry per write."""
    def __init__(self, store: OutputStore, counter: int, kind: str):
        self._store, self._counter, self._kind = store, int(counter), str(kind)

    def write(self, text: str) -> int:
        if text:
            self._store.record(self._counter, self._kind, str(text))
        return len(text)

    def flush(self) -> None:
        return None

def _guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
    if str(name).split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"the console does not import {name!r} for a cell")
    return builtins.__import__(name, *args, **kwargs)

_SAFE_NAMES = (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "float", "format", "int",
    "isinstance", "len", "list", "max", "min", "print", "range", "repr", "reversed", "round",
    "set", "sorted", "str", "sum", "tuple", "zip", "Exception", "KeyError", "RuntimeError",
    "TypeError", "ValueError", "ZeroDivisionError", "True", "False", "None")
SAFE_BUILTINS: dict[str, Any] = {name: getattr(builtins, name) for name in _SAFE_NAMES}
SAFE_BUILTINS["__import__"] = _guarded_import

def _execute(code: str, namespace: dict[str, Any]) -> Any:
    """Run one cell's source and return the value of its last expression."""
    module = ast.parse(code, filename="<cell>")
    body = list(module.body)
    tail = body.pop() if body and isinstance(body[-1], ast.Expr) else None
    if body:
        exec(compile(ast.Module(body=body, type_ignores=[]), "<cell>", "exec"), namespace)
    if tail is None:
        return None
    return eval(compile(ast.Expression(tail.value), "<cell>", "eval"), namespace)

class Shell:
    """The console's Python shell: one namespace, one output store, two hooks."""
    def __init__(self, execution_count: int = 1):
        self.execution_count = int(execution_count)
        self.history = OutputStore()
        self.events = EventManager(("pre_run_cell", "post_run_cell"))
        self.user_ns: dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS),
                                        "Out": OutView(self.history)}

    def run_cell(self, code: str, store_history: bool = True) -> CellResult:
        """Run one cell the way the front end runs it.

        The cell occupies the counter ``execution_count`` holds, and that
        counter advances only for a numbered cell, so a quiet cell and the
        numbered cell after it write into one place. Both hooks fire for both.
        """
        counter = self.execution_count
        info = CellInfo(code=str(code), counter=counter, store_history=bool(store_history))
        for callback in self.events.callbacks("pre_run_cell"):
            callback(info)
        error: BaseException | None = None
        out = _Stream(self.history, counter, OUT_STREAM)
        err = _Stream(self.history, counter, ERR_STREAM)
        with redirect_stdout(out), redirect_stderr(err):
            try:
                value = _execute(str(code), self.user_ns)
                if value is not None:
                    self.history.record(counter, EXECUTE_RESULT, repr(value))
            except BaseException as exc:  # noqa: BLE001 - the cell's own failure
                error = exc
        result = CellResult(
            code=str(code), counter=counter, success=error is None, error=error,
            execution_count=counter if store_history else None)
        if store_history:
            self.execution_count = counter + 1
        for callback in self.events.callbacks("post_run_cell"):
            callback(result)
        return result

def write_bundle(path: Any, metadata: Mapping[str, Any],
                 events: Sequence[Mapping[str, Any]], *, overwrite: bool = False) -> str:
    """Publish one bundle: ``metadata.json`` and ``events.jsonl`` inside a zip.

    The archive is built beside the target and moved into place, so the target
    is always the bundle that was there before or the finished new one. Raises
    ``FileExistsError`` when the target exists and ``overwrite`` is off.
    """
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(str(target))
    body = json.dumps(dict(metadata), ensure_ascii=False, indent=2, sort_keys=True)
    lines = "".join(json.dumps(dict(event), ensure_ascii=False, sort_keys=True) + "\n"
                    for event in events)
    part = target.with_name(target.name + ".part")
    with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in ((METADATA_NAME, body), (EVENTS_NAME, lines)):
            archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), text)
    os.replace(part, target)
    return str(target)

def read_bundle(path: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The two members of a bundle as objects. It checks nothing and runs nothing."""
    with zipfile.ZipFile(Path(path)) as archive:
        metadata = json.loads(archive.read(METADATA_NAME).decode("utf-8"))
        lines = archive.read(EVENTS_NAME).decode("utf-8").splitlines()
    return dict(metadata), [json.loads(line) for line in lines if line.strip()]

def schema_errors(metadata: Mapping[str, Any],
                  events: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Everything wrong with one bundle, as codes rather than prose.

    Files reach this console from other machines, other console builds,
    truncated uploads and text editors, so this is the one description of what
    the format requires: the container fields, a declared ``event_count`` that
    matches, one event per cell of type ``cell``, ``seq`` running from 1 in
    execution order, an integer ``execution_count`` that rises event to event,
    an execute result carrying ``text/plain`` when it is not empty, and a failed
    event carrying an error with a non-empty traceback. Empty means the file is
    a bundle this console will run.
    """
    codes: list[str] = []
    if metadata.get("format") != BUNDLE_FORMAT:
        codes.append("metadata.format")
    version = metadata.get("format_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        codes.append("metadata.format_version")
    for key in REQUIRED_METADATA:
        if key not in metadata:
            codes.append(f"metadata.missing:{key}")
    if "event_count" in metadata and metadata["event_count"] != len(events):
        codes.append("metadata.event_count")
    previous: int | None = None
    for position, event in enumerate(events, start=1):
        prefix = f"event.{position}"
        if not isinstance(event, Mapping):
            codes.append(f"{prefix}.type")
            continue
        for key in REQUIRED_EVENT_KEYS:
            if key not in event:
                codes.append(f"{prefix}.missing:{key}")
        if event.get("type") != "cell":
            codes.append(f"{prefix}.type")
        if event.get("seq") != position:
            codes.append(f"{prefix}.seq")
        counter = event.get("execution_count")
        if not isinstance(counter, int) or isinstance(counter, bool) or (
                previous is not None and counter <= previous):
            codes.append(f"{prefix}.execution_count")
        else:
            previous = counter
        codes += [f"{prefix}.{key}" for key in ("code", "stdout", "stderr")
                  if key in event and not isinstance(event.get(key), str)]
        result = event.get("execute_result")
        if not isinstance(result, Mapping) or (
                result and not isinstance(result.get("text/plain"), str)):
            codes.append(f"{prefix}.execute_result")
        if event.get("success") is False:
            error = event.get("error") if isinstance(event.get("error"), Mapping) else {}
            trace = error.get("traceback")
            if not (error.get("ename") and error.get("evalue") and isinstance(trace, list) and trace):
                codes.append(f"{prefix}.error")
        elif event.get("success") is not True:
            codes.append(f"{prefix}.success")
    return tuple(codes)
