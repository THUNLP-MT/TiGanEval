# Nightly queue runbook

On-call notes for the analytics fleet's nightly pricing queue. Operational
facts, kept up to date by whoever is on the rota.

## Licence desk

The kit vendor bills us per licence check, and a check is raised when a kit file
finishes coming up. Finance signed off a clean night as one check per kit file
the run brings up; the August invoice was queried because the desk billed 41
checks against 11 kit files, and nobody could say what the other 30 were for.

## Worker settings

Kit paths are typed in per worker by hand. The two that are live tonight, copied
out of the worker records verbatim:

```text
night-1   kit_path=/opt/kits-legacy:/srv/kits
night-2   kit_path= "/opt/kits-legacy/" : /srv/kits/ : /opt/kits
```

night-2's entry was retyped during the shared-directory rollout. Both workers
are meant to be pricing the same night against the same kits, and the release
stamp on their output is the same stamp, so the audit cannot tell two nights
apart if they are not.

`/opt/kits-legacy` is still listed while the migration finishes. It holds an
older copy of some kits, so a kit that is in both directories exists twice with
two different bodies.

## Piloting a kit

When a team wants to change a shared kit they put a copy of it in one job's own
folder and run that job for a few nights before the change goes into the shared
directory. `/srv/runs/pilot` has one in it at the moment. The nightly folder
also carries a pinned market list of its own, which the queue's own jobs use and
the shared kits are not supposed to.

## Dispatch order

The queue hands jobs out as workers free up, so the order changes night to
night. The monthly audit diffs what two nights ended with, entry for entry. It
sorts both catalogs by key before it compares them, because the order entries
were published in follows whichever job the queue handed out first, and then it
raises anything that moved. It also puts the two nights' run reports side by
side and compares the list of kits each worker says it held, line for line and
as the worker wrote it.

## Logs

The console captures each job's own runtime stream into that job's log file, one
file per job, and that is what support reads when finance asks which job pulled
a stale kit into last night's prices. Anything a worker writes to the process
console instead is interleaved across the jobs on that worker and attributed to
none of them; we keep it only as a crash dump.

When a job is asked to talk, support reads its log against what the job did.
Every `use` that job made leaves the line for the lookup and then one more: the
line for bringing that file up, or the line for handing back one the worker was
already holding. A log short of either is a job we cannot follow through, which
is where August left us.

## Cron

```text
runtime-worker --queue nightly --job {job} --trace
```

The `--trace` on the cron line is ours; some workers also carry `trace` in their
own settings, which the platform team owns. The two are set by different people
and neither team tells the other when it changes.
