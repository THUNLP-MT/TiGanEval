'Owner persona, belief, and Observation contexts for SWE-keyset-pagination.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Elif, who leads the mobile app team and consumes the catalogue listing API. "
    "She watches the session recordings the app uploads, the support queue and "
    "what a replay of a recorded scenario prints; she does not read the listing "
    "service's code."
)

USER_BELIEF = (
    "I want a fortnight of restock days where nobody writes in to say they saw a "
    "product on the storefront that never appeared in a complete app scroll. Infinite scroll is the "
    "whole shop on a phone: a customer comes down the list, everything in it goes "
    "past them once, and the list ends when the catalogue ends. These restock "
    "walks add and withdraw products without changing their sort values. Since the restock "
    "job moved to the middle of the working day, support has been taking those "
    "tickets in tens, merchandising has stopped trusting the app to show its own "
    "work, and two of my testers now check the storefront instead. What I can see "
    "is the session recordings, the support queue and the request log the app "
    "writes. Done, for me, is a fortnight like that with no product coming down "
    "the screen twice, no spinner left turning at the bottom of a category, and "
    "merchandising able to put a line back on sale at midday and watch it appear."
)

OBSERVATION_SCENE = (
    "The mobile team's morning look at yesterday's session recordings and the "
    "tickets that came in with them"
)


DID_NOT_RUN = observation(
    first=(
        "One listing rehearsal stopped before its review completed, so I cannot "
        "treat that run as evidence about the listing."
    ),
    second=(
        "The console line from the stopped rehearsal is: {error}. That run needs "
        "to finish before its result can be reviewed."
    ),
    detail="{error}",
)

CATALOGUE_MISSING = observation(
    first=(
        "One complete recorded scroll does not contain every product held by the "
        "catalogue under the requested sort."
    ),
    second=(
        "Under {sort}, {missing_count} catalogue products never reach the screen, "
        "starting with {missing_item}. Compare the complete walk with the catalogue "
        "order in that replay."
    ),
    detail="{missing_count}",
)

CATALOGUE_REPEATED = observation(
    first=(
        "One complete recorded scroll contains a product more than once while its "
        "catalogue is unchanged."
    ),
    second=(
        "In the {sort} walk, {repeated_item} appears {times_delivered} times among "
        "the {rows_delivered} delivered products."
    ),
    detail="{times_delivered}",
)

CATALOGUE_ORDER_MISMATCH = observation(
    first=(
        "One recorded scroll does not agree with the catalogue order for the sort "
        "named by its requests."
    ),
    second=(
        "Under {sort}, the first mismatch is product {position}: the catalogue has "
        "{expected_item} there and the phone was handed {delivered_item}."
    ),
    detail="{position}",
)

SORTLESS_REQUEST_NOT_REFUSED = observation(
    first=(
        "One recorded listing request named no sort and carried no cursor, but did "
        "not return the refusal the app uses for recovery."
    ),
    second=(
        "At {label}, the request named no sort, carried no cursor, and "
        "{offset_shape}. The response was {what_came_back}."
    ),
    detail="{what_came_back}",
)

CURSOR_REQUEST_NOT_REFUSED = observation(
    first=(
        "One recorded request carrying a cursor the app could not use did not "
        "return the refusal the app uses for recovery."
    ),
    second=(
        "At {label}, the cursor-bearing request returned {what_came_back}. Compare "
        "that request in the replay with the app's refusal path."
    ),
    detail="{what_came_back}",
)

OFFSET_WINDOW_MISMATCH = observation(
    first=(
        "One row-counted listing request does not agree with the corresponding "
        "window of the catalogue under the same sort."
    ),
    second=(
        "At {label}, the request asks for the products after row "
        "{offset_asked_for}. The response was {what_came_back}; the catalogue window "
        "starts at {first_product_expected}."
    ),
    detail="{what_came_back}",
)

RESTOCK_REPEAT = observation(
    first=(
        "A product appears more than once in one recorded restock scroll."
    ),
    second=(
        "In that walk, {product} appears {times_delivered} times against a closing "
        "catalogue of {catalogue_rows} products."
    ),
    detail="{times_delivered}",
)

STANDING_PRODUCT_MISSING = observation(
    first=(
        "A product present at both ends of one recorded restock scroll never reaches "
        "the screen."
    ),
    second=(
        "The replay finds {missing_count} such products, including {product}, against "
        "a closing catalogue of {catalogue_rows} products."
    ),
    detail="{missing_count}",
)

RESTOCKED_PRODUCT_MISSING = observation(
    first=(
        "A product marked for delivery after being put back on sale never reaches "
        "the screen in that recorded scroll."
    ),
    second=(
        "The missing restocked product is {product}, recorded as {item_id}. Compare "
        "its insertion point with the pages that follow in the replay."
    ),
    detail="{item_id}",
)

