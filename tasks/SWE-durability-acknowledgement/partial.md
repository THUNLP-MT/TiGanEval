Dennis Aluko · storage, write path · 09:12

At 03:14 on Tuesday c-7 restarted and writes we had already told the replicas were safe were not in the log after recovery. We rebuilt the replica set and were down 26 minutes.

Can you take the ack path off guesswork for me? I left a prototype in `engine/durability.py`: it calls the listener at the end of apply, remembers that sequence number, and `wait_for_durability(seq)` comes back once the number has got there. Finish it so the number the ack path reads is the log's rather than the memtable's, and so nothing goes out to the replicas before the device has actually taken it. I took the 200ms sleep out when I put that prototype in, so whatever it says now is what the client hears.

To me the feed callback and `wait_for_durability` are two views of the same acknowledgement. If their released sequence numbers agree with recovery, I expect the two sides to be telling the same story.

`project_records/ack-path-incident.json` is Tuesday's traffic. Replay that against your build and show me the released sequence numbers matching what recovery would return.

`engine/protocol.py` ships with the storage release, so leave that one where it is.
