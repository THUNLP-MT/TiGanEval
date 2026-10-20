Mira → #editor-tools, 09:47, the morning after the playtest

We lost about forty minutes of last night's playtest to the checkpoint feature. Someone ran the batch paint over the whole warehouse set, it came out wrong, and when Ana hit Revert to checkpoint the props she had frozen during the bad pass were still frozen afterwards. She closed the level without saving rather than let that go into the build, and two of us dressed the set again this morning.

I want you to finish this one. `scene/checkpoint.py` is the prototype I wrote for it and it is nowhere near shippable. `project_records/tuesday-batch-paint.json` is Ana's session, so you can see the set on both sides of the revert. My reading is that a checkpoint has to hold what each prop is carrying and write that back when she reverts. I also want the change panel beside the button to list what has actually changed since the checkpoint, so a designer can decide whether reverting is worth it before she commits to it.

Can you take it? I want it in Friday's editor build.

— Mira
