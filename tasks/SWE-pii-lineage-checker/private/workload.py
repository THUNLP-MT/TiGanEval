'Deterministic pipeline corpora and drill programs for the lineage audit.'

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

_LABEL = re.compile(r"@([DC])(\d\d)@")
_FIELD = re.compile(r"@F(\d)@")


_ROTATED_FIELDS = ("ssn", "phone", "birthdate")


def _fill(text: str, number: int) -> str:
    def swap(match: re.Match[str]) -> str:
        prefix = "ledger" if match.group(1) == "D" else "ops"
        return f"{prefix}-{number:02d}-{match.group(2)}"

    def field(match: re.Match[str]) -> str:
        return _ROTATED_FIELDS[(number + int(match.group(1))) % len(_ROTATED_FIELDS)]

    return _FIELD.sub(field, _LABEL.sub(swap, text)).strip() + "\n"


def _parts(text: str) -> tuple[str, list[str]]:
    "One module's text as its header and its steps."

    head, *rest = text.strip("\n").split("\n\ndef ")
    steps = ["def " + part for part in rest]
    if head.startswith("def "):
        return "", [head, *steps]
    return head, steps


def _module(text: str, number: int, extra: Sequence[str] = ()) -> str:
    "One module as this drill's team left it: the same steps, written in     their order and spaced the way that file is spaced."

    head, steps = _parts(text)
    steps += [item.strip("\n") for item in extra]
    turn = number % len(steps) if steps else 0
    gap = "\n" * (1 + number % 3)
    body = gap.join(part + "\n" for part in steps[turn:] + steps[:turn])
    return (head + "\n" if head else "") + gap + body


_ORDERS = '''
"""Nightly order lines for the warehouse."""

from pipeline_io import warehouse, notify
from privacy import mask, hash_id

def daily_lines(row):
    line = "order for " + row["email"]
    warehouse.write_rows("@D01@", line)

def masked_contact(row):
    subject_email = mask(row["email"])
    warehouse.write_rows("@D02@", subject_email)

def chained_lines(row):
    first = row.get("@F1@")
    label = "subject:" + first
    payload = label
    warehouse.write_rows("@D03@", payload)

def keyed_batch(row):
    subject_email = row["email"]
    warehouse.write_rows("@D04@", "counts only", subject_email)

def two_fields(row):
    subject_email = row["email"]
    subject_phone = row["phone"]
    warehouse.write_rows("@D05@", subject_email + " / " + subject_phone)
'''

_TICKETS = '''
"""Ticket notices for the support channel."""

from pipeline_io import notify, warehouse
from privacy import hash_id, coarse_age

def percent_note(row):
    body = "subject %s asked for a copy" % row["email"]
    notify.publish("@C06@", body)

def formatted_note(row):
    body = "{} <{}>".format(row["region"], row["email"])
    warehouse.write_rows("@D07@", body)

def accumulated_batch(row):
    lines = "ticket header"
    lines += row["@F2@"]
    warehouse.write_rows("@D08@", lines)

def hashed_batch(row):
    if (token := hash_id(row["ssn"])):
        warehouse.write_rows("@D09@", token)

def bundled_batch(row):
    warehouse.write_rows("@D10@", rows={"region": row["region"], "contact": row["phone"]})

def paired_batch(row):
    warehouse.write_rows("@D33@", row["email"]); warehouse.write_rows("@D34@", row.get("phone"))

def direct_note(person):
    notify.publish("@C12@", person.phone)

def summary_batch(row):
    notify.publish("@C11@", "the nightly batch finished")
'''


_LATER = '''
def nested_batch(row):
    parts = ["copy", row["email"]]
    warehouse.write_rows("@D35@", parts[1])

def region_note(row):
    body = "{} region".format(row["region"])
    notify.publish("@C36@", body)

def aged_note(row):
    band = coarse_age(row["birthdate"])
    notify.publish("@C37@", band)
'''
_LATER_STEPS = _parts(_LATER)[1]


def standalone_modules(number: int) -> dict[str, str]:
    later = _LATER_STEPS[: number % 4]
    return {
        "steps/orders.py": _fill(_module(_ORDERS, number), number),
        "steps/tickets.py": _fill(_module(_TICKETS, number, later), number),
    }


_DESK = '''
"""Standing notices the @TEAM@ desk sends every quarter."""

from pipeline_io import warehouse
'''

