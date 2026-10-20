'Sandbox entry point. Only public components and delivered integration import.'

import contextlib
import importlib
import io
import json
import sys
import traceback

from copydesk.host import Host, snapshot


def run(payload):


    measure = snapshot
    installer = importlib.import_module("copydesk.shared_bar").install
    sheets = []
    for session in payload["sessions"]:
        host = Host(session["page"])
        installer(host)
        rows = []
        for op in session["operations"]:
            host.operate(op)
            rows.append({"label": op["label"], "state": measure(host)})
        sheets.append({"name": session["name"], "rows": rows})
    return {"ok": True, "sheets": sheets}


def main():
    payload = json.load(sys.stdin)
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            result = run(payload)
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "diagnostic": traceback.format_exc()[-1000:]}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
