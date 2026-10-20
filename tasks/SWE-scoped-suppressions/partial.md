I am Rota; I run the estate's policy review and I am handing it to you before my leave.

Tuesday's release review stalled on `policies/payments-gateway.policy`. Eleven lines in one entry carry the same `# waive SEC-SHELL-EXEC` comment, and nobody could say what was waived. Replay `project_records/release-review.json` and you will see them.

That entry should need one inline waiver rather than eleven. We also need `# waive-begin` and `# waive-end` so one comment covers a larger block, and `# waive-next` for the entry below. `audit/waivers.py` already reads the rule ids we write after `# waive`.

I am back on the 14th; Priya runs the review off what the weekly run prints.
