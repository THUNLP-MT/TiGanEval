# `iter_json` holds the whole body in memory — the big sites are killing the cycle

Tuesday's 04:00 collection was killed on the container's memory limit half way through the biggest site's readings. Billing invoiced from Monday's numbers until Thursday. I need you to take this on.

`client/reader.py` takes the whole body before it looks at any of it, so a feed costs its full size in RAM before the first reading reaches the writer. Replay `project_records/slow-producer-trace.json`: on the ndjson endpoint the byte counter already reads 217 of a 217-byte body when the first record comes back, and that gateway pushes it out four bytes at a time.

What I want from you is a collector that pulls a feed of any size without the container noticing, and that stores exactly the readings the gateway sent, in the order it sent them.

My guess: on the ndjson endpoint each line is one reading, so `iter_json` can hand it over when the line completes instead of pulling the body first. Empty pieces between readings or at the end are harmless flushes there, and I expect an empty segment to mean the same thing in the other streaming formats. Memory then tracks one reading, not one feed.

`encode_body` in `client/wire.py` is the gateways' own encoder, so anything they send us can be built here and stepped through byte by byte. When it is working, replay that trace and show me the counter climbing with the readings.

— Marta, readings collection
