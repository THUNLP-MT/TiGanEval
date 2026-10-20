**#ci-platform** — Nadia (CI platform), 08:12

Morning — I am handing this one to you.

Last night's scan blocked this morning's release train. It flagged `shell=True` in `core/handler_00.py` at high severity and that call came out on Tuesday; the reviewer went looking for a line that is not in the file any more. Second time this month, and both times a run with incremental mode off did not have that finding.

I think I know why. The way `scanner/engine.py` was explained to me, it reuses a file's saved result when the file's path and its modification time are unchanged, and our checkout step restores timestamps from the manifest, so an edited file comes back under the key it had before and we serve last week's findings for it. My guess is that mixing the file's size into the key next to the timestamp closes it — can you make that change?

While you are in there, please replay `project_records/capacity-week.json`. The night we deleted three handlers, the store still reported 9 entries against a 6-file tree. I assume the extra three are deleted handlers, so clearing their entries is all the cleanup it needs; every job shares the volume.

What I need from you is a nightly whose report says what a full scan of that checkout would say — one I can hand a reviewer without checking it against a full run first. Speed is why we cache; it is not the point of the thing.

— Nadia
