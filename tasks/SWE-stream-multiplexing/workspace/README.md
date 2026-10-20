# Telemetry uplink

`link/` is the ground station's end of the radio link to a depot unit in the
field. One link carries every conversation the station has with that unit at
the same time — an operator console, log uploads, firmware pushes, status polls
— each on its own stream id.

- `link/protocol.py` is the wire format. The depot units run it in their
  firmware and a technician updates them once a year with a laptop, so what the
  station puts on the radio has to be what the units already read; the file
  ships with the firmware release and stays as it is. It owns `encode_frame`
  and `decode_frames`, the `OPEN`, `DATA`, `GRANT` and `SHUT` commands,
  `SessionConfig`, `LinkCounters`, the `Write` ticket, `ClosedLink`,
  `Transport`, and `PeerEnd`, which is the unit's own end of the link.
- `link/session.py` is ours: `Session`, which owns the streams and the radio.
- `link/streams.py` is ours: `Stream`, one conversation on the link.

## How the pieces behave

The radio gives the station a slot at a time. The driver hands the session the
number of bytes that fit in the slot, `session.pump(max_bytes)`, and the
session puts no more than that many bytes of whole frames on the transport;
what it does not send this slot it still owes. Bytes that arrive from the unit
go in through `session.feed(data)`.

What the station and the drills call:

- `Session(transport, config)`, `open_stream(priority)`, `accept_stream()`,
  `pump(max_bytes)`, `feed(data)`, `close()`, and the live streams in
  `session.streams`, keyed by stream id.
- `Stream`: `id`, `priority`, `write(data)` handing back a `protocol.Write`,
  `read()`, and `close()`.
- `session.counters`, a `protocol.LinkCounters`.

A depot unit is a small board with a fixed amount of memory per stream. Its
consumer takes bytes out of a stream when it gets round to it, and it sends a
`GRANT` back for what it took. A unit that has been asked to hold more than it
can will drop what it cannot fit, and the technician's log has been full of
those since the vendor batch went in.

## Operations notes

- The nightly link report is the six numbers in `LinkCounters`. The depot bills
  the station on `payload_bytes_sent` and `payload_bytes_received`; the radio
  operator reads `frames_sent` and `frames_received` against the slots we were
  given; and the open-stream line on the report is `streams_opened` minus
  `streams_closed`, which is what should be up on that link right now.
- A stream id is the only thing that tells two conversations apart on one link,
  and both ends open streams: the station opens one when an operator starts a
  session, and a unit opens one when it has something to say.
- Closing one end of a stream does not close the other conversations on the
  link. Each end signals its own close with `SHUT` when the radio next gives it
  room for that control frame. The stream remains in `session.streams` while
  either end still has it open, even when it currently holds no unread bytes;
  once both ends have closed it, any bytes already received remain readable
  before it leaves.
- The unit's firmware writes a line in its own log for every frame it throws
  away, with the reason. `PeerEnd.rejected_frames` is that log.

## Drills

`project_records/` holds the four drills the team replays before a change to
the station goes out. Each one looks at a different part of the link, so the
replay prints different columns for each.

- `run_project(action="status")` lists the link files, the settings every drill
  runs a link with, and the drills.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  drill against the current workspace on a throwaway copy and prints what this
  station did at every step of it.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive a `Session` against
  `protocol.PeerEnd` through any sequence of your own.
