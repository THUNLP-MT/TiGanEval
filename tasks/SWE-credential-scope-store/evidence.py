'Owner persona, belief, and Observation contexts for SWE-credential-scope-store.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Anwen, the security engineer who owns the relay client. She reads the "
    "collection job's own request log, the audit exports the sources send back, "
    "and the tickets those source teams open against us; she does not read the "
    "store's code."
)

USER_BELIEF = (
    "I want a quarter of nightly collection runs that finish, and that nobody "
    "outside this team has to tell us about. Last week the vendor's portal "
    "rate-limited us at 03:12 because our run had signed in forty-one times in "
    "one night, and the 06:00 export went out two days short; the week before "
    "that, a site we crawl turned up holding one of the vendor's session values "
    "and I spent an afternoon on a call about it. What I can see is our own "
    "request log -- which host we called, when, what we carried, what came back "
    "-- and whatever the source teams send me. Done, for me, is a quarter in "
    "which no source team opens a ticket about credentials of theirs arriving "
    "somewhere they never issued them, no run loses its session part way and "
    "starts over, and the morning export is one I can hand across without a "
    "note attached."
)

OBSERVATION_SCENE = "Security review of the nightly collection run's request log"


DID_NOT_RUN = observation(
    first=(
        "I put your build on the console box for this morning's review and started "
        "last night's sweep through it. It stopped part way instead of running to "
        "the end, so there is no request log, no host answers and nothing to read. "
        "I have nothing to take to the sources about the change."
    ),
    second=(
        "I started it once more, from the top, and it stopped part way there too. "
        "Where the request log should be, the console has one line: {error}. Until "
        "an ordinary night runs end to end I cannot judge anything else about it."
    ),
    detail="{error}",
)


UNISSUED_GRANT = observation(
    first=(
        "One of the sources refused a request because the grant header carried "
        "a credential value it does not recognise as one it issued. The host, "
        "the request and the returned status are all in our own log; from that "
        "first refusal I cannot tell where the value changed."
    ),
    second=(
        "I repeated the sweep and isolated the refusal at {host}. The grant named "
        "`{grant_name}` carried a value that was not among the values that source "
        "had issued, so it again answered `unexpected_grant`."
    ),
    detail="{grant_name}",
)


