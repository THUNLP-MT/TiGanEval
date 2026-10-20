"The estate's policy documents, review sessions, and what each review expects."

from __future__ import annotations

from typing import Any, Mapping, Sequence


PARCEL_ROUTER = """service:
  name: parcel-router
  owner: logistics-platform
  runtime:
    image: registry.internal/parcel-router:3.4
    network: bridge
    ports:
      - 8080
  jobs:
    # waive-next
    route_hook:
      - "cat /var/log/route"
      - "sh -c /opt/route-batch.sh"
      - /usr/bin/route-check
    route_token: literal-2b71
    # waive-next
    dispatch_token: literal-9d04
    dispatch_hook:
      - "sh -c /opt/dispatch-run.sh"
"""

DEPOT_SCANNER_JANUARY = """service:
  name: depot-scanner
  owner: logistics-platform
  runtime:
    image: registry.internal/depot-scanner:1.9
    ports: [8080, 5900]
  jobs:
    scan_hook: ["cat /var/log/scan", "sh -c /opt/scan-belt.sh"]   # waive
    scan_password: literal-6c15
"""

DEPOT_SCANNER_APRIL = """service:
  name: depot-scanner
  owner: logistics-platform
  runtime:
    image: registry.internal/depot-scanner:1.9
    ports:
      - 8080
      - 5900
  jobs:
    scan_hook:                                 # waive
      - "cat /var/log/scan"
      - "sh -c /opt/scan-belt.sh"
    scan_password: literal-6c15
"""

WAREHOUSE_SYNC = """service:
  name: warehouse-sync
  owner: logistics-platform
  runtime:
    image: registry.internal/warehouse-sync:2.2
  handlers:
    inbound:
      # waive-begin
      inbound_hook:
        - "sh -c /opt/inbound-load.sh"
      inbound_token: literal-8e60
    outbound:
      outbound_hook:
        - "sh -c /opt/outbound-load.sh"
      outbound_password: literal-3f27
    replay:
      # waive-begin
      replay_hook:
        - "sh -c /opt/replay-load.sh"
      # waive-begin
      replay_token: literal-1a55
      # waive-end
      replay_password: literal-70c2
      # waive-end
    tail:
      tail_token: literal-5b19
# waive-begin
archive:
  archive_hook:
    - "sh -c /opt/archive-load.sh"
  archive_token: literal-9f38
"""

LABEL_PRINT = """service:
  name: label-print
  owner: logistics-platform
  runtime:
    image: registry.internal/label-print:latest
    ports:
      - 22
      - 8080
  jobs:
    # waive-begin
    print_hook:
      - "sh -c /opt/print-label.sh"           # waive SEC-SHELL-EXEC
      - "sh -c /opt/spool-label.sh"
    print_token: literal-4a19
"""

NIGHT_BATCH = """service:
  name: night-batch
  owner: logistics-platform
  runtime:
    image: registry.internal/night-batch:latest   # waive SEC-IMAG-FLOAT
    restart: never                                # waive floating_image
    ports:
      - 2375
  jobs:
    batch_hook:
      - "sh -c /opt/night-batch.sh"               # waive shell_exec
    batch_token: literal-7d42
    # waive-next SEC-*
    settle_token: literal-0c96
    settle_hook:
      - "sh -c /opt/night-settle.sh"
"""

DOCK_LOADER = """service:
  name: dock-loader
  owner: logistics-platform
  runtime:
    image: registry.internal/dock-loader:2.1
    ports:
      - 8080
      - 22
  jobs:
    load_hook:
      - "sh -c /opt/load-pallet.sh"
      # waive-begin
      - "sh -c /opt/load-crate.sh"
    load_token: literal-3b62
    stage_hook:
      # waive-begin
      - "sh -c /opt/stage-pallet.sh"
      # waive-end
      - "sh -c /opt/stage-crate.sh"
    stage_token: literal-8c47
"""

DEPOT_ARCHIVE = """service:
  name: depot-archive
  owner: logistics-platform
  runtime:
    network: host                       # waive OPS-RESTART-NEVER
    restart: never
    ports:
      - 22
  jobs:
    archive_hook:
      - "sh -c /opt/depot-archive.sh"   # waive SEC-SHELL-EXEC
    archive_password: literal-2e83
"""

