'Owner persona, belief, and Observation contexts for SWE-layered-policy-merge.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Idris, the platform engineer who owns the ingress policy layer; he reads the "
    "push log, the plan a route ends up serving, the per-pod request counts on "
    "the edge dashboard and what support and the other teams send him, not the "
    "plane's code."
)

USER_BELIEF = """Since checkout went from two pods to six, support has been closing abandoned-cart tickets all day, and every one I trace is the same shopper hitting a different pod half way through. The storefront already sends everything you would need to recognise a shopper; the plane just does not use it.

What I want is for a shopper to stay on one pod for as long as they are checking out, and for the teams who write these policy files to get out of them what they wrote. Joana tried laying the checkout policy over the fleet one key by key and giving the proxy the result; the layering makes sense to me, but the counts through her push were no better than before.

Before a policy set goes out we push it across the estate on the drill box and watch the counts, so what I have to go on is the push log, the plan each route ends up serving, and where the traffic went. Done, for me, is a week where support has nothing to send me and both the platform's policy and the route teams' policies are still doing what they say on the file."""

OBSERVATION_SCENE = "Morning on the ingress platform"


_PUSH_STOPPED = observation(
    first=(
        "The rehearsal push stopped part way through last night, so there is no push log "
        "to go through this morning and nobody can say what the plane would have done "
        "with the routes it never reached."
    ),
    second=(
        "I ran the same push on your build myself and it stops there too. The log holds "
        "one line where the rest of the run should be: {error}"
    ),
    detail="{error}",
)

