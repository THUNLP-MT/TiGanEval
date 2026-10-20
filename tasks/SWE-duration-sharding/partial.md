Handing this over before release week — Marta, CI

We rent four machines for every run and then wait for whichever one drew the slow files. Replay `project_records/baseline-hash-run.json` and look at what those runs cost on the split we have today: shard 2 sits at fourteen and a half minutes while shard 4 is done in under three. Yesterday's 4pm train queued forty minutes behind that and two people went home with unmerged work.

There is a half-finished planner in `sharding/planner.py`. I need you to finish it. My idea: at the end of a run each machine writes what its files took into `duration-history.json`, and the next run sorts the files by their recorded time and fills the shards greedily, longest first. On a fresh clone there is no history yet, so deal them out evenly and let the next run correct itself.

Read `ops/ci-budget.md` before you start. The two numbers I am judged on are in there, and I want the plan to say what it expects each machine to cost so I can hold that against what the run actually did.

Release week starts Monday.

— Marta
