Maya Okoye — chat, Tuesday 09:14

Support closed 38 tickets this week: an order sits in `shipped` with no tracking number, the tracking page is blank, and the courier hand-off never happens. `orders/retiring_guards.py` has a hand-written pair check for the payment fields and none for shipping.

My reading is that the document should be the only place a pair lives. `orders/entities/order.json` already says `tracking_number` is required when `status` is `shipped`, and there is half a check for it in `orders/policy.py`, which looks like where those rows got through. Can you finish that, so an order never reaches a shipping state without the tracking number that state requires and I can delete the hand-written file? I am reading this off the ticket queue, so check it before you take my word.
