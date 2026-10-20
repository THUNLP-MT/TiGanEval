# Catalogue listing service

`listing/` is the endpoint every catalogue list in the product reads: the two
phone apps, the storefront's category pages and the nightly reporting
integration. One process holds the catalogue store, and the console builds a
store, edits it the way merchandising does and calls the endpoint.

- `listing/protocol.py` ships in the platform release and is the same file in
  the storefront and the reporting integration, so it stays as it is. It owns
  `Item` and `Store`; `SORTABLE_FIELDS`, `parse_order`, `order_text` and
  `list_all`; `encode_cursor` and `decode_cursor`; the `page` and `rejected`
  envelopes with `is_refusal`, `items_of` and `cursor_of`; `catalogue_summary`,
  which the sort menu reads; and `ServiceConfig` with `load_config`.
- `listing/pages.py` is ours: `Catalogue` with `find`.
- `listing/shelves.py` is empty and ours too.

## How a client reads a list

A client asks for a sort and a page size and gets a page back. While a page
carries a continuation the client asks for the next one; the first page that
carries none is the end of the list and the app stops asking and hides its
spinner. A refusal is different: the app throws away what it is holding and
starts the list again from the top, which is why the two phone apps show a
short flicker when one arrives. Anything raised out of `find` never reaches
that path at all — it comes back to the client as a server fault and the app
shows its error screen instead of the list.

Every list is asked for by sort, and the sort menu reads `catalogue_summary`
before the first page of one. Requests still arrive with no sort on them most
days: a retry after a dropped connection sends the query string back without
it, and links pasted into a chat app lose it the same way.

Clients hold on to whatever a page hands them. The apps keep a continuation in
the scroll state and replay it after a dropped connection, the storefront puts
it in the query string so a category page can be linked and bookmarked, and the
sort dropdown changes the sort under a list a customer is already half way
down.

## Operations notes

- `default_limit` and `max_page_size` come from `service.toml`. Nothing goes
  out larger than `max_page_size`; the note in the file gives the 4 March
  reporting request that set it.
- The listing service runs on two instances behind the load balancer and is
  redeployed two or three times on a working day. A client's next request lands
  on whichever instance the balancer picks, and neither instance has heard of
  the other or of what it was doing before the deploy.
- Merchandising works in the catalogue all day: the restock job adds rows in
  the morning, the buyers withdraw sold-out rows continuously, and prices move
  whenever a promotion starts. `Store.items()` hands rows back in the order
  they were added, which is nobody's idea of a catalogue order; `list_all` is
  what puts the catalogue in the order a client asked for.
- A walk's once-only delivery guarantee covers additions and withdrawals while
  existing products keep their sort values. Changes to other columns are fine;
  a price change during a price-sorted walk can move a product across the
  customer's place, so that walk is outside this guarantee. Item ids are not
  reused during a walk.
- `offset` is what the storefront's category pages still send, and the
  reporting integration sends a large page size once a night. Both keep
  working.

## Recorded scenarios

`project_records/` holds four stretches of listing traffic the team replays
before a change to `find` goes out.

- `run_project(action="status")` lists the listing files, the settings in
  `service.toml` and the four scenarios with the catalogue and the page sizes
  each one uses.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  scenario against the current workspace on a copied catalogue and prints the
  request log: every request with the sort, the page size asked for, the row
  count it started from if it sent one, the rows it served, whether it carried
  a continuation and whether it was refused; every edit merchandising made
  between requests; and the complete sequence of product ids delivered. It
  reports those measurements without comparing them with a reference result.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can build a `Store`, call `find`
  through any sequence of your own and read `list_all` back.
