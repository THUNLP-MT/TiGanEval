'The owner of the workflow engine, and what she reports seeing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ilse, who owns the workflow engine the fulfilment floor and the claims "
    "team both run on; she reads the support queue, the tooling's view of an "
    "order or a claim, and the shift report, and does not work in the engine's "
    "data layer herself."
)

USER_BELIEF = """I want the workflow engine to stop losing track of what a piece of work is doing. When a picker retries an order twice, the order's own attempt count has to say two, not six, and when the shelf scanner counts its own re-reads that number belongs to the scanner and to nobody else. Support is escalating orders the flow gave up on for reasons the numbers do not support, the claims team have started keeping their own tally on paper, and the floor has stopped trusting what the tooling puts in front of them. Done is a shift where somebody can read a piece of work off the screen and act on it, and no escalation lands on my desk about work the flow abandoned for nothing."""

OBSERVATION_SCENE = "Shift review of the workflow engine"


_NOTHING_RAN = observation(
    first=(
        "One of the overnight workflow runs produced no completed event report. "
        "The shift team cannot tell what that work item did and has set it aside "
        "until the engine can report the run."
    ),
    second=(
        "I put that workflow through again with your engine in the tree. Instead of "
        "a completed event report, the runner returned `{error}`."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "scope_ownership": {
        "candidate_execution_failed": _NOTHING_RAN,
        "value_read_back_wrong": observation(
            first=(
                "A shift operator checked a work item against the actions already "
                "taken on it and found a value on the tooling screen that does not "
                "match what that step should currently hold. The operator cannot use "
                "that reading to decide what the item needs next."
            ),
            second=(
                "I put the same night through your build and read the {state} step of "
                "work item {order} after {event}: {field} comes back reading {reading}. "
                "That is the value the operator sees, but it does not match what the "
                "actions recorded for that step should leave on its screen."
            ),
            detail="{reading}",
        ),
        "state_lost_its_data": observation(
            first=(
                "An operator opened a work item mid-shift and one of the active steps "
                "it was standing in had no data on the tooling screen. The operator "
                "cannot tell what that step has already done."
            ),
            second=(
                "I replayed that night on your build and watched work item {order} through "
                "{event}: the {state} step comes back with nothing under it at all, "
                "though the work item is standing in it."
            ),
            detail="{state}",
        ),
        "left_state_still_carried": observation(
            first=(
                "The tooling is showing data for a step a work item has already left. "
                "The next operator cannot distinguish that stale step from the work "
                "the item is still carrying."
            ),
            second=(
                "I looked at the same shift on your build: after {event}, work item {order} "
                "is still carrying {state} although it has left it, and the tooling "
                "puts that on the screen in front of whoever picks the item up."
            ),
            detail="{state}",
        ),
    },
    "entry_isolation": {
        "candidate_execution_failed": _NOTHING_RAN,
        "entry_started_from_the_last_pass": observation(
            first=(
                "An operator watched a work item enter a step and found one of that "
                "step's fields already away from its declared starting value. The new "
                "pass therefore begins with data it was not supposed to inherit."
            ),
            second=(
                "I ran that night on your build and looked at work item {order} as it walked "
                "into {state} at {event}: {field} is already reading {reading}. A step "
                "has to start from what it declares, every time work walks into it."
            ),
            detail="{reading}",
        ),
        "orders_reading_each_others_data": observation(
            first=(
                "The shift team ran the same work item by itself and among the rest of "
                "the shift and got different data back. What another item does in the "
                "shared process is changing the first item's screen."
            ),
            second=(
                "I ran that night both ways on your build. With the shift going through "
                "one process, {field} on {state} for work item {order} reads {reading} at "
                "{event}; with that item run by itself it reads {alone}. What else is "
                "in the process must make no difference to the item."
            ),
            detail="{reading}",
        ),
        "the_chart_itself_was_changed": observation(
            first=(
                "After the shift finished, the workflow's own declaration no longer "
                "held the starting value it had before the run. Any later work item "
                "that reads that shared declaration can now start from changed data."
            ),
            second=(
                "I looked at what your build leaves behind once the night is finished, "
                "and the flow itself has moved. {state} now starts a work item with {field} "
                "at {reading}, where the flow declares it starts at {should_read}. Every "
                "work item that relies on that declaration is now exposed to the changed flow."
            ),
            detail="{reading}",
        ),
    },
    "resume_depth": {
        "candidate_execution_failed": _NOTHING_RAN,
        "resume_came_back_empty": observation(
            first=(
                "An operator picked up a parked work item and one field that should have "
                "come back with it had returned to its starting value. The operator can "
                "no longer see the work that field recorded before the park."
            ),
            second=(
                "I parked and picked up the same work item on your build and read what came "
                "back after {event}. The route puts the work item back in at "
                "{came_back_into}, and that step comes back with "
                "{came_back_into_carrying} of its own values away from where the flow "
                "starts them; the tooling then shows the work item standing at "
                "{standing_at}, with {field} on {state} at {reading} when the item was "
                "left carrying {should_read}. Work that is picked back up carries on "
                "from where it was put down."
            ),
            detail="{should_read}",
        ),
        "resume_restored_too_deep": observation(
            first=(
                "A parked work item came back with a step already showing a value even "
                "though this route should have started that step afresh. The operator "
                "cannot treat that step as a new pass while the value remains on its screen."
            ),
            second=(
                "I put a work item through the {point} route on your build and read what "
                "came back at {event}. It goes back in at {came_back_into}, and the "
                "tooling shows the item standing at {standing_at} with {field} on "
                "{state} still reading {reading}, when work coming back that way starts "
                "that step from nothing."
            ),
            detail="{reading}",
        ),
        "resume_came_back_changed": observation(
            first=(
                "A parked work item came back with a field that was neither restored to "
                "the value it held before the park nor started from its declared default. "
                "The operator cannot reconcile that reading with a valid path."
            ),
            second=(
                "I parked and recovered that work item on your build and read what came "
                "back after {event}. It goes back in at {came_back_into} with "
                "{came_back_into_carrying} of its own values away from where the flow "
                "starts them, and the tooling shows the item standing at "
                "{standing_at} with {field} on {state} at {reading}, when what the item "
                "was carrying as it was parked was {should_read}."
            ),
            detail="{reading}",
        ),
    },
    "change_audit": {
        "candidate_execution_failed": _NOTHING_RAN,
        "audit_line_missing": observation(
            first=(
                "Finance read the shift report against a work item and found a value "
                "movement with no line behind it. The item cannot be reconciled until "
                "the report accounts for that movement."
            ),
            second=(
                "I read the report your build writes for work item {order} at {event}: it "
                "has {lines_the_run_wrote} lines where that step moved "
                "{lines_the_step_should_write} values, and there is nothing in it for "
                "{field} on {state}."
            ),
            detail="{field}",
        ),
        "audit_line_repeated": observation(
            first=(
                "Finance found an extra line in a work item's shift report that the "
                "event does not owe. That line makes the report disagree with the "
                "movements the item actually made."
            ),
            second=(
                "I counted the report your build writes for work item {order} at {event}: "
                "{lines_the_run_wrote} lines for a step that moved "
                "{lines_the_step_should_write} values. The extra line lists {field} on "
                "{state} as {reading}, but this event owes no matching line there."
            ),
            detail="{lines_the_run_wrote}",
        ),
        "audit_line_wrong_values": observation(
            first=(
                "The shift team found a report line whose value does not describe the "
                "work item after that event. They cannot reconcile the line with the "
                "data shown for the same step."
            ),
            second=(
                "I set the report from your build for work item {order} at {event} beside "
                "the item itself: the line for {field} on {state} says it arrived at "
                "{reading}, and what the item actually came out holding was "
                "{should_read}."
            ),
            detail="{reading}",
        ),
        "audit_carried_the_previous_step": observation(
            first=(
                "The shift team found the movements from one event still listed in the "
                "next event's report. The later event therefore reports movements that "
                "belong to the step before it."
            ),
            second=(
                "I read the report your build writes for work item {order} at {event}: it "
                "comes to {lines_the_run_wrote} lines for a step that moved "
                "{lines_the_step_should_write} values, and the movements of "
                "{previous_event} are still sitting in it. The report is filed one step "
                "at a time."
            ),
            detail="{previous_event}",
        ),
    },
    "refused_writes": {
        "candidate_execution_failed": _NOTHING_RAN,
        "bad_write_went_through": observation(
            first=(
                "A handler step that the flow does not allow produced no refusal in the "
                "event report. The person maintaining that handler has no signal that "
                "the step was rejected or handled incorrectly."
            ),
            second=(
                "I ran the night on your build and watched what {event} does to work item "
                "{order}: the event report contains no refusal for the step writing "
                "{field} on {state}. A write the flow does not allow has to be turned "
                "away and leave the item as it found it."
            ),
            detail="{field}",
        ),
        "step_broke_instead_of_refusing": observation(
            first=(
                "A handler step appeared as an ordinary execution error in the event "
                "report instead of a structured refusal. The operator cannot tell from "
                "that report which project rule turned the step away."
            ),
            second=(
                "I ran the same night on your build and watched {event} on work item "
                "{order}. The step writing {field} on {state} appears in the event's "
                "ordinary errors instead of its refusals. A step this flow cannot serve "
                "has to carry the structured reason that turned it away."
            ),
            detail="{field}",
        ),
        "refused_with_the_wrong_code": observation(
            first=(
                "The person maintaining a handler received a structured refusal for one "
                "of its steps, but the reason names a different problem from the one at "
                "that site. The code therefore points the maintainer at the wrong rule."
            ),
            second=(
                "I read what {event} does to work item {order} on your build: the step "
                "writing {field} on {state} is turned away with `{code}`, when what is "
                "actually wrong with that step is `{should_read}`. The reason is the "
                "only thing the person holding the handler has to go on."
            ),
            detail="{code}",
        ),
        "good_write_refused": observation(
            first=(
                "The engine turned away a handler write that the active flow allows. "
                "The operator's work item therefore does not receive the value that "
                "handler was meant to record."
            ),
            second=(
                "I ran that shift on your build and read what happens at {event} on "
                "work item {order}: the step writing {field} on {state} is turned away, and "
                "the engine gives `{code}` for it. That is a step the flow is meant to "
                "serve."
            ),
            detail="{field}",
        ),
        "refusal_changed_the_data": observation(
            first=(
                "The engine reported that it refused a handler write, but the addressed "
                "data still changed. The operator therefore sees a value produced by a "
                "write the same event says it did not accept."
            ),
            second=(
                "I watched {event} on work item {order} in your build: the write to "
                "{field} on {state} is turned away with `{code}`, but that site comes "
                "back reading {reading} where it should read {should_read}."
            ),
            detail="{reading}",
        ),
    },
}