OWN_CURSOR_OUTCOME_MISMATCH = observation(
    first=(
        "A cursor just produced for a list does not provide a usable continuation "
        "when returned under the same sort."
    ),
    second=(
        "At {label}, the service's own cursor was returned under "
        "{sort_asked_for}, and the response was {what_came_back}."
    ),
    detail="{what_came_back}",
)

LIST_ENDED_EARLY = observation(
    first=(
        "A recorded listing request leaves the walk without a usable continuation "
        "while catalogue rows remain."
    ),
    second=(
        "At {label}, the replay records {rows_served} delivered products and "
        "{rows_left} catalogue products still beyond that response."
    ),
    detail="{rows_left}",
)

EXTRA_CONTINUATION = observation(
    first=(
        "A listing response advertises a continuation even though no catalogue rows "
        "follow that response."
    ),
    second=(
        "At {label}, the response carries {rows_served} products and a continuation, "
        "with {rows_left} catalogue products left after it."
    ),
    detail="{rows_served}",
)

PAGE_OVER_CAP = observation(
    first=(
        "One listing response contains more products than the service's configured "
        "page-size cap."
    ),
    second=(
        "At {label}, the request asks for {rows_asked_for} products and the response "
        "contains {rows_served}; the configured cap is {max_page_size}."
    ),
    detail="{rows_served}",
)

PAGE_SHORT_WITH_ROWS_LEFT = observation(
    first=(
        "One listing response is shorter than the requested bounded page even though "
        "catalogue rows remain."
    ),
    second=(
        "At {label}, the request asks for {rows_asked_for} products and receives "
        "{rows_served}, with {rows_left} still behind them and a cap of "
        "{max_page_size}."
    ),
    detail="{rows_served}",
)

PORTABLE_PAGE_MISMATCH = observation(
    first=(
        "A cross-instance continuation does not return the same next page as the "
        "corresponding original-instance request."
    ),
    second=(
        "At {label}, the expected page begins at {first_item_expected} and the fresh "
        "service's page begins at {first_item_served}; their row counts are "
        "{rows_expected} and {rows_served}."
    ),
    detail="{first_item_served}",
)

PORTABILITY_NOT_ESTABLISHED = observation(
    first=(
        "One cross-instance continuation replay does not establish agreement between "
        "the original service and the freshly built service."
    ),
    second=(
        "At {label}, the fresh service's response was {what_came_back}. The replay "
        "did not produce a completed comparison with the corresponding original "
        "instance page."
    ),
    detail="{what_came_back}",
)


OBSERVATIONS = {
    "page_order_matches_catalogue": {
        "candidate_execution_failed": DID_NOT_RUN,
        "products_missing_from_the_list": CATALOGUE_MISSING,
        "products_repeated_in_the_list": CATALOGUE_REPEATED,
        "list_not_in_the_order_asked_for": CATALOGUE_ORDER_MISMATCH,
        "request_without_a_sort_served": SORTLESS_REQUEST_NOT_REFUSED,
        "offset_page_served_the_wrong_products": OFFSET_WINDOW_MISMATCH,
    },
    "scroll_delivers_each_row_once": {
        "candidate_execution_failed": DID_NOT_RUN,
        "product_delivered_twice_in_one_scroll": RESTOCK_REPEAT,
        "product_present_throughout_never_reached": STANDING_PRODUCT_MISSING,
        "restocked_product_never_reached": RESTOCKED_PRODUCT_MISSING,
    },
    "cursor_refusal_contract": {
        "candidate_execution_failed": DID_NOT_RUN,
        "own_cursor_not_honoured": OWN_CURSOR_OUTCOME_MISMATCH,
        "cursor_from_another_sort_honoured": CURSOR_REQUEST_NOT_REFUSED,
        "unreadable_cursor_not_refused": CURSOR_REQUEST_NOT_REFUSED,
        "edited_cursor_honoured": CURSOR_REQUEST_NOT_REFUSED,
        "cursor_without_a_sort_served": CURSOR_REQUEST_NOT_REFUSED,
        "cursor_with_an_offset_served": CURSOR_REQUEST_NOT_REFUSED,
    },
    "page_boundary_honesty": {
        "candidate_execution_failed": DID_NOT_RUN,
        "list_ended_while_products_remained": LIST_ENDED_EARLY,
        "continuation_offered_on_a_finished_list": EXTRA_CONTINUATION,
        "page_larger_than_the_service_serves": PAGE_OVER_CAP,
        "page_shorter_than_the_size_asked_for": PAGE_SHORT_WITH_ROWS_LEFT,
    },
    "cursor_is_self_contained": {
        "candidate_execution_failed": DID_NOT_RUN,
        "second_instance_returned_a_different_page": PORTABLE_PAGE_MISMATCH,
        "cursor_not_recognised_after_a_restart": PORTABILITY_NOT_ESTABLISHED,
    },
}
