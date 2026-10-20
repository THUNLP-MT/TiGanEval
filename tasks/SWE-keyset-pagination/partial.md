Elif from the mobile team — writing this to you rather than raising it at standup again.

Our infinite scroll shows people the same product twice, and since Tuesday's restock support has taken thirty tickets about products that stayed on sale but never appeared during a complete scroll, despite being visible on the storefront under the same sort. Replay `project_records/restock-mid-scroll.json` against `listing/pages.py` and you can watch both.

I think the endpoint is counting rows: merchandising inserts while somebody scrolls, so the fortieth row is a different row by the next request. Can you make `find` hand back a nextCursor instead — the last product's id, packed so clients cannot pick it apart? The app already sends the sort again on every request, so I assumed the token would not need to repeat it. The `cursor` argument is already there and half works. Please leave `listing/protocol.py` alone; the storefront ships the same file.

When you have it, I will run that record again, and what I want back is a scroll where every product comes down the screen once.
