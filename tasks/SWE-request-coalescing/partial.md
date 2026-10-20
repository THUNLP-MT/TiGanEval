Halima (backend lead), 16:55

Friday's invoice run took the summary backend down and checkout with it: a row of desks all asked for invoice-2291 inside a couple of seconds and we hammered the backend with a rendering for each of them.

I started the in-flight table in relay/sharing.py that afternoon and never finished it. The idea is simple enough — when several desks are asking for the same thing at the same moment, run it once and hand all of them that summary.

Can you pick it up and finish it? project_records/invoice-run-spike.json is that Friday — I want those fourteen desks coming out of it served, with one rendering behind the lot of them.
