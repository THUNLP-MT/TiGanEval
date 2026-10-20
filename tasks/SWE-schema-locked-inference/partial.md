SUP-2318 — escalated to you: one customer, two different scores

**Case 1.** A customer read one score in the app and another on the statement the nightly batch produced, same week. I re-ran `project_records/serving-requests.json` and got the same split: the full row the warehouse sends comes back as 111.848175389, and the shorter payload the app posts for that same customer comes back as 107.811191867. We cannot tell that customer which number is theirs.

**Case 2.** A record that reached us with no amount on it at all still came back with a number, 102.636255505. It is in `project_records/bad-request-drill.json`. Support had quoted it before anyone noticed there was nothing on it to score.

My guess — I only read the note at the top — is that the app posts fewer fields than the warehouse row, and the trained model itself fills omitted fields with a fallback it learned during training. `pipeline/pipeline.py` says a column a caller does not send is "read as an absent cell and encoded like any other value."

I need you to make a scoring ticket answerable: one customer record means one score however it reaches us, and a record we cannot honestly score comes back as a rejected request instead of a number my team has to defend. When it is done, re-run those two records and tell me what they print: one number for that customer whichever way it arrives, and a rejection where 102.636255505 is now.

— Dani, support lead
