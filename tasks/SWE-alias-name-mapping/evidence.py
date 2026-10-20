'Owner persona, belief, and Observation contexts for SWE-alias-name-mapping.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Hanne, the integrations engineer who owns partner payload intake. She reads "
    "the intake log, what a replay of a recorded run prints, the schema partners "
    "fetch before they post, and the tickets partners send back; she does not read "
    "the loader's code."
)

USER_BELIEF = (
    "I want a quarter where a partner can spell a field their own way and nobody on "
    "my side has to do anything about it. Every partner who spells a key differently "
    "gets a configuration of its own today, and last Tuesday one partner's cutover "
    "posted for four hours under both of their spellings at once; finance re-posted "
    "1,900 orders on Wednesday because the totals in the warehouse did not match the "
    "partner's own. What I can see is the intake log -- which posts came through, "
    "which bounced, and what we told the partner when we bounced them -- plus the "
    "schema partners fetch before they post and the tickets they raise. Done, for "
    "me, is a quarter in which a partner onboards on one configuration, nothing "
    "lands in the warehouse under the wrong field, and a partner we bounce can act "
    "on what we sent them without ringing us."
)

OBSERVATION_SCENE = "Integrations review of the intake log after a week of partner posts"


DID_NOT_RUN = observation(
    first=(
        "One of the intake rehearsals stopped before its review completed, "
        "so I cannot treat that run as evidence about the partner posts."
    ),
    second=(
        "The console line from the stopped rehearsal is: {error}. That run needs "
        "to finish before its intake result can be reviewed."
    ),
    detail="{error}",
)

AMBIGUOUS_OUTCOME = observation(
    first=(
        "A post carrying more than one accepted spelling for a field did not leave "
        "the refusal and account that the integrations desk expects."
    ),
    second=(
        "The first such post is {payload_id} from {partner}; it carried {keys} for "
        "one field. Compare that replay's result and trail with the payload."
    ),
    detail="{keys}",
)

ORDINARY_LOAD_OUTCOME = observation(
    first=(
        "A post did not leave the intake outcome called for by its shape and payload."
    ),
    second=(
        "The first post I could not reconcile is {payload_id} from {partner}. The "
        "intake log shows its payload and the outcome together."
    ),
    detail="{payload_id}",
)

ACCEPTED_KEY_OUTCOME = observation(
    first=(
        "A post using a configured spelling did not leave the expected record and "
        "key accounting at intake."
    ),
    second=(
        "For {payload_id} from {partner}, the spelling to trace through the replay "
        "is {key}."
    ),
    detail="{key}",
)

COLLECTED_ACCEPTED_KEY = observation(
    first=(
        "The collecting endpoint kept a configured spelling among the keys it says "
        "intake did not recognise."
    ),
    second=(
        "The first such spelling is {key} on {payload_id} from {partner}; compare "
        "the record body with its collected extras."
    ),
    detail="{key}",
)

STRICT_UNKNOWN_OUTCOME = observation(
    first=(
        "A strict-endpoint post containing an unrecognised key did not produce the "
        "unknown-key outcome shown by the intake contract."
    ),
    second=(
        "The key to trace is {key} on {payload_id} from {partner}; the replay shows "
        "the actual result and trail."
    ),
    detail="{key}",
)

COLLECTED_UNKNOWN_OUTCOME = observation(
    first=(
        "A key and value sent only as an unrecognised extra were not preserved "
        "exactly in the collecting endpoint's extras."
    ),
    second=(
        "The first mismatch is {key} on {payload_id} from {partner}; compare the "
        "posted value with the collected mapping."
    ),
    detail="{key}",
)

INVENTED_UNKNOWN = observation(
    first=(
        "The collecting endpoint reported an extra key that was absent from the "
        "post it was accounting for."
    ),
    second=(
        "The first added key is {key} on {payload_id} from {partner}; compare the "
        "payload with the collected mapping."
    ),
    detail="{key}",
)

COLLISION_OUTCOME = observation(
    first=(
        "A configuration in which two fields claim one incoming key did not produce "
        "the configuration refusal expected at start-up."
    ),
    second=(
        "For {partner}, the fields are {fields} and the shared key is {key}. The "
        "configuration replay shows how start-up ended."
    ),
    detail="{fields}",
)

SELF_KEY_BUILD_OUTCOME = observation(
    first=(
        "A live one-field configuration that repeats one spelling did not reach a "
        "usable loader."
    ),
    second=(
        "The first build mismatch is for {partner} around {key}; its configuration "
        "and console result appear together in the replay."
    ),
    detail="{key}",
)

SELF_KEY_LOAD_OUTCOME = observation(
    first=(
        "A loader built from a live one-field configuration did not reproduce the "
        "planned record for an ordinary post."
    ),
    second=(
        "The first post I could not reconcile is {payload_id} from {partner}; the "
        "replay shows its configured spelling and actual outcome."
    ),
    detail="{payload_id}",
)

