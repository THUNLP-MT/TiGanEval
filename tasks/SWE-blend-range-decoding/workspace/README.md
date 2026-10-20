# Catalogue compositor

`plate/` is the compositor behind the overnight product-page export. It opens
the source files the studio draws in, flattens each shot into the plate the
page carries, and writes every file it opened back so the designers pick up the
same files in the morning.

- `plate/protocol.py` is shared with the design tool, the page exporter and the
  studio's own scripts, and ships in the design tool's release rather than
  ours, so it stays as it is. It owns the stored plate format (`read_document`,
  `Document`, `Layer`), the stored range words (`unpack_handles`,
  `pack_handles`, `entries`, `DEFAULT_ENTRY`), the studio's grey formula
  (`luminosity`), the way a layer's cuts fold into one coverage weight
  (`combine`), the compositing step and its rounding (`mix`, `coverage`,
  `quantize`), and `plain_stack`, the compositor as it published plates before
  any layer stored range work at all.
- `plate/bands.py` is ours: the reader and writer for a layer's stored range
  work, half written.
- `plate/compose.py` is ours: the flattener the export runs.
- `plate/support.py` is ours and empty.

## How the pieces behave

A shot is an opaque backdrop with layers composited onto it, bottom layer
first. A layer declares the channels it stores; a layer drawn with soft edges
stores a transparency channel as well.

The sliders the designers drag in the tool are stored on the layer as range
words, four words to an entry. `unpack_handles` is the only way to read the two
grips out of one word; the design tool writes them back the same way. How many
entries a layer stores is a property of the file the studio saved, and every
release of the tool has written a slightly different block.

## Operations notes

- The design tool is the authority on what a plate looks like. Every recorded
  scenario ships the plate the tool published for the shots it flattens, so a
  replay prints the two plates one after the other.
- The export re-writes the source files it opens. Whatever `bands.decode`
  produces for a layer goes back through `bands.encode` on the way out, and
  that is what lands in the studio's file.
- What the export calls: `compose.flatten(document)` for the plate,
  `bands.decode(layer.block)` and `bands.encode(model)` on the write-back.
- Only a small part of the catalogue has any range work on it. The archive
  rebuilds still go through `protocol.plain_stack`.

## Recorded scenarios

`project_records/` holds the four scenarios the pipeline replays before a
compositor change goes out. Each one looks at different shots, and a scenario
may write a source file back without flattening it. They are the shots that
happened to be in front of somebody when the scenario was recorded, not the
shots the overnight export runs.

- `run_project(action="status")` lists the compositor files and, for every
  scenario, the shots it runs and what each of their layers stores.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  scenario against the current workspace on a throwaway copy and prints, per
  step, the plate this build published and the plate the design tool published
  for that shot.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can flatten plates of your own.
