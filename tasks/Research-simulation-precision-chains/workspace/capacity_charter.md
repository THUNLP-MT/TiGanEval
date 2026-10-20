# Reservation capacity: what the platform committed to, and what the review asks

Agreed 14 October 2026. Signatories: the platform group, the capacity modelling
group, and the customer commitments desk.

## The commitment

The reservation platform's service agreement is written on the busiest minute of
a quarter. In a quarter that behaves, the peak wait at the reservation desk stays
under **2.5 seconds**. The commitment the desk signed allows the peak to pass 2.5
seconds in **no more than 5 per cent of quarters**. Over that and the commitments
desk renegotiates the agreement at the next renewal; under it and the platform
holds the terms it has.

## What the review takes from the modelling group

One number, and a range for it: how often the fitted capacity model puts a
quarter's peak wait over 2.5 seconds. The number is a share of quarters, not a
duration.

The range that goes under the number is the one that **holds nineteen times in
twenty**. The desk reads the renewal against it and will not take a range built
to any other level.

The review closes the question for a quarter when the range it is given is **no
more than 0.03 end to end** and sits wholly on one side of the 5 per cent line.
A range that reaches across the line leaves the question open however narrow it
is, and the review will not take the nearer end of it as the answer.

## How the model is fitted

The model is fitted by a sampler that walks the parameter space and writes out
what each step implies for the quarter's peak wait. The runs are queued on the
shared compute grant; `compute_ledger.md` carries its terms, and every run the
console has served is on `collection_receipts.json`.

## Minute of 8 December 2026, kept on the file at the commitments desk's request

The 2026 Q2 dispatch review went to the desk with a share of 3 per cent and a
range that ran from 1 to 5 per cent. The desk read the 3 and signed a renewal on
it. The 2026 Q3 refit put the same quarter at 7 per cent. The desk carried the
difference for two quarters and asked that this minute stay with the charter, and
that no review close on a range that reaches across the line.