CATALOGUE_KEY_OUTCOME = observation(
    first=(
        "For one partner, the published key catalogue does not agree with the keys "
        "intake accepts or with which single spelling is required."
    ),
    second=(
        "The first catalogue entry to compare is {key} for {partner}. The public "
        "catalogue and the replay expose both sides of that disagreement."
    ),
    detail="{key}",
)

CATALOGUE_FRAGMENT_OUTCOME = observation(
    first=(
        "A published key's schema fragment does not agree with the field behind "
        "that key."
    ),
    second=(
        "The first fragment to compare is {key} for {partner}; inspect it beside "
        "the field's published fragment in the replay."
    ),
    detail="{key}",
)

VALUE_FAILURE_OUTCOME = observation(
    first=(
        "A bad-value post did not produce the error-family and trail account that "
        "support expects from that payload."
    ),
    second=(
        "For {payload_id} from {partner}, the value arrived under {sent} and the "
        "reported trail was {reported}; compare both with the replay's outcome."
    ),
    detail="{reported}",
)

SPELLING_LOAD_OUTCOME = observation(
    first=(
        "A post using a spelling supplied by the partner configuration did not "
        "produce the planned record."
    ),
    second=(
        "The first spelling to trace is {key} on {payload_id} from {partner}; the "
        "configuration and replay show how it reached {field}."
    ),
    detail="{key}",
)

DUMP_OUTSIDE_PUBLISHED_KEYS = observation(
    first=(
        "A dumped record contains a key outside that partner's published output-key "
        "set."
    ),
    second=(
        "The first outside key is {key} for {partner}; compare the dump with the "
        "published keys shown in the replay."
    ),
    detail="{key}",
)

DUMP_VALUE_OUTCOME = observation(
    first=(
        "A dumped record does not preserve the complete published record handed to "
        "the output step."
    ),
    second=(
        "The first differing key is {key} for {partner}; compare the record and dump "
        "shown in the replay."
    ),
    detail="{key}",
)

DUMP_SHAPE_OUTCOME = observation(
    first=(
        "One output step did not return a record-shaped result for a partner record."
    ),
    second=(
        "For {partner}, the output ended as {ended_as}. The replay shows the record "
        "that was handed to the output step."
    ),
    detail="{ended_as}",
)


OBSERVATIONS = {
    "single_key_consumption": {
        "candidate_execution_failed": DID_NOT_RUN,
        "two_spellings_one_field_accepted": AMBIGUOUS_OUTCOME,
        "refusal_named_the_wrong_keys": AMBIGUOUS_OUTCOME,
        "missing_required_field_not_refused": ORDINARY_LOAD_OUTCOME,
        "one_spelling_payload_refused": ORDINARY_LOAD_OUTCOME,
    },
    "key_partition_accounting": {
        "candidate_execution_failed": DID_NOT_RUN,
        "alias_key_not_recognised": ACCEPTED_KEY_OUTCOME,
        "alias_collected_as_extra": COLLECTED_ACCEPTED_KEY,
        "unknown_key_not_reported": STRICT_UNKNOWN_OUTCOME,
        "unknown_key_not_collected": COLLECTED_UNKNOWN_OUTCOME,
        "unknown_key_was_invented": INVENTED_UNKNOWN,
    },
    "namespace_validation": {
        "candidate_execution_failed": DID_NOT_RUN,
        "colliding_fields_built_anyway": COLLISION_OUTCOME,
        "collision_refused_outside_the_error_family": COLLISION_OUTCOME,
        "live_config_refused_at_build": SELF_KEY_BUILD_OUTCOME,
        "live_config_refused_every_payload": SELF_KEY_LOAD_OUTCOME,
    },
    "client_contract_agreement": {
        "candidate_execution_failed": DID_NOT_RUN,
        "schema_omits_an_accepted_key": CATALOGUE_KEY_OUTCOME,
        "error_trail_named_an_unsent_key": VALUE_FAILURE_OUTCOME,
        "schema_demanded_one_spelling": CATALOGUE_KEY_OUTCOME,
        "schema_key_typed_unlike_the_field": CATALOGUE_FRAGMENT_OUTCOME,
        "schema_key_published_unlike_the_field": CATALOGUE_FRAGMENT_OUTCOME,
        "schema_published_an_unaccepted_key": CATALOGUE_KEY_OUTCOME,
        "schema_omitted_a_required_key": CATALOGUE_KEY_OUTCOME,
    },
    "alias_derivation": {
        "candidate_execution_failed": DID_NOT_RUN,
        "generated_alias_not_accepted": SPELLING_LOAD_OUTCOME,
        "explicit_alias_was_rewritten": SPELLING_LOAD_OUTCOME,
        "alias_leaked_into_the_output": DUMP_OUTSIDE_PUBLISHED_KEYS,
        "dump_record_disagrees": DUMP_VALUE_OUTCOME,
        "dump_did_not_write_a_record": DUMP_SHAPE_OUTCOME,
    },
}