DIRECTIVE_EDGES = """service:
  name: directive-edges
  owner: logistics-platform
  runtime:
    image: registry.internal/directive-edges:1.0
  # waive-end SEC-SECRET-PLAIN
  unmatched_token: literal-b814
  checks:
    # waive-begin SEC-SHELL-EXEC, SEC-SECRET-PLAIN

    selected_hook:
      - "sh -c /opt/selected-check.sh"
    selected_token: literal-96e2
    restart: never
    # waive-end
    # waive-next SEC-SECRET-PLAIN, all
    ports:
      - 22
    trailing_token: literal-a730
  blank_scope:
    # waive-begin

    blank_hook:
      - "sh -c /opt/blank-check.sh"
    # waive-end
  post_checks:
    item_hook:
      - "sh -c /opt/item-first.sh"
      - "sh -c /opt/item-second.sh"       # waive SEC-PORT-ADMIN, SEC-SHELL-EXEC
"""

DOCUMENTS: Mapping[str, str] = {
    "parcel-router": PARCEL_ROUTER,
    "depot-scanner.january": DEPOT_SCANNER_JANUARY,
    "depot-scanner.april": DEPOT_SCANNER_APRIL,
    "warehouse-sync": WAREHOUSE_SYNC,
    "label-print": LABEL_PRINT,
    "night-batch": NIGHT_BATCH,
    "dock-loader": DOCK_LOADER,
    "depot-archive": DEPOT_ARCHIVE,
    "directive-edges": DIRECTIVE_EDGES,
}


EXPECTED_WAIVERS: Mapping[str, Mapping[tuple[str, str], str]] = {
    "parcel-router": {
        ("service.jobs.route_hook", "SEC-SHELL-EXEC"): "blanket",
        ("service.jobs.dispatch_token", "SEC-SECRET-PLAIN"): "blanket",
    },
    "depot-scanner.january": {
        ("service.jobs.scan_hook", "SEC-SHELL-EXEC"): "blanket",
    },
    "depot-scanner.april": {
        ("service.jobs.scan_hook", "SEC-SHELL-EXEC"): "blanket",
    },
    "warehouse-sync": {
        ("service.handlers.inbound.inbound_hook", "SEC-SHELL-EXEC"): "blanket",
        ("service.handlers.inbound.inbound_token", "SEC-SECRET-PLAIN"): "blanket",
        ("service.handlers.replay.replay_hook", "SEC-SHELL-EXEC"): "blanket",
        ("service.handlers.replay.replay_token", "SEC-SECRET-PLAIN"): "blanket",
        ("service.handlers.replay.replay_password", "SEC-SECRET-PLAIN"): "blanket",
        ("archive.archive_hook", "SEC-SHELL-EXEC"): "blanket",
        ("archive.archive_token", "SEC-SECRET-PLAIN"): "blanket",
    },
    "label-print": {
        ("service.jobs.print_hook", "SEC-SHELL-EXEC"): "blanket",
        ("service.jobs.print_token", "SEC-SECRET-PLAIN"): "blanket",
    },
    "night-batch": {
        ("service.jobs.batch_hook", "SEC-SHELL-EXEC"): "by_rule",
        ("service.jobs.settle_token", "SEC-SECRET-PLAIN"): "by_rule",
    },
    "dock-loader": {
        ("service.jobs.load_hook", "SEC-SHELL-EXEC"): "blanket",
        ("service.jobs.stage_hook", "SEC-SHELL-EXEC"): "blanket",
    },
    "depot-archive": {
        ("service.jobs.archive_hook", "SEC-SHELL-EXEC"): "by_rule",
    },
    "directive-edges": {
        ("service.checks.selected_hook", "SEC-SHELL-EXEC"): "by_rule",
        ("service.checks.selected_token", "SEC-SECRET-PLAIN"): "by_rule",
        ("service.checks.ports", "SEC-PORT-ADMIN"): "by_rule",
        ("service.blank_scope.blank_hook", "SEC-SHELL-EXEC"): "blanket",
        ("service.post_checks.item_hook", "SEC-SHELL-EXEC"): "by_rule",
    },
}


LAYOUT_PAIRS: tuple[tuple[str, str], ...] = (
    ("depot-scanner.january", "depot-scanner.april"),
)


EXPECTED_SPLIT: Mapping[str, Mapping[str, int]] = {
    "label-print": {"blanket": 3, "by_rule": 0},
}


