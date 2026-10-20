# Cluster notes — research cluster, September

Kept by the sweep operator. Operations only; the science lives in the notebook.

## Node types

- `n-a` — the eight-card boxes in rack 3. Fastest thing we have and the one
  everybody asks for.
- `n-b` — the four-card boxes in racks 5 and 6. Most of the sweep has run here.
- `n-c` — the two-card boxes left over from the vision cluster. Slow, but they
  are almost always free.

## Reservations

- `n-a` went to the evaluation team on the morning of the 14th and is held for
  them until the end of the month. Nothing from the sweep goes on it in that
  window; the console turns those jobs away.
- `n-b` and `n-c` are open to the sweep for the rest of the window.

## Booking

- A job is booked in whole wall hours, four at the least and sixteen at the
  most. The scheduler will not hold a slot shorter than four and will not let
  one run past sixteen without a fresh ticket.
- A job that is turned away still costs an hour off the grant; the console logs
  it with the reason.
- A job comes back with the rows the trainer wrote while it ran, and the ledger
  gets a segment for it.

## Launch scripts

- Everything in the sweep goes out on `launch/train_v4.sh`, whose evaluation
  hook writes a row every 250 steps.
- `cfg-05` went out on `launch/train_v3.sh` on the 27th and has stayed on it
  through every resume since, so its rows come every 2,000 steps. Nobody has
  wanted to restart it from the top just to change the hook.

## Housekeeping

- `run_ledger.csv` gets a row per segment as the segment finishes. `first_step`
  and `last_step` are the trainer's own counter for that segment, and
  `resumed_from` names the segment it carried on from.
- `curves/<segment>.csv` is what the evaluation hook wrote for that segment:
  `step`, `lr` and `loss`, one row per hook fire.
