Post-mortem action item 3, 2.4.0 — yours to pick up. I ran that publish myself.

The upload host turned away the first two files the build handed over, both with a 503. The job dropped them, published the other two, and the release page went out short; I put the missing pair up by hand at eleven that night. Replay `project_records/2.4.0-partial.json` and you will have the whole of it in front of you.

So: what I want out of this is `publish/uploader.py` going back to a file the host turns away instead of dropping it. My reading is that the `retry` block in `release.toml`, sitting there unread since March, is most of the answer. And put every try into the attempts block while you are in there — that count is what I take to the vendor.
