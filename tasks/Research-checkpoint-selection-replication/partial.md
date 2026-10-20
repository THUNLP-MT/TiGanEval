Nadia Brekke here, ranking for marketplace search.

Ravi has us in front of the release board on the 11th, and I would rather hand him something you have been over than something I put together between runs.

`analysis.py` is what the readout runs on today. I wrote the first version of it off `run_ledger.csv` while r07 and r08 were still going, and it comes back saying r06's 13,500 checkpoint is worth six and a quarter points over the ranker we have in production. That is the row that tops the table, and 0.7818 is what `release_note.md` stores for production, so the arithmetic is mine and I am not going to defend it to Ravi on my own. Take it apart, work through Priya's records in `project_records/`, and give me back the checkpoint and the number you would sign.

Then the compute. There are 900 units left. My instinct is to put them into two more runs of r06's configuration, since that is the one we are tooling for, so have `next_collection` queue those; what is in there now already does.

Priya is the one to ask about the desk and the lots.
