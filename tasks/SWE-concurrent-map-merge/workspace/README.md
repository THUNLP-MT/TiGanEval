# Whiteboard client

`board/` is the part of the whiteboard client that keeps a session's cards.
People run sessions on laptops and tablets that spend a lot of the day off the
network: they keep editing, and their changes reach everyone else whenever the
connection comes back.

- `board/contract.py` is the sync contract. The desktop app, the tablet app and
  the sync service are all built against it and ship it with their release, so
  it is read-only here. It holds the wire form of an operation, `pack` and
  `unpack`, the version-vector helpers (`dominates`, `happens_before`,
  `merge_vectors`, `contiguous_vector`, `covered_ids`), the canonical form of a
  board and `digest_of_board`, the `DISPOSITIONS` a merge account may use, and
  the validators the service runs over everything a copy hands back.
- `board/merge.py` holds `Replica`, one client's copy of the session.
- `board/helpers.py` is empty and available for anything the merge needs.

## What the sync service does

The service keeps no board of its own. It forwards packets between the clients
in a session, drops nothing on purpose, and retries a packet it has not seen
acknowledged, so the same operations reach two clients in different orders and
sometimes twice.

When a client reconnects, the service asks it for its state vector and then
forwards every operation the client's peer holds that the vector does not
account for, in the order the peer received them. There is no other way an
operation reaches a client that missed it.

## What support looks at

Every copy hands back a merge account alongside the board. Support reads that
account next to the card when someone says their work went missing, and tells
them who replaced their line and when.

Two people in the same session are supposed to be looking at the same thing.
`digest_of_board` is what support compares when a customer sends a screenshot,
because reading two screens side by side misses a field.

## Sessions support kept

`project_records/` holds four sessions that customers complained about, each
with the operations people made, the packets the service managed to deliver,
and the reconnect that followed.

`run_project(action="replay", record="project_records/<name>.json")` runs one of
those sessions against a copy of this workspace and reports the record's
support note and what every client copy did, packet by packet: the operations
themselves, the state vector and board digest after each packet, what the
service resent on reconnect, and the board, vector and account each copy ended
with. A replay changes nothing here and reaches no customer.

`run_experiment` runs a Python script you write against a copy of the
workspace, so you can build operations of your own with `board/contract.py`,
hand them to `Replica` in any order you like, and compare what comes out.
