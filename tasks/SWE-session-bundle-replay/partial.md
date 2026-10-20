SUP-2291 is yours. Everything under this line is my note.

I am Rafa, on the support desk. What I need from you is a console that records a session into one file and opens that file back up here, so that when a customer's figure is questioned I can rebuild the number myself.

Why now: the Halberd clinic disputed a figure we had signed off, and by the time the ticket reached me their analyst had closed the console. No notebook, one screenshot, four hours of my afternoon and nothing to tell them.

Dana started `bundle/recorder.py` and `bundle/replay.py` before she moved teams. The recorder hangs off the console already and puts a line per cell in the file it writes. Please run `project_records/analysis-handoff.json` back through and read the console log that comes out, because that is what the recorder makes of a session today.

Security want one thing settled before a file like that goes to a customer: our upload tokens must not be in it anywhere. A string replace over the recorded code, for whatever patterns get handed to `start`, ought to cover it.

Tell me when you have it and I will record a session on this desk and read the file that comes out.
