Subject: catalogue load — stop reloading from zero when it dies

Twice in the last fortnight the nightly catalogue load died part way through: the feed dropped mid-stream both times, and one restart lost a warehouse commit as well. Both mornings the fix was the same — wait for upstream to republish, then load the next export from row 0 at nine with the warehouse tied up — because `loader/importer.py` still reads every row and writes them in one transaction.

I need you to make this a load nobody babysits: it finishes on its own, and the warehouse then holds what the export says, restart or no restart. A three o'clock death should mean a five-past restart that carries on, not a full reload at nine.

My plan: read the export in batches, commit every 25 rows, and record where we got to so the next run resumes from there. The scheduler already chooses the file for each attempt; from my side the checkpoint is just the row number the restart should pick up from. `checkpoint_interval` is already on `ImportConfig` with 25 as its default and nothing uses it. Batch size is what the warehouse team keeps asking about — how long we hold a transaction open while their morning reports queue behind us.

Please leave `loader/protocol.py` alone: the warehouse side and the feed client are built against it and ship it with their release. `loader/support.py` is empty and yours.

`project_records/` has the four nights this job has had, two of which died; replay the interrupted one with `run_project` and show me that night ending on its own.

— Priya, data platform
