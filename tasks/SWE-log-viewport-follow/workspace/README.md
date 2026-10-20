# Incident console

The console is the wall view the on-call watches during a page. Workers write
lines into it, the operator drags the divider between its two panes, and the
toolbar above it shows a Live or Paused badge and keeps a session audit.

- `console/protocol.py` ships in the console release and the incident exporter
  reads the same file, so it stays as it is. It owns `Entry`, `Extent` and the
  `FollowChanged` record; `effective_width`, `wrap_text` and `render_entry`;
  `render_all` and `content_extent`; `extent_of_lines`; `max_scroll_y`,
  `at_end` and `clamp_scroll`; and `PlainPane`, the plain-text pane in the
  console's left column.
- `console/rich_pane.py` is ours: `RichPane`.
- `console/support.py` is empty and ours too.
- `console.toml` is what the console is configured with, and the house rules
  the shift leads wrote into it after the post-mortems are in there too.

## What the console calls, and what reads the pane back

The console builds one `RichPane(height=..., min_width=..., max_entries=...,
name=...)` and then drives it:

- `write(entry_id, text, full_width=False)` — a worker line. `full_width` is
  what the console passes for the rule and banner lines that separate one
  incident from the next.
- `resize(width)` — the layout has settled, or an operator dragged the divider.
  A pane has no width until the first `resize`, and the console writes the
  opening lines of an incident before that happens.
- `set_min_width(min_width)` — the reading width the operator asked for.
- `scroll_to(line)`, `scroll_by(lines)` — the scrollbar and the wheel.
- `follow_end()` — the toolbar's Follow button.
- `clear()` — the console clears the pane between incidents.

The rest of the console reads the pane: `scroll_y` and `max_scroll_y` for the
vertical bar, `is_following_end` for the badge, `strips()` for what is drawn
(each retained entry with the display lines it occupies, top to bottom),
`extent()` for both scrollbars, and `messages()` for the audit.

## Recorded sessions

`project_records/` holds four sessions the shift leads replay before a console
change goes out. Each one is an event script plus what the operator, the
toolbar or the exporter recorded that night.

- `run_project(action="status")` lists the console files, the settings in
  `console.toml`, and the four sessions with the pane settings each ran with.
- `run_project(action="replay", record="project_records/<name>.json")` drives
  one session against the current workspace on a copied tree and prints the
  console view: for every event the pane's `scroll_y`, `max_scroll_y`, badge,
  drawn line count and widest drawn line, which entry is at the top of the
  viewport and which line inside it, the rows on screen, and any record the
  pane posted to the audit — next to what the console recorded that night.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `RichPane`, `PlainPane` and
  anything in `console/protocol.py` through any sequence of your own.
