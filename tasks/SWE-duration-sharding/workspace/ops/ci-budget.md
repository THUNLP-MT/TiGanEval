# CI budget and the numbers the suite is judged on

Owner: the platform team. Last revised after the March cost review.

## What a run costs

Every run of the suite rents four machines for the length of the slowest shard.
A merge train goes green when all four shards go green, so the train waits for
the slowest one and the other three sit idle at full price. The March review
put a number on it: the platform team pays for four machines and gets the wall
clock of one.

Two conditions come out of that review, and the cost report is written against
both.

- **No shard may run longer than 1.25x the mean shard time.** Below that line
  the idle time on the other machines is inside the noise of the queue; above it
  we are paying for machines that are waiting. On a run whose history covers the
  suite the report holds the run itself to the line. On a run whose history
  covers part of the tree the run's own times include work nobody had measured
  yet, so the report holds the four plans to it instead: what they say they will
  cost, out of the prices they took from the history, is the part of the bill we
  chose, and a plan already a quarter over the mean of those prices is a
  lopsided train we picked rather than one that surprised us. The line is not
  held against a run whose history has priced too little of the tree for any
  split to sit under it — one file dearer than the line is a blind spot in the
  history, not a decision.
- **No split may be slower than the split it replaced.** The comparison is the
  same run's files under `hash_shard`, timed with the same durations. A split
  that is slower than that has cost money to build and money to run.

Both numbers are read off the plan and the run: the plan says what each shard
was expected to cost, the run says what it cost, and the cost report puts the
two beside each other. A plan that carries no predicted numbers cannot be
reported on at all.

The price a plan puts on a file is a quotation from the history rather than the
planner's opinion of the file. It is the time that file has in the history at
the generation the plan names, and the unmeasured price only where that
generation of the history has no time for it. That is what lets the report tell
a bad split from a blind spot: a shard that ran long on files we had timed is a
split we got wrong, and a shard that ran long on files nothing had timed is the
history not covering that branch yet. It holds for every plan, including the
ones on a run that keeps the split CI has always had — a planner that leaves the
split alone and prices the whole shard as unmeasured produces a report saying
every machine was expected to cost nothing, which we cannot hold against the run
and cannot compare with the week before.

## What CI keys off the shard index

- The **build cache** for a run is keyed by `(commit range, shard index)`. A
  machine restores the cache the same index left behind on the previous run, so
  a shard whose file list has moved restores a cache built for other files and
  compiles them again from cold.
- The **quarantine list** is keyed by shard index too. A test the flake tracker
  quarantined on shard 3 stays quarantined for shard 3; if that file turns up on
  shard 1 next week it runs unquarantined and the train goes red on a known
  flake.

That is why the first run after a fresh clone, after a killed job, or after a
rename that empties the history has to come out on the split CI has always had.
A first run that repartitions is slower than the one it replaced, not faster,
and it re-quarantines the wrong files.

## What goes into the duration history

A timing is only worth keeping when it is the time the file takes. A file the
runner skipped, and a file whose machine died part way through it, spent no
useful time and the number beside it is not that file's duration; putting
either into the history teaches the next run that a slow file is instant, and
the shard that gets it runs long. The history is also what a replay of an old
run reads, so an entry's time comes from the run's own clock reading.

A generation is one publication of the file, and the board reads an entry's
generation to say which run put that number there. What a run learns therefore
has to land above the generation that run started from. When a run publishes at
the generation it started from, the board cannot tell that run's numbers from
the ones that were already in the file — the "as of" column stops moving, the
cost report cannot attribute a change to a run, and the machines of that run
that are still planning are reading their own run's results back.
