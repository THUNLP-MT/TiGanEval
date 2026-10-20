Handing the settlement fleet over before I go on leave — this part is yours now.

Since we scaled the settlement workers to three replicas our partner has been settling the same instruction twice. Tuesday cost their finance team an afternoon of reversals and they have asked us in writing to stop.

Please make `partner-settlement` one worker's job at a time in `dispatch/assignment.py`: while one worker has the class no other one gets its jobs, and when that worker's link drops the next one picks it up. `JobClassSpec` in `dispatch/protocol.py` has an `exclusive` flag the scheduler has never looked at.

Replay `project_records/handover-drill.json` when you have it and show me one worker per settlement.

— Meera, fleet operations
