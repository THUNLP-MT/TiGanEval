'Deterministic, sandboxed analysis of one delivery portal workspace.'

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import RECORDS, build_program, outline


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("surface/routing.py", "surface/metering.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-portal-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}

BUCKETS: Mapping[str, str] = {
    "body_free_projection": "projection_failures",
    "path_method_advertisement": "advertisement_failures",
    "layered_defaults_resolution": "layer_failures",
    "explicit_operations_win": "explicit_failures",
    "generated_traffic_accounting": "accounting_failures",
}


LAYER_NAMES = ("the operation", "the mount", "the router", "the service", "the service")
NO_ANSWER = (None, 404, 405)

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `surface/protocol.py`, loaded from the project's own tree."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "surface" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_surface_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def _nothing(request: Any, values: Any) -> Any:
    raise RuntimeError("the reference table does not serve requests")


def _deciding_layer(name: str, layers: tuple[Mapping[str, Any], ...]) -> str:
    for index, layer in enumerate(layers):
        if name in dict(layer or {}):
            return LAYER_NAMES[min(index, len(LAYER_NAMES) - 1)]
    return "the platform's own default"


def _reference(assembly: Mapping[str, Any]) -> dict[str, Any]:
    "Everything the portal's own rules say this surface must serve."

    protocol = reference_protocol()
    nodes: dict[str, dict[str, Any]] = {}
    for step in assembly.get("steps", ()):
        op = str(step["op"])
        if op in ("service", "router"):
            name = "app" if op == "service" else str(step["name"])
            nodes[name] = {"settings": dict(step.get("settings") or {}), "routes": [], "mounts": []}
        elif op == "route":
            nodes[str(step["router"])]["routes"].append(step)
        else:
            nodes[str(step.get("into", "app"))]["mounts"].append(step)

    rows: list[dict[str, Any]] = []

    def walk(name: str, prefix: str, mount: Mapping[str, Any], outside: tuple) -> None:
        node = nodes[name]
        around = (dict(mount), node["settings"], *outside)
        for route in node["routes"]:
            layers = (dict(route.get("settings") or {}), *around)
            rows.append({
                "path": f"{prefix}{route['path']}", "local_path": str(route["path"]),
                "method": str(route["method"]).upper(), "name": str(route.get("name", "")),
                "summary": str(route.get("summary", "")), "cost": int(route.get("cost", 1)),
                "published": bool(protocol.layer_value("in_catalogue", layers, default=True)),
                "auto_head": bool(protocol.layer_value("auto_head", layers, default=True)),
                "auto_options": bool(protocol.layer_value("auto_options", layers, default=False)),
                "head_layer": _deciding_layer("auto_head", layers),
                "options_layer": _deciding_layer("auto_options", layers),
            })
        for entry in node["mounts"]:
            walk(str(entry["router"]), f"{prefix}{entry['prefix']}",
                 dict(entry.get("settings") or {}), around)

    walk("app", "", {}, ())
    paths = list(dict.fromkeys(row["path"] for row in rows))
    here = {path: [row for row in rows if row["path"] == path] for path in paths}
    methods = {path: [row["method"] for row in here[path]] for path in paths}
    generated: dict[tuple[str, str], str] = {}
    for path in paths:
        if protocol.PROBE_METHOD in methods[path]:
            continue


        reads = [row for row in here[path] if row["method"] == "GET"]
        if reads and reads[0]["auto_head"]:
            generated[(path, protocol.PROBE_METHOD)] = reads[0]["head_layer"]
            methods[path].append(protocol.PROBE_METHOD)
    for path in paths:
        if protocol.SUMMARY_METHOD in methods[path]:
            continue
        source = [row for row in here[path] if row["auto_options"]]
        if source:
            generated[(path, protocol.SUMMARY_METHOD)] = source[0]["options_layer"]
            methods[path].append(protocol.SUMMARY_METHOD)
    catalogue = protocol.build_catalogue(
        protocol.Endpoint(
            path=row["path"], method=row["method"], handler=_nothing,
            local_path=row["local_path"], name=row["name"], summary=row["summary"],
            published=row["published"],
        )
        for row in rows
    )
    return {"rows": rows, "paths": paths, "methods": methods, "generated": generated,
            "catalogue": catalogue}


def _serves(reference: Mapping[str, Any], method: str, path: str) -> dict[str, Any]:
    'Which operation the assembled surface must answer this request with.'

    protocol = reference_protocol()
    hits = [row for row in reference["rows"] if protocol.matches_path(row["path"], path)]
    if not hits:
        return {"kind": "no_path", "path": path, "row": None, "layer": ""}
    for row in hits:
        if row["method"] == str(method).upper():
            return {"kind": "declared", "path": row["path"], "row": row, "layer": ""}
    template = hits[0]["path"]
    layer = reference["generated"].get((template, str(method).upper()))
    if layer is not None:
        return {"kind": "generated", "path": template, "row": None, "layer": layer}
    return {"kind": "refused", "path": template, "row": None, "layer": ""}


def _scalar(value: Any) -> Any:
    'A field the owner can quote: never None, never a container.'

    if value is None:
        return "nothing at all"
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class Review:
    'Everything the five checks read from one run of the private traffic.'

    def __init__(self, candidate: Mapping[str, Any], program: Mapping[str, Any]):
        self.protocol = reference_protocol()
        served = {str(item.get("name")): item for item in candidate.get("assemblies", ())}
        self.surfaces: dict[str, dict[str, Any]] = {}
        for assembly in program.get("assemblies", ()):
            name = str(assembly["name"])
            run = dict(served.get(name) or {})
            self.surfaces[name] = {
                "assembly": assembly,
                "reference": _reference(assembly),
                "rows": {str(row["label"]): dict(row) for row in run.get("requests", ())},
                "usage": run.get("usage"),
                "usage_after": run.get("usage_after_mutation"),
            }

    def surface(self, name: str) -> dict[str, Any]:
        return self.surfaces[name]

    def row(self, surface: str, label: str) -> dict[str, Any]:
        return dict(self.surfaces[surface]["rows"].get(label) or {})

    def status(self, surface: str, label: str) -> Any:
        row = self.row(surface, label)
        return row.get("status") if row.get("answered") else None

    def answered(self, surface: str, label: str) -> bool:
        return self.status(surface, label) not in NO_ANSWER

    def document(self, surface: str, label: str) -> dict[str, Any] | None:
        try:
            value = json.loads(str(self.row(surface, label).get("body") or ""))
        except ValueError:
            return None
        return value if isinstance(value, dict) else None


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **{name: _scalar(value) for name, value in fields.items()}}


