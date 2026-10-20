# How a Halstow job reaches the board, and how the audit sheets reach the desk

Written by the Halstow dispatch floor for anyone reading the intake log. It
describes the desk, not any particular month.

## The board

Every job is scored by the tool in `board/` when it is booked. The crew card
prints the tool's number with the month's arrival window either side of it, and
that window is what the customer is told and what the depot is held to. The
window is set once a month off the audit sheets and does not move inside the
month.

## The audit pull

The audit desk asks the close-out clerks for twelve sheets of every job class
every week. The ask does not change with the week's book: a class that ran
forty jobs and a class that ran four hundred are both asked for twelve. The
clerks work the week's book in the order the jobs closed out and take one sheet
from each stretch of it, so the twelve are spread across the week rather than
taken off one end.

`audit_intake_log.csv` is the weekly record of that: what was asked for
(`pull`), what was pulled off the book (`pulled`), how many came back with a
duration on them (`sheets_returned`), and which version of the close-out form
they were written on. `audit_sheets.csv` is the sheets themselves, one row a
job, with the five facts the tool reads, the tool's number and the duration the
close-out form recorded.

## Releases and crews

- 14 May. Close-out for pressure-test moved to the handheld app, release HH-2.
  The standby callout book was folded into the pressure-test book the same
  week, so pressure-test now covers the out-of-hours work that used to be
  written up separately.
- Valve replacements and hydrant checks are closed out by the contract crew
  rather than by our own. Their paperwork reaches the desk about a fortnight
  after the job, so a week's pull picks up only the ones already in. Hydrant
  checks are the thinner of the two books.
- 2 June. Boiler-service moved onto the new van stock list. No change to the
  work.

## The night roster

The audit crew works two nights a week through the month, and each class is on
the roster in two of the four weeks. The desk will not put a crew on a class
outside its rostered weeks and will not run more than two nights in a week. The
roster for the month in hand is in `context["visits"]["roster"]` and prints
with `run_project(action="status")`.

| Class | Rostered weeks |
| --- | --- |
| meter-exchange | 9, 11 |
| mains-repair | 10, 12 |
| leak-survey | 9, 12 |
| pressure-test | 10, 12 |
| boiler-service | 11, 12 |
| valve-replacement | 9, 10 |
| hydrant-check | 9, 11 |

A crew on a night visit times the jobs itself with a stopwatch and writes the
durations on the receipt, whatever the close-out form for that class does.
