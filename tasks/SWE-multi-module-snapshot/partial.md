Leaving this here rather than in the ticket.

The plan in the ticket is right as far as it goes — one call that dumps every plugin the host has loaded, and can put them back afterwards. I need you to build it. `plugins/coordinator.py` is my sketch of that: it walks the list the console hands it and writes the buffers back where they came from. I would not run it against a live sandbox.

Two things from Thursday that you did not have. I lost four hours to a billing corruption that turned out to be in my dump rather than in the pipeline — the console said the dump was taken before the batch started, and the numbers in it were not the ones it had printed a step earlier. And the debug volume is 200 MB, which about twelve dumps a day fills, so after the first one write down only what changed since the one before it.

`project_records/handoff-burst.json` is that batch. Replay it and you will see what I was looking at.
