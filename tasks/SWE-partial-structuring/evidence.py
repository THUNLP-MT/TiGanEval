'The owner of the nightly provider ingest, and what she reports seeing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Naomi Adeyemi, the data engineer who owns the nightly provider ingest; she reads "
    "the scheduler's log, the ledger rows, the tickets in the support console, "
    "and a replay of a recorded drop, and does not work in the reading's code."
)

USER_BELIEF = """I want the nightly provider drop to stop costing us the whole file. One column we cannot read in one payload should not mean nothing publishes, because when that happens the accounts on the console go stale, support spends the morning on the phone, and the provider deletes the file before we can ask for it again. What I want out of a night is the drop sitting in the ledger by morning, and a list of the columns that gave trouble going to the provider so somebody can chase them column by column. Support works those tickets off the lines the job has always printed, so whatever we send them has to still read the way their runbook says. Done is a fortnight of nights where the drop publishes, nobody is on the phone at nine, and finance stops finding numbers they cannot trace back to the provider."""

OBSERVATION_SCENE = "Nightly provider drop review"


_DID_NOT_RUN = observation(
    first=(
        "The 02:30 job came back with nothing at all last night: no ledger "
        "rows, no tickets, and the console is still showing Tuesday's "
        "balances. Support opened the morning with three accounts they could "
        "not explain and no file to point anybody at."
    ),
    second=(
        "I ran the drop again with your reading in the tree and there is no "
        "drop timeline in it at all, just `{error}` where the first payload "
        "should be. Nothing behind it gets read, so the night stops before it "
        "starts."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "field_provenance_accounting": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "field_accounting_not_reported": observation(
            first=(
                "The nightly job stopped before it wrote a single ledger row "
                "last night. The publisher went looking for the list of "
                "columns it is meant to record as the provider's and did not "
                "find one, so nothing was published and support came in to a "
                "console with no tickets on it."
            ),
            second=(
                "I put last night's drop through your reading and looked at "
                "what came back for {record_id}: {problem}. The publisher goes "
                "to the reading for the columns it records as the provider's "
                "and for the ones it puts on the provider ticket, so with that "
                "gone nothing is written and nobody upstream is told anything."
            ),
            detail="{problem}",
        ),
        "absent_column_reported_as_provider_data": observation(
            first=(
                "Finance came to me with a reconciliation break this morning: "
                "a ledger row's confirmed-column list says the provider sent "
                "us a column that is not in its payload at all. Whatever value "
                "the row holds there did not come from the provider, so finance "
                "cannot reconcile it as theirs."
            ),
            second=(
                "I read Thursday's drop again on your build and lined the file "
                "up against the row for {record_id}: the payload carries no "
                "`{column}` key at all, and the reading still hands that "
                "column to the publisher as the provider's. Nobody ever asks "
                "them for it, so the break stays."
            ),
            detail="{column}",
        ),
        "fallback_value_reported_as_provider_data": observation(
            first=(
                "Support closed a provider ticket last week saying the column "
                "was fine, and it is not fine. The file had something in it we "
                "could not read, we quietly published our own standby value "
                "instead, and the ticket never mentioned the column, so the "
                "provider has been sending the same thing every night since."
            ),
            second=(
                "I read the drop again on your build and checked {record_id} "
                "against the file: `{column}` came in unreadable and the row "
                "still went out with that column recorded as the provider's "
                "own. What we published under it is ours."
            ),
            detail="{column}",
        ),
        "derived_column_in_the_accounting": observation(
            first=(
                "The provider wrote back this morning asking what we meant. "
                "Our ticket asked them about a column that is not in their "
                "file at all, one we work out ourselves after we have read the "
                "record, and their engineer spent a day looking for it before "
                "somebody picked up the phone."
            ),
            second=(
                "I opened the ticket your build produced for {record_id} and "
                "`{column}` is on it. That one is worked out on our side from "
                "the record we publish, so there is nothing for the provider "
                "to send us."
            ),
            detail="{column}",
        ),
        "supplied_column_on_both_lists": observation(
            first=(
                "The provider's engineer came back on a ticket this morning "
                "wanting to know which of two things we meant. We had asked "
                "them to fix a column and, on the same night's row, told "
                "finance we hold their value for it. Finance is now "
                "reconciling against a column support is chasing."
            ),
            second=(
                "I read last night's drop again on your build and looked at "
                "{record_id}: `{column}` is on the ticket and in the row's "
                "confirmed columns at the same time. Every column the file "
                "supplies sits on exactly one of those two sides."
            ),
            detail="{column}",
        ),
        "name_that_is_not_a_column_of_the_file": observation(
            first=(
                "The provider's console bounced one of our tickets overnight. "
                "The name in its list of columns to chase is not declared in "
                "the provider's contract at all, so it was rejected before it "
                "reached a person. This is different from a declared column "
                "being absent from one payload: there is no provider column "
                "under this name for support to chase."
            ),
            second=(
                "I opened the ticket your build produced for {record_id}: "
                "`{column}` is in the list of columns we are asking the "
                "provider to chase, and the contract does not declare it, so "
                "there is nothing on their side for it to match."
            ),
            detail="{column}",
        ),
        "supplied_column_on_neither_list": observation(
            first=(
                "Finance asked me yesterday whether a column on last night's "
                "rows was the provider's own value, and I could not tell them. "
                "It is not in what we confirm to them and it is not on any "
                "ticket we raised, so nobody has stood behind it and nobody has "
                "chased it. They have stopped signing the reconciliation off."
            ),
            second=(
                "I went through last night's drop on your build for "
                "{record_id}: `{column}` is not in the columns we hold as the "
                "provider's and it is not on the ticket. Every column the file "
                "supplies has to be on one of those two lists."
            ),
            detail="{column}",
        ),
        "clean_column_reported_as_a_gap": observation(
            first=(
                "Support worked a ticket all Tuesday for a column the provider "
                "had actually sent us. They went back through the raw file with "
                "the provider's own engineer, found it sitting there and "
                "perfectly readable, and we had still asked them to fix it."
            ),
            second=(
                "I read the drop again on your build and went through the "
                "ticket for {record_id}: `{column}` is on it, and that column "
                "came out of the file and read cleanly. A column we could read "
                "is a column we hold as theirs."
            ),
            detail="{column}",
        ),
        "read_whole_although_the_ticket_has_columns_on_it": observation(
            first=(
                "An analyst spent yesterday afternoon on accounts the console "
                "had listed as read whole. Two of them had provider tickets "
                "open at the same time and she could not work out which of the "
                "two states was the real one. Support has stopped trusting that "
                "list, and it is the list they work down every morning."
            ),
            second=(
                "I looked at what your build said about {record_id} last night: "
                "the reading calls that record read whole, and `{column}` is in "
                "its list of columns to chase at the same time. Finance goes by "
                "that flag, so it has to say the same thing as that list."
            ),
            detail="{column}",
        ),
        "not_read_whole_although_the_ticket_is_empty": observation(
            first=(
                "Finance would not close last night's reconciliation. They "
                "leave out every account the reading says we did not read "
                "whole, and one of the accounts they left out has not one "
                "column on it for anybody to chase. The analyst went back "
                "through the provider's file for that account and found every "
                "column it owes us sitting there and readable, so we are "
                "carrying it as unfinished business on a file we hold in full."
            ),
            second=(
                "I read the drop again on your build and checked {record_id}: "
                "all {columns_the_file_gave_us} columns the file supplies came "
                "out of it and read cleanly, there is no column on that record "
                "for anybody to chase, and the reading still calls it not read "
                "whole. Finance goes by that flag, so it has to say the same "
                "thing as the list of columns we are chasing."
            ),
            detail="{columns_the_file_gave_us}",
        ),
    },
    "publishable_or_withheld": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "record_published_without_a_required_column": observation(
            first=(
                "Billing found records in last night's ledger with one of the "
                "required columns empty. There is no fallback we can honestly "
                "put in a required gap, so finance cannot use those rows and "
                "has to hold the affected work back by hand."
            ),
            second=(
                "I ran the drop again on your build and looked at the row for "
                "{record_id}: it went to the ledger with `{column}` empty. "
                "There is nothing we can honestly put in that column, so a "
                "record like that has to be held back rather than published "
                "with a hole in it."
            ),
            detail="{column}",
        ),
        "record_withheld_although_every_gap_has_a_fallback": observation(
            first=(
                "Half the drop never reached the ledger last night. The "
                "records were held back over columns we carry standby values "
                "for, and the accounts they belong to sat dark on the console "
                "for a day while support chased a file that was fine."
            ),
            second=(
                "I read last night's drop again on your build: the record for "
                "{record_id} is held back, and every column it is short of is "
                "one we declared a standby value for. A record like that is "
                "publishable."
            ),
            detail="{record_id}",
        ),
        "record_withheld_although_nothing_is_missing": observation(
            first=(
                "A new customer went a whole billing cycle without an invoice. "
                "Every column the provider owes us for that account was in "
                "their file and readable, and the record still never reached "
                "the ledger. Their account manager found out when the customer "
                "rang to ask why nothing had been charged."
            ),
            second=(
                "I read last night's drop again on your build: the record for "
                "{record_id} is held back and it is short of nothing at all. "
                "All {columns_the_file_gave_us} columns came out of the file "
                "and read, so there is nothing about that one we cannot "
                "publish."
            ),
            detail="{columns_the_file_gave_us}",
        ),
        "published_column_holds_neither_the_file_nor_the_fallback": observation(
            first=(
                "The reconciliation job flagged a row this morning that "
                "matches nothing. The value sitting in it is not what the "
                "provider sent us and it is not the standby value we fall back "
                "to, so nobody can say where it came from."
            ),
            second=(
                "I compared the ledger row your build wrote for {record_id} "
                "against the file column by column: `{column}` holds something "
                "that is in neither place. A published column has to be the "
                "provider's own value, and where they gave us nothing it has "
                "to be the standby value we declared."
            ),
            detail="{column}",
        ),
        "computed_column_does_not_match_the_record": observation(
            first=(
                "Billing keyed a night's rows into the wrong accounts. The key "
                "the ingest works out for itself came out of step with the "
                "record it sits on, and two customers were invoiced for a plan "
                "somebody else is on. Finance had to reverse both by hand."
            ),
            second=(
                "I read the drop again on your build and looked at the row for "
                "{record_id}: `{column}` does not match the record it is worked "
                "out from. That column is ours to compute, and the billing "
                "table is keyed on it."
            ),
            detail="{column}",
        ),
        "publisher_failed_during_the_drop": observation(
            first=(
                "The 02:30 publisher stopped before the drop completed last "
                "night. No completed ledger result or support ticket set came "
                "back, the console stayed on the previous balances, and the "
                "morning team had no finished drop to work from."
            ),
            second=(
                "I ran the same drop again on your build and the publisher "
                "stopped with `{error}`. It returned no completed ledger or "
                "ticket result for the night."
            ),
            detail="{error}",
        ),
    },
    "diagnosis_matches_the_strict_reading": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "diagnosis_not_reported": observation(
            first=(
                "Support has worked the provider tickets off the lines this "
                "job prints for two years; the runbook quotes them word for "
                "word. This morning the tickets came through with nothing on "
                "them, so the analyst on shift had a list of account numbers "
                "and no idea what was wrong with any of them."
            ),
            second=(
                "I read the drop again on your build and looked at what came "
                "back for {record_id}: {problem}. The console prints those "
                "lines straight onto the ticket, so an empty one is what the "
                "provider receives."
            ),
            detail="{problem}",
        ),
        "absent_column_produces_no_line": observation(
            first=(
                "The provider dropped a column out of their export in June and "
                "we found out in September, from finance. The job read past it "
                "every single night without a word, so the ticket never said "
                "anything and nobody upstream knew there was a column to put "
                "back."
            ),
            second=(
                "I read the drop again on your build and went through the "
                "ticket for {record_id}: the line `{line}` is not on it. A "
                "column the file did not carry has to show up in the "
                "diagnosis the same as one we could not read."
            ),
            detail="{line}",
        ),
        "line_missing_from_the_diagnosis": observation(
            first=(
                "The analyst on the provider ticket this morning could not "
                "match it to anything in the runbook. Lines this job has "
                "always printed are missing from what we send now, so the "
                "provider gets a shorter story than the incident actually has "
                "and comes back asking us to run the file again."
            ),
            second=(
                "I put the same payload down both readings on your build and "
                "diffed what came out for {record_id}: `{line}` is in the "
                "strict one and not in yours. The provider works from those "
                "lines, and so does our own ticket history."
            ),
            detail="{line}",
        ),
        "line_the_strict_reading_does_not_give": observation(
            first=(
                "The provider pushed back hard this morning. Our ticket "
                "pointed their engineer at a place in the file that this job "
                "has never complained about, they spent the morning there, and "
                "the column that was actually broken was somewhere else "
                "entirely."
            ),
            second=(
                "I pushed the same payload through both readings on your build "
                "and compared what each said about {record_id}: yours prints "
                "`{line}`, which the strict one does not give for that payload "
                "at all."
            ),
            detail="{line}",
        ),
        "the_same_line_twice_on_the_ticket": observation(
            first=(
                "The provider's engineer came back on a ticket this morning "
                "wanting to know whether we had found two problems on that "
                "account or one. The same complaint was printed on it twice, "
                "their side works those lines off one at a time, and the "
                "account went another day without being chased."
            ),
            second=(
                "I read the drop again on your build and counted the lines on "
                "the ticket for {record_id}: `{line}` is printed on it "
                "{times_on_the_ticket} times, and the reading this job has "
                "always done gives it once. Support works that ticket down "
                "line by line."
            ),
            detail="{line}",
        ),
    },
    "nested_and_collection_recovery": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "recovered_block_reported_as_provider_data": observation(
            first=(
                "Finance reconciled the provider's invoice against the columns "
                "we record as theirs and one of them turned out to be our own "
                "standby value. It has been going out as confirmed every night "
                "since August, and the provider has been billing us against it."
            ),
            second=(
                "I read the drop again on your build and opened the ledger row "
                "for {record_id}: `{column}` is sitting in its confirmed "
                "columns, and what we published under it did not all come out "
                "of the file."
            ),
            detail="{column}",
        ),
        "nested_block_discarded_although_part_of_it_read": observation(
            first=(
                "The courier sent back a pallet of undeliverable parcels this "
                "morning. The addresses on them are our placeholder, street "
                "and city and all, even though the provider's file had the "
                "street and the city in it perfectly well. One piece we could "
                "not read and the whole block went in the bin."
            ),
            second=(
                "I read the drop again on your build and looked at the address "
                "we published for {record_id}: the first line of it comes back "
                "as `{line1}`, and the file had the street and the city in it. "
                "Whatever of a block the file did give us has to survive into "
                "what we publish."
            ),
            detail="{line1}",
        ),
        "published_block_is_not_the_block_the_file_gave_us": observation(
            first=(
                "The label printer threw a whole batch of shipping rows out "
                "this morning. What is sitting in the address on them is not "
                "something it can print: no city it recognises, no postcode in "
                "the right shape. Those parcels missed the courier's eleven "
                "o'clock cut-off and are still on the floor."
            ),
            second=(
                "I read the drop again on your build and opened the address on "
                "the row for {record_id}: the postcode on it comes back as "
                "{postcode}, and the block is not the one the file describes. "
                "What goes out under a block is what the file gave us, down to "
                "the standby value where it gave us nothing."
            ),
            detail="{postcode}",
        ),
        "published_list_does_not_match_the_file": observation(
            first=(
                "Finance could not reconcile a batch of invoices: the order "
                "lines in the ledger were not the same list as the provider's "
                "file, element for element and in order. The totals can no "
                "longer be traced back to what the provider sent."
            ),
            second=(
                "I read that drop again on your build and compared the order "
                "lines on the row for {record_id} element by element and in "
                "order. The row has {published_line_count} lines and the "
                "reading owes {line_count_the_reading_owes}; the lists still "
                "do not match, even when their lengths happen to be equal."
            ),
            detail="{published_line_count}",
        ),
    },
    "corrections_fold_into_the_reading": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "corrections_not_folded_into_the_reading": observation(
            first=(
                "Support sent their first round of corrections through the "
                "console yesterday and the console fell over on them. The "
                "provider had already deleted that day's file by then, so "
                "those records are still sitting unpublished with nothing "
                "anybody can do about them."
            ),
            second=(
                "I sent the same correction through on your build and watched "
                "what came back for {record_id}: {problem}. The console has no "
                "other way in, and the file it came from is gone."
            ),
            detail="{problem}",
        ),
        "correction_lost_a_column_that_had_already_read": observation(
            first=(
                "Support fixed two columns on an account yesterday and the "
                "record came out of it worse than it went in. Columns that had "
                "read perfectly well the night before no longer remain as the "
                "same confirmed provider values after the correction."
            ),
            second=(
                "I sent the same correction through on your build and compared "
                "the record for {record_id} before and after: `{column}` had "
                "read cleanly out of the file, but afterwards the reading no "
                "longer carries that same confirmed column and value. A "
                "correction only ever adds to what we already hold."
            ),
            detail="{column}",
        ),
        "correction_overwrote_a_column_that_had_already_read": observation(
            first=(
                "An operator retyped a couple of columns they did not need to "
                "touch while sending a correction, and the values the provider "
                "had actually given us were replaced by what they typed. "
                "Nothing in the record says it happened, and finance bills off "
                "that record."
            ),
            second=(
                "I sent that correction through on your build {arrangement} "
                "and looked at {record_id}: `{column}` had come out of the "
                "file and it now holds what the console sent instead. A "
                "correction has nothing to say about a column that already "
                "read."
            ),
            detail="{column}",
        ),
        "correction_left_the_record_unpublishable": observation(
            first=(
                "Support answered a provider ticket in full yesterday, column "
                "by column, and the account still did not reach the ledger "
                "overnight. It has been dark for three days now, and the "
                "customer has been on to their account manager about invoices "
                "they never received."
            ),
            second=(
                "I sent that correction through on your build {arrangement} and "
                "the record still did not reach the ledger afterwards. Once "
                "support has given us the columns the ticket asked for, that "
                "record is publishable."
            ),
            detail="{arrangement}",
        ),
        "corrected_record_does_not_hold_what_support_sent": observation(
            first=(
                "An operator corrected an address on Tuesday, watched the "
                "console take it, and the parcels went out to the placeholder "
                "anyway. She sent it three times. Support now keeps their own "
                "spreadsheet of what they have corrected, because they do not "
                "believe the console holds it."
            ),
            second=(
                "I sent the correction through on your build {arrangement} and "
                "read the record for {record_id} afterwards: `{column}` does "
                "not hold what support sent for it. What they answer a ticket "
                "with is what the ledger ends up holding."
            ),
            detail="{column}",
        ),
        "corrected_reading_still_shows_the_column_as_a_gap": observation(
            first=(
                "Support answered the provider ticket, sent the corrected "
                "columns through, and the ticket came straight back open the "
                "next morning with the same columns on it. They have sent that "
                "correction three times now and the provider has stopped "
                "replying to us."
            ),
            second=(
                "I sent the correction through on your build and read the "
                "record for {record_id} afterwards: `{column}` came in on the "
                "correction and is still on the ticket. Once support has sent "
                "us a column, that column is held."
            ),
            detail="{column}",
        ),
        "correction_outcome_depends_on_how_it_arrives": observation(
            first=(
                "Two analysts sent the same corrections for the same account "
                "in different shapes yesterday and we ended up with two "
                "different records for it. Support cannot tell me which one "
                "the ledger is holding, and neither can I."
            ),
            second=(
                "I sent the same corrections through on your build two ways "
                "and compared what came out: the record built {arrangement} is "
                "not the record one message produces for {record_id}. Support "
                "sends these in whatever pieces the provider answers in."
            ),
            detail="{arrangement}",
        ),
        "the_earlier_reading_changed_when_the_correction_arrived": observation(
            first=(
                "An analyst discarded a correction result while working an "
                "open ticket. When she continued from the original reading, "
                "it and an untouched copy no longer agreed about the account. "
                "Support could not tell which correction work had actually "
                "been saved."
            ),
            second=(
                "I discarded a correction result on your build and returned "
                "to the original reading for {record_id}. Compared with an "
                "untouched copy, the difference is in {member}. Discarding a "
                "result must not change the reading or what a later correction "
                "produces from it."
            ),
            detail="{member}",
        ),
    },
}
