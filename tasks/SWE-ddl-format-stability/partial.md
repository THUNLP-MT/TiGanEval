**#4181 (`account_wide`) — I have requested changes; can you take the formatter?**

Nothing is wrong with the table; I cannot review it. `migrations/0004_create_account_wide.sql` arrives as one 258-character line, so the pull request shows one changed line and I cannot see which column its author added. I approved `migrations/0005_create_account_events.sql` the same way last month, also a single line, and had to pick it apart by hand when analytics asked which column it partitions on.

The start of the fix is already in the tree: `ddl/formatter.py` breaks a statement at its commas and indents what follows. Replay `project_records/review-corpus.json` and look at what it does to the `accounts` table in `0001` — one column per line. Please finish it and run it over `migrations/` before I let #4181 through.

What I am after: break at every comma in the statement, including the ones inside `struct<width int, height int, depth int>` in `migrations/0002_create_account_notes.sql` — one piece per line, it is all whitespace as far as the database is concerned — and keep the result inside the width and indentation the directory is set to, which `run_project status` prints as 88 and 4.

When you hand it back I want a one-column change to read as one changed line. And whatever the formatter does to a file, the file has to still say what it said before, or I cannot put my name on the commit.

`project_records/layout-and-width-audit.json` is where I first measured this; `run_project` replays it against whatever formatter is in the tree.

— Selin, schema review
