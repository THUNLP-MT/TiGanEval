# Estate policy audit

`audit/` reads a service policy document and produces the report the estate
review works from: what is open, and what somebody waived.

- `audit/contract.py` ships with the estate release and is the same file on
  every platform, so it stays as it is. It owns the document model
  (`parse_document`, `Line`, `Unit`, `unit_span`, `unit_of_line`,
  `next_unit_after`), the rule table with the id and the name of each rule,
  `PROFILES` and `enabled_rules`, `resolve_selector`, the detector
  `baseline_findings`, and the `Report` and `Counters` the review signs off.
- `audit/waivers.py` is ours: `build_report(document, profile)`.
- `audit/shared.py` is empty and ours too.

## The estate

`policies/` holds the documents the weekly run reads. Every platform team
writes its own, and the exporter that produces them changed in March: it now
writes list values as items on their own lines where it used to write short
ones inside brackets on the key line. `ledger-sync.february.policy` and
`ledger-sync.march.policy` are the same policy either side of that change.

A reviewer silences a finding by writing `# waive` on the line the audit
reports it at, with rule ids or rule names after it. Reviewers have also
started writing `# waive-begin`, `# waive-end` and `# waive-next` by hand
ahead of the change, and `policies/checkout-web.policy` and
`policies/legacy-invoicer.policy` carry some; nothing reads them today.

## Operations notes

- The weekly report is the open list every platform team is asked to act on.
- An open finding names the entry a team has to fix. The line beside it is
  where the value happens to be written in this export, which is why the
  review reads the list entry by entry and asks teams to answer for entries.
- `reconciliation.json` is the sheet the security review signed off last
  quarter: for each document, how many findings the rule table objects to,
  the three numbers the review accepted for it, and the count it accepted for
  the run with `Profile.ignore_waivers` set. The review works through that
  sheet document by document, which is why the numbers are kept rather than
  recomputed.
- `PROFILES` is which rules a run has switched on. The weekly run is
  `release`. The platforms finance is retiring are read under `hardening`,
  which the estate cut down to the `SEC-` rules when the retirement plan was
  agreed, so `legacy-invoicer.policy` is scanned with a smaller table than
  the rest.
- Rule ids are typed by hand into policy documents by whoever writes the
  waiver, and nobody checks them at commit time.

## Recorded reviews

`project_records/` holds four review sessions the estate replays before a
change to the audit goes out.

- `run_project(action="status")` lists the audit files, the policy documents
  with each unit's path and line span, what the rule table objects to in each,
  and the four sessions.
- `run_project(action="replay", record="project_records/<name>.json")` runs
  one session against the current workspace on copied files and prints, for
  every document it read: the profile, whether waivers were ignored, what the
  rule table objects to, what the report came back with, the three counters,
  and the numbers the last review signed off for that document.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can read any document through
  `audit.contract` and `audit.waivers` yourself.
