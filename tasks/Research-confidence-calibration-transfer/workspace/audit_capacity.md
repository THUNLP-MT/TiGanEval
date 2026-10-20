# Adjudication credits, and what a batch costs

Agreed 28 August 2026 between the automation council, the listing review desk
and finance.

## The grant

The marketplace listing queue carries 1,200 adjudication credits this quarter.
200 of them were already charged before the council sat; the receipts are in
`audit_receipts.json`. Credits do not carry into next quarter and the desk
stops when they are gone.

## What a batch costs

- A batch names one cell: one channel and one intake plan. The desk cannot
  book a batch that leaves either out, and it works the cell's backlog oldest
  first.
- At most 150 listings in a single batch. A batch asking for more is turned
  away, and the receipt says so.
- Two credits a listing on the partner feed and on the reseller import; one on
  web and on mobile. A cell that returns listings is charged for the listings
  it returns, however many were asked for.
- A cell the desk works and finds nothing in is charged a flat 20 credits for
  the trip, and the receipt says the cell came back empty.
- A batch the credits left cannot pay for is turned away and charged nothing.

## Which batch to book next

The next batch is meant to close the largest part of the uncertainty that is
still relevant to the stream being served now.

- A cell remains worth a call only while its backlog holds at least forty
  listings and the credits left can pay for at least forty from that channel.
- Rank those cells by the channel's share of the stream served now, multiplied
  by the share of that channel's auto-cleared listings in the export that the
  cell would put an outcome against. This ranking uses the whole cell backlog,
  not only the part one batch can return.
- Ask for the highest-ranked cell and for as many listings as its backlog, the
  150-listing cap and the credits left allow. Return `"stop"` only when no cell
  remains worth a call.

The deployment's own terms come through on `context["audit"]`:
`credits_granted`, `max_listings_per_batch`, `credit_cost` by channel and
`empty_cell_charge`. Each queue the readout runs on has its own grant.

## Reporting

Every batch the desk was charged for appears in the readout once, with its
batch id, the listings it returned and the credits it cost, the turned-away
ones included. Finance reads the readout's credit total against the receipts.
