# Partner intake

`intake/` is how a payload a partner posts becomes a warehouse record. One
process holds it, the intake console builds one loader per partner at start-up
and then runs that day's posts through them.

- `intake/protocol.py` ships in the platform release and is the same file in
  every service that takes partner payloads, so it stays as it is. It owns
  `FieldSpec` and `Shape`; `NAME_STYLES` and `convert_name`; `MappingConfig`,
  `merge_configs`, `declared_aliases` and `declared_styles`; the envelope reader
  `unwrap_payload`; `coerce` and the `KEY_LOG` it writes; `schema_property`; and
  the errors intake raises — `ConfigError` while a loader is being built, and
  the `LoadError` family, whose `trail` is what support quotes back to a
  partner.
- `intake/mapper.py` is ours: `build_loader`, and the `Loader` it returns with
  `load`, `dump` and `input_schema`.
- `intake/support.py` is empty and ours too.

## How a partner is configured

Configuration arrives in layers — the platform base first, then the partner's
own file — and `merge_configs` folds them into the `MappingConfig` a loader is
built from. Nineteen partners are configured that way today. A loader is built
once, when the service boots, so an operator meets a `ConfigError` against the
file they just wrote rather than in the middle of a partner's run.

## Operations notes

- Partners fetch `input_schema()` as the key-and-type catalogue their gateways
  use before posting. It lists exactly the keys intake accepts with the field
  fragment each carries, and marks a required field's published key as required
  when that field has no alternative spelling. The catalogue does not encode
  whole-payload rules for multiple alternative spellings or `extra_policy`;
  intake enforces those when the payload arrives.
- When we bounce a payload, support quotes the failure's `trail` in the ticket
  we send the partner. A ticket that names a key the partner never sent comes
  straight back to us.
- The strict endpoint (`extra_policy` set to `forbid`) is there to catch a
  partner's typo on the day they make it. The collecting endpoint (`collect`)
  keeps what we do not recognise beside the record, and the migration team
  counts those keys every week against what the partner says they sent.
- We do not guess between two names for one thing. `unwrap_payload` bounces a
  payload that arrived in both envelopes instead of picking one, and it does
  that even when the two hold the same fields, because nothing in the payload
  says which the sender meant to be the real one.
- A `ConfigError` out of building a loader is the one start-up failure the
  console knows what to do with: it holds the box and shows the operator the
  line against the file they just wrote. Anything else escapes to the
  supervisor, which restarts intake and pages whoever is on call, and the
  operator never learns which file was wrong.
- `alias_style` is a blanket switch over the whole shape, single-word fields
  such as `note` included, and a single word's spelling in another style is
  usually the spelling it already has.

## Recorded runs

`project_records/` holds four runs of partner posts the team replays before a
change to the loader goes out.

- `run_project(action="status")` lists the intake files and the four runs with
  the shape and the partners each one involves.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  of them against the current workspace on copied state and prints the intake
  log: for every post, the envelope it arrived in, the keys the partner sent,
  which key each field's value was taken out of, and either the record intake
  built or the failure it bounced with and that failure's trail; for a schema
  operation, what the partner fetches; and the settings each partner's layers
  fold into.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can build a loader over any shape and
  configuration of your own and post anything you like to it.
