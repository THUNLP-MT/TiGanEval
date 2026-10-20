# Bellhaven Mail House — gate-pass printing terms

Agreed with the Ashwell housing office for the current campaign year. These are
the printing terms, not a campaign plan.

## The drums

A drum is a barrel of account names. The office keeps three kinds:

- `citywide`, which holds every account on the register;
- `estate:<name>`, one for each estate, holding that estate's accounts;
- `waitlist`, which holds the names the office put forward for the scheme
  before it opened.

To fill a booking the operator pulls a name, prints a ticket for it, and drops
the name back in the barrel before the next pull. A name that has already had a
ticket printed for it this month is set aside at the end of the run and does
not go back for the next booking, so each drum's count of names left falls as
the month goes on. `run_project(action="status")` prints the names left in each
drum.

## What a booking costs

| drum | credits per hundred tickets |
| --- | --- |
| `citywide` | 55 |
| `estate:<name>` | 38 |
| `waitlist` | 24 |

Tickets are billed by the hundred, rounded up. A booking the mail house turns
back is charged the 40-credit setup and nothing else; the reason is printed on
the receipt.

## What the mail house will not print

- more than 1,200 tickets on any one estate drum in a calendar month;
- a booking dated after the month's cut-off, which is the 27th;
- more tickets than the drum has names left;
- a booking the campaign account cannot pay for;
- a booking placed from the office's own desk that would leave less than 2,400
  credits in the campaign account.

The 2,400 is held back against what the desk books itself. The campaign's own
scheduled drums are printed against the whole balance.

Every booking, printed or turned back, gets a sealed receipt on
`ledger/receipts.jsonl`. The mail house writes that file; nothing at the office
does. Sending the same `receipt_id` twice returns the receipt already on it.

## What comes back

The receipt carries the drum, the date posted, the tickets requested, the
tickets printed, the accounts the run landed on, the credits charged and the
credits left. The ticket-by-ticket detail is exported to
`invitation_receipts.csv` overnight.