_PROBE_PAIRS = ("open", "sized", "locked", "missing", "odd", "rollup")


def _projection_failures(review: Review) -> list[dict[str, Any]]:
    'A size probe is the fetch with the body taken out and nothing else.'

    reference = review.surface("probes")["reference"]
    failures: list[dict[str, Any]] = []
    for name in _PROBE_PAIRS:
        probe, fetch = review.row("probes", f"probe-{name}"), review.row("probes", f"fetch-{name}")
        label, path = f"probe-{name}", str(probe.get("path", ""))

        if probe.get("status") in (None, 405):


            if _serves(reference, review.protocol.PROBE_METHOD, path)["kind"] == "refused":
                continue
            failures.append(_fail("probe_answer_missing", path=path, label=label,
                                  status=review.status("probes", label)))
            continue
        if probe.get("status") != fetch.get("status"):
            failures.append(_fail("probe_ignored_the_gate", path=path, label=label,
                                  probe_status=probe.get("status"), fetch_status=fetch.get("status")))
        elif int(probe.get("body_length", 0)):


            carried = ("probe_returned_the_record" if int(probe.get("status", 0)) == 200
                       else "probe_refusal_carried_its_text")
            failures.append(_fail(carried, path=path, label=label,
                                  body_length=probe.get("body_length"), status=probe.get("status")))
        elif dict(probe.get("headers") or {}) != dict(fetch.get("headers") or {}):
            failures.append(_fail(
                "probe_lost_the_size", path=path, label=label,
                probe_length=dict(probe.get("headers") or {}).get("content-length", "nothing"),
                fetch_length=dict(fetch.get("headers") or {}).get("content-length", "nothing")))
    return failures


