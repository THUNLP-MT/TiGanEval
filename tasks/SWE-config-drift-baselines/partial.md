Subject: the nightly configuration check

I need you to make `estate/reconcile.py` into something we can run every night against every environment.

Two things happened this year. In June somebody moved `web-api` in staging onto a hand-built image and nobody found out until a rollback pulled that build back in front of customers for twenty minutes. Then on the night of the London rack move the shell script we had said every service in staging had changed, because the hosts came back reporting their settings in another order, and the duty operator stopped opening it. `project_records/reboot-night.json` is that pair of nights. The collector also sometimes comes back without a setting it normally reports. That silence is not a confirmed change, so I would not expect it by itself to make either the morning list or the Monday number worse.

What I want out of this is a record we can audit, with a seven-in-the-morning queue where the duty operator can work down every newly detected item without losing the acknowledged and ignored decisions behind it, and one compliance number per environment that I can take to the Monday review. The comparison in the tree is roughly what I mean already -- walk the declaration we captured, report the services that no longer match it -- it is just not something she can work from yet, and it is not careful about that ordering.

`estate/protocol.py` is the same file in every region's release, so leave that one where it is.

Marek
