Audit finding PRV-114

The privacy office ran their own pass on Tuesday and found an export we ship nightly that hands a subject's email out. Ours had nothing on it: `lineage/tracer.py` goes by what the names inside the export call look like. Three teams read that clean report as proof.

Can you make it follow the field instead? My guess is we mark the locals a personal field is assigned into, then flag an export that mentions one of them. `warehouse.write_rows` and `notify.publish` are the calls that put data outside the company.

Whatever you change, `project_records/audit-baseline.json` stays green: the gate fails the release on those rows.

Rhea, security engineering
