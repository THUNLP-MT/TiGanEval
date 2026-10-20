# Reminder schedule engine

`recur/` turns the recurring rules customers store into the times we actually
send reminders at. One process holds it; the reminder dispatcher, the
subscription feeds, the mobile export and the customer-facing calendar view all
call into it.

- `recur/protocol.py` is shared with the dispatcher, the mobile importer and the
  calendar view, and ships in their release rather than ours, so it stays as it
  is. It owns the zone table `ZONES` and `local_offsets`, `to_utc`, `from_utc`
  and `offset_in_force`; `Window` with its `contains`; `RuleSpec`, the stored
  rule; `slice_window`; and `parse_rule_text`, which is the reader every one of
  those consumers uses.
- `recur/schedule.py` is ours: `expand`, `serialize` and `merge_feeds`.
- `recur/support.py` carries nothing yet and is ours too.

## How the pieces behave

A rule is written the way a person says it: a time of day, a zone, and how
often it comes round. A reminder is sent at an absolute moment. The zone table
covers 2024-06-01 to 2028-06-01 and refuses readings outside that range rather
than guessing an offset; it is written out by hand so that the same reading
resolves the same way on every machine.

The offsets in the table are whole seconds, not whole hours: two of the five
zones we sell into are not on an hour boundary, and three of them change offset
twice a year on dates that are not the same dates.

## Operations notes

- The reminder dispatcher does not ask for a day at a time. It walks forward in
  slices and asks for the next slice's reminders each time it wakes, so it can
  be restarted mid-day without replaying what it has already sent. Whatever we
  hand it for a slice is what goes out for that slice.
- A customer's schedule is the merge of every feed they subscribe to plus the
  invites they hold themselves. A team feed and a personal invite for the same
  meeting are routinely stored by different products in different zones.
- Customers book a standing meeting once and then leave it alone. A daily
  standup is normally stored with a `TIMES` in the thousands, or with an end
  years out; the calendar view and the dispatcher only ever ask about a week or
  a night of one. The longest of them run on past the far end of the zone table.
- Customers export a series into their phone or their desktop calendar and then
  subscribe to it from us as well. Whatever we write out comes back in through
  `parse_rule_text`, so text that reader disagrees with is a series the customer
  sees differently from the way we hold it.
- Support answers "when will this go out" from the calendar view, which renders
  the times `expand` returns.

## Scenes we replay

`project_records/` holds the four scenes the team replays before a change to the
engine goes out. Each names the situation it covers; the steps and the rules
belong to the scene and are printed when it is replayed.

- `run_project(action="status")` lists the engine files, the zone table and the
  scenes.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  scene against the current workspace and prints, next to what support or the
  operator wrote down the last time it was looked at, every step this engine
  performed: the reminders it would send with their absolute reading, their
  wall-clock rendering and the offset in force, what it wrote out and what the
  importer read back, each feed on its own next to the merge, and each slice the
  dispatcher would walk.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `expand`, `serialize` and
  `merge_feeds` through any rule, zone and window of your own.
