Leaving this on my plan for the change rather than on the ticket: better we agree the shape before you start. I own `relay/vault.py`, and I need you to rebuild the store in it.

Tuesday's crawl signed in forty-one times, the portal rate-limited us at 03:12, and the 06:00 export went out two days short. `vault.py` replays a grant only on a request back to the exact URL that handed it over, so the moment the vendor moves us onto the records subhost we are anonymous again. Replay `project_records/nightly-vendor-sweep.json` and you will see it.

Build one dict per site instead: key it by the site suffix, fill it from every `Grant-Set` a reply carries, and send it whole wherever the host ends with that suffix.

`relay/wire.py` ships with the other collectors; leave it be.

When you have it, I want to run a night's sweep through your build and read a request log I can take to the vendor.