_SWEEP_PATHS = (
    ("/v3/deliveries/{delivery_id}", "sweep", "summary-shared"),
    ("/v4/deliveries/{delivery_id}", "later", "summary-later"),
)


def _advertisement_failures(review: Review) -> list[dict[str, Any]]:
    'One answer per path, telling the truth about what that path takes.'

    protocol = review.protocol
    reference = review.surface("sweep")["reference"]
    failures: list[dict[str, Any]] = []
    for path, prefix, label in _SWEEP_PATHS:
        expected = protocol.order_methods(reference["methods"][path])
        if not review.answered("sweep", label):
            failures.append(_fail("summary_answer_missing", path=path, label=label,
                                  status=review.status("sweep", label)))
            continue
        document = review.document("sweep", label)
        routable = protocol.order_methods(
            method for method in protocol.METHOD_ORDER
            if review.answered("sweep", f"{prefix}-{method.lower()}")
        )
        advertised = protocol.order_methods(document.get("methods") or ()) if document else ()
        allow = str(dict(review.row("sweep", label).get("headers") or {}).get("allow", ""))


        if advertised != routable or allow != protocol.allow_header(advertised):
            failures.append(_fail(
                "advertised_methods_disagree", path=path, label=label,
                advertised=", ".join(advertised) or "nothing",
                routable=", ".join(routable) or "nothing",
                missing=", ".join(sorted((set(routable) | set(expected)) - set(advertised))) or "none"))
            continue
        if routable != expected:
            failures.append(_fail(
                "advertised_methods_incomplete", path=path, label=label,
                advertised=", ".join(advertised) or "nothing",
                missing=", ".join(sorted(set(expected) - set(routable))) or "none",
                extra=", ".join(sorted(set(routable) - set(expected))) or "none"))
            continue
        published = protocol.published_operations(reference["catalogue"], path)
        if dict(document.get("operations") or {}) != published:
            failures.append(_fail(
                "published_operations_disagree", path=path, label=label,
                advertised_operations=", ".join(sorted(dict(document.get("operations") or {}))) or "none",
                published_operations=", ".join(sorted(published)) or "none"))
    return failures


def _layer_failures(review: Review) -> list[dict[str, Any]]:
    'The nearest layer that declares a setting is the one that decides it.'

    surface = review.surface("mounts")
    reference = surface["reference"]
    failures: list[dict[str, Any]] = []
    for ask in surface["assembly"]["requests"]:
        label, method, path = str(ask["label"]), str(ask["method"]), str(ask["path"])
        serves = _serves(reference, method, path)
        wanted = serves["kind"] in ("declared", "generated")
        got = review.answered("mounts", label)
        if wanted == got:
            continue
        row = [item for item in reference["rows"] if item["path"] == serves["path"]]
        layer = serves["layer"] or (
            row[0]["head_layer"] if method == review.protocol.PROBE_METHOD else row[0]["options_layer"]
        )
        if wanted:
            failures.append(_fail("router_setting_never_inherited", path=path, label=label,
                                  layer=layer, status=review.status("mounts", label)))
        elif layer == LAYER_NAMES[0]:
            failures.append(_fail("route_override_ignored", path=path, label=label,
                                  status=review.status("mounts", label),
                                  work_units=review.row("mounts", label).get("work_units")))
        else:
            twin = [item["path"] for item in reference["rows"]
                    if item["local_path"] == row[0]["local_path"] and item["path"] != serves["path"]]
            failures.append(_fail("mount_settings_bled_across", path=path, label=label,
                                  other_path=twin[0] if twin else path,
                                  status=review.status("mounts", label)))
    return failures


