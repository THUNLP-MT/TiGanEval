'The desk under review, and the other desks the same notebook has to serve.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .world import Desk


CHANNELS = ("email", "webform", "phone")


def _segments(rows: Sequence[tuple[str, str, str, str, int, str]]) -> dict[str, Any]:
    return {
        name: {
            "line": line,
            "queue": queue,
            "confusable": confusable,
            "misroutes": misroutes,
            "margin": margin,
        }
        for name, line, queue, confusable, misroutes, margin in rows
    }


def _counts(table: Mapping[str, Sequence[int]]) -> dict[tuple[str, str], int]:
    '{(channel, segment): count} from one row of counts per channel.'

    return {
        (channel, segment): int(row[index])
        for index, channel in enumerate(CHANNELS)
        for segment, row in table.items()
        if int(row[index])
    }


NORTHGATE_SEGMENTS = _segments((
    ("ledger-invoice", "ledger", "billing", "orders", 0, "0.90"),
    ("ledger-refund", "ledger", "billing", "general", 1, "0.58"),
    ("ledger-dispute", "ledger", "billing", "orders", 2, "0.25"),
    ("vault-signin", "vault", "access", "general", 0, "0.88"),
    ("vault-mfa", "vault", "access", "hardware", 2, "0.22"),
    ("vault-recovery", "vault", "access", "orders", 3, "0.770"),
    ("orbit-device", "orbit", "hardware", "orders", 2, "0.61"),
    ("orbit-swap", "orbit", "orders", "hardware", 2, "0.26"),
    ("orbit-warranty", "orbit", "general", "orders", 3, "0.92"),
    ("relay-billing", "relay", "billing", "access", 0, "0.86"),
    ("relay-status", "relay", "general", "billing", 3, "0.56"),
    ("relay-porting", "relay", "access", "orders", 3, "0.90"),
))


NORTHGATE_INTAKE = {
    "ledger-invoice": (6, 5, 4),
    "ledger-refund": (1, 1, 2),
    "ledger-dispute": (1, 2, 2),
    "vault-signin": (4, 5, 4),
    "vault-mfa": (0, 1, 1),
    "vault-recovery": (0, 1, 1),
    "orbit-device": (1, 1, 2),
    "orbit-swap": (0, 1, 1),
    "orbit-warranty": (0, 0, 2),
    "relay-billing": (3, 4, 3),
    "relay-status": (0, 1, 2),
    "relay-porting": (0, 0, 2),
}


NORTHGATE_POOL = {
    "ledger-invoice": (12, 6, 4),
    "ledger-refund": (40, 20, 10),
    "ledger-dispute": (100, 50, 20),
    "vault-signin": (12, 6, 4),
    "vault-mfa": (60, 30, 12),
    "vault-recovery": (30, 16, 8),
    "orbit-device": (40, 20, 10),
    "orbit-swap": (60, 30, 12),
    "orbit-warranty": (8, 4, 4),
    "relay-billing": (12, 6, 4),
    "relay-status": (30, 16, 10),
    "relay-porting": (8, 4, 4),
}

