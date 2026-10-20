'Run one quarter notebook over a batch of quarters inside the sandbox.'

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


COLUMNS = ("step", "arrival_rate", "service_rate", "peak_wait_s", "step_size", "accepted")


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _publish(context: dict, receipts: list) -> None:
    'Lay the quarter out on disk the way the reporting job leaves it.'

    folder = Path("chains")
    folder.mkdir(exist_ok=True)
    for path in folder.glob("*.csv"):
        path.unlink()
    manifest = ["chain_id,node,job_id,steps_stored,init_source"]
    for chain in context.get("chains", ()):
        draws = chain["draws"]
        peaks = draws["peak_wait_s"]
        lines = [",".join(COLUMNS)]
        for index in range(len(peaks)):
            lines.append(
                f"{index + 1},{draws['arrival_rate'][index]:.3f},"
                f"{draws['service_rate'][index]:.3f},{peaks[index]:.4f},"
                f"{draws['step_size'][index]:.4f},{draws['accepted'][index]}"
            )
        (folder / f"{chain['chain_id']}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        manifest.append(
            f"{chain['chain_id']},{chain['node']},{chain['job_id']},"
            f"{len(peaks)},{chain['init_source']}"
        )
    Path("chain_manifest.csv").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    Path("collection_receipts.json").write_text(
        json.dumps({"study": context.get("study"), "entries": receipts}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        contexts = list(payload.get("contexts") or ())
        results = []
        published = None
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context")
                key = context if isinstance(context, int) else None
                if isinstance(context, int):
                    context = contexts[context]
                context = context or {}
                receipts = list(request.get("receipts") or ())


                stamp = (key, len(receipts))
                if stamp != published:
                    _publish(context, receipts)
                    published = stamp
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_run(context, receipts))
                    else:
                        answer = report_view(analysis.analyze(context, receipts))
                    json.dumps(answer, allow_nan=False)
                    results.append({"ok": True, "answer": answer})
                except BaseException as exc:
                    results.append({"ok": False, "error": _describe(exc)})
        result = {"ok": True, "results": results, "stdout": captured.getvalue()[-2000:]}
        json.dumps(result, allow_nan=False)
    except BaseException as exc:
        result = {"ok": False, "error": _describe(exc)}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
