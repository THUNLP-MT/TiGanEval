'Owner persona, belief, and Observation contexts for SWE-schema-locked-inference.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Dani, the support lead who fields the scoring tickets; they read what customers, "
    "the app team, and the data team report, and can re-run the recorded runs under "
    "project_records/, but they do not read the pipeline code."
)

USER_BELIEF = (
    "Customers read their score in the app and again on the statement the nightly "
    "batch produces, and this week those two numbers stopped agreeing for the same "
    "person. My team cannot answer a ticket when one record has two answers. What I "
    "want is that one customer record means one score, whichever system it arrived "
    "through and whatever shape it arrived in, and that a record we cannot honestly "
    "score comes back as a rejected request instead of a number my team then has to "
    "defend. Done, for me, is a week of scoring tickets in which nobody has two "
    "scores and nobody has a score we cannot explain."
)

OBSERVATION_SCENE = "Scoring ticket review"


_DID_NOT_RUN = observation(
    first=(
        "The data team tried to refresh the model on your build this morning and it "
        "stopped before it trained anything at all: no run, no files, nothing for my "
        "team to check a ticket against. We are still quoting scores from the model "
        "that was already deployed."
    ),
    second=(
        "They started it again and pasted what came back. There is no timeline to "
        "read: not one step returned a result, and what came out of the run of "
        "pipeline/pipeline.py instead is {error_text}. Nobody here can say which part "
        "of it went wrong."
    ),
    detail="{error_text}",
)


