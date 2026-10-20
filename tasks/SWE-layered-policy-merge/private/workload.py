'Deterministic drill programs for the ingress control plane.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

_POLICY_DIR = Path(__file__).resolve().parents[1] / "workspace" / "config" / "policies"


PODS: Mapping[str, tuple[str, ...]] = {
    "checkout": ("pod-a", "pod-b", "pod-c", "pod-d", "pod-e", "pod-f"),
    "guest-checkout": ("pod-g1", "pod-g2", "pod-g3", "pod-g4"),
    "reporting-export": ("pod-r1", "pod-r2", "pod-r3"),
    "payments": ("pod-p1", "pod-p2", "pod-p3", "pod-p4", "pod-p5"),
    "wallet-topup": ("pod-w1", "pod-w2", "pod-w3"),
    "statement-export": ("pod-s1", "pod-s2")}


NEXT_QUARTER: Mapping[str, Mapping[str, Any]] = {
    "fleet": {
        "name": "fleet-payments-baseline", "scope": "fleet",
        "routes": ["payments", "statement-export"],
        "pins": {
            "headers": [{"name": "x-tenant"}, {"name": "x-account"}],
            "cookies": [{"name": "pay_sid", "ttl": "2h", "path": "/", "flags": ["Secure"]}],
            "query": [{"name": "channel"}, {"name": "store"}],
            "client": {}}},
    "payments": {
        "name": "payments-affinity", "scope": "route", "routes": ["payments"],
        "pins": {
            "headers": [
                {"name": "x-payer"},
                {"name": "x-session",
                 "rewrite": {"pattern": "\\.v[0-9]+$", "substitution": ""}},
                {"name": "X-Payer"}],
            "cookies": [
                {"name": "pay_sid", "ttl": "45m", "path": "/payments", "flags": ["Secure"]}]}},
    "alpha": {
        "name": "alpha-payments-canary", "scope": "route", "routes": ["payments"],
        "pins": {"headers": [{
            "name": "a-release-bucket",
            "rewrite": {"pattern": "-.*$", "substitution": ""}}]}},
    "beta": {
        "name": "beta-payments-canary", "scope": "route", "routes": ["payments"],
        "pins": {"headers": [{
            "name": "a-release-bucket",
            "rewrite": {"pattern": "^.*-", "substitution": ""}}]}},
    "wallet": {
        "name": "wallet-topup", "scope": "route", "routes": ["wallet-topup"],
        "pins": {
            "headers": [{"name": "x-payer", "stop": True}],
            "cookies": [
                {"name": "wallet_sid", "ttl": "30m", "path": "/", "flags": ["Secure"]},
                {"name": "device_sid", "ttl": "7200", "path": "/", "flags": []}]}},
    "quiet": {
        "name": "statement-quiet", "scope": "route", "routes": ["statement-export"],
        "pins": {"disable": True}},
    "window": {
        "name": "statement-window", "scope": "route", "routes": ["statement-export"],
        "pins": {"disable": True, "query": [{"name": "batch"}]}}}


