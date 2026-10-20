# Migration formatter

`ddl/` is the formatter the schema team runs over the migrations directory of
the schema repository.

- `ddl/protocol.py` is the pinned runtime contract, shared with the migration
  runner and the review tooling, so it ships on their release and not ours:
  `tokenize`, `split_statements`, and `comments` for reading a file;
  `parse_schema`, the authoritative reading of a statement — two texts describe
  the same schema exactly when it returns equal values for them, and it returns
  `None` for a statement shape this project does not format; `FormatOptions`
  with the directory's `line_width` and `indent`; and `require_report`, which
  states the fields every formatter report must carry.
- `ddl/formatter.py` implements `format_statements(text, options)` and is ours
  to change.
- `ddl/support.py` is empty and is there for helpers.

`migrations/` holds a sample of the schema repository's migrations, the ones the
project records run over. The directory the formatter actually runs against is
larger and changes weekly: four teams write migrations into it and each
annotates a schema in its own way, so a formatter that only works on these files
is not finished.

The schema review index reads the formatter's written text directly. Each annotation is keyed by the physical output line that carries it, and the index has no continuation field for joining one note across lines. A replay's `formatted` text is exactly what that index reads.

`project_records/` names, per record, the migration files one review covered.
`run_project(action="replay", record="project_records/<name>.json")` formats
those files with the formatter currently in the tree and reports what came out:
the source, the formatted text, the statement rows the formatter reported, the
width of every written line, and the text the same formatter wrote when that
output went back in. It reports; it does not compare, and it does not tell you
whether what came out is right. `ddl/protocol.py` is on the path in
`run_experiment`, so any comparison you want to make you can write yourself. A
replay does not change the working tree and does not deliver anything.
