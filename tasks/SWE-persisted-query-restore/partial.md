Handing the restore work over to you -- I am on the depot integration from Monday.

Three tickets this week, all the same shape. A crew member force-quits the handset with the depot's red bar on a job, opens it again at the next stop, and the bar has gone. The screen comes back looking like a clean load, so they send the reading twice. `project_records/reopen-after-decline.json` is one of those; replay it and watch the bar go.

I got as far as a prototype in `handset/persister.py`: `restore_one` reads the saved copy off the device and hands back `state["data"]` alone, so the rows come back and nothing else does. I need you to finish it and give the crew the whole saved screen. When you hand it back I want to replay that record and see the bar still up.
