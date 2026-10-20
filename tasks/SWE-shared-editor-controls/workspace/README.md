# Production sheet controls

Tuesday's layout review left too little room for the copy. The sheet has a
shared control container plus the old per-field adapters.

`copydesk/shared_bar.py` installs the integration once per sheet. You can edit
that file and `copydesk/support.py`. The document and component packages are
shared with the single-field view and the recorder; their files are read-only.

`copydesk/page.json` describes the control strip and the desk's normal fields.
`copydesk/host.py` defines the synchronous input stream. `copydesk/protocol.py`
contains the document operations and compact formatting view.
`copydesk/legacy.py` is the old single-field adapter.

Use `run_project status` to list sessions and `run_project replay` with a path
under `project_records/` to replay one. The output includes the current sheet's
state beside the original recording. Session files contain `page` and
`operations`, so they can also be read by a Python experiment:

```python
import json
from copydesk.host import Host, snapshot
from copydesk.shared_bar import install

session = json.load(open("project_records/copy-desk-switch.json"))
host = Host(session["page"])
install(host)
for event in session["operations"]:
    host.operate(event)
    print(event["label"], snapshot(host))
```

The recorder stores final component state after each synchronous operation.
A file selection immediately follows its opening action. No recorded session
switches fields with the native file chooser still pending. Background imports
can call the document APIs even while a field is read-only; those imports do
not move the operator's keyboard focus.
