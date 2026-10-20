Hand-over note before leave — Sanne Voss, uplink

I am out for three weeks from Friday; I need you to finish the multiplexing work on `link/session.py`.

Tuesday the unit at Kirkby stopped reading its log upload and the whole link went quiet for forty minutes; the operator's cancel never got there and we drove out to power-cycle it. You can watch it in `project_records/tuesday-link-silence.json`.

We already tag every chunk with a stream id, and the operator's channel is already opened high — you can see that on the same drill. What I think is missing is order of service: its frames should go out ahead of an upload's, and no frame should be bigger than `max_frame_size`. The slot figures in the drill are payload allowance; the radio team accounts for the frame wrapping separately. `link/protocol.py` is what the depot firmware implements, so leave that one alone.

I want to leave the depot team a link that stays up.