_NOTICE = '''
def notice_@N@(row):
    warehouse.write_rows("@D@N@@", {"email": "desk@example.test", "note": "reminder"})
'''

_INVOICE = '''
def invoice_batch(row):
    warehouse.write_rows("@D30@", {"email": row["email"], "total": row["total"]})
'''

_STATEMENT = '''
def statement_batch(row):
    line = "statement for " + row["email"]
    warehouse.write_rows("@D31@", line)
'''


_DESKS = (
    ("desk", "front", 13, 4, ()),
    ("billing", "billing", 18, 3, (_INVOICE,)),
    ("support", "support", 22, 1, (_STATEMENT,)),
)


def audit_modules(number: int) -> dict[str, str]:
    modules: dict[str, str] = {}
    for name, team, first, notices, tail in _DESKS:
        standing = range(first, first + notices + number % 2)
        steps = [_NOTICE.replace("@N@", f"{index:02d}") for index in standing]
        body = _module(_DESK.replace("@TEAM@", team), number, [*steps, *tail])
        modules[f"audit/{name}.py"] = _fill(body, number)
    return modules


_INLINE = '''
"""The week-12 case handler, before the pipeline team split it up."""

from pipeline_io import warehouse, notify
from privacy import mask

def handle_case(row):
    email_line = "case " + row["email"]
    warehouse.write_rows("@D40@", email_line)
    notify.publish("@C41@", row["phone"])
    notify.publish("@C44@", mask(row["ssn"]))

def notice_batch(row):
    subject_email = row["email"]
    notify.publish("@C42@", subject_email)

def spill_batch(row):
    subject_phone = row["phone"]
    warehouse.write_rows("@D43@", subject_phone)
'''

_EXTRACTED = {
    "app/handler.py": '''
"""The week-12 case handler, after the pipeline team split it up."""

from pipeline_io import notify
from privacy import mask
from app.build import build_case
from app.retry import push_batch
from app.send import send_case

def handle_case(row):
    payload = build_case(row)
    send_case(payload)
    push_batch(row["phone"])
    notify.publish("@C44@", mask(row["ssn"]))
''',
    "app/build.py": '''
def build_case(row):
    return "case " + row["email"]
''',
    "app/send.py": '''
"""Handing a built case on, and the retry the channel team asked us to keep."""

from app.stage import stage_case
from app.retry import push_batch

def send_case(payload):
    stage_case(payload)
    push_batch(payload)
''',
    "app/stage.py": '''
from app.deliver import hand_over

def stage_case(payload):
    hand_over(payload)
''',
    "app/deliver.py": '''
"""Delivery, and the spill notice that shares its module."""

from pipeline_io import warehouse

def hand_over(payload):
    warehouse.write_rows("@D40@", payload)

def spill_batch(row):
    subject_phone = row["phone"]
    warehouse.write_rows("@D43@", subject_phone)
''',
    "app/retry.py": '''
"""Retrying a batch the channel refused, and the notice desk."""

from pipeline_io import notify

def push_batch(value):
    notify.publish("@C41@", value)
    retry_batch(value)

def retry_batch(value):
    push_batch(value)

def notice_batch(row):
    subject_email = row["email"]
    notify.publish("@C42@", subject_email)
''',
}

_TREE_WALK = (
    "app/deliver.py", "app/stage.py", "app/send.py",
    "app/retry.py", "app/build.py", "app/handler.py",
)


def committed_order(number: int) -> list[str]:
    'The order the release checkout walked the split-up handler in.'

    turn = number % len(_TREE_WALK)
    return list(_TREE_WALK[turn:] + _TREE_WALK[:turn])


def inline_modules(number: int) -> dict[str, str]:
    return {"app/handler.py": _fill(_module(_INLINE, number), number)}


def extracted_modules(number: int) -> dict[str, str]:
    return {name: _fill(_module(text, number), number) for name, text in _EXTRACTED.items()}


_DISPATCH_INLINE = '''
"""The intake dispatch, before the team pulled the shared line builder out."""

from pipeline_io import warehouse, notify

bootstrap = {"email": "dispatch@example.test"}
notify.publish("@C54@", bootstrap["email"])

class DispatchAudit:
    def receipt(self, row):
        notify.publish("@C53@", row.email)

def dispatch_case(row):
    warehouse.write_rows("@D50@", "case " + row["email"])

def dispatch_summary(row):
    warehouse.write_rows("@D51@", "case " + row["region"])

def dispatch_notice(row):
    def hand_off():
        notify.publish("@C52@", "notice for " + row["@F3@"])
    hand_off()

def dispatch_keyword(row):
    notify.publish("@C55@", row["phone"])

def dispatch_varargs(row):
    warehouse.write_rows("@D56@", row["ssn"])
'''

