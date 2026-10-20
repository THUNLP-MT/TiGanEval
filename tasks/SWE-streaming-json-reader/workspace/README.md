# Collector client

`client/` holds the HTTP client the readings collector uses to pull each site
gateway's feed.

`client/reader.py` and `client/support.py` are this project's own files and are
the only ones anybody edits here. `client/protocol.py` and `client/wire.py`
mirror the gateway side of the contract and ship with the gateway firmware
release, so they are pinned and stay as they are.

- `client/protocol.py` is the runtime contract: `DecodingError`,
  `StreamConsumed` and `StreamClosed`; the metered `ByteStream` transport; the
  `Response` object and its `iter_raw`, `read`, and `close`; the media types
  that carry a JSON value stream; `READ_AHEAD_SLACK_BYTES`;
  `split_content_type`; `detect_encoding`; and the JSON scanning primitives
  `scan_json_value` and `parse_json_text`.
- `client/wire.py` is the encoder the gateways run, and its docstring is the
  wire description of the three framings they publish. Any body this client
  has to read can therefore be built locally and stepped through byte by byte.
- `client/reader.py` implements `iter_json(response)`.
- `client/support.py` is empty and available for helpers.

A streaming `Response` hands its body over in whatever chunks the transport
delivered; a non-streaming one is already in memory and can be replayed. The
transport counts the chunks and bytes pulled from it, how many times it was
closed, and whether it was read after closing.

Streaming responses borrow their connection from the collector's pool, so the
pool's rule decides what a reader owes it. Every streaming response gives its
connection back exactly once — when the read finishes, when it fails, and when
the caller walks away after a few records. A connection never given back is
lost to the pool for the rest of the cycle; one given back twice can already
belong to another caller, and reading it after that is reading somebody else's
response. A response already in memory borrows nothing and closes nothing: the
validation step and the writer both read it, so it has to give its records back
every time it is read.

`READ_AHEAD_SLACK_BYTES` is the collector's flow budget: when a value reaches
the caller, the bytes pulled from the transport should be no more than that
value's framing needed plus the transport chunk in flight plus that slack.

Recorded response traces are under `project_records/`.
`run_project(action="replay", record=...)` re-runs one trace against whatever
reader is in the tree and prints, side by side, what the gateway sent and what
this build did with it. `run_project(action="status")` lists the traces and the
collector's flow budget. `run_experiment` runs a Python script you write against
a throwaway copy of this workspace, which is how you try bodies of your own.
Neither changes the working project or delivers anything for review.