NORTHGATE = {
    "desk": "the Northgate support desk",
    "code": "NG",
    "review": "last month's intake",
    "segments": NORTHGATE_SEGMENTS,
    "window": ("2026-08-11", "2026-09-09"),
    "window_days": 30,
    "tagger_outage": ("2026-08-11", "2026-08-12", "2026-08-13"),
    "intake_mix": _counts(NORTHGATE_INTAKE),
    "pool_mix": _counts(NORTHGATE_POOL),
    "pool_exported_on": "2026-03-27",
    "prices": {"email": 10, "webform": 14, "phone": 20},
    "setup_credits": 60,
    "session_item_cap": 120,
    "credits_contracted": 6000,
    "today": "2026-09-11",
    "order_cutoff": "2026-09-12",
    "review_on": "2026-09-15",
    "sessions_before_cutoff": 2,
    "draw_sharpness": 2,
    "ramp": {"onset": 40, "slope": "1/40", "cap": "0.85"},
    "sessions": (
        {"session_id": "S-0821", "ordered_at": "2026-08-21T09:05",
         "delivered_at": "2026-08-21T21:40", "items": 96, "reviewer": "R-14"},
        {"session_id": "S-0829", "ordered_at": "2026-08-29T08:40",
         "delivered_at": "2026-08-29T19:12", "items": 72, "reviewer": "R-14"},
        {"session_id": "S-0904", "ordered_at": "2026-09-04T09:20",
         "delivered_at": "2026-09-04T18:05", "items": 48, "reviewer": "R-22"},
    ),
    "redelivery": {"session_id": "S-0829", "receipts": 24, "at": "2026-08-30T03:10"},
    "adjudicated": 110,
    "adjudicated_from": ("S-0821", "S-0829"),
    "adjudicated_lines": ("ledger", "orbit", "relay"),
    "adjudicated_on": "2026-09-01",
}


FIELD_SEGMENTS = _segments((
    ("depot-return", "depot", "orders", "billing", 0, "0.87"),
    ("depot-damage", "depot", "orders", "hardware", 2, "0.29"),
    ("depot-missing", "depot", "orders", "general", 3, "0.91"),
    ("site-install", "site", "hardware", "orders", 0, "0.85"),
    ("site-callout", "site", "hardware", "access", 2, "0.25"),
    ("site-permit", "site", "hardware", "billing", 2, "0.59"),
    ("meter-read", "meter", "general", "billing", 2, "0.28"),
    ("meter-fault", "meter", "hardware", "general", 3, "0.90"),
    ("meter-swap", "meter", "orders", "hardware", 0, "0.86"),
    ("plan-upgrade", "plan", "billing", "orders", 2, "0.57"),
    ("plan-cancel", "plan", "access", "billing", 3, "0.92"),
    ("plan-hold", "plan", "billing", "general", 0, "0.84"),
))

FIELD_INTAKE = {
    "depot-return": (4, 3, 2),
    "depot-damage": (1, 1, 2),
    "depot-missing": (0, 1, 1),
    "site-install": (3, 3, 2),
    "site-callout": (1, 1, 2),
    "site-permit": (1, 1, 1),
    "meter-read": (0, 1, 2),
    "meter-fault": (0, 1, 2),
    "meter-swap": (2, 2, 2),
    "plan-upgrade": (1, 1, 2),
    "plan-cancel": (0, 0, 2),
    "plan-hold": (2, 2, 2),
}

FIELD_POOL = {
    "depot-return": (24, 14, 8),
    "depot-damage": (40, 22, 10),
    "depot-missing": (8, 6, 4),
    "site-install": (22, 12, 8),
    "site-callout": (40, 22, 10),
    "site-permit": (20, 12, 8),
    "meter-read": (36, 20, 10),
    "meter-fault": (8, 6, 4),
    "meter-swap": (22, 12, 8),
    "plan-upgrade": (20, 12, 8),
    "plan-cancel": (8, 6, 4),
    "plan-hold": (22, 12, 8),
}

FIELD = {
    "desk": "the field-service desk",
    "code": "FS",
    "review": "the field-service review",
    "segments": FIELD_SEGMENTS,
    "window": ("2026-09-11", "2026-10-10"),
    "window_days": 30,
    "tagger_outage": ("2026-09-11", "2026-09-12"),
    "intake_mix": _counts(FIELD_INTAKE),
    "pool_mix": _counts(FIELD_POOL),
    "pool_exported_on": "2026-04-24",
    "prices": {"email": 12, "webform": 12, "phone": 18},
    "setup_credits": 80,
    "session_item_cap": 100,
    "credits_contracted": 5200,
    "today": "2026-10-12",
    "order_cutoff": "2026-10-14",
    "review_on": "2026-10-16",
    "sessions_before_cutoff": 3,
    "draw_sharpness": 2,
    "ramp": {"onset": 56, "slope": "1/35", "cap": "0.8"},
    "sessions": (
        {"session_id": "F-0918", "ordered_at": "2026-09-18T09:00",
         "delivered_at": "2026-09-18T20:30", "items": 88, "reviewer": "R-31"},
        {"session_id": "F-0926", "ordered_at": "2026-09-26T08:30",
         "delivered_at": "2026-09-26T18:40", "items": 64, "reviewer": "R-31"},
    ),
    "redelivery": None,
    "adjudicated": 90,
    "adjudicated_from": ("F-0918",),
    "adjudicated_on": "2026-10-02",
}


