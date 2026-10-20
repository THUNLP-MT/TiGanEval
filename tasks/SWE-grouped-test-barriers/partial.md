Tuesday we found out the handover suite has never tested a handover. North-a works through the whole case, north-b is never driven at all, and `project_records/swap-north-bench.json` is the session we have called green since April. The firmware drop is three weeks out.

I am Dilara; I run the lab. I have read down the change, and since you are the one taking it on, here is the part that matters to me.

Ravi's plan, which I half believe: every phone stops at a named point and waits for the others before going on. His sketch is `harness/rendezvous.py`. What I need from you is a bench's phones working a case together — `lab_devices.json` now says which bench a handset is on — and each run knowing which handset it drives. When you are done I want to watch a night where north-a and north-b are both live inside that case at the same moment.
