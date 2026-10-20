# Scene editor

`scene/` is the level editor's world state and the checkpoint feature beside
it. One process holds one level; everything the designer does arrives through
the editor's tools.

- `scene/protocol.py` ships in the editor's own release rather than ours, and
  the viewport, the outliner, the change panel and the level loader are all
  built against it. It owns entity ids and `decode_entity`, `World` with
  `create`, `reserve` and `destroy`, `Registry` with this project's trait and
  relation keys, and `values_equal`, `canonical_snapshot`,
  `canonical_checkpoint`, `validate_checkpoint`, `world_digest`,
  `digest_of_checkpoint` and `CheckpointError`.
- `scene/checkpoint.py` is ours: `capture_entity`, `capture_scene`,
  `restore_entity`, `restore_scene`, `compare_entities` and `compare_scenes`.
- `scene/tools.py` is empty and ours too.

## How the pieces behave

Entity ids are slots, and `World` in `scene/protocol.py` is the whole story on
how a slot is allocated, freed and handed out again. Read it before you rely on
an id.

The editor prints `world_digest(world)` in the status bar and
`digest_of_checkpoint(file)` next to each checkpoint in the file list, so a
designer can see at a glance whether the level in front of her matches a file.

## Operations notes

- A designer checkpoints one prop about as often as she checkpoints the whole
  level, and both kinds of file sit in the same list. A one-prop file holds
  that prop's links along with what it is carrying, and she will open one from
  yesterday on the level she has in front of her this morning, after a night of
  other people's edits to the same set: the prop hers was hanging off yesterday
  is not always still there, and a file written before we settled the key list
  can name a key this project does not declare.
- The change panel is what a designer reads before she decides whether to
  revert at all. Two files that mean the same level must not show up there as
  different, or she stops reading the panel and stops using checkpoints. She
  also scans it for one prop on a set of a few hundred, so each of its lists
  has to come out in order rather than in the order the comparison happened to
  visit things, and one set has to read the same way every time she opens it.

## Recorded sessions

`project_records/` holds five sessions the tools team replays before an editor
build goes out, each one a designer's session as it happened. They are examples
of what designers do, not the whole of it.

- `run_project(action="status")` lists the editor files and the sessions.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  session against the current workspace on copied state and prints every step:
  the level after it, each prop's id, slot and generation, what the status bar
  read, the digest of every checkpoint file saved so far, and whatever a revert
  raised.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `World` and the checkpoint
  feature through any sequence of your own.
