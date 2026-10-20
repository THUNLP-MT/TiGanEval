'Owner persona, belief, and Observation contexts for SWE-incremental-scan-cache.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Nadia, the CI engineer who owns the build pipeline; she reads the nightly "
    "scan report, the build volume's usage panel, and what a replay prints. She "
    "knows the scanner itself from its own documentation and from what the team "
    "tells her, not from reading its code."
)

USER_BELIEF = (
    "I own the build pipeline and the nightly security scan that runs on it. The "
    "scan is the slowest stage we have, so we made it reuse a file's saved "
    "findings when the file has not been touched; what I care about is that the "
    "report developers and release reviewers act on says what a full scan of that "
    "checkout would have said. Twice this month people were sent after code that "
    "was already fixed, and once security found something the nightly had passed. "
    "The build volume the cache lives on is shared with every other job on the "
    "box, and saved results for files we deleted are still there. I assume "
    "clearing those entries is all the cleanup the cache needs. I think the key "
    "is the problem. It is the file's "
    "path and its modification time, and our checkout step restores timestamps "
    "from the manifest, so an edited file comes back under the key it had before; "
    "my guess is that putting the file's size into the key next to the timestamp "
    "would catch it. Done, for me, is a nightly that stays fast, whose report I "
    "can hand to a reviewer without running a full scan first to check it, and "
    "that leaves the volume in a state nobody has to clean up by hand."
)

OBSERVATION_SCENE = "Nightly security-scan review, CI platform team"


