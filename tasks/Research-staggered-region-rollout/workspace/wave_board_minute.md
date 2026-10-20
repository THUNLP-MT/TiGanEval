# Wave board: standing minute

Agreed 11 January 2026. Present: the wave board, delivery finance, the dispatch
platform group. Amended 2 May 2026 with the capacity line below.

## What the board decides

Batching goes to the last five metros on the register, or Halcombe stays on the
one-drop dispatcher for the rest of the year. The board takes that decision from
the rollout readout and from nothing else.

## The book

The programme is judged on the region book cut on 1 February 2026. The book is
the metros the board committed the half to, with the orders each of them was
running on the day it was cut; `region_book.json` carries both. The window the
board reads closes on 20 April 2026 and a metro that has not gone live by then
has nothing in the readout.

The board reads a metro on its first four weeks on batching, against the four
weeks before it, because that is the comparison the depot managers were shown
when they signed up to the schedule.

For each day in those first four weeks, the comparison is the other metros in
the same service band that had not gone live by that day. Read those same
comparison metros over the before-period. If the export starts inside a
metro's four weeks before go-live, use every pre-live day the export carries;
do not drop that metro or its batching days to manufacture a complete pair.

The book decides which live metros enter the number and weights them at the
orders recorded on the cut day. Within a metro, each daily sampled rate is one
day's reading regardless of how many orders the sampling job happened to take
that day; sampled-order counts determine the range, not the day's weight.

## What earns the decision

A move in on-time share, in on-time points, batching against no batching.
`board_bar_points` in `rollout_context.json` carries the number the board acts
inside: 1.5 points. The board will not take a decision from a readout whose
range is wider than that, and this half it has not been able to.

One sentence here is delivery finance's own and stands as they wrote it: at most
one chance in twenty, across the whole set of networks this readout is produced
for, of acting on a number that is not there. The same notebook produces the
readout for Halcombe, Ashgate, Pell and Wickham.

## Wave capacity

The board granted the programme twelve region-weeks this half. Two are charged:
Sculthorpe in the week of 27 April, and the week of 4 May the board handed back.
`wave_receipts.json` carries the receipts and is the board's own record of what
it charged.

The terms the wave board serves on, unchanged since January:

- at most three region-weeks in any one calendar week;
- between 20 and 40 percent of the metro's orders held back from batching for
  the week, so the depot keeps a control on its own ground;
- only a metro that has not gone live, and only one running more than 400 orders
  a day, because the wave desk will not staff a smaller one;
- a week the board hands back is charged against the twelve all the same. The
  desk time goes whether or not the vans move.

Until the current range is inside the board's bar, the next week must leave the
next board's range at least as narrow as a full week on the largest metro the
desk will still serve at the smallest held-back share allowed above. If no
region-week can meet the desk's terms, there is nothing to book.

## Minute of 14 December 2025, kept on the file at finance's request

The Ashgate programme came to this board in October on a readout of +4.4 points
against a bar of 1.5 and was signed off for the whole network. February's
follow-up put the same change at +1.6. Delivery finance carried 240,000 of
re-planning cost across the two quarters and asked that this minute stay with
the standing terms.
