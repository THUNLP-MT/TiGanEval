Anneke here, ops. I am handing this to you off the audit that closed on Friday.

The auditor pulled six nights out of the offsite vault and opened all six on her own laptop without asking us for anything. Sealing came off the host with the old archiver when the filer went in, so everything the job has put offsite since the move is a plain `.sql.gz`, and `orders` is the job she sampled. The finding is written up against us with a remediation date at the end of the month.

What I want is the dump sealed before it leaves the host, with the archive key configured for that host, and both `nearline` and `offsite` still getting the night. This host uses `ARCHIVE_KEY`; some of the copied hosts use the key-file configuration described with the job. `nightly/pipeline.py` is the job as it stands: it compresses the dump, puts it in both, and that is all it does.

The one thing I will not trade away is the drill. Rob picks a night out of the window every quarter and works through the runbook with it, and whatever you change he has to be able to open whichever night he picks — the nights from either side of the move included, since they are all still in the window.

Can you have something I can look at this week?