_PUSH_RAISED = observation(
    first=(
        "One push came back as an error instead of a plan and the run stopped on it, so "
        "half the estate never got looked at. A plane that raises in the middle of a "
        "reconcile is the worst thing this change could do to us."
    ),
    second=(
        "Ran it again on your build and it stops at the same place, on {route}, with the "
        "plane raising instead of answering: {error}"
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "merged_plan_matches_the_policies": {
        "candidate_execution_failed": _PUSH_STOPPED,
        "edge_operation_failed": _PUSH_RAISED,
        "plan_refused_by_proxy": observation(
            first=(
                "I pushed the new policy set and the dashboard did not move. Nothing failed "
                "on our side, but the routes are splitting sessions exactly the way they "
                "were, so as far as anyone using the storefront is concerned nothing "
                "happened at all."
            ),
            second=(
                "Went back through the push log on your build: {route} never took the new "
                "plan and is still serving the {still_serving} lines it had before. The "
                "proxy did give a reason for turning it away: {refusal}"
            ),
            detail="{refusal}",
        ),
        "inherited_entry_dropped": observation(
            first=(
                "The platform's own policy stopped counting for anything. We keep a tenant "
                "on one set of pods across the estate, and after the push that tenant's "
                "traffic was spread over every pod on the route; their cache hit rate "
                "halved and they noticed before we did."
            ),
            second=(
                "Held the plan up against the attached files on {route}: nothing from "
                "{policy} came through, and the {pin_kind} line for {key} is not in what "
                "the proxy took."
            ),
            detail="{key}",
        ),
        "entry_not_in_any_policy": observation(
            first=(
                "There is a line in the plan the proxy took that nobody wrote. Whatever it "
                "pins on, no team can point at the file it came out of, and that is not "
                "something I can put in front of a change review."
            ),
            second=(
                "Read the plan back against the attached files on {route}: it pins on the "
                "{pin_kind} {key}, which is in none of the policies on that route."
            ),
            detail="{key}",
        ),
        "entries_out_of_precedence_order": observation(
            first=(
                "All of the attached policies reached the route, but their blocks are in a "
                "different precedence order from the one the control plane publishes. A "
                "lower-ranked block is being walked before a block that should precede it."
            ),
            second=(
                "Put the plan and the two files side by side on {route}: {policy} gets its "
                "{key} in ahead of {should_follow}, although their policy blocks rank the "
                "other way round."
            ),
            detail="{should_follow}",
        ),
    },
    "each_key_pins_once": {
        "candidate_execution_failed": _PUSH_STOPPED,
        "edge_operation_failed": _PUSH_RAISED,
        "key_pins_twice": observation(
            first=(
                "Somebody tidied a policy file, adding a line that was already in it and "
                "changing nothing else, and the next push moved practically every session "
                "on that route. An edit that changes nothing should not relocate live "
                "traffic."
            ),
            second=(
                "Counted the lines the proxy took on {route}: it pins on the {pin_kind} "
                "{key} {times} times over, spelt {spellings}, so every request folds that "
                "one value in more than once."
            ),
            detail="{spellings}",
        ),
        "lower_precedence_definition_kept": observation(
            first=(
                "Two attached policies define the same pin key, and the proxy received the "
                "definition from the one that loses their published precedence comparison. "
                "The winning policy's setting never reached the edge."
            ),
            second=(
                "Read back what the proxy took for {key} on {route}: it carries {kept} "
                "from the lower-ranked definition where {policy}, which wins precedence, "
                "asks for {wanted}."
            ),
            detail="{kept}",
        ),
        "authored_definition_changed": observation(
            first=(
                "A pin line reached the proxy with a setting that none of the attached "
                "policies wrote. The teams can point to what is in their files and to what "
                "went out, and the two are not the same setting."
            ),
            second=(
                "Read back what the proxy took for {key} on {route}: it carries {kept} "
                "where {policy} asks for {wanted}, and no attached policy carries the "
                "setting the proxy received."
            ),
            detail="{kept}",
        ),
        "key_never_pins": observation(
            first=(
                "The plan the proxy took has nothing in it for the value the route team "
                "pins on, so the route is spreading sessions the way it did before anyone "
                "wrote a policy at all, and carts are still being dropped mid-checkout."
            ),
            second=(
                "Looked at what {route} is serving on your build: there is no {pin_kind} "
                "line for {key} anywhere in it, and {policy} names it."
            ),
            detail="{key}",
        ),
    },
    "pinning_survives_a_repush": {
        "candidate_execution_failed": _PUSH_STOPPED,
        "edge_operation_failed": _PUSH_RAISED,
        "plan_depends_on_reconcile_order": observation(
            first=(
                "The controller restarted at four this morning, nothing else changed "
                "anywhere, and by five support had a wave of dropped baskets. The policies "
                "are the same files they were the night before; the only thing that moved "
                "is the plane."
            ),
            second=(
                "Pushed the same two files twice on your build, once in each order, and got "
                "two different plans on {route}: the second comes back with {line} in a "
                "place the first one does not have it."
            ),
            detail="{line}",
        ),
        "plan_depends_on_authoring_order": observation(
            first=(
                "A relabel went through the estate overnight. The files were rewritten with "
                "their lists in a different order and not one value in them changed, and "
                "sessions moved on routes nobody had touched. A cosmetic edit is not "
                "supposed to be visible to a shopper."
            ),
            second=(
                "Rewrote one file's lists the other way round and pushed again on your "
                "build: {route} comes back with {line} in a place it was not in before, and "
                "the shoppers move with it."
            ),
            detail="{line}",
        ),
        "plan_depends_on_process_start": observation(
            first=(
                "The controller restarted, the same files were pushed again, and the route "
                "came back with a different plan. Nothing in the policies changed, but "
                "live sessions moved as soon as the new process reconciled them."
            ),
            second=(
                "Restarted the controller around the same push on your build: {route} came "
                "back with {line} in a place it did not occupy before the restart."
            ),
            detail="{line}",
        ),
        "shopper_moved_by_repush": observation(
            first=(
                "Two pushes of the same policy set, and between them a good part of the "
                "route's traffic changed pod. Every one of those is a basket that lost its "
                "session for a reason nobody can point at."
            ),
            second=(
                "Replayed the same hour after both pushes on your build: {moved} of {total} "
                "shoppers changed pod on {route}, {shopper} among them, from {earlier_pod} "
                "to {pod}."
            ),
            detail="{shopper}",
        ),
    },
    "opt_out_clears_inherited_pinning": {
        "candidate_execution_failed": _PUSH_STOPPED,
        "edge_operation_failed": _PUSH_RAISED,
        "inherited_pinning_survives_opt_out": observation(
            first=(
                "The data team turned pinning off on their export route months ago, because "
                "the whole job comes from one office address and pinning drops it onto a "
                "single pod. After the push it was back on one pod, that pod's queue backed "
                "up, and the export missed its window."
            ),
            second=(
                "Ran the export again on your build: {busiest_share} of {requests} requests "
                "went to {busiest_pod}, and {route} is still serving a {pin_kind} line for "
                "{key} that the policy switching it off should have cleared."
            ),
            detail="{busiest_pod}",
        ),
        "contradictory_policy_reached_proxy": observation(
            first=(
                "The quarter-end policy made it all the way to the proxy before being "
                "turned away. The route kept its old plan, but the control plane did not "
                "stop a document it cannot apply, so the push failed at the last component."
            ),
            second=(
                "Read both sides of the push log on your build: {policy} on {route} reached "
                "the proxy, which turned it away with {refusal}."
            ),
            detail="{refusal}",
        ),
        "contradictory_policy_half_applied": observation(
            first=(
                "A policy that turns pinning off and also sets a pin went out with the "
                "quarter-end batch, and the export bunched back onto one pod overnight. It "
                "is a file nobody can read two ways at once, and it went through and "
                "changed what the route serves."
            ),
            second=(
                "Traced it on your build: the push of {policy} on {route} was applied and "
                "moved the route off the plan it had, and the export after it put "
                "{busiest_share} of {requests} requests on {busiest_pod}."
            ),
            detail="{policy}",
        ),
        "contradictory_policy_accepted": observation(
            first=(
                "The push log says applied against a policy that contradicts itself. Nobody "
                "can tell me what that route is serving now without going and reading it "
                "off the proxy, which is the position the admission check exists to keep us "
                "out of."
            ),
            second=(
                "Checked the push log on your build: {policy} on {route} is recorded as "
                "applied, and it is a file the plane cannot apply as it is written."
            ),
            detail="{policy}",
        ),
    },
    "pin_key_matches_the_reference": {
        "candidate_execution_failed": _PUSH_STOPPED,
        "edge_operation_failed": _PUSH_RAISED,
        "absent_value_folded": observation(
            first=(
                "Guest checkout fell over during the promotion. Everyone who arrived without "
                "signing in ended up on the same pod, that pod ran out of connections, and "
                "the ones who had signed in were fine, so it took an hour to see what the "
                "two groups had in common."
            ),
            second=(
                "Replayed the promotion hour on your build and took one anonymous basket "
                "apart: {request} on {route} contributes {reported} for {key}, which that "
                "request does not carry at all."
            ),
            detail="{reported}",
        ),
        "rewritten_value_not_used": observation(
            first=(
                "A shopper moves pod every few minutes on a long checkout, and it follows "
                "the storefront's token refresh exactly. The value the route pins on is not "
                "the same string twice in a row, and there is a line in the policy file "
                "about precisely that which is doing nothing."
            ),
            second=(
                "Followed one basket through two refreshes on your build: {request} on "
                "{route} folds {reported}, where the file asks for {expected}."
            ),
            detail="{reported}",
        ),
        "stop_ignored": observation(
            first=(
                "Signed-in guests are being spread across the pods when they should be held "
                "by who they are. That route was written so a signed-in shopper is decided "
                "by their id and nothing after it, and something after it is still being "
                "taken into account."
            ),
            second=(
                "Walked one signed-in basket through on your build: after {key} on {route} "
                "it goes on to fold {reported}, so anything that changes later in the "
                "session moves them."
            ),
            detail="{reported}",
        ),
        "pin_part_wrong": observation(
            first=(
                "Support sent me one basket that changed pod twice in ten minutes and asked "
                "me why. I put that request next to the policy file the route team owns and "
                "could not make the two line up at all, so the shopper got an apology and no "
                "answer."
            ),
            second=(
                "Took one request apart on your build: {request} on {route} folds "
                "{reported} where the contract gives {expected}."
            ),
            detail="{expected}",
        ),
        "cookie_ttl_not_normalised": observation(
            first=(
                "The cookie the proxy sets on one route is going out with the wrong "
                "lifetime, so the browser drops the cart early and the shopper comes back to "
                "an empty basket. Half the estate writes that lifetime one way and half the "
                "other, and both spellings are committed today."
            ),
            second=(
                "Read the cookie line the proxy would set on {route}: {key} goes out with "
                "{reported} where the file's lifetime comes to {expected} seconds."
            ),
            detail="{reported}",
        ),
        "cookie_line_wrong": observation(
            first=(
                "The plan carries the cookie settings the route team wrote, but the cookie "
                "line sent to the browser does not carry those same settings. Shoppers are "
                "therefore losing carts outside the lifetime and path the team reviewed."
            ),
            second=(
                "Rendered the cookie on your build for {route}: {key} goes out as "
                "{reported}, while the proxy contract renders that served step as "
                "{expected}."
            ),
            detail="{reported}",
        ),
        "request_sent_to_wrong_pod": observation(
            first=(
                "The dashboard's chosen pod does not match the ring result for the pin "
                "parts the same request produced. The plan can look right while the "
                "shopper still lands somewhere else."
            ),
            second=(
                "Replayed {request} on {route}: your build sent it to {reported}, while the "
                "proxy's ring puts those recorded pin parts on {expected}."
            ),
            detail="{request}",
        ),
    },
}