OBSERVATIONS = {
    "grant_audience": {
        "candidate_execution_failed": DID_NOT_RUN,
        "grant_sent_beyond_its_scope": observation(
            first=(
                "The vendor's security contact wrote to me this morning. A site we "
                "crawl that has nothing to do with them turned up holding one of "
                "their session values, and they only heard about it because that "
                "site's operator forwarded them the header. Our account with the "
                "vendor is under review while they decide what to do about it."
            ),
            second=(
                "I ran last night's sweep on your build and read the request log "
                "host by host. {host} answered that it had never issued the grant "
                "we sent it, and it never did. Nobody there has given us anything, "
                "so nothing of ours has any business arriving with them."
            ),
            detail="{host}",
        ),
        "sealed_grant_sent_in_the_clear": observation(
            first=(
                "Our own network team flagged this one. The vendor session is going "
                "out over the old plain-text listener on their site, where anyone on "
                "the path can lift it. Their runbook says a session seen in the "
                "clear is a session they revoke on the spot, and that would stop "
                "every collection run we have until somebody signs in by hand."
            ),
            second=(
                "I watched the sweep again on your build and stopped it at the plain "
                "listener. The request went out carrying `{grant_name}`, which is "
                "the one the portal marks as not to leave us in the clear, and the "
                "listener answered that it had never issued anything of the sort."
            ),
            detail="{grant_name}",
        ),
        "grant_sent_outside_its_path": observation(
            first=(
                "The vendor's platform team has opened a ticket against us. They can "
                "see one of their own section grants arriving on requests to a part "
                "of the site that section has nothing to do with, and they are "
                "reading it as us reaching for pages we were never given. They have "
                "asked for the crawl to stop until we explain it."
            ),
            second=(
                "I replayed last night's sweep on your build and found it. The "
                "request to {path} carried `{grant_name}`, which that host had "
                "handed us for a narrower part of the site. The section it was given "
                "for spells the beginning of the one we sent it to, and they are two "
                "different places."
            ),
            detail="{path}",
        ),
        "grant_withheld_from_its_scope": observation(
            first=(
                "Last night's log has a request that should still have carried a grant "
                "we received earlier, but it left without it. Sometimes that means a "
                "page asks us to sign in again; sometimes it quietly leaves one "
                "section of the collection without the state it was given. I cannot "
                "tell from the first report which move in the run lost it."
            ),
            second=(
                "I ran it again on your build and watched what actually left us. The "
                "requests to {host} went out carrying no `{grant_name}` at all, "
                "although the run had received it earlier for an audience and path "
                "covering that request, and nothing about it had run out."
            ),
            detail="{host}",
        ),
        "host_only_grant_sent_to_sibling": observation(
            first=(
                "A source has found one of its host-only grants on a sibling host. The "
                "two hosts sit under the same site name, but the source never widened "
                "that grant beyond the machine that handed it to us, so the sibling "
                "has refused the request and opened a credential ticket."
            ),
            second=(
                "I replayed the move on your build and found the request to {host}. It "
                "carried `{grant_name}`, even though that grant was handed to us by a "
                "different host without any site-wide scope on it."
            ),
            detail="{host}",
        ),
        "grant_rejected_as_unissued": UNISSUED_GRANT,
    },
    "grant_lifetime": {
        "candidate_execution_failed": DID_NOT_RUN,
        "expired_grant_still_presented": observation(
            first=(
                "A source can see our run presenting one of its grants after the "
                "deadline it supplied. A dead session can start the sign-in loop we "
                "have already seen, while a shorter-lived section grant can leave a "
                "different hole in the export; the first report does not yet tell me "
                "which expired grant this build retained."
            ),
            second=(
                "I timed it off the request log on your build. We presented "
                "`{grant_name}` {waited_s} seconds after that host handed it over, "
                "where the host had said on the way out that it was good for "
                "{lasted_s}. It answered that the value was one of its own and no "
                "longer live."
            ),
            detail="{waited_s}",
        ),
        "revoked_grant_still_presented": observation(
            first=(
                "Last night's run signed out of the portal and then went on "
                "using the session it had just given up. The portal reads a "
                "signed-out session coming back at it as somebody replaying a stolen "
                "one, and it has put a hold on our account for the rest of the week. "
                "Nothing collects while that hold is on."
            ),
            second=(
                "I read the run back on your build. The first request after the "
                "sign-out still went out with `{presented}` in its grant header, so "
                "the portal watched the session it had just closed come straight "
                "back at it."
            ),
            detail="{presented}",
        ),
        "unreadable_deadline_dropped_the_grant": observation(
            first=(
                "The archive section of the portal has stopped working for us "
                "altogether. Every request into it comes back as though we had never "
                "been given anything for it, so the archive part of the export has "
                "been empty three nights running and the research team has started "
                "asking."
            ),
            second=(
                "I ran it again on your build and looked at what that page hands "
                "over. Its grant comes with a date written `{stamp}`, which is not "
                "how anything else on that site writes one, and the run went on to "
                "the next request carrying nothing from that page at all."
            ),
            detail="{stamp}",
        ),
        "grant_rejected_as_unissued": UNISSUED_GRANT,
    },
    "grant_identity_and_bounds": {
        "candidate_execution_failed": DID_NOT_RUN,
        "same_grant_presented_twice": observation(
            first=(
                "The ledger host is refusing us outright now. Its message is that our "
                "requests arrive with the same credential written into them twice, "
                "which it treats as somebody trying to pin a session on it, and it "
                "drops the request rather than answer. The nightly posting run has "
                "not written a line for two days."
            ),
            second=(
                "I put the run through on your build and read the header we sent. "
                "`{grant_name}` is in there twice over, the same value both times, on "
                "the request the ledger then refused. It was handed to us once."
            ),
            detail="{grant_name}",
        ),
        "refresh_left_two_live_grants": observation(
            first=(
                "After the ledger hands us a replacement, the next request carries "
                "more than one credential under the same name. That leaves the host "
                "to resolve state the ledger had already replaced, so I cannot treat "
                "the posting run or its audit line as belonging to one live session."
            ),
            second=(
                "I counted what one request carried on your build, taken after the "
                "ledger had handed over a replacement: {presented_count} under the "
                "one name, where the ledger had replaced what came before it. A "
                "replacement is a replacement."
            ),
            detail="{presented_count}",
        ),
        "bounds_exceeded": observation(
            first=(
                "The tile host has started refusing the back half of every run that "
                "walks its tiles. It hands us something new with each reply, and part "
                "way down the tiles it stops answering us and says our request is too "
                "big to accept. The run finishes with a fraction of the images it "
                "should have brought back."
            ),
            second=(
                "I ran the tile stretch on your build and looked at its last "
                "request. It carried {presented_count} of that host's grants at once, "
                "{header_bytes} bytes of header against the {max_header_bytes} that "
                "host publishes, where the profile sizes us at "
                "{max_grants_per_scope} for any one site."
            ),
            detail="{presented_count}",
        ),
        "trim_dropped_the_established_grant": observation(
            first=(
                "The request back to the ledger after the tile stretch carries no "
                "ledger session and comes back asking us to sign in. The ledger had "
                "issued that session before the pressure began; this first line does "
                "not tell me whether the build failed to retain it at the start or "
                "discarded it while making room for the tiles."
            ),
            second=(
                "I ran the same night on your build. After the tile stretch the "
                "request to the ledger went out with no `{grant_name}` on it at all, "
                "although the ledger had handed that grant over before the tile "
                "stretch. The tiles are the things that arrive by the hundred."
            ),
            detail="{grant_name}",
        ),
        "trimmed_grant_returned_after_retirement": observation(
            first=(
                "The tile host retired the newest batch of grants, and credentials "
                "from much earlier in the walk then came back into the next request. "
                "Those older entries should already have made room when the site's "
                "store reached its configured size; their return makes the host treat "
                "our retained state as larger than the run is allowed to keep."
            ),
            second=(
                "I repeated the pressure stretch on your build. After the retirement, "
                "the next request carried `{grant_name}` among "
                "{presented_count} tile grants; the profile allows "
                "{max_grants_per_scope}, and the one expected survivor was "
                "`{expected_survivor}`."
            ),
            detail="{grant_name}",
        ),
        "pressure_survivor_missing_after_retirement": observation(
            first=(
                "The tile host retired the newest batch of grants, but the next "
                "request carried none of the one older grant that should still be "
                "live. The run stays below its configured size by losing retained "
                "state, so the last tile cannot be fetched."
            ),
            second=(
                "I repeated the pressure stretch on your build. After the retirement, "
                "the next request omitted `{grant_name}`; it carried "
                "{presented_count} tile grants where the profile allows "
                "{max_grants_per_scope}. That named grant was the one entry outside "
                "the retired batch that should have survived."
            ),
            detail="{grant_name}",
        ),
        "grant_rejected_as_unissued": UNISSUED_GRANT,
    },
    "fold_invariance": {
        "candidate_execution_failed": DID_NOT_RUN,
        "folded_reply_lost_a_grant": observation(
            first=(
                "Two runs on the same night against the same source come back with "
                "different exports, and which one you get depends on whether their "
                "edge answered instead of the origin. About half our nights go "
                "through the edge, and those nights come back short. I cannot tell an "
                "analyst why yesterday's file has rows that today's does not."
            ),
            second=(
                "I ran both halves of the asset stretch on your build and put the two "
                "request logs side by side. Against the edge, `{missing_grant}` never "
                "went out after it was handed over; on the corresponding origin "
                "request it did. The two hosts said the same thing, written "
                "differently."
            ),
            detail="{missing_grant}",
        ),
        "junk_segment_stored_as_a_grant": observation(
            first=(
                "I was reconciling Tuesday's two asset runs and the one that went "
                "through the edge carries something on its requests that the run "
                "against the origin never carries. It is not a name that host has "
                "ever handed us, and the edge team have asked what we think we are "
                "sending them."
            ),
            second=(
                "I looked again on your build. On the edge side the run sends a grant "
                "called `{junk_grant}`, and there is nothing of that name anywhere in "
                "what the host actually handed back; it reads like a piece of one of "
                "their headers taken for a name of its own."
            ),
            detail="{junk_grant}",
        ),
        "folded_reply_changed_a_grant": observation(
            first=(
                "The direct and edge runs keep the same grant names, but one of the "
                "values written back on the edge path is not the value the source "
                "issued. The source refuses that request, so matching the two lists by "
                "name alone is hiding a real transport difference."
            ),
            second=(
                "I put the two request logs side by side on your build. The grant named "
                "`{grant_name}` has different values after the folded reply and the "
                "one-per-header reply, even though those replies carried the same "
                "directives."
            ),
            detail="{grant_name}",
        ),
        "grant_rejected_as_unissued": UNISSUED_GRANT,
    },
    "grant_send_order": {
        "candidate_execution_failed": DID_NOT_RUN,
        "wrong_desk_on_a_scoped_page": observation(
            first=(
                "The vendor's quarterly audit export has our run reading team B's "
                "pages under the shared desk's identity. Team B's lead saw it before "
                "I did and wants to know whether we have been reading their pages as "
                "somebody else all quarter. The account manager would like an answer "
                "today."
            ),
            second=(
                "I put the audit stretch through your build and lined our log up "
                "against theirs. On the request to {path} the board acted for "
                "{acted_for}, where we had gone in as {entered_as}. The board takes "
                "the first grant of its session name that it finds in the header, so "
                "whichever one our header put first settled that line."
            ),
            detail="{acted_for}",
        ),
        "page_read_with_no_desk_grant": observation(
            first=(
                "The vendor's audit export has lines for our run with no desk against "
                "them at all. Their compliance team reads an unattributed request as "
                "one they cannot account for, and they want to know how a run that "
                "signed in reaches their pages as nobody. The account manager has to "
                "answer them on Thursday."
            ),
            second=(
                "I put the audit stretch through your build and read our own log. The "
                "request to {path} went out with nothing of the desk we had gone in as "
                "-- {entered_as} -- in its header, so the board had no session to read "
                "and wrote no desk on the line."
            ),
            detail="{path}",
        ),
        "wrong_desk_after_re_entering": observation(
            first=(
                "We enter as one desk, then as another, and the audit line the vendor "
                "writes for the request straight afterwards names whichever of them "
                "it likes. Last quarter that put one desk's rows into another desk's "
                "export, and the correction went out with the account manager's name "
                "on it."
            ),
            second=(
                "I ran the audit stretch on your build and matched the lines up. The "
                "run had entered as {entered_as}, and the request straight after that "
                "came back acted for {acted_for}. The board takes the first one in "
                "the header, so the order we write them in decides the whole thing."
            ),
            detail="{acted_for}",
        ),
        "grant_rejected_as_unissued": UNISSUED_GRANT,
    },
}