HARBOUR_SEGMENTS = _segments((
    ("berth-booking", "berth", "orders", "billing", 2, "0.30"),
    ("berth-change", "berth", "orders", "access", 0, "0.88"),
    ("berth-cancel", "berth", "orders", "general", 3, "0.93"),
    ("crane-slot", "crane", "hardware", "orders", 2, "0.26"),
    ("crane-fault", "crane", "hardware", "general", 3, "0.90"),
    ("crane-permit", "crane", "access", "hardware", 0, "0.86"),
    ("gate-pass", "gate", "access", "billing", 2, "0.59"),
    ("gate-vehicle", "gate", "access", "orders", 0, "0.85"),
    ("gate-escort", "gate", "general", "access", 3, "0.91"),
    ("fee-invoice", "fee", "billing", "orders", 0, "0.87"),
    ("fee-dispute", "fee", "billing", "general", 2, "0.28"),
    ("fee-waiver", "fee", "general", "billing", 2, "0.62"),
))

HARBOUR_INTAKE = {
    "berth-booking": (1, 2, 2),
    "berth-change": (3, 3, 2),
    "berth-cancel": (0, 1, 1),
    "crane-slot": (1, 1, 2),
    "crane-fault": (0, 1, 2),
    "crane-permit": (3, 2, 2),
    "gate-pass": (1, 1, 2),
    "gate-vehicle": (3, 3, 2),
    "gate-escort": (0, 0, 2),
    "fee-invoice": (3, 3, 3),
    "fee-dispute": (1, 2, 2),
    "fee-waiver": (1, 1, 2),
}

HARBOUR_POOL = {
    "berth-booking": (34, 20, 12),
    "berth-change": (18, 10, 6),
    "berth-cancel": (6, 4, 4),
    "crane-slot": (34, 20, 12),
    "crane-fault": (6, 4, 4),
    "crane-permit": (18, 10, 6),
    "gate-pass": (22, 12, 8),
    "gate-vehicle": (18, 10, 6),
    "gate-escort": (6, 4, 4),
    "fee-invoice": (18, 10, 6),
    "fee-dispute": (34, 20, 12),
    "fee-waiver": (22, 12, 8),
}

HARBOUR = {
    "desk": "the harbour operations desk",
    "code": "HB",
    "review": "the harbour review",
    "segments": HARBOUR_SEGMENTS,
    "window": ("2026-10-11", "2026-11-09"),
    "window_days": 30,
    "tagger_outage": ("2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14"),
    "intake_mix": _counts(HARBOUR_INTAKE),
    "pool_mix": _counts(HARBOUR_POOL),
    "pool_exported_on": "2026-05-29",
    "prices": {"email": 9, "webform": 15, "phone": 22},
    "setup_credits": 50,
    "session_item_cap": 140,
    "credits_contracted": 4800,
    "today": "2026-11-11",
    "order_cutoff": "2026-11-13",
    "review_on": "2026-11-17",
    "sessions_before_cutoff": 2,
    "draw_sharpness": 2,
    "ramp": {"onset": 28, "slope": "1/25", "cap": "0.9"},
    "sessions": (
        {"session_id": "H-1019", "ordered_at": "2026-10-19T09:10",
         "delivered_at": "2026-10-19T22:05", "items": 104, "reviewer": "R-07"},
        {"session_id": "H-1030", "ordered_at": "2026-10-30T08:15",
         "delivered_at": "2026-10-30T17:50", "items": 56, "reviewer": "R-07"},
    ),
    "redelivery": {"session_id": "H-1019", "receipts": 16, "at": "2026-10-20T02:40"},
    "adjudicated": 96,
    "adjudicated_from": ("H-1019",),
    "adjudicated_on": "2026-11-02",
}