_DISPATCH_EXTRACTED = {
    "intake/render.py": '''
"""The line the dispatch steps have shared since the quarter's tidy-up."""

def render_line(value):
    return "case " + value
''',
    "intake/dispatch.py": '''
"""The intake dispatch, after the team pulled the shared line builder out."""

from pipeline_io import warehouse, notify
from intake.channel import send_bootstrap, send_keyword, send_notice, send_varargs
from intake.render import render_line

bootstrap = {"email": "dispatch@example.test"}
send_bootstrap(bootstrap["email"])

class DispatchAudit:
    def receipt(self, row):
        notify.publish("@C53@", row.email)

def dispatch_case(row):
    warehouse.write_rows("@D50@", render_line(row["email"]))

def dispatch_summary(row):
    warehouse.write_rows("@D51@", render_line(row["region"]))

def dispatch_notice(row):
    def hand_off():
        send_notice("notice for " + row["@F3@"])
    hand_off()

def dispatch_keyword(row):
    send_keyword(body=row["phone"])

def dispatch_varargs(row):
    send_varargs(row["ssn"], "dispatch")
''',
    "intake/channel.py": '''
"""The channel the dispatch notices go out on."""

from pipeline_io import notify, warehouse

def send_notice(body):
    notify.publish("@C52@", body)

def send_bootstrap(body):
    notify.publish("@C54@", body)

def send_keyword(*, body):
    notify.publish("@C55@", body)

def send_varargs(*parts):
    warehouse.write_rows("@D56@", parts)
''',
}


def dispatch_inline_modules(number: int) -> dict[str, str]:
    return {"intake/dispatch.py": _fill(_module(_DISPATCH_INLINE, number), number)}


def dispatch_extracted_modules(number: int) -> dict[str, str]:
    return {
        name: _fill(_module(text, number), number)
        for name, text in _DISPATCH_EXTRACTED.items()
    }


def _scan(label: str, modules: Mapping[str, str], **extra: Any) -> dict[str, Any]:
    return {"type": "scan", "label": label, "modules": dict(modules), **extra}


def _audit_program(number: int) -> list[dict[str, Any]]:
    return [_scan("quarter-audit", audit_modules(number))]


def _review_program(number: int) -> list[dict[str, Any]]:
    return [_scan("standalone-steps", standalone_modules(number))]


def _extract_program(number: int) -> list[dict[str, Any]]:
    return [
        _scan("case-handler-inline", inline_modules(number)),
        _scan(
            "case-handler-extracted", extracted_modules(number),
            order=committed_order(number), variant_of="case-handler-inline",
        ),
    ]


def _dispatch_program(number: int) -> list[dict[str, Any]]:
    return [
        _scan("dispatch-inline", dispatch_inline_modules(number)),
        _scan(
            "dispatch-extracted", dispatch_extracted_modules(number),
            variant_of="dispatch-inline",
        ),
    ]


def _second_worker(number: int, same_as: str) -> dict[str, Any]:
    return _scan(
        "checkout-worker-b", extracted_modules(number),
        order=list(reversed(committed_order(number))), same_set_as=same_as,
    )


def _checkout_program(number: int) -> list[dict[str, Any]]:
    return [
        _scan("checkout-worker-a", extracted_modules(number), order=committed_order(number)),
        _second_worker(number, "checkout-worker-a"),
    ]


def _release_program(number: int) -> list[dict[str, Any]]:
    return [
        *_review_program(number),
        *_extract_program(number),
        _second_worker(number, "case-handler-extracted"),
        *_dispatch_program(number),
        *_audit_program(number),
    ]


PROGRAM_BUILDERS = {
    "audit": _audit_program,
    "review": _review_program,
    "extract": _extract_program,
    "checkout": _checkout_program,
    "dispatch": _dispatch_program,
    "release": _release_program,
}


def build_program(profile: str, number: int) -> list[dict[str, Any]]:
    builder = PROGRAM_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown drill profile: {profile}")
    return [{"profile": profile, **event} for event in builder(number)]
