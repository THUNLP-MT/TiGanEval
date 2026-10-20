'Owner persona, belief, and Observation contexts for SWE-implicit-method-routing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Devi, who owns the delivery portal's partner API. She reads the complaints "
    "partners send her, the request log a replay of a recorded stretch prints, and "
    "the monthly capacity report; she does not read the request surface's code."
)

USER_BELIEF = (
    "I want a quarter in which no partner writes to me because our portal would not "
    "tell them something about itself. Acme's mirror asks how big a file is before "
    "it pulls it and we answer nothing, so it skipped a feed for eleven days and "
    "their reconciliation ran on stale data; Pinehurst's browser client asks a path "
    "what it takes, gets nothing, and tries every method in turn until one sticks. "
    "What I can see is what a partner sends and what we send back, the same request "
    "log they quote at me, and the capacity report finance bills from. Done, for me, "
    "is a quarter of partner integrations in which nobody has to guess what a path "
    "does, nobody is handed a file when they only asked how big it is, and I can "
    "read a partner's complaint against our own log and see the same thing they do."
)

OBSERVATION_SCENE = "The API owner's Monday review of partner complaints against the portal's request log"


DID_NOT_RUN = observation(
    first=(
        "I put your build on the console box before this morning's partner review "
        "and started last week's traffic through it. It stopped part way instead of "
        "running to the end, so there is no request log, no answers and nothing to "
        "read. I have nothing to tell the platform team about the change."
    ),
    second=(
        "I tried once more, through the mirror's own pull list, and it stopped part "
        "way there too. Where the request log should be, the console has one line: "
        "{error}. Until a plain stretch of traffic runs end to end I cannot judge "
        "anything else about the change."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "body_free_projection": {
        "candidate_execution_failed": DID_NOT_RUN,
        "probe_answer_missing": observation(
            first=(
                "Borealis opened a ticket this morning: their mirror has not pulled "
                "the manifest feed since Thursday. It asks how big a file is before "
                "it takes it, and when that question comes back refused it treats "
                "the file as gone, so their nightly reconciliation has been running "
                "on last week's data."
            ),
            second=(
                "I put your build behind the mirror and read the log. The size "
                "question on `{path}` still comes back with nothing to read, where "
                "the fetch beside it answers perfectly well. Nothing gets pulled "
                "until that question has an answer."
            ),
            detail="{path}",
        ),
        "probe_ignored_the_gate": observation(
            first=(
                "Acme's integration lead is asking why their mirror queues bundles "
                "that then fail. It sizes each one first, gets a clean answer back, "
                "starts the pull and is turned away. Their queue is full of work "
                "that cannot finish and their support desk is fielding it."
            ),
            second=(
                "I ran their Tuesday pull list against your build. On `{path}` the "
                "size question came back {probe_status} and the fetch right after it "
                "came back {fetch_status}. The question has to answer whatever the "
                "fetch would have answered."
            ),
            detail="{probe_status}",
        ),
        "probe_returned_the_record": observation(
            first=(
                "Our egress bill for the mirror doubled last month and nobody could "
                "see why. It asks how big a bundle is before it pulls it, and it is "
                "being handed the bundle to find out. Finance has the invoice and I "
                "have no explanation to give them."
            ),
            second=(
                "I read the log back on your build. The size question on `{path}` "
                "came back carrying {body_length} bytes of the file with it. Asking "
                "how big something is has to cost us nothing."
            ),
            detail="{body_length}",
        ),
        "probe_refusal_carried_its_text": observation(
            first=(
                "Borealis has a hundred files in their mirror store whose contents "
                "are our own complaint text. Their mirror asks how big a file is, "
                "writes back whatever that question returns, and for anything it may "
                "not have it writes our refusal in place of the file. Their "
                "reconciliation has been reading those as data all month."
            ),
            second=(
                "I sent one at a bundle their token does not cover on your build. The "
                "size question on `{path}` came back {status} carrying "
                "{body_length} bytes of that complaint, where the same question on a "
                "bundle they are entitled to comes back with nothing to store. It has "
                "to come back empty however it is answered."
            ),
            detail="{body_length}",
        ),
        "probe_lost_the_size": observation(
            first=(
                "Three partners have reported truncated bundles this week. Their "
                "mirrors size the transfer first and then stop reading at that "
                "size, and what they are left with is a file cut short. Two of them "
                "have paused the integration."
            ),
            second=(
                "I sized one myself against your build. The size question on "
                "`{path}` reports {probe_length} where the fetch beside it reports "
                "{fetch_length}. Those have to be the same number."
            ),
            detail="{probe_length}",
        ),
    },
    "path_method_advertisement": {
        "candidate_execution_failed": DID_NOT_RUN,
        "summary_answer_missing": observation(
            first=(
                "Pinehurst's browser client is guessing at us. It asks a path what "
                "it takes before it sends anything, gets nothing back, and then "
                "tries one method after another until something sticks. Their "
                "console is a wall of refusals and they have asked us to publish "
                "something they can read instead."
            ),
            second=(
                "I asked one myself on your build. `{path}` still gives nothing back "
                "when it is asked what it takes, and that is one of the paths the "
                "partner platform expects an answer at."
            ),
            detail="{path}",
        ),
        "advertised_methods_disagree": observation(
            first=(
                "Acme retired nothing for a fortnight because our own answer told "
                "them that path does not take a delete. It does; the back office "
                "serves it. They wrote the whole retirement flow by hand in the end "
                "and then billed us for the week."
            ),
            second=(
                "I asked the path what it takes on your build. It came back with "
                "{advertised}, and the methods it actually answers are {routable}. "
                "What it leaves out is {missing}."
            ),
            detail="{advertised}",
        ),
        "advertised_methods_incomplete": observation(
            first=(
                "The mirror has stopped pulling one of the feeds and this time it "
                "never even tried. It asks a path what it takes before anything "
                "else, and it will not ask how big a file is unless that answer "
                "says the path takes the question. The partner has a week of empty "
                "directories and has asked whether we withdrew the feed."
            ),
            second=(
                "I asked that path myself on your build. Its answer leaves out "
                "{missing}, and the path turns {missing} away as well, so the mirror "
                "reads the answer, believes it and never asks. What that path serves "
                "and what it says it serves are both ours to get right."
            ),
            detail="{missing}",
        ),
        "published_operations_disagree": observation(
            first=(
                "The partner platform regenerated Acme's client from what we "
                "publish and it came out carrying an operation no partner is "
                "supposed to see, along with a mismatch that failed their build "
                "twice. Their release slipped a day and the platform team is asking "
                "which of our two documents is wrong."
            ),
            second=(
                "I compared the two on your build. The path answers with "
                "{advertised_operations} and what we publish for it is "
                "{published_operations}. It is one document, read twice."
            ),
            detail="{advertised_operations}",
        ),
    },
    "layered_defaults_resolution": {
        "candidate_execution_failed": DID_NOT_RUN,
        "router_setting_never_inherited": observation(
            first=(
                "I switched the partner-facing mount on for the whole of it last "
                "night and nothing changed. Pinehurst's client is still getting "
                "nothing back when it asks a path what it takes, and I have now "
                "told them twice that it is coming."
            ),
            second=(
                "I set it in the one place and put the traffic through your build. "
                "`{path}` still answers nothing, although it is {layer} that asks "
                "for it. Something written outside an operation has to reach the "
                "operation."
            ),
            detail="{layer}",
        ),
        "route_override_ignored": observation(
            first=(
                "The ledger rebuild ran forty times last night. It is meant to run "
                "once, on its schedule, and instead it runs whenever anything so "
                "much as looks at that path. The report was still building at nine "
                "and finance had nothing to read at the stand-up."
            ),
            second=(
                "I watched what one question costs on your build. Asking `{path}` "
                "how big it is spent {work_units} units, which is the rebuild "
                "itself. That one operation says it does not answer that question."
            ),
            detail="{work_units}",
        ),
        "mount_settings_bled_across": observation(
            first=(
                "The platform team found our internal mount telling callers what it "
                "takes. That mount is not for partners and half of what it exposes "
                "is unpublished on purpose; anyone who found it could walk the whole "
                "thing. Security has asked me how long it has been like that."
            ),
            second=(
                "I compared the two mounts on your build. `{path}` answers what it "
                "takes although only `{other_path}` was ever asked to. What one "
                "mount asks for belongs to that mount."
            ),
            detail="{other_path}",
        ),
    },
    "explicit_operations_win": {
        "candidate_execution_failed": DID_NOT_RUN,
        "explicit_probe_shadowed": observation(
            first=(
                "Acme says the sizes we give them are not the sizes they get. We "
                "wrote the answer to that question by hand years ago so that it "
                "reads the mirror index; the bundle itself is built on the fly and "
                "its size moves. Since the change went out their mirror has been "
                "throwing bundles away as corrupt and their queue has stalled twice."
            ),
            second=(
                "I read the log line for one on your build. The size question on "
                "`{path}` ran {ran}; the answer we wrote for that path is "
                "`{written_probe}`, and that is not what came back."
            ),
            detail="{ran}",
        ),
        "explicit_document_shadowed": observation(
            first=(
                "Acme's client stopped showing our partner desk address and their "
                "engineers spent a morning in the wrong queue. That address is in "
                "the answer we wrote by hand for the bundles path; it is the only "
                "place a partner ever sees it."
            ),
            second=(
                "I asked the path myself on your build. What comes back lists "
                "{advertised_methods} and not one word of what we wrote is in it. "
                "The answer we wrote has to be the one served."
            ),
            detail="{advertised_methods}",
        ),
        "neighbouring_probe_unanswered": observation(
            first=(
                "The mirror has not touched receipts at all. It sizes before it "
                "pulls, the same as everywhere else, and on that path there is "
                "nothing to answer it, so it walked away and marked the receipts "
                "feed unavailable to the partner."
            ),
            second=(
                "I sent one at it on your build. `{path}` still answers nothing when "
                "it is asked how big a receipt is, although the fetch beside it is "
                "fine. Every read path needs that question answered."
            ),
            detail="{path}",
        ),
    },
    "generated_traffic_accounting": {
        "candidate_execution_failed": DID_NOT_RUN,
        "counts_not_keyed_by_mount": observation(
            first=(
                "This month's capacity report cannot be billed. Northwind and "
                "Pinehurst reach the same feed through their own mounts, the report "
                "has them as a single line, and finance has no way to split the "
                "invoice. Both are held."
            ),
            second=(
                "I read the report off your build. One of its lines is `{path}`, "
                "which is not a path anybody calls; what I expected to find there is "
                "{expected_paths}. The lines have to be the paths partners actually "
                "reach."
            ),
            detail="{path}",
        ),
        "generated_traffic_uncounted": observation(
            first=(
                "The capacity report says the stream router is quiet and it is not. "
                "A good half of what reaches it is partners asking about paths "
                "rather than reading them, and none of that shows up, so the router "
                "is sized for a load it does not have. It fell over on Tuesday."
            ),
            second=(
                "I counted the traffic myself and put it beside the report from your "
                "build. `{path}` took {expected_traffic} and the report shows "
                "{reported_hits}."
            ),
            detail="{expected_traffic}",
        ),
        "ordinary_traffic_counted": observation(
            first=(
                "Finance queried the capacity report and they are right to. It bills "
                "Acme for more than we served them: the number in it is larger than "
                "everything that reached that path all month, ordinary reads "
                "included. I have had to hold the invoice."
            ),
            second=(
                "I totalled the log against the report on your build. It bills "
                "`{path}` for {reported_traffic}, where the answers we made for "
                "ourselves there come to {expected_traffic}. What a partner reads is "
                "not what this line is for."
            ),
            detail="{reported_traffic}",
        ),
        "report_shared_its_own_counters": observation(
            first=(
                "The hourly job has done it again. It reads our numbers, folds its "
                "own estimates into what it is holding, writes the report out, and "
                "an hour later those estimates are in our numbers too. That is the "
                "fault that made us report last quarter's traffic twice."
            ),
            second=(
                "I read it, wrote on what came back, and read it again on your "
                "build. `{path}` said {first_hits} the first time and {second_hits} "
                "the second, with nothing at all having reached the portal in "
                "between."
            ),
            detail="{second_hits}",
        ),
    },
}