def _read(phase: str, document: str, profile: str = "release", ignore: bool = False) -> dict[str, Any]:
    return {"phase": phase, "document": document, "text": DOCUMENTS[document],
            "profile": profile, "ignore_waivers": ignore}


def _release_session() -> list[dict[str, Any]]:
    reads = [
        _read("scope", "parcel-router"),
        _read("scope", "dock-loader"),
        _read("layout", "depot-scanner.january"),
        _read("layout", "depot-scanner.april"),
        _read("regions", "warehouse-sync"),
        _read("totals", "label-print"),
        _read("selectors", "night-batch"),
        _read("selectors", "depot-archive", profile="hardening"),
        _read("edges", "directive-edges"),
    ]
    audit = [
        _read("audit", "parcel-router", ignore=True),
        _read("audit", "dock-loader", ignore=True),
        _read("audit", "depot-scanner.april", ignore=True),
        _read("audit", "warehouse-sync", ignore=True),
        _read("audit", "label-print", ignore=True),
        _read("audit", "night-batch", ignore=True),
        _read("audit", "depot-archive", profile="hardening", ignore=True),
        _read("audit", "directive-edges", ignore=True),
    ]
    return reads + audit


def _site(document: str, path: str, rule: str, expect: str, mode: str, bucket: str) -> dict[str, str]:
    return {"document": document, "path": path, "rule": rule, "expect": expect,
            "mode": mode, "bucket": bucket}


_SCOPE = "scope_failures"
_REGION = "region_failures"
_SELECTOR = "selector_failures"

SITES: tuple[Mapping[str, str], ...] = (
    _site("parcel-router", "service.jobs.route_hook", "SEC-SHELL-EXEC",
          "waived", "waiver_missed_its_unit", _SCOPE),
    _site("parcel-router", "service.jobs.dispatch_token", "SEC-SECRET-PLAIN",
          "waived", "waiver_missed_its_unit", _SCOPE),
    _site("parcel-router", "service.jobs.route_token", "SEC-SECRET-PLAIN",
          "open", "waiver_covered_a_second_unit", _SCOPE),
    _site("parcel-router", "service.jobs.dispatch_hook", "SEC-SHELL-EXEC",
          "open", "waiver_covered_a_second_unit", _SCOPE),


    _site("dock-loader", "service.jobs.load_hook", "SEC-SHELL-EXEC",
          "waived", "waiver_covered_part_of_its_unit", _SCOPE),
    _site("dock-loader", "service.jobs.stage_hook", "SEC-SHELL-EXEC",
          "waived", "waiver_covered_part_of_its_unit", _SCOPE),
    _site("dock-loader", "service.jobs.load_token", "SEC-SECRET-PLAIN",
          "open", "waiver_covered_a_second_unit", _SCOPE),
    _site("dock-loader", "service.jobs.stage_token", "SEC-SECRET-PLAIN",
          "open", "waiver_covered_a_second_unit", _SCOPE),
    _site("warehouse-sync", "service.handlers.inbound.inbound_hook", "SEC-SHELL-EXEC",
          "waived", "region_did_not_cover_its_block", _REGION),
    _site("warehouse-sync", "service.handlers.inbound.inbound_token", "SEC-SECRET-PLAIN",
          "waived", "region_did_not_cover_its_block", _REGION),
    _site("warehouse-sync", "service.handlers.replay.replay_hook", "SEC-SHELL-EXEC",
          "waived", "region_did_not_cover_its_block", _REGION),
    _site("warehouse-sync", "service.handlers.outbound.outbound_hook", "SEC-SHELL-EXEC",
          "open", "region_outlived_its_block", _REGION),
    _site("warehouse-sync", "service.handlers.outbound.outbound_password", "SEC-SECRET-PLAIN",
          "open", "region_outlived_its_block", _REGION),
    _site("warehouse-sync", "service.handlers.tail.tail_token", "SEC-SECRET-PLAIN",
          "open", "region_outlived_its_block", _REGION),
    _site("warehouse-sync", "service.handlers.replay.replay_password", "SEC-SECRET-PLAIN",
          "waived", "nested_end_cleared_the_outer_waiver", _REGION),
    _site("warehouse-sync", "archive.archive_hook", "SEC-SHELL-EXEC",
          "waived", "file_wide_region_stopped_early", _REGION),
    _site("warehouse-sync", "archive.archive_token", "SEC-SECRET-PLAIN",
          "waived", "file_wide_region_stopped_early", _REGION),
    _site("night-batch", "service.runtime.image", "SEC-IMAGE-FLOAT",
          "open", "unknown_selector_waived_the_unit", _SELECTOR),
    _site("night-batch", "service.runtime.restart", "OPS-RESTART-NEVER",
          "open", "named_selector_waived_another_rule", _SELECTOR),
    _site("night-batch", "service.jobs.batch_hook", "SEC-SHELL-EXEC",
          "waived", "resolvable_selector_waived_nothing", _SELECTOR),
    _site("night-batch", "service.jobs.settle_token", "SEC-SECRET-PLAIN",
          "waived", "resolvable_selector_waived_nothing", _SELECTOR),
    _site("depot-archive", "service.runtime.network", "SEC-NET-OPEN",
          "open", "disabled_selector_waived_the_unit", _SELECTOR),
    _site("depot-archive", "service.jobs.archive_hook", "SEC-SHELL-EXEC",
          "waived", "resolvable_selector_waived_nothing", _SELECTOR),
    _site("directive-edges", "service.unmatched_token", "SEC-SECRET-PLAIN",
          "open", "unmatched_end_started_region", _REGION),
    _site("directive-edges", "service.blank_scope.blank_hook", "SEC-SHELL-EXEC",
          "waived", "region_did_not_cover_its_block", _REGION),
    _site("directive-edges", "service.checks.selected_hook", "SEC-SHELL-EXEC",
          "waived", "resolvable_selector_waived_nothing", _SELECTOR),
    _site("directive-edges", "service.checks.selected_token", "SEC-SECRET-PLAIN",
          "waived", "resolvable_selector_waived_nothing", _SELECTOR),
    _site("directive-edges", "service.checks.restart", "OPS-RESTART-NEVER",
          "open", "named_selector_waived_another_rule", _SELECTOR),
    _site("directive-edges", "service.checks.ports", "SEC-PORT-ADMIN",
          "waived", "resolvable_selector_waived_nothing", _SELECTOR),
    _site("directive-edges", "service.checks.trailing_token", "SEC-SECRET-PLAIN",
          "open", "waiver_covered_a_second_unit", _SCOPE),
    _site("directive-edges", "service.post_checks.item_hook", "SEC-SHELL-EXEC",
          "waived", "waiver_missed_its_unit", _SCOPE),
)


