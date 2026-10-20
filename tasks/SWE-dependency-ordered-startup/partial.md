Action item 2 out of Tuesday's 08:00 deploy review, and it is yours.

The cutover window is five minutes wide. We finished a minute and a half outside it and the traffic switch slipped with us. `bootstrap/startup.py` starts one service, waits for it, starts the next, and three services in that morning's manifest sit on their handshake for a minute or more each. That boot is `project_records/morning-cold-start.json`; the elapsed ticks the console prints beside `deploy_window_ticks` are the number this review is about. I need you to take that start-up and get the next cutover inside the window.

Bram wrote a plan out on the bridge call. Work out how deep each service sits under the things it is built on, bring each depth up together, never let more than `max_parallel_starts` connect at once because the warehouse counts our in-flight connections, and if one of them blows up, hand the lot to `shutdown_all` and raise, so the deploy stops somewhere we can see it rather than half up.

I half believe him. The last deploy that came apart on its own left the warehouse holding something nobody could account for, and I would rather not do that to them twice. When you have it, show me that morning's manifest coming up inside the window.
