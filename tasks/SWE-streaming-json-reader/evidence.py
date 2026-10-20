'Owner persona, belief, and Observation contexts for SWE-streaming-json-reader.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Marta, who runs the collector that pulls each site gateway's readings feed "
    "into the readings store; she reads the collector's run log, the reading "
    "counts per site, and the recorded response traces she can replay, and she "
    "does not work in the client's code."
)

USER_BELIEF = (
    "I run the collector that polls each site's gateway for its readings feed "
    "and writes what comes back into the readings store. I want a collector "
    "that can pull a feed of any size without the container running out of "
    "memory, and that stores exactly the readings the gateway sent, in the "
    "order it sent them. When a gateway sends us something we cannot read, I "
    "want the collector to say so and fail that site's pull rather than store "
    "half of it and call the cycle a success. Billing invoices off these "
    "readings and the operations dashboard says which sites are reporting, so "
    "a wrong or missing reading costs us far more than a late one. Done looks "
    "like a week of cycles where every site lands complete or is reported as a "
    "bad fetch, and nothing needs reconciling in the morning."
)

OBSERVATION_SCENE = "Collection cycle review"


_DID_NOT_RUN = observation(
    first=(
        "This delivery did not produce a usable collection result, so I have "
        "no response-level trace or readings to compare with the gateways."
    ),
    second=(
        "I ran the collector's response checks again this morning. The runner "
        "reported `{error}`, and the checks ended without a usable result for "
        "me to compare."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "chunking_invariant_value_stream": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "iteration_raised_unexpectedly": observation(
            first=(
                "One site's pull failed while the collector was iterating a "
                "response that the gateway produced as an ordinary readings "
                "feed. The pull did not complete, so billing cannot use it."
            ),
            second=(
                "I re-ran the packet sweep this morning. The first response it "
                "stops on is {situation}, and that body is byte for byte what "
                "the gateway sent us."
            ),
            detail="{situation}",
        ),
        "values_differ_from_reference": observation(
            first=(
                "An ordinary gateway pull completed, but the readings handed to "
                "the store did not match the gateway's own copy. Billing cannot "
                "use values that differ from what the site reported."
            ),
            second=(
                "I put that feed back through the packet sweep at {packet_sizes} "
                "byte packets. At every one of them the reader {observed}, so how "
                "the network breaks the body up is not what is doing it."
            ),
            detail="{observed}",
        ),
        "chunk_split_changes_values": observation(
            first=(
                "The packet sweep handed the same response bytes over in "
                "different packet sizes and the runs produced different "
                "readings. The gateway body did not change, so the collector's "
                "result is depending on transport chunking."
            ),
            second=(
                "I put that feed back through the packet sweep with your reader "
                "in the tree. It gives me {distinct_record_sequences} different "
                "sets of readings out of {situation}, so what we store depends on "
                "how the network happened to break the body up that night."
            ),
            detail="{situation}",
        ),
    },
    "explicit_framing_rejection": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "unsupported_media_type_accepted": observation(
            first=(
                "The collector accepted a response whose media type is not one "
                "the gateways publish readings in and treated its body as a "
                "feed. Billing cannot use a pull whose response type should "
                "have been refused."
            ),
            second=(
                "I put the framing catalogue back through this morning. Your "
                "reader {observed}, and that is not a media type any gateway "
                "publishes readings in."
            ),
            detail="{observed}",
        ),
        "truncated_body_accepted": observation(
            first=(
                "A site's response ended before its JSON framing was complete, "
                "but the collector still reported the pull as clean. We can no "
                "longer tell an incomplete response from a complete cycle."
            ),
            second=(
                "I replayed that site's bad responses against your build. It "
                "{observed}. A response that did not arrive whole has to stop "
                "that site's pull, not hand us a short one that billing then "
                "invoices from."
            ),
            detail="{observed}",
        ),
        "trailing_data_accepted": observation(
            first=(
                "A gateway response had data where its JSON document or framed "
                "record permits none, but the collector still reported the pull "
                "as clean. Even plausible readings from that response cannot "
                "establish that the transfer was intact."
            ),
            second=(
                "I looked at what that gateway now sends. Your reader {observed}; "
                "a body containing extra data where its framing permits none has "
                "to fail the pull."
            ),
            detail="{observed}",
        ),
        "malformed_document_accepted": observation(
            first=(
                "A site's JSON document was malformed, but the collector still "
                "reported the pull as clean. We cannot treat that result as "
                "trustworthy when the response was not one valid document."
            ),
            second=(
                "I replayed the damaged response against this build. The reader "
                "{observed}; an array whose separators no longer form one valid "
                "JSON document has to fail the pull."
            ),
            detail="{observed}",
        ),
        "empty_document_accepted": observation(
            first=(
                "An application/json response containing no JSON text was "
                "reported as a clean pull with no readings. That makes an invalid "
                "empty response indistinguishable from a completed collection "
                "cycle."
            ),
            second=(
                "I ran the framing catalogue against that response. Your reader "
                "{observed}, so a gateway that has stopped answering properly "
                "looks exactly like one that is up to date."
            ),
            detail="{observed}",
        ),
        "unframed_sequence_accepted": observation(
            first=(
                "The collector accepted a json-seq response that did not begin at "
                "a valid record boundary and marked the pull clean. That body may "
                "be malformed or incomplete, so billing cannot treat it as a "
                "complete feed."
            ),
            second=(
                "I put that response through the framing catalogue. It {observed}. "
                "A body that does not start where it should has to fail the pull, "
                "not give us readings."
            ),
            detail="{observed}",
        ),
        "partial_value_yielded": observation(
            first=(
                "A response whose framing was broken handed the store a reading "
                "that was not present intact before the failure point, or handed "
                "the arrived readings over in the wrong order. The store now "
                "holds data the gateway did not deliver that way."
            ),
            second=(
                "I went back through the bad responses from that night. Your "
                "reader {observed}. Nothing may reach the store out of a response "
                "except what actually arrived in it."
            ),
            detail="{observed}",
        ),
        "invalid_record_value_yielded": observation(
            first=(
                "A response contained a framed record that was not valid and "
                "the pull failed, but a reading from that same record had "
                "already reached the store. The failed pull therefore still "
                "changed stored data."
            ),
            second=(
                "I replayed the malformed response against this build. The "
                "reader {observed}. A record that never became valid cannot "
                "contribute a reading before the pull reports its failure."
            ),
            detail="{observed}",
        ),
        "wrong_error_type": observation(
            first=(
                "An unreadable gateway response failed with a kind of error the "
                "collector does not classify as a bad fetch. The affected site "
                "therefore cannot be isolated through the normal failure path."
            ),
            second=(
                "I checked what the collector actually sees. It {observed}, so it "
                "never reaches the branch that marks the site as a bad fetch; our "
                "failure handling catches the one kind and nothing else."
            ),
            detail="{observed}",
        ),
        "media_type_parameters_mishandled": observation(
            first=(
                "A gateway response carrying a legitimate media type with "
                "parameters or different letter case did not land as the "
                "readings it sent. The header form must not turn a valid feed "
                "into a failed or altered pull."
            ),
            second=(
                "I replayed the affected response. Its header is "
                "`{content_type}`, and the reader {observed}; that is a "
                "legitimate way for a gateway to label this feed."
            ),
            detail="{content_type}",
        ),
        "empty_stream_mishandled": observation(
            first=(
                "A legitimate json-seq cycle with no readings did not finish as "
                "the same empty pull the gateway sent. The collector turned the "
                "absence of records into a different outcome, so the cycle "
                "result cannot be trusted."
            ),
            second=(
                "I put it through the framing catalogue this morning. Your reader "
                "{observed}; the gateway sent a legitimate cycle containing "
                "exactly zero readings."
            ),
            detail="{observed}",
        ),
        "blank_record_mishandled": observation(
            first=(
                "A valid feed containing an ignorable blank record did not land "
                "as the readings the gateway sent. Padding between records must "
                "not fail the pull or alter its values."
            ),
            second=(
                "I looked at what changed in its body. Your reader {observed}, and "
                "padding like that is normal on the gateway side; it must not cost "
                "us the site."
            ),
            detail="{observed}",
        ),
    },
    "encoding_contract_fidelity": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "declared_charset_ignored": observation(
            first=(
                "One gateway declares how its response is encoded, but the "
                "collector did not reproduce the readings it sent. Billing "
                "cannot use a pull that fails or changes those values."
            ),
            second=(
                "I pulled up what one of those gateways actually sends and put it "
                "back through this morning. Its header says `{content_type}`, and "
                "the response {symptom}, so the collector does not reproduce "
                "what the gateway sent."
            ),
            detail="{content_type}",
        ),
        "encoding_detection_wrong": observation(
            first=(
                "One gateway does not declare a character set in its header, and "
                "the collector did not reproduce the readings encoded in its "
                "body. The pull is unusable whether it fails or changes them."
            ),
            second=(
                "I stepped through their bodies byte by byte. Neither header "
                "carries a character set; each body announces how it is written "
                "in its own leading bytes, and {situation} still {symptom}."
            ),
            detail="{situation}",
        ),
        "byte_order_mark_mishandled": observation(
            first=(
                "One gateway's response begins with a byte-order mark, and the "
                "collector did not reproduce its complete readings. Billing "
                "cannot use the resulting pull."
            ),
            second=(
                "I stepped through {situation}. It {symptom}; the trace isolates "
                "the boundary at the leading mark but does not establish a "
                "single decoder cause."
            ),
            detail="{situation}",
        ),
        "invalid_charset_mishandled": observation(
            first=(
                "A response named a character set that no codec supports, but "
                "the collector did not report the bad-fetch failure used to "
                "isolate unreadable site responses."
            ),
            second=(
                "I went back to that header: it says `{content_type}`, and that "
                "response {symptom}. When a gateway names something no codec "
                "answers to, the honest answer is to fail that pull as a bad "
                "fetch rather than guess at it."
            ),
            detail="{content_type}",
        ),
    },
    "bounded_stream_buffering": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "flow_read_failed": observation(
            first=(
                "The slow-producer trace did not give us both the gateway's "
                "readings and one trustworthy handoff mark for each of them. "
                "Until it does, I cannot tell whether slow sites are landing "
                "correctly or incrementally."
            ),
            second=(
                "I ran the slow-producer trace this morning. On {situation} the "
                "read still {symptom}. Whatever the pace, the read has to come "
                "back with the readings."
            ),
            detail="{situation}",
        ),
        "unmetered_body_access": observation(
            first=(
                "The slow-producer trace now shows readings reaching the store "
                "before its transport counter says those bytes arrived. That "
                "makes the memory result impossible to trust: the collector is "
                "getting data through a path the trace does not account for."
            ),
            second=(
                "I stepped through the trace again. The reader {observed}; the "
                "transport record and the readings have to describe the same "
                "bytes before we can rely on its flow behaviour."
            ),
            detail="{observed}",
        ),
        "whole_body_buffered": observation(
            first=(
                "The slow-producer trace shows a complete response being pulled "
                "before its first reading reaches the store. On a large site that "
                "defeats incremental handoff and makes the first reading wait for "
                "the rest of the feed."
            ),
            second=(
                "I traced the slow producer again after your change. The reader "
                "{observed}, so its first reading still waits for bytes belonging "
                "to later readings instead of moving through incrementally."
            ),
            detail="{observed}",
        ),
        "look_ahead_bound_exceeded": observation(
            first=(
                "The slow-producer trace shows at least one reading withheld "
                "until bytes beyond its read-ahead budget had arrived. That is "
                "less incremental than the connection contract allows, even "
                "though the exact delay depends on the link."
            ),
            second=(
                "I traced one of them against your build. The reader {observed} — "
                "past what that reading needed, past the packet in flight, past "
                "the {slack} of slack we allow on top, so that reading waited on "
                "bytes that belong to later ones."
            ),
            detail="{observed}",
        ),
    },
    "stream_lifecycle_discipline": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "lifecycle_read_failed": observation(
            first=(
                "The connection drill could not complete the first read required "
                "by one of its cases. Until that read is faithful, the drill "
                "cannot tell me whether connection handling is right."
            ),
            second=(
                "I ran the drill again this morning. Its case for {situation} "
                "still cannot complete the first read that case requires, so the "
                "remaining lifecycle evidence is not interpretable."
            ),
            detail="{situation}",
        ),
        "stream_read_after_close": observation(
            first=(
                "The response traces show the collector touching a connection "
                "after it had already returned it to the pool. Whether or not "
                "the pull surfaced an error, that connection may already belong "
                "to another caller."
            ),
            second=(
                "I went back through the affected response traces. They show "
                "that {observed}. "
                "Once a connection is back in the pool it can belong to another "
                "caller, and the pool's rule is that we do not touch it after "
                "that."
            ),
            detail="{observed}",
        ),
        "stream_not_closed": observation(
            first=(
                "An affected response trace ends without the collector returning "
                "its connection to the pool. Repeated across a collection cycle, "
                "that can exhaust the pool and leave later sites unpolled."
            ),
            second=(
                "I traced the affected response again. It shows that {observed}, so that "
                "connection stays out of the pool for the rest of the cycle."
            ),
            detail="{observed}",
        ),
        "stream_closed_more_than_once": observation(
            first=(
                "An affected response trace shows the same connection returned "
                "to the pool more than once. A repeated return can touch a "
                "connection the pool has already handed to another caller."
            ),
            second=(
                "I went through the affected response traces. They show that {observed}, "
                "and a connection handed over a second time is one the pool may "
                "already have given to somebody else."
            ),
            detail="{observed}",
        ),
        "second_iteration_mishandled": observation(
            first=(
                "An already-consumed streaming response was read a second time, "
                "but the caller was not told that its body was gone. The second "
                "read therefore cannot be classified correctly."
            ),
            second=(
                "I reproduced it in the connection drill: {observed}. A body we "
                "have already read is not there any more, and the collector has "
                "to be told that."
            ),
            detail="{observed}",
        ),
        "buffered_response_closed": observation(
            first=(
                "A response that was already held in memory was closed even "
                "though it owns no pooled connection. The validation step and "
                "the writer both need that same body to remain available."
            ),
            second=(
                "I ran the connection drill again. It shows that the reader "
                "{observed}. This body was already in our hands and must remain "
                "available for later passes without closing anything."
            ),
            detail="{observed}",
        ),
        "buffered_response_not_repeatable": observation(
            first=(
                "The validation step and the writer both look at the small feeds "
                "we hold in memory, but the second pass did not reproduce what "
                "the gateway sent. With no live transport involved, both passes "
                "must see the same readings."
            ),
            second=(
                "I ran the connection drill, and this is what it shows: "
                "{observed}. Nothing is being streamed there, the body is in our "
                "own hands, and it has to be readable as often as we need it."
            ),
            detail="{observed}",
        ),
        "abandoned_read_drained_body": observation(
            first=(
                "The early-stop drill asks for one reading, but the trace shows "
                "the entire response was already pulled before the caller "
                "stopped. That defeats the bandwidth and time saved by abandoning "
                "a read early."
            ),
            second=(
                "I traced the shape check against the connection drill: "
                "{observed}, so stopping early buys us nothing at all."
            ),
            detail="{observed}",
        ),
    },
}