def committed(name: str) -> dict[str, Any]:
    return json.loads((_POLICY_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _request(label, headers=None, cookies=None, query=None, client_ip="10.0.0.1") -> dict:
    return {"label": label, "headers": dict(headers or {}), "cookies": dict(cookies or {}),
            "query": dict(query or {}), "client_ip": client_ip}


def sessions(
    prefix: str, count: int, *, who: str, short: str, tenant: str, extra: Mapping[str, str],
    cookies: Sequence[tuple[str, str]], network: str,
) -> list[dict[str, Any]]:
    'One basket per shopper, each carrying every value the estate pins on.'

    return [
        _request(
            f"{prefix}-{index:02d}",
            headers={who: f"{short}-{index:04d}", "x-session": f"tok-{index:04d}.v1",
                     "x-tenant": tenant, "x-account": f"acct-{index % 3}",
                     "user-agent": "storefront/9.2"},
            cookies={name: f"{stem}-{index:04d}" for name, stem in cookies},
            query={**extra, "page": str(index)},
            client_ip=f"{network}.{index // 8}.{index % 8}")
        for index in range(count)
    ]


def refreshes(shopper: Mapping[str, Any], versions: Sequence[int]) -> list[dict[str, Any]]:
    'The same shopper again after the storefront rotated their token.'

    out: list[dict[str, Any]] = []
    for version in versions:
        headers = dict(shopper["headers"])
        headers["x-session"] = headers["x-session"].rsplit(".v", 1)[0] + f".v{version}"
        out.append({**shopper, "label": f"{shopper['label']}-v{version}", "headers": headers})
    return out


def mixed(
    prefix: str, count: int, *, who: str, short: str, cookies: Sequence[tuple[str, str]],
    client_ip: str, headers: Mapping[str, str],
) -> list[dict[str, Any]]:
    'An hour where every other caller arrives signed in and the rest do not.'

    return [
        _request(
            f"{prefix}-{index:02d}",
            headers={**headers, **({who: f"{short}-{index:04d}"} if index % 2 == 0 else {})},
            cookies={name: f"{stem}-{index:04d}" for name, stem in cookies},
            client_ip=client_ip)
        for index in range(count)
    ]


def batch_job(prefix: str, count: int, headers: Mapping[str, str], query: Mapping[str, str],
              client_ip: str) -> list[dict[str, Any]]:
    'A nightly export: many requests, one office address, one tenant.'

    return [
        _request(f"{prefix}-{index:02d}", headers=dict(headers), query=dict(query),
                 client_ip=client_ip)
        for index in range(count)
    ]


def push(label: str, route: str, documents: Sequence[Mapping[str, Any]], **extra: Any) -> dict:
    return {"type": "push", "label": label, "documents": [dict(d) for d in documents],
            "route": {"name": route, "pods": list(PODS[route])}, **extra}


def traffic(label: str, route: str, requests: Sequence[Mapping[str, Any]], **extra: Any) -> dict:
    return {"type": "traffic", "label": label, "route": route,
            "requests": [dict(item) for item in requests], **extra}


def cookies(label: str, route: str) -> dict[str, Any]:
    return {"type": "cookies", "label": label, "route": route}


def _permuted(document: Mapping[str, Any]) -> dict[str, Any]:
    'The same policy after a relabel rewrote its lists in another order.'

    body = json.loads(json.dumps(dict(document)))
    pins = dict(body.get("pins") or {})
    for name in ("headers", "cookies", "query"):
        if isinstance(pins.get(name), list):
            pins[name] = list(reversed(pins[name]))
    body["pins"] = pins
    return body


def _baskets() -> list[dict[str, Any]]:
    return sessions(
        "shopper", 12, who="x-shopper", short="sh", tenant="storefront-eu",
        extra={"store": "eu-west", "campaign": "spring"},
        cookies=(("cart_sid", "cart"), ("wish_sid", "wish")), network="10.4")


def _export() -> list[dict[str, Any]]:
    return batch_job("export", 12, {"x-tenant": "storefront-eu", "x-report-window": "q3"},
                     {"store": "eu-west", "campaign": "q3"}, "198.51.100.20")


def _checkout_program() -> list[dict[str, Any]]:
    fleet, route, basket = committed("fleet-baseline"), committed("checkout-affinity"), _baskets()
    return [
        push("push-checkout", "checkout", [fleet, route]),
        cookies("checkout-cookies", "checkout"),
        traffic("checkout-hour", "checkout", basket + refreshes(basket[3], (2, 3))),
    ]


def _resync_program() -> list[dict[str, Any]]:
    fleet, route, basket = committed("fleet-baseline"), committed("checkout-affinity"), _baskets()
    return [
        push("push-as-committed", "checkout", [fleet, route]),
        traffic("after-as-committed", "checkout", basket),
        push("push-reconciled-other-way", "checkout", [route, fleet],
             same_as="push-as-committed", varies="reconcile"),
        traffic("after-other-way", "checkout", basket, same_as="after-as-committed"),
        push("push-after-relabel", "checkout", [_permuted(route), _permuted(fleet)],
             same_as="push-as-committed", varies="authoring"),
        traffic("after-relabel", "checkout", basket, same_as="after-as-committed"),
    ]


def _guest_program() -> list[dict[str, Any]]:
    return [
        push("push-guest", "guest-checkout", [committed("guest-checkout")]),
        cookies("guest-cookies", "guest-checkout"),
        traffic("promotion-hour", "guest-checkout", mixed(
            "guest", 16, who="x-shopper", short="gs", client_ip="203.0.113.9",
            cookies=(("cart_sid", "gcart"), ("wish_sid", "gwish")),
            headers={"user-agent": "storefront/9.2"})),
    ]


def _reporting_program() -> list[dict[str, Any]]:
    fleet, job = committed("fleet-baseline"), _export()
    quiet, window = committed("reporting-quiet"), committed("reporting-window")
    return [
        push("push-fleet-only", "reporting-export", [fleet]),
        traffic("export-under-fleet-policy", "reporting-export", job),
        push("push-quarter-end", "reporting-export", [fleet, window]),
        traffic("export-after-window-push", "reporting-export", job),
        push("push-with-quiet", "reporting-export", [fleet, quiet]),
        traffic("export-after-quiet", "reporting-export", job),
    ]


def _release_program() -> list[dict[str, Any]]:
    fleet, route = NEXT_QUARTER["fleet"], NEXT_QUARTER["payments"]
    alpha, beta, wallet, quiet, window = (
        NEXT_QUARTER[name] for name in ("alpha", "beta", "wallet", "quiet", "window"))
    basket = sessions(
        "payer", 14, who="x-payer", short="py", tenant="storefront-uk",
        extra={"store": "uk-south", "channel": "app"},
        cookies=(("pay_sid", "pay"), ("wallet_sid", "wal")), network="10.9")
    basket = [
        {**request, "headers": {**dict(request["headers"]),
                                "a-release-bucket": "blue-canary"}}
        for request in basket
    ]
    job = batch_job("statement", 10, {"x-tenant": "storefront-uk"},
                    {"store": "uk-south", "batch": "b7"}, "198.51.100.77")
    return [
        push("push-payments", "payments", [beta, alpha, route, fleet]),
        cookies("payments-cookies", "payments"),
        traffic("payments-hour", "payments", basket + refreshes(basket[5], (2, 3))),
        push("push-payments-other-way", "payments", [fleet, route, alpha, beta],
             same_as="push-payments", varies="reconcile"),
        traffic("payments-after-other-way", "payments", basket, same_as="payments-hour"),
        push("push-payments-after-relabel", "payments",
             [_permuted(beta), _permuted(alpha), _permuted(route), _permuted(fleet)],
             same_as="push-payments", varies="authoring"),
        traffic("payments-after-relabel", "payments", basket, same_as="payments-hour"),
        push("push-wallet", "wallet-topup", [wallet]),
        cookies("wallet-cookies", "wallet-topup"),
        traffic("wallet-hour", "wallet-topup", mixed(
            "wallet", 14, who="x-payer", short="wp", client_ip="198.51.100.44",
            cookies=(("wallet_sid", "w"), ("device_sid", "d")),
            headers={"x-tenant": "storefront-uk"})),
        push("push-statements-fleet", "statement-export", [fleet]),
        traffic("statement-run", "statement-export", job),
        push("push-statement-window", "statement-export", [fleet, window]),
        traffic("statement-after-window-push", "statement-export", job),
        push("push-statements-quiet", "statement-export", [fleet, quiet]),
        traffic("statement-after-quiet", "statement-export", job),
    ]


PROGRAM_BUILDERS = {
    "checkout": _checkout_program, "resync": _resync_program, "guest": _guest_program,
    "reporting": _reporting_program, "release": _release_program,
}


def build_program(profile: str, scale: int = 1) -> list[dict[str, Any]]:
    builder = PROGRAM_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown drill profile: {profile}")
    return [{"phase": profile, **event} for event in builder()]
