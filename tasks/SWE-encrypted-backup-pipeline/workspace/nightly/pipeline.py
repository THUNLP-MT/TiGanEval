"""Tonight's archive: take the dump, compress it, put a copy in every
destination, and hand the scheduler the row it files.

This is the job as it has run since the filer went in. It knows nothing about
keys yet: what lands in the vault is the compressed dump.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import CHUNK_BYTES, NightRun, compress, night_report, object_name


def run_night(run: NightRun) -> Mapping[str, Any]:
    """Run one night and report how it went."""

    dump = run.dump.read()
    payload = compress(dump)
    name = object_name(run.job, run.night, sealed=False)
    landed = []
    for destination in run.destinations.values():
        destination.begin(name)
        for start in range(0, len(payload), CHUNK_BYTES):
            destination.write(name, payload[start : start + CHUNK_BYTES])
        destination.finalize(name)
        destination.close(name)
        landed.append(destination.name)
    return night_report(
        run.night,
        "completed",
        object=name,
        destinations=landed,
        source_bytes=len(dump),
        stored_bytes=len(payload),
    )