RIDGE_SEGMENTS = _segments((
    ("north-access", "north", "access", "billing", 2, "0.31"),
    ("north-outage", "north", "access", "hardware", 3, "0.89"),
    ("north-meter", "north", "access", "orders", 0, "0.86"),
    ("south-billing", "south", "billing", "access", 2, "0.29"),
    ("south-refund", "south", "billing", "orders", 3, "0.92"),
    ("south-plan", "south", "billing", "general", 0, "0.85"),
    ("east-device", "east", "hardware", "orders", 2, "0.60"),
    ("east-return", "east", "orders", "hardware", 3, "0.90"),
    ("east-repair", "east", "hardware", "general", 0, "0.84"),
    ("west-order", "west", "orders", "billing", 2, "0.58"),
    ("west-delivery", "west", "general", "orders", 3, "0.91"),
    ("west-address", "west", "orders", "access", 0, "0.87"),
))

RIDGE_INTAKE = {
    "north-access": (1, 1, 2),
    "north-outage": (0, 1, 1),
    "north-meter": (2, 2, 2),
    "south-billing": (1, 1, 2),
    "south-refund": (0, 1, 1),
    "south-plan": (2, 2, 2),
    "east-device": (1, 1, 1),
    "east-return": (0, 1, 1),
    "east-repair": (2, 1, 2),
    "west-order": (1, 1, 1),
    "west-delivery": (0, 1, 1),
    "west-address": (2, 2, 2),
}

RIDGE_POOL = {
    "north-access": (20, 12, 6),
    "north-outage": (6, 4, 2),
    "north-meter": (10, 6, 4),
    "south-billing": (20, 12, 6),
    "south-refund": (6, 4, 2),
    "south-plan": (10, 6, 4),
    "east-device": (12, 8, 4),
    "east-return": (6, 4, 2),
    "east-repair": (10, 6, 4),
    "west-order": (12, 8, 4),
    "west-delivery": (6, 4, 2),
    "west-address": (10, 6, 4),
}

RIDGE = {
    "desk": "the ridge road desk",
    "code": "RR",
    "review": "the ridge road review",
    "segments": RIDGE_SEGMENTS,
    "window": ("2026-11-11", "2026-12-10"),
    "window_days": 30,
    "tagger_outage": ("2026-11-11", "2026-11-12"),
    "intake_mix": _counts(RIDGE_INTAKE),
    "pool_mix": _counts(RIDGE_POOL),
    "pool_exported_on": "2026-06-26",
    "prices": {"email": 11, "webform": 13, "phone": 21},
    "setup_credits": 70,
    "session_item_cap": 110,
    "credits_contracted": 1500,
    "today": "2026-12-12",
    "order_cutoff": "2026-12-14",
    "review_on": "2026-12-17",
    "sessions_before_cutoff": 2,
    "draw_sharpness": 2,
    "ramp": {"onset": 16, "slope": "1/16", "cap": "0.9"},
    "sessions": (
        {"session_id": "R-1120", "ordered_at": "2026-11-20T09:00",
         "delivered_at": "2026-11-20T21:15", "items": 100, "reviewer": "R-44"},
    ),
    "redelivery": None,
    "adjudicated": 70,
    "adjudicated_from": ("R-1120",),
    "adjudicated_on": "2026-12-03",
}


CURRENT = Desk(NORTHGATE)
SIBLINGS = (Desk(FIELD), Desk(HARBOUR))
OUT_OF_REGIME = Desk(RIDGE)