OBSERVATIONS = {
    "persisted_schema_completeness": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "baseline_fit_failed": observation(
            first=(
                "The data team's nightly training did not produce a model last night. It "
                "stopped partway through the same settings we have been running for "
                "months, so nothing downstream was refreshed and every score my team "
                "quoted today came from a model that is a day stale."
            ),
            second=(
                "They started it again on your build with exactly the settings the "
                "nightly job uses: "
                "target=target, record_id excluded, drop_constant and drop_duplicate on. "
                "It stops at {step} with {error}."
            ),
            detail="drop_constant",
        ),
        "schema_artifact_missing": observation(
            first=(
                "A customer disputed their score and I asked the data team what the model "
                "had actually been trained on. Nobody could answer from the finished run. "
                "We have nothing to show the customer and nothing to show compliance."
            ),
            second=(
                "I went through what the last run left behind, one file at a time. It left "
                "{left}. There is no feature_schema.json in the run directory at all, so "
                "nothing the run wrote records what a raw record has to become before the "
                "model sees it."
            ),
            detail="feature_schema.json",
        ),
        "description_artifact_missing": observation(
            first=(
                "A reviewer asked me for the summary of last night's training and there "
                "was nothing to send them. The run finished, but the readable account of "
                "what it did was not in the folder the data team hands over."
            ),
            second=(
                "I listed the folder myself. The run left {left}, and no description.json, "
                "which is the one file in there a person can actually open. Every question "
                "about that run now has to come back to you."
            ),
            detail="description.json",
        ),
        "model_artifact_missing": observation(
            first=(
                "The data team went to deploy last night's run and there was nothing to "
                "deploy. The training reported that it had finished, and yet what it left "
                "behind cannot score a single customer."
            ),
            second=(
                "I had them list the folder. It holds {left} and no model.json at all, so "
                "whatever that run learned did not survive the end of it. Serving is still "
                "on the model from the night before."
            ),
            detail="model.json",
        ),
        "schema_artifact_incomplete": observation(
            first=(
                "The data team could not use the feature file from the finished run to "
                "rebuild what the model reads. The file does not form a usable contract "
                "for this build, so reviewing a disputed score still means coming back to "
                "you rather than reading the run."
            ),
            second=(
                "I asked them to check it against what this build can use. The comparison "
                "stops here: {problem}."
            ),
            detail="{problem}",
        ),
        "schema_encoding_disagrees_with_scoring": observation(
            first=(
                "The feature file and the scoring run give two different accounts of what "
                "an unfamiliar category becomes before it reaches the model. That leaves "
                "the data team unable to reproduce or explain the score from the run's "
                "own artifacts."
            ),
            second=(
                "I had them compare the file with the model-input record for {feature}. "
                "feature_schema.json declares {declared_unknown} for an unfamiliar value, "
                "but the scoring call put {model_input} in that feature's position."
            ),
            detail="{feature}",
        ),
        "description_disagrees_with_schema": observation(
            first=(
                "Two people reviewing the same training run came to different conclusions "
                "about which columns the model reads, because the files that run left tell "
                "two different stories. My team cannot quote one of them to a customer "
                "without knowing which."
            ),
            second=(
                "I had them read the two files from the last run side by side. "
                "description.json, the one a person actually opens, says the model reads "
                "{description_input_features}, while the feature file written beside it "
                "says {schema_input_features}. Both came out of the same training."
            ),
            detail="description.json",
        ),
        "schema_does_not_describe_model_input": observation(
            first=(
                "The data team tried to rebuild a disputed score by hand from what the run "
                "recorded and could not: what the run says the model reads does not add up "
                "to the model that is deployed. Checking one score means retraining."
            ),
            second=(
                "They counted it out on the last run. model.json carries {model_weights} "
                "weights, and the list of input columns the same run recorded has "
                "{schema_width} names on it. Nobody can rebuild a score by hand out of "
                "two different widths."
            ),
            detail="model.json",
        ),
        "model_artifact_not_fitted": observation(
            first=(
                "The data team could not reconcile the model file from a finished run with "
                "that run's training timeline. The run therefore cannot show that the "
                "scorer it left is the one its recorded training supports."
            ),
            second=(
                "They repeated the comparison from the training timeline into model.json. "
                "It first becomes irreconcilable at {model_component}: {model_issue}."
            ),
            detail="{model_component}",
        ),
        "export_failed_at_baseline": observation(
            first=(
                "The team that pulls our exported model every night got nothing again. The "
                "step that produces it stopped, so their load had no model to work from and "
                "they spent the day calling our endpoint row by row instead."
            ),
            second=(
                "I had the data team run just that step on the last training. The step the "
                "run calls export-baseline stops with {error}, so there is no export for "
                "them to pull at all."
            ),
            detail="export-baseline",
        ),
        "export_disagrees_with_schema": observation(
            first=(
                "The team that consumes our exported model found that its stated input "
                "width does not agree with the feature file from the same run. They cannot "
                "tell which shape to build and have stopped loading the export."
            ),
            second=(
                "I had both numbers pulled from the same run. What the export reports as "
                "its input_width is {export_width}, and the run's own feature file names "
                "{schema_width} input columns. Anyone integrating the export is sizing "
                "against a number the run itself contradicts."
            ),
            detail="input_width",
        ),
        "export_lists_different_features": observation(
            first=(
                "The team that consumes our exported model found two different column lists "
                "in the same run. The counts agree, so they cannot tell which alignment is "
                "the one the model actually reads and have stopped loading the export."
            ),
            second=(
                "I had them read the export against the run's own feature file. The export "
                "names {exported_features}; the feature file the same run wrote names "
                "{schema_features}. The count matches, so nothing warned them, and that is "
                "still not the list the model reads."
            ),
            detail="{exported_features}",
        ),
        "schema_drop_record_wrong": observation(
            first=(
                "A reviewer compared the warehouse columns with the feature file from the "
                "same run, and its account of what entered the model and what was left out "
                "does not add up. We cannot use that file to explain a disputed score."
            ),
            second=(
                "I had the data team compare the training frame and its configuration with "
                "feature_schema.json. The classification is inconsistent around {columns}; "
                "the same file cannot truthfully use those names as its input and drop "
                "record."
            ),
            detail="{columns}",
        ),
    },
    "consistent_inference_across_consumers": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "consumer_call_failed": observation(
            first=(
                "One of the scoring paths stopped with an error on a customer record instead "
                "of returning an answer. The system using that path could not complete its "
                "work, and support had no score from it to explain."
            ),
            second=(
                "I re-ran the recorded scoring paths on your build and watched where they "
                "stop. {label} comes back as {error}. Those five rows are one customer sent "
                "in the shapes our systems actually use; some carry amount_copy where "
                "others carry amount."
            ),
            detail="{error}",
        ),
        "consumer_inputs_disagree": observation(
            first=(
                "The data team compared what the model was handed for one customer through "
                "the scoring paths and found at least two different rows of numbers. The "
                "same record is reaching the model differently depending on who asks."
            ),
            second=(
                "I had them put the model_input_rows for that one request side by side. The "
                "rows built by {paths} are still not the same, so which number we quote "
                "depends on which system asked for it."
            ),
            detail="model_input_rows",
        ),
        "consumer_predictions_disagree": observation(
            first=(
                "Support has a customer holding different numbers from two scoring paths for "
                "the same record and week. We promised to tell them which number is theirs "
                "and still cannot."
            ),
            second=(
                "I put the answers for that one record next to each other: {answers}. "
                "predict returns the number itself, evaluate reports mean_prediction, and "
                "the endpoint puts prediction in its body, and for one customer there is "
                "one right answer."
            ),
            detail="mean_prediction",
        ),
        "consumer_prediction_not_from_model": observation(
            first=(
                "A scoring path returned a number that the model saved in the same run does "
                "not produce from the row that path recorded. The paths may agree with one "
                "another, but that number is not the fitted model's answer."
            ),
            second=(
                "I had the data team replay {label} from its recorded model input. The path "
                "returned {returned}; model.json applied to that same row returns "
                "{model_prediction}."
            ),
            detail="{label}",
        ),
        "request_form_changes_input": observation(
            first=(
                "The data team found that the model input changes depending on which system "
                "shaped a customer's record, although nothing about the customer changed. "
                "Support cannot rely on a score built from a sender-dependent input."
            ),
            second=(
                "I sent one customer through in each of the shapes our systems actually use "
                "and had the model inputs written down: {sent} shapes went in, {shapes} "
                "different rows reached the model. Those shapes differ only in things that "
                "are not the customer, down to an extra unrelated_column the model never "
                "trained on."
            ),
            detail="unrelated_column",
        ),
        "training_scoring_inputs_disagree": observation(
            first=(
                "The data team compared the model-input records made during training with "
                "those same records scored again from the finished run, and the two sides "
                "do not establish the same fitted rows. Even agreeing caller paths cannot "
                "show they use the fitted space when that comparison fails."
            ),
            second=(
                "I had them repeat the training-to-scoring comparison. The measured point "
                "where it fails is this: {input_difference}."
            ),
            detail="{input_difference}",
        ),
        "export_disagrees_with_consumers": observation(
            first=(
                "The team that took our exported model found that its stated input width "
                "does not match the row a scoring path actually builds. They cannot use the "
                "export contract to construct the same model input as production."
            ),
            second=(
                "I had them compare the shape rather than the numbers. What the export "
                "reports as its input_width is {export_width}, while the row the endpoint "
                "actually builds for a request comes to {consumer_width}. Anything built on "
                "the export is scoring a differently shaped input from production."
            ),
            detail="input_width",
        ),
    },
    "schema_violation_refusal": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "missing_source_not_refused": observation(
            first=(
                "A record reached us with no amount on it at all and came back with a score "
                "anyway. Support quoted that number to the customer before anyone noticed "
                "there was nothing behind it, and we have had to withdraw it."
            ),
            second=(
                "I sent that record through your build again. It carries neither amount nor "
                "amount_copy, so there is no column on it the model can read an amount "
                "from, and what comes back is still {returned}."
            ),
            detail="neither amount nor amount_copy",
        ),
        "conflicting_sources_not_refused": observation(
            first=(
                "One customer's record carried the same piece of information through two "
                "different source columns, and their values did not agree. It was scored "
                "anyway, and support has already quoted that number to the customer."
            ),
            second=(
                "I looked at that record again. Its two sources for one piece of information "
                "do not agree: {stated}. Nobody here can say which value is the customer's, "
                "and what came back for it is {returned} all the same."
            ),
            detail="{stated}",
        ),
        "refusal_missing_column_names": observation(
            first=(
                "The pipeline turned a record down without identifying every source involved. "
                "The team that sent it cannot determine the complete correction from that "
                "refusal and has had to bring the record to support."
            ),
            second=(
                "I collected the last few turn-downs. The whole of what comes back for "
                "{label} is {message}, which does not identify every source involved. The "
                "columns actually at fault on that record are {columns}."
            ),
            detail="{columns}",
        ),
        "model_ran_on_refused_input": observation(
            first=(
                "The data team noticed the pipeline is doing the scoring work for records "
                "it then turns down. On a heavy morning we pay for every one of those and "
                "the record is refused at the end of it anyway."
            ),
            second=(
                "I looked at what the run recorded for a record it refused. There are "
                "model_input_rows for {label}, so the row was built and handed to the model "
                "before anything decided to refuse it."
            ),
            detail="model_input_rows",
        ),
        "known_input_wrongly_refused": observation(
            first=(
                "A scoring request the fitted schema can represent was turned away because "
                "one of its category values simply had not appeared in the training rows. "
                "A new value is not a broken record, so this request should not have been "
                "refused."
            ),
            second=(
                "I put that record back through your build myself. Its {category_column} is "
                "{category_value}, a value absent from the training rows, and what comes "
                "back is {error}. The request was turned away rather than receiving a "
                "score."
            ),
            detail="{category_value}",
        ),
        "invalid_specification_accepted": observation(
            first=(
                "A training run received a feature configuration that could not establish a "
                "valid feature selection, but it trained a model anyway. The data team "
                "cannot approve that run for scoring because its requested inputs were "
                "never valid."
            ),
            second=(
                "I had them repeat the configuration the failed run used. The one labelled "
                "{label} has a feature selection that {complaint}, but it produced a model "
                "anyway. A configuration like that has to be turned down before a model "
                "exists."
            ),
            detail="{complaint}",
        ),
        "model_ran_on_invalid_specification": observation(
            first=(
                "The data team found that a feature configuration the pipeline ultimately "
                "refused had already reached model fitting. That leaves model work and state "
                "behind a training request that was never valid."
            ),
            second=(
                "I checked the rejected training operation labelled {label}. Its selection "
                "{complaint}, and the same operation still contains a recorded Model.fit "
                "call before it ends."
            ),
            detail="{label}",
        ),
    },
    "caller_contract_error_reporting": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "serve_raised_instead_of_reporting": observation(
            first=(
                "The app team paged us: their scoring calls were coming back as failures "
                "rather than as answers. On their side that reads as our service being "
                "down, so they opened an incident and stopped sending us traffic."
            ),
            second=(
                "I looked at which calls do it. {label} in the drill comes back as {error} "
                "instead of an answer, and their client cannot tell that apart from us "
                "being down. The endpoint has to answer every request it is given, "
                "including the ones it will not score."
            ),
            detail="{label}",
        ),
        "serve_failed_valid_request": observation(
            first=(
                "An endpoint call ended as a service failure instead of returning the response "
                "object the app consumes. The app team received no status or body, so they "
                "could not distinguish the request outcome from an outage."
            ),
            second=(
                "I repeated {label} on the last run. It ended with {error} and returned no "
                "endpoint response for the request carrying {request_columns}."
            ),
            detail="{error}",
        ),
        "serve_scored_a_refusable_record": observation(
            first=(
                "The app showed a customer a score for a record we should never have put a "
                "number on, because our endpoint answered that request exactly as it "
                "answers a good one. My team then had to tell that customer the figure was "
                "not real."
            ),
            second=(
                "I sent it through the endpoint on your build again. {label} comes back as "
                "status 200, "
                "the same answer a record we can score gets, so nothing on the app's side "
                "can tell the two apart."
            ),
            detail="status 200",
        ),
        "serve_status_wrong": observation(
            first=(
                "The app team is treating our rejections as outages. Their client retries "
                "anything that is not a clean rejection, so one unusable record turns into "
                "a retry storm against us and the customer still gets nothing."
            ),
            second=(
                "I checked what their client keys off. A record we cannot score has to come "
                "back as status 400; that is what tells their side the request was wrong "
                "rather than the service. What {label} comes back as is {status}."
            ),
            detail="status 400",
        ),
        "serve_detail_missing_columns": observation(
            first=(
                "The app team gets a rejection that does not identify every source involved. "
                "They cannot determine the complete correction from the response and end up "
                "with support because part of the record problem is still hidden."
            ),
            second=(
                "I read the body they get back for {label}. It says {body_detail} and stops "
                "there. For that record the columns at fault are {columns}, and "
                "that is what has to reach the sender."
            ),
            detail="{columns}",
        ),
        "evaluate_did_not_refuse": observation(
            first=(
                "The nightly evaluation report came out with a number for a record that "
                "could not be turned into a defensible model input. That number went into "
                "the weekly figures, and we only found it because a customer disputed one."
            ),
            second=(
                "I traced one of them back. For {label} the evaluation ran to the end and "
                "put {returned} into the report instead of stopping, so a record we cannot "
                "honestly score reads there as though it scored normally."
            ),
            detail="{returned}",
        ),
        "refusal_wrong_exception_type": observation(
            first=(
                "The data team's caller received an ordinary pipeline failure for a record "
                "the schema was supposed to refuse. Their job treats that as a broken build "
                "instead of a bad record, so one input stopped the queue behind it."
            ),
            second=(
                "I had them repeat the call and read the failure type. {label} came back as "
                "{error_type}, not the SchemaError their caller handles as a refusal."
            ),
            detail="{error_type}",
        ),
        "serve_rejected_valid_request": observation(
            first=(
                "The endpoint is turning away live traffic it can score. The app team is "
                "seeing customers refused mid-session on records that look completely "
                "ordinary to them, and those customers come straight to support."
            ),
            second=(
                "I sent the shapes our systems actually post through the endpoint, one at a "
                "time. {label} does not come back with a score, and the record it was given "
                "carries {request_columns}, which is everything the model needs to score "
                "that customer."
            ),
            detail="{request_columns}",
        ),
    },
    "stable_artifact_reuse": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "artifacts_not_reproducible": observation(
            first=(
                "We could not confirm that the model running in production is the model the "
                "data team thinks they built. They rebuilt it from the same data with the "
                "same configuration and the files came out different, so there is nothing "
                "to compare against."
            ),
            second=(
                "I had them run it twice back to back on your build, the two the drill "
                "calls "
                "artifacts-first and artifacts-second, over the same rows with the same "
                "configuration. What came out is not the same file set: the two runs differ "
                "in {differing_artifacts}."
            ),
            detail="artifacts-first",
        ),
        "schema_depends_on_row_order": observation(
            first=(
                "The data team repeated a run after the warehouse changed only the order "
                "of its rows, and the feature schema came out different. They cannot treat "
                "that file as a stable account of the run when an arrival-order accident "
                "changes it."
            ),
            second=(
                "I went back to the drill for this one. It has a run that feeds exactly the "
                "same rows in a different order, artifacts-shuffled, and the {artifact} it "
                "records still differs from the run before it. Row order is an accident of "
                "how the warehouse exported that night."
            ),
            detail="artifacts-shuffled",
        ),
        "model_depends_on_row_order": observation(
            first=(
                "The data team rebuilt from the same training records and targets after "
                "only their arrival order changed, and the fitted model came out different. "
                "That makes a warehouse ordering accident change customer scores."
            ),
            second=(
                "I compared the ordinary run with {label}. Both contain the same records "
                "and target values, but the {artifact} they leave is different after the "
                "rows are reordered."
            ),
            detail="{label}",
        ),
        "unsupported_artifact_version_accepted": observation(
            first=(
                "A run directory from a different build was accepted by one of its consumers "
                "even though its layout is not one this build supports. Anything downstream "
                "from that output is suspect because this build cannot interpret that run "
                "under its own contract."
            ),
            second=(
                "I had the drill carry on from a run directory whose feature schema says it "
                "was written to the version 99 layout, which is not the one this build "
                "reads. {label} worked from it anyway and came back with {used}."
            ),
            detail="version 99",
        ),
        "unversioned_artifacts_accepted": observation(
            first=(
                "Nobody can tell which build produced a given run directory. One that had "
                "been sitting around was accepted by a consumer and produced output before "
                "anyone noticed it could not be identified as the current layout."
            ),
            second=(
                "I went through what the drill hands on. That run directory has no "
                "feature_schema.json in it at all, and {label} took it and answered from it "
                "regardless. This build reads version 2, and it has to be able to tell that "
                "a directory was written for it."
            ),
            detail="version 2",
        ),
        "artifact_refusal_wrong_exception_type": observation(
            first=(
                "The data team tried to read a run directory this build could not identify "
                "or use, and the consuming job reported a software failure instead of the "
                "known schema refusal. They stopped the remaining runs unnecessarily."
            ),
            second=(
                "They repeated the read and checked the failure type. {label} came back as "
                "{error_type}, not the SchemaError their job handles as an incompatible run."
            ),
            detail="{error_type}",
        ),
        "serve_artifact_refusal_wrong": observation(
            first=(
                "The app team tried to score from a run this build cannot read and their "
                "client treated our answer as an outage. It retried the same run directory "
                "until support stopped the traffic."
            ),
            second=(
                "I checked the endpoint response for {label}. It came back as {status}; an "
                "incompatible run has to be a status 400 rejection so the app does not retry "
                "it as a service failure."
            ),
            detail="{status}",
        ),
    },
}
