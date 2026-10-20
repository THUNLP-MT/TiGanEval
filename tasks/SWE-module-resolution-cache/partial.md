I own the scripting runtime the nightly pricing queue runs on — can you take this one?

Finance has queried the August kit licence invoice: the desk billed us 41 checks against 11 kit files. `ops/nightly-runbook.md` has the numbers and I have to answer for the other 30. `runtime/loader.py` brings a kit up again on every `use`, which is where I think the money goes; replay `project_records/nightly-2026-08-19.json` and you will see it.

Please make it hold on to what it has brought up, keyed on the path the job handed us, so a second `use` costs nothing. And while you are in there: the cron passes `--trace` and nothing comes of it. Make it tell us what it loaded.
