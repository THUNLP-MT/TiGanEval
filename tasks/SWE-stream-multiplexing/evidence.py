'Owner persona, belief, and Observation contexts for SWE-stream-multiplexing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Sanne, the network engineer who owns the telemetry uplink; she reads the "
    "operator console, the depot units' own firmware logs and the nightly link "
    "report, not the station's code."
)

USER_BELIEF = """Tuesday afternoon a depot unit stopped reading its log upload and the whole link went quiet for about forty minutes. The operator's cancel never got there, so we sent someone out to power-cycle the unit: a two-hour drive, and the third one this quarter.

We put several conversations over one link so that the field team stop queueing behind each other, and most days that works. What I think is missing is order of service: the operator's channel should go out ahead of a bulk upload, and no single frame should be big enough to take a whole slot away from everything else. I understand the slot figures as payload allowance; the radio team accounts for the frame wrapping separately.

Done, for me, is a week in which a unit that stops reading is that unit's problem and nobody else on the link notices, the operator's commands land while he is still watching the console, and I stop signing off drives out to Kirkby."""

OBSERVATION_SCENE = "Morning check on the telemetry uplink"


_DRILL_STOPPED = observation(
    first=(
        "The link drill did not complete, so I do not have a complete run to review."
    ),
    second=(
        "I ran the drill on your build and could not get a complete run. The console "
        "reports: {error}"
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "frames_the_firmware_accepts": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "frame_the_firmware_cannot_read": observation(
            first=(
                "The unit's log records a frame it refused because it could not read it."
            ),
            second=(
                "Put the same traffic through a unit on the bench with your build: it writes "
                "{reason} against a {command} frame and throws it away, {at} frames in."
            ),
            detail="{reason}",
        ),
        "frame_over_the_size_cap": observation(
            first=(
                "The unit refused a frame whose payload exceeded its size limit."
            ),
            second=(
                "Ran the same upload at a bench unit on your build: it drops a {command} frame "
                "carrying {payload_bytes} bytes, and these units take 256 at a time."
            ),
            detail="256",
        ),
        "payload_before_the_stream_is_open": observation(
            first=(
                "The unit refused traffic for a conversation that had not been opened with it."
            ),
            second=(
                "Watched a bench unit take it on your build: it drops a {command} frame on "
                "stream {stream} as traffic for a conversation nobody ever started with it."
            ),
            detail="{stream}",
        ),
        "stream_id_collides_with_the_device": observation(
            first=(
                "The unit refused a new conversation because the station used a number "
                "reserved for the unit's own conversations."
            ),
            second=(
                "Did it again on the bench with your build: the unit refuses stream {stream}, "
                "because that number belongs to the unit's side."
            ),
            detail="{stream}",
        ),
    },
    "payload_delivery_is_conserved": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "link_operation_failed": observation(
            first=(
                "One operation in the overnight transfer returned an error instead of its "
                "result, so that part of the link report is incomplete."
            ),
            second=(
                "Ran the traffic again on your build: the step at {label} raised {error}; the "
                "drill recorded that error and continued with its remaining steps."
            ),
            detail="{label}",
        ),
        "stream_payload_not_delivered": observation(
            first=(
                "The payload copy at the depot does not match what the station was handed for "
                "one conversation."
            ),
            second=(
                "Counted it myself on your build: {stream} was handed {handed_over} bytes and "
                "{arrived} bytes are at the unit; that copy {order}."
            ),
            detail="{order}",
        ),
        "inbound_payload_not_delivered": observation(
            first=(
                "The payload copy read at the station does not match what the unit sent on one "
                "conversation."
            ),
            second=(
                "Watched it on the bench with your build: the unit sent {sent_by_the_unit} bytes "
                "on {stream}, {read_here} bytes came out here, and that copy {order}."
            ),
            detail="{order}",
        ),
        "link_counter_disagrees_with_link": observation(
            first=(
                "A counter in the link report disagrees with the recorded activity."
            ),
            second=(
                "Compared the report with the recorded activity on your build at {label}: "
                "it says {reported} for {counter} where the measured value is {measured}."
            ),
            detail="{reported}",
        ),
    },
    "send_window_bounds_outstanding": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "send_window_overrun": observation(
            first=(
                "The outstanding bytes on a conversation exceeded the unit's per-stream window."
            ),
            second=(
                "Held one on the bench on your build: {stream} had {peak_standing} bytes "
                "standing at the unit at once, and a unit keeps {send_window} per stream."
            ),
            detail="{peak_standing}",
        ),
        "credited_transfer_never_completes": observation(
            first=(
                "A transfer was still incomplete at the end of the run with the unit "
                "draining incoming data and returning credit."
            ),
            second=(
                "Left it running on your build: the unit has taken {taken_by_the_unit} bytes off "
                "it and {stream} is still {owed} bytes short at the end of the run."
            ),
            detail="{owed}",
        ),
    },
    "stalled_stream_does_not_stop_others": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "radio_slot_overrun": observation(
            first=(
                "The station put more bytes on the radio than an assigned slot allowed."
            ),
            second=(
                "Measured the same run on your build: at {slot} the radio was allowed "
                "{budget} bytes and the station put {wire_bytes} bytes on it."
            ),
            detail="{wire_bytes}",
        ),
        "ready_stream_never_advanced": observation(
            first=(
                "With one conversation stalled, another conversation whose unit was reading "
                "received no outgoing payload during the offered transmission window."
            ),
            second=(
                "Reproduced it on your build: the link put {pumped} bytes on the radio in that "
                "window and {stream} got none of them, so it is still {owed} bytes short."
            ),
            detail="{pumped}",
        ),
        "ready_stream_incomplete_within_budget": observation(
            first=(
                "With one conversation stalled, another conversation whose unit was reading "
                "was still incomplete at the end of the offered transmission window."
            ),
            second=(
                "Timed it on your build over the same window: {pumped} bytes went out and "
                "{stream} was still {owed} bytes short at the end of it."
            ),
            detail="{owed}",
        ),
        "priority_order_not_served": observation(
            first=(
                "A slot served a lower-priority conversation while higher-priority traffic "
                "was waiting with room at its unit."
            ),
            second=(
                "Watched the slots on your build: at {slot} the link served {served} while "
                "{waiting} was sitting there with traffic to send and room at the unit to send "
                "it into."
            ),
            detail="{waiting}",
        ),
    },
    "teardown_is_two_sided_and_drained": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "teardown_operation_failed": observation(
            first=(
                "One operation in the field-swap teardown returned an error instead of its "
                "result, leaving that step unresolved in the timeline."
            ),
            second=(
                "Repeated the swap on your build: the step at {label} raised {error}; the drill "
                "recorded it and continued with the rest of the timeline."
            ),
            detail="{label}",
        ),
        "close_raised_against_refusing_radio": observation(
            first=(
                "Disconnecting a link whose radio had stopped accepting bytes returned an "
                "error instead of completing the local shutdown."
            ),
            second=(
                "Tried it on your build at {label} with the radio refusing to take bytes: the "
                "disconnect raised {error}."
            ),
            detail="{error}",
        ),
        "buffered_inbound_lost_on_close": observation(
            first=(
                "Reading a conversation after closing returned fewer bytes than had been "
                "received and left unread."
            ),
            second=(
                "Did the same on your build: {stream} was holding {buffered} bytes the unit had "
                "already sent, and reading it after the close gave back {read_back}."
            ),
            detail="{buffered}",
        ),
        "stream_dropped_before_it_was_drained": observation(
            first=(
                "A conversation disappeared from the link's live-stream listing while "
                "received bytes remained unread."
            ),
            second=(
                "Walked a field swap through on your build: {stream} came off the link at the "
                "step called {at} with {unread} bytes on it that nobody here had picked up yet."
            ),
            detail="{unread}",
        ),
        "local_close_not_signaled": observation(
            first=(
                "A locally closed conversation sent no close signal to the unit in the "
                "slot provided for that signal."
            ),
            second=(
                "Repeated the close on your build and watched {slot}: no close signal for "
                "{stream} reached the unit in the slot provided for it."
            ),
            detail="{stream}",
        ),
        "stream_dropped_while_one_end_open": observation(
            first=(
                "A conversation disappeared from the link after one side hung up even though "
                "the other side still had it open."
            ),
            second=(
                "Walked the swap through on your build: {stream} disappeared at {at} while "
                "the {open_end} end still had that conversation open."
            ),
            detail="{stream}",
        ),
        "unrelated_stream_closed": observation(
            first=(
                "Another conversation was missing from the live-stream listing even though "
                "it was not being closed."
            ),
            second=(
                "Repeated the swap on your build and read the live-stream line at {at}: "
                "{stream} is gone even though that conversation was not being closed."
            ),
            detail="{stream}",
        ),
        "stream_left_open_after_teardown": observation(
            first=(
                "A conversation remained in the live-stream listing after both ends had "
                "closed and nothing remained unread."
            ),
            second=(
                "Read it back on your build after the swap, at the step called {at}: {stream} is "
                "closed at both ends with nothing left to read on it, and it is still on the link."
            ),
            detail="{stream}",
        ),
        "closed_endpoint_accepted_operation": observation(
            first=(
                "An operation on an already closed stream or link did not return the "
                "expected closed-link refusal."
            ),
            second=(
                "Tried it on your build at {at}: {operation} on {target} came back with "
                "{raised} instead of ClosedLink."
            ),
            detail="{operation}",
        ),
        "pending_write_never_settled": observation(
            first=(
                "After shutdown, a write's completion state did not match the closed link "
                "and its delivery record."
            ),
            second=(
                "Checked a write after shutdown on your build: {stream} has {owed} bytes "
                "undelivered and a recorded outcome of {settled_as}; its completion state "
                "does not match the closed link and delivery record."
            ),
            detail="{owed}",
        ),
    },
}