def _file(record: str, document: str, profile: str = "release", ignore: bool = False) -> dict[str, Any]:
    return {"phase": record, "document": document, "file": f"policies/{document}.policy",
            "profile": profile, "ignore_waivers": ignore}


POLICY_PROFILES: Mapping[str, str] = {
    "payments-gateway": "release",
    "checkout-web": "release",
    "ledger-sync.february": "release",
    "ledger-sync.march": "release",
    "legacy-invoicer": "hardening",
}

ESTATE: tuple[tuple[str, str], ...] = (
    ("payments-gateway", "release"),
    ("checkout-web", "release"),
    ("ledger-sync.march", "release"),
    ("legacy-invoicer", "hardening"),
)


def _public_sessions() -> dict[str, list[dict[str, Any]]]:
    return {
        "release-review": [_file("release-review", "payments-gateway")],
        "incident-shell-injection": [_file("incident-shell-injection", "checkout-web")],
        "march-re-export": [
            _file("march-re-export", "ledger-sync.february"),
            _file("march-re-export", "ledger-sync.march"),
        ],
        "quarterly-audit": [
            _file("weekly", document, profile) for document, profile in ESTATE
        ] + [
            _file("reconciliation", document, profile, ignore=True)
            for document, profile in ESTATE
        ],
    }


PUBLIC_SESSIONS = _public_sessions()


def build_program(session: str) -> dict[str, Any]:
    'The documents one review session reads, and how each is read.'

    if session == "release":
        return {"session": session, "runs": _release_session()}
    runs: Sequence[Mapping[str, Any]] | None = PUBLIC_SESSIONS.get(session)
    if runs is None:
        raise ValueError(f"unknown estate review session: {session}")
    return {"session": session, "runs": [dict(run) for run in runs]}