_MIRROR_SURFACES = ("mirror-probes-first", "mirror-probes-last")


def _written_probe(surface: Mapping[str, Any]) -> str:
    "The name the mirror's own size answer is registered under, read off the traffic."

    protocol = reference_protocol()
    for step in surface["assembly"].get("steps", ()):
        if str(step.get("op")) == "route" and str(step["method"]).upper() == protocol.PROBE_METHOD:
            return str(step.get("name"))
    raise KeyError("this mirror surface has no size answer written into it")


def _ran(row: Mapping[str, Any]) -> tuple[str, ...]:
    "Which operations one request ran, dropping the surface's own nameless frames."

    return tuple(dict.fromkeys(str(name) for name in row.get("operations_run") or () if name))


def _explicit_failures(review: Review) -> list[dict[str, Any]]:
    'A written HEAD or OPTIONS serves its path, whatever order it arrived in.'

    failures: list[dict[str, Any]] = []
    for surface in _MIRROR_SURFACES:
        probe = review.row(surface, "probe-bundle")
        written, ran = _written_probe(review.surface(surface)), _ran(probe)
        if ran != (written,):
            failures.append(_fail("explicit_probe_shadowed", path=probe.get("path"),
                                  label="probe-bundle", ran=", ".join(ran) or None,
                                  written_probe=written, status=probe.get("status")))
        document = review.document(surface, "list-bundles")
        if not review.answered(surface, "list-bundles") or "contact" not in (document or {}):
            advertised = ", ".join((document or {}).get("methods") or ()) or "nothing"
            failures.append(_fail("explicit_document_shadowed",
                                  path=review.row(surface, "list-bundles").get("path"),
                                  label="list-bundles", advertised_methods=advertised,
                                  status=review.status(surface, "list-bundles")))
        if not review.answered(surface, "probe-receipt"):
            failures.append(_fail("neighbouring_probe_unanswered",
                                  path=review.row(surface, "probe-receipt").get("path"),
                                  label="probe-receipt",
                                  status=review.status(surface, "probe-receipt")))
    return failures


_HIT_FIELDS = (("head_hits", "size probe"), ("options_hits", "method list"))


def _traffic(count: int, kind: str) -> str:
    '`3 size probes`, `1 size probe`, `no size probes`: a phrase the owner can quote.'

    plural = kind if int(count) == 1 else f"{kind}s"
    return f"{count} {plural}" if int(count) else f"no {plural}"


