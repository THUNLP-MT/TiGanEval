# Order platform: storage and the write path

`orders/` is the code every service that touches an order goes through: the
checkout API, the fulfilment job, the support dashboard, the reconciliation
worker and the nightly partner hand-off.

- `orders/protocol.py` is the storage client. It ships in the client's release
  and is shared with the partner importer and the checkout form, so it stays as
  it is. It owns the schema document model (`Attr`, `Requirement`, `Schema`,
  `load_schema`, `walk`, `apply_defaults`, `to_stored`, `from_stored`,
  `stored_paths`), the condition nodes and `evaluate`, the `Store`, the
  published-contract validator `validate_contract`, and `SchemaError`,
  `ValidationError` and `ConditionalCheckFailed`.
- `orders/entities/order.json` and `orders/entities/refund.json` are the two
  live entity documents.
- `orders/retiring_guards.py` is the imperative pair check the API still runs
  entity by entity — one function per entity, each written by hand as a pair
  came up. It is being retired.
- `orders/policy.py` is ours: `check_schema`, `admit`, `build_update` and
  `read_view`. Nothing in it names an entity: it runs over whatever document is
  loaded, and the schema owners have more entities queued behind the two live
  ones.
- `orders/contract.py` is ours: `to_contract`, `to_dto` and `from_dto`.

The cutover is half done. The API still calls `orders/retiring_guards.py`;
`orders/policy.py` and `orders/contract.py` are what every service will go
through once it is finished, and the records under `project_records/` replay
them as though it already were.

## How the pieces behave

The store holds physical names. An attribute's `stored_as` is what the item
carries; the logical name is what the document, the API and the dashboard use.
Change sets and projections name logical paths, including dotted paths inside a
map. Setting a map replaces that whole map, while setting a path inside it
changes only that child. A value of `None` in `set` clears the named attribute,
just as naming it in `remove` does. A dotted projection comes back in the same
nested logical shape as a full view.

`Store.update(key, patch, condition)` applies exactly the paths the patch names
and nothing else, and it applies them only if `condition` holds against the item
the store already has; otherwise it raises `ConditionalCheckFailed` and writes
nothing. The store is the only thing in the platform that can see the stored
item while a write is being decided — `build_update` is handed the change set
and never the item.

A `required_when` declaration in a document names a sibling attribute — any
attribute in the same map, wherever it stands in the document — and the values
that make the pair binding.

## Operations notes

- One process reloads entity documents when the schema owners publish them, and
  `check_schema` runs over every document before it goes live and over every
  document sitting in the review queue.
- Every document declares exactly one key attribute. The store keys the item by
  its value, it is written when the item is created, and no stored item is ever
  without it, so nothing else in a document can change whether it is there.
- The support dashboard lists open orders and the support tool corrects them;
  both go through `read_view`, and the two list views ask for a projection
  rather than the whole item.
- The store has held orders since long before the current documents. Some of
  them do not satisfy what the documents say today.
- The nightly hand-off publishes `to_contract(schema)` to the partner, who
  validates every order with `protocol.validate_contract` before importing it,
  and ships `to_dto(schema)` to the reconciliation worker, which rebuilds it
  with `from_dto` and validates the same orders on the other side of the
  process boundary.

## Records

`project_records/` holds the four recorded scenes the platform replays before a
write-path change goes out. Each one looks at a different service, so the
replay prints different columns for each.

- `run_project(action="status")` lists the modules, the entity documents and the
  records.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  scene against the current workspace on a throwaway copy and prints what this
  build did at every step of it.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `Store`, `policy` and
  `contract` through any sequence of your own.
