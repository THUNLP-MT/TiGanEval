Anders Kolbe, reliability lead on EM-9. Leaving this on your change rather than in the tracker: the review sits on the 26th and I am at the fab until the 23rd.

March closed on the 24th and the review needs one number out of it — the hours before a module loses a tenth of its output, at the drive and case we specify. `analysis.py` gives me 4,509. I put that file together myself off `project_records/soak_traces.csv` while R-B was still running, and 4,509 is where loss against log hours reaches a tenth. It clears the 3,000 on the datasheet by half again, and nobody on the bench believes this family is that good.

Take the file apart, work through Nils's notes in `project_records/`, and give me back the number you would put your own name to.

Then the fourteen chamber-days in `chamber_plan.md`. I would spend them on more ports at 1.7 A, because that is where the loss actually shows, so have `next_block` send Nils there. It already does.

Nils is the one to ask about the racks and the loggers. He is a long way ahead of me on both.