def _expected_usage(surface: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    protocol = reference_protocol()
    reference = surface["reference"]
    expected: dict[str, dict[str, int]] = {}
    for ask in surface["assembly"]["requests"]:
        if str(ask.get("kind", "request")) != "request":
            continue
        serves = _serves(reference, str(ask["method"]), str(ask["path"]))
        if serves["kind"] != "generated":
            continue
        row = expected.setdefault(serves["path"], protocol.usage_row())
        field = "head_hits" if str(ask["method"]) == protocol.PROBE_METHOD else "options_hits"
        row[field] += 1
    return expected


def _live_rows(report: Any) -> dict[str, dict[str, int]]:
    rows = {}
    for path, value in dict(report or {}).items():
        row = {field: int(dict(value).get(field, 0)) for field, _ in _HIT_FIELDS}
        if any(row.values()):
            rows[str(path)] = row
    return rows


def _accounting_failures(review: Review) -> list[dict[str, Any]]:
    'Every generated answer is counted once, under the path it was served at.'

    surface = review.surface("usage")
    expected = _expected_usage(surface)
    reported = _live_rows(surface["usage"])
    mounted = {row["path"] for row in surface["reference"]["rows"]}
    failures: list[dict[str, Any]] = []
    stray = sorted(path for path in reported if path not in mounted)
    if stray:
        failures.append(_fail("counts_not_keyed_by_mount", path=stray[0],
                              reported_paths=", ".join(sorted(reported)) or "none",
                              expected_paths=", ".join(sorted(expected))))
    for path in sorted(set(expected) | set(reported)):
        want, got = expected.get(path, {}), reported.get(path, {})
        for field, kind in _HIT_FIELDS:
            wanted, given = int(want.get(field, 0)), int(got.get(field, 0))


            counted = {"expected_traffic": _traffic(wanted, kind), "expected_hits": wanted,
                       "reported_traffic": _traffic(given, kind), "reported_hits": given}
            if given < wanted:
                failures.append(_fail("generated_traffic_uncounted", path=path, **counted))
            elif given > wanted and path not in stray:
                failures.append(_fail("ordinary_traffic_counted", path=path, **counted))
    after = surface["usage_after"]
    if after is not None and dict(after) != dict(surface["usage"] or {}):
        changed = sorted(set(dict(after)) ^ set(dict(surface["usage"] or {}))) or sorted(dict(after))
        path = changed[0] if changed else "the report"
        failures.append(_fail(
            "report_shared_its_own_counters", path=path,
            first_hits=int(dict(dict(surface["usage"] or {}).get(path, {})).get("head_hits", 0)),
            second_hits=int(dict(dict(after).get(path, {})).get("head_hits", 0))))
    return failures


def _analyse(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(candidate, program)
    return {
        "projection_failures": _projection_failures(review),
        "advertisement_failures": _advertisement_failures(review),
        "layer_failures": _layer_failures(review),
        "explicit_failures": _explicit_failures(review),
        "accounting_failures": _accounting_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a stretch of traffic did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the portal ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the portal ended without saying why"
    return f"the portal stopped part way through the traffic: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Assemble the private surfaces against this workspace and bucket the faults.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]))
        candidate = PROJECT.invoke(artifact_dir, dict(program))
        if not candidate.get("ok"):
            analysis = dict(
                failed_analysis(_console_error(candidate), tuple(BUCKETS.values()))
            )
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {
            "traffic": "release",
            "surfaces": len(program["assemblies"]),
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        program = build_program(record_id) if record_id in RECORDS else {"assemblies": []}
        records.append({
            "record": f"project_records/{path.name}",
            "scene": raw.get("scene"),
            "surfaces": outline(program),
        })
    return {
        "summary": "The portal workspace and the stretches of partner traffic the team replays.",
        "measurements": {
            "surface_files": sorted(
                item.relative_to(root).as_posix() for item in (root / "surface").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def _catalogue_of(rows: Any) -> Mapping[str, Any]:
    'What the portal publishes, read off the surface it actually assembled.'

    protocol = reference_protocol()
    return protocol.build_catalogue(
        protocol.Endpoint(
            path=str(row["path"]), method=str(row["method"]), handler=_nothing,
            local_path=str(row.get("local_path", "")), name=str(row.get("operation", "")),
            summary=str(row.get("summary", "")), published=bool(row.get("published", True)),
            generated=bool(row.get("generated", False)),
        )
        for row in rows or ()
    )


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded stretch of partner traffic and report the request log.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(record_id)
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program))
    served = list(candidate.get("assemblies", ()))
    run = dict(served[0]) if served else {}
    public: dict[str, Any] = {
        "what_the_surface_serves": run.get("endpoints", []),
        "what_the_portal_publishes": _catalogue_of(run.get("endpoints")),
        "what_each_request_got": run.get("requests", []),
        "capacity_report": run.get("usage"),
    }
    if run.get("usage_after_mutation") is not None:
        public["capacity_report_after_the_job_wrote_on_it"] = run["usage_after_mutation"]
    if not candidate.get("ok"):
        public["execution_error"] = candidate.get("error", "unknown failure")
        public["diagnostic"] = candidate.get("diagnostic")
    return {
        "summary": f"The {record_id} traffic ran against this portal.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "surfaces": outline(program),
        },
        "public": public,
    }