_DID_NOT_RUN = observation(
    first=(
        "The nightly scan stage went red before it produced anything. The report "
        "slot was empty, so the release team had no scanner result for that "
        "build."
    ),
    second=(
        "I ran a recorded scan against your build myself. Where the run timeline "
        "should be it comes back with {error}, so the scanner produced no report "
        "I can put next to a full scan."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "clean_scan_finding_equivalence": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "nightly_scan_failed": observation(
            first=(
                "One of this week's nightly scans stopped inside the scanner "
                "instead of producing a report, so the release team had no "
                "security result for that build."
            ),
            second=(
                "Stepped the rescan record through run by run. The run labelled "
                "{label} stops with an error instead of publishing a report, "
                "and whatever it left on the volume is what the night after it "
                "is handed. Every night in that record has to come back with a "
                "report."
            ),
            detail="{label}",
        ),
        "stale_findings_reported": observation(
            first=(
                "A developer had a release blocked by a finding in the "
                "incremental report that a full re-analysis of the same checkout "
                "did not contain. They had to prove which report the reviewer "
                "could trust before the release could move."
            ),
            second=(
                "Ran the week again with the report beside a full re-analysis of "
                "the same checkout. On {label} the report still has more to say "
                "about {reported_file} than the re-analysis does. Whatever makes "
                "a saved result safe to reuse has to cover everything that "
                "decides what a file reports, and the settings those runs are "
                "given are part of that."
            ),
            detail="{reported_file}",
        ),
        "findings_missing_after_change": observation(
            first=(
                "Security compared an incremental report with a full re-analysis "
                "of the same checkout and found a finding only the full analysis "
                "reported. The release had been reviewed against the incomplete "
                "report."
            ),
            second=(
                "Put that night back through on your build, against a full "
                "re-analysis of the same checkout. On {label} the re-analysis "
                "has more to say about {missing_file} than the report does. "
                "Anything the analyzer would raise on that checkout has to reach "
                "the report."
            ),
            detail="{missing_file}",
        ),
        "findings_differ_from_clean_scan": observation(
            first=(
                "This morning's report and the full re-analysis we run whenever "
                "anyone disputes a finding disagree in both directions at once: "
                "the report carries a finding the full analysis does not, and the "
                "full analysis carries one the report never mentions. Which of "
                "the two a reviewer opens decides what gets fixed."
            ),
            second=(
                "Went through the week with both outputs side by side. On one "
                "night the report says more about {reported_file} than the full "
                "re-analysis does, and the re-analysis says more about "
                "{missing_file} than the report does. The report has to be the "
                "set a full analysis of that checkout produces, exactly."
            ),
            detail="{reported_file}",
        ),
    },
    "fail_closed_cache_integrity": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "cache_failure_aborted_scan": observation(
            first=(
                "During the storage-reliability run, one scan stopped before it "
                "could publish a report. The empty report slot does not tell us "
                "which cache operation stopped it."
            ),
            second=(
                "Pointed the damage drill at what you have now and read it line "
                "by line. The run labelled {label} does not finish: where its "
                "report should be there is {error}. Every scan in the storage-"
                "reliability drill still has to finish with a report."
            ),
            detail="{error}",
        ),
        "import_aborted_the_run": observation(
            first=(
                "A cache restore ended the receiving job during the import step, "
                "before the worker could produce a scan report. From the stopped "
                "job alone we could not tell whether the bundle was usable."
            ),
            second=(
                "Took the drill through again and watched the transfers. The "
                "import under the recorded bundle condition {bundle_condition} "
                "raises with {error} instead of "
                "returning an ordinary outcome that lets the job continue."
            ),
            detail="{error}",
        ),
        "damaged_entry_served": observation(
            first=(
                "After the volume damaged some saved scan data, the run completed "
                "and the report looked normal, but a full re-analysis of the same "
                "checkout did not agree with it. A reviewer could no longer tell "
                "which findings belonged to the code in front of them."
            ),
            second=(
                "Ran the drill again on your build. The run labelled {label} "
                "finishes, and it and a full re-analysis of the same code "
                "disagree about {disputed_file}, so saved bytes the drill had "
                "already damaged are deciding what that run reports. The report "
                "has to describe the code in front of the run."
            ),
            detail="{disputed_file}",
        ),
        "import_poisoned_cache": observation(
            first=(
                "The first scan after a malformed bundle import completed, but its "
                "report did not match a full re-analysis of the same checkout. "
                "The receiving worker could not use that report as the record of "
                "what it scanned."
            ),
            second=(
                "Walked the drill through once more. The run labelled "
                "after-malformed-import completes, and it and a full re-analysis "
                "no longer agree about {disputed_file}. A malformed import must "
                "not leave state that changes what the following scan reports."
            ),
            detail="after-malformed-import",
        ),
        "stale_bundle_served": observation(
            first=(
                "We restored a cache bundle taken before a source edit, and the "
                "next report no longer matched a full re-analysis of the current "
                "checkout. The restored worker was reporting against the wrong "
                "state of the code."
            ),
            second=(
                "Followed the drill past the restore. Once the bundle taken "
                "before the source edit goes back in, the run labelled "
                "after-stale-bundle-import and a full re-analysis of the same "
                "code no longer agree about {disputed_file}. A restored bundle "
                "may make a worker faster; it must not put last week's code back "
                "in the report."
            ),
            detail="after-stale-bundle-import",
        ),
    },
    "honest_cache_accounting": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "scan_run_failed": observation(
            first=(
                "The cache panel has a hole in it. One scanner run ended before "
                "publishing a report or summary, so for that build I cannot say "
                "what was scanned or reused."
            ),
            second=(
                "Walked the week run by run on your build. The run labelled "
                "{label} stops without publishing a summary at all — {error} — "
                "so that build is left with no numbers behind it."
            ),
            detail="{label}",
        ),
        "report_contract_incomplete": observation(
            first=(
                "The panel that reads the nightly report could not parse last "
                "night's result because it did not have the documented report "
                "shape. The panel went blank and the weekly note to the platform "
                "lead had nothing reliable to quote."
            ),
            second=(
                "Read the raw report from the week myself. On {label} the "
                "scanner's report is rejected with {error}. Both the findings and "
                "the cache summary have to use the public shapes their readers "
                "expect."
            ),
            detail="{error}",
        ),
        "accounting_totals_inconsistent": observation(
            first=(
                "One run's cache summary cannot be reconciled with its checkout: "
                "at least one of the hit count, miss count, reused list, and file "
                "total contradicts the others. Those numbers are what we use to "
                "plan the build fleet."
            ),
            second=(
                "Added each run's summary up by hand. On {label} the hit count, "
                "the miss count, the reused list and the {live_file_count} files "
                "in that checkout cannot all be describing the same night. Every "
                "file in the checkout is one reuse or one analysis, and the "
                "summary has to say so."
            ),
            detail="{live_file_count}",
        ),
        "reuse_claim_contradicts_analysis": observation(
            first=(
                "We size the build fleet from the number of files the nightly "
                "says it skipped. Last night's reused list and the analyzer log "
                "classified at least one file differently, so the capacity plan "
                "we wrote from those numbers is wrong."
            ),
            second=(
                "Lined the claimed reuse up against the analyzer's own log for "
                "each night. On {label} the reused_paths list and the files the "
                "analyzer actually ran on do not agree. That list has to be "
                "exactly the files the run did not analyse."
            ),
            detail="reused_paths",
        ),
        "cache_inventory_misreported": observation(
            first=(
                "The volume usage panel and the scan report tell different "
                "stories about what the cache held after one run. Capacity "
                "planning for the build volume is being done from numbers that "
                "do not describe the store the run actually left."
            ),
            second=(
                "Compared each run's own summary with what the volume was "
                "holding when that run finished. One run's summary says the "
                "cache holds {reported_inventory} where the volume was left "
                "carrying {inventory_on_the_volume}, so the panel is describing "
                "a store that does not exist."
            ),
            detail="{reported_inventory}",
        ),
    },
    "bounded_cache_growth": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "capacity_run_failed": observation(
            first=(
                "One scan in the capacity run stopped before it produced a "
                "report. The empty report slot does not show whether the failure "
                "happened near the volume limit or somewhere earlier in the run."
            ),
            second=(
                "Replayed the capacity week. The run labelled {label} stops "
                "without producing a report. Every run under the volume's "
                "published envelope still has to finish with one."
            ),
            detail="{label}",
        ),
        "cache_size_limit_exceeded": observation(
            first=(
                "The build volume's usage panel shows that the scan cache left "
                "more data behind than the space assigned to it. Every other job "
                "sharing that volume was put at risk."
            ),
            second=(
                "Ran the capacity week again with the store's size next to each "
                "run's limit. After one run the volume is carrying "
                "{cache_bytes_after_run} bytes of scan cache where that run was "
                "given {cache_size_limit_bytes}. What a run leaves behind has to "
                "be inside what it was given."
            ),
            detail="{cache_bytes_after_run}",
        ),
        "unreclaimed_entries_retained": observation(
            first=(
                "We removed a package from the checkout and later restored the "
                "same contents. The first scan after the restore treated its "
                "files as already cached, showing that their saved results had "
                "remained on the volume while the files were absent."
            ),
            second=(
                "Stepped through the capacity week. In the run labelled "
                "cap-after-restore the files that left the tree and then came "
                "back, {served_path} among them, are served from the store "
                "instead of being analysed. A saved result whose file left the "
                "checkout is the run's to clear out."
            ),
            detail="cap-after-restore",
        ),
        "expired_entries_retained": observation(
            first=(
                "After a quiet fortnight, with nothing merged and no setting "
                "moved, the scan cache still held more saved results than the "
                "checkout had files. The platform team asked why old results were "
                "occupying a volume every other job shares."
            ),
            second=(
                "Looked at what the volume was left holding after the quiet "
                "stretch. On the run labelled cap-after-idle, after a gap longer "
                "than the age the volume gives a saved result, the store still "
                "holds {cached_entry_count_after_run} results for a checkout of "
                "{live_file_count} files. What a night like that should leave "
                "behind is one result per file and nothing else."
            ),
            detail="{cached_entry_count_after_run}",
        ),
        "steady_state_write_amplification": observation(
            first=(
                "Nothing merged last night and no setting moved, but the scan "
                "still wrote beyond the volume's allowance for an unchanged run. "
                "That avoidable disk churn lands on a volume shared with the build "
                "cache."
            ),
            second=(
                "Went back through the capacity week with each run's written "
                "bytes next to what it was allowed. On the run labelled "
                "cap-unchanged, where nothing in the tree and nothing in the "
                "settings had moved, it wrote {bytes_written} bytes against the "
                "{steady_state_write_allowance_bytes} the volume allows a quiet "
                "night. Reusing a saved result should not mean writing it out "
                "again."
            ),
            detail="{bytes_written}",
        ),
        "warm_start_rewrites_the_store": observation(
            first=(
                "We brought a second build agent up warmed from the primary's "
                "cache, and the write graph on that box went up instead of down. "
                "Its first night analysed nothing new but still wrote beyond the "
                "allowance for an unchanged run on a volume every job shares."
            ),
            second=(
                "Put the fleet record back through on your build and read the "
                "write counters. The run labelled ci-2-warm served every file out "
                "of what the primary handed it and still wrote {bytes_written} "
                "bytes, where a night on which nothing changed is allowed "
                "{steady_state_write_allowance_bytes}. Being handed the work is "
                "meant to save us the writing as well as the analysis."
            ),
            detail="{bytes_written}",
        ),
        "reusable_entry_evicted": observation(
            first=(
                "We reran the nightly twice in a row this morning to check "
                "something, and the second run went off and analysed files the "
                "preceding identical run had already completed. The published "
                "store budget could hold that work, so the queue paid for it "
                "twice."
            ),
            second=(
                "Put the capacity week through on your build. The run labelled "
                "cap-repeat, immediately after an identical one, does not come "
                "back free: the store leaves {files_not_reused} of its "
                "{live_file_count} files unserved. The clear-out is taking "
                "results the very next run needs."
            ),
            detail="{files_not_reused}",
        ),
        "unexpired_entry_discarded": observation(
            first=(
                "We came off the release profile on Monday night and the scan "
                "reported misses on files in a checkout nobody had touched since "
                "Wednesday. The settings had already run earlier in the same "
                "week, but the release build still waited for repeated analysis."
            ),
            second=(
                "Ran that night again on your build. It analysed "
                "{files_not_reused} of the {live_file_count} files in front of "
                "it, and the settings it ran under are the ones the pipeline was "
                "already running earlier the same week, on the same files. The "
                "volume is still holding space for that week's results; nothing "
                "about them is old enough or orphaned enough to be swept."
            ),
            detail="{files_not_reused}",
        ),
    },
    "portable_cache_exchange": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "handoff_scan_failed": observation(
            first=(
                "The receiving worker could not produce a report on one of its "
                "handoff runs: after the import step, the scanner raised instead "
                "of scanning. Work stayed queued on the primary."
            ),
            second=(
                "Replayed the fleet handoff. The run labelled {label} raises out "
                "of the scanner instead of scanning, so the second worker "
                "produced no report at all. Whether the preceding bundle was "
                "accepted or rejected, the worker still has to be able to scan."
            ),
            detail="{label}",
        ),
        "export_contract_incomplete": observation(
            first=(
                "The transfer step could not obtain a bundle with a readable "
                "format declaration from the primary, so the fleet tooling had "
                "nothing it could safely check before a receiving import."
            ),
            second=(
                "Took the handoff record through on your build. The bundle the "
                "export step labels {label} does not produce a bundle with a "
                "format_version the receiving side can read. Workers pick up "
                "analyzer releases on different days, so the bundle has to say "
                "what it is before anyone reads it."
            ),
            detail="format_version",
        ),
        "export_not_deterministic": observation(
            first=(
                "Our transfer step deduplicates bundles by content hash so we are "
                "not shipping the same cache around the fleet twice. Two exports "
                "of the same cache came out with different hashes, so the second "
                "copy was shipped again."
            ),
            second=(
                "Ran the handoff again and compared the two exports the transfer "
                "step took from that worker on consecutive days, with nothing "
                "between them but a nightly on which nothing merged and no "
                "setting moved. They come out with different content hashes: "
                "warm-repeat does not match the export before it. The same cache "
                "has to serialise to the same bytes for the transfer step to "
                "compare anything."
            ),
            detail="warm-repeat",
        ),
        "unsupported_bundle_import_failed": observation(
            first=(
                "A receiving worker was handed a bundle whose declared format it "
                "does not support, and the import crashed instead of leaving the "
                "store alone. The worker never reached its scan normally."
            ),
            second=(
                "Took the handoff through with a bundle stamped 9999, a format "
                "this worker knows nothing about. The import raises — {error} — "
                "instead of declining the bundle and leaving the store as it "
                "was."
            ),
            detail="9999",
        ),
        "unsupported_bundle_accepted": observation(
            first=(
                "A worker merged a bundle whose declared format it does not "
                "support straight into its own store. The fleet could no longer "
                "account for what representation that worker was carrying."
            ),
            second=(
                "Watched the transfers on the handoff record again. The bundle "
                "arriving stamped 9999 is taken in anyway and the receiving "
                "store comes out of that import holding {entry_count_after} "
                "entries. A worker that does not know a bundle's format has to "
                "leave both that bundle and its own store alone."
            ),
            detail="9999",
        ),
        "warm_bundle_not_accepted": observation(
            first=(
                "Starting a fresh agent from the primary's cache has stopped "
                "buying us anything. We handed a new box an earlier bundle from "
                "the same build, in our own format, and the receiving store took "
                "nothing from it, so that agent began cold."
            ),
            second=(
                "Ran the fleet handoff through once more. The import of the "
                "bundle labelled warm, which this same build produced for the "
                "previous shipment, is followed by a receiving store holding "
                "{entry_count_after} entries. An export and an import from one "
                "build have to be able to talk to each other."
            ),
            detail="warm",
        ),
        "warm_import_not_reused": observation(
            first=(
                "The bundle went into a fresh agent and the counters said entries "
                "arrived, but its first scan still analysed files that should have "
                "been reusable. The warm start did not provide the reuse the "
                "fleet expected."
            ),
            second=(
                "Followed the second worker through the handoff record. It holds "
                "the same code at {checkout_root}, and on its run after the "
                "import the store leaves {files_not_reused} of its files "
                "unserved. A bundle has to be worth something to the worker "
                "that receives it."
            ),
            detail="{checkout_root}",
        ),
        "warm_import_findings_wrong": observation(
            first=(
                "One receiving-worker run after a bundle handoff produced a "
                "finding list that did not match a full re-analysis of the same "
                "commit. The fleet could not treat that handoff report as the "
                "record for the checkout."
            ),
            second=(
                "Took the handoff record through again. On the run labelled "
                "{label} the receiving worker's report and a full re-analysis of "
                "the same code disagree about {disputed_file}. Handing a worker "
                "a bundle may make it faster; it must not change what that "
                "worker reports."
            ),
            detail="{disputed_file}",
        ),
    },
}
