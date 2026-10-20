'What the copy-desk lead knows and can observe on a delivered sheet.'

from tiganeval.taskkit import observation

USER_PERSONA = "Morgan leads the copy desk. They review the sheet's visible text, toolbar, file dialogs and the desk recorder, without maintaining the component code."
USER_BELIEF = "Tuesday's layout review left too little room for copy because every field had its own toolbar. I want one strip that lets me work on the field I select. I thought giving the field adapters the same container and keeping their callbacks would get us there. The normal desk sequence is in project_records/copy-desk-switch.json; I do not know how the theme's components are wired."
OBSERVATION_SCENE = "Copy desk review of the production sheet"

_STOPPED = observation(
    first="I opened the production sheet and it stopped responding before I could finish the review. The copy team cannot work on this build.",
    second="I opened it again and copied the last message: {error}.", detail="{error}")

OBSERVATIONS = {
    "active_document_commands": {
        "candidate_execution_failed": _STOPPED,
        "command_changed_another_document": observation(
            first="I pressed a formatting control while working on one field and another field changed. I cannot send that copy onward without checking every field again.",
            second="I replayed the desk session. At {label}, the recorder logged {actual_actions} document actions for that press; the original sheet logged {expected_actions}.", detail="{label}"),
        "command_effect_not_conserved": observation(
            first="I used a formatting control and the resulting copy did not match the change I made in the single-field view. The copy review is blocked.",
            second="I repeated {record}. At {label}, the recorder logged {actual_actions} document actions; the original sheet logged {expected_actions}.", detail="{label}"),
    },
    "selection_survives_toolbar_focus": {
        "candidate_execution_failed": _STOPPED,
        "selected_text_changed_differently": observation(
            first="I highlighted a passage and used the toolbar, but the resulting text did not have the formatting from the same gesture in the single-field view. I had to redo that passage.",
            second="I repeated {label}. The document contents after that gesture differ from the recording for {expected_focus}.", detail="{label}"),
        "toolbar_lost_the_edit_range": observation(
            first="I highlighted words and moved into the toolbar to format them. The editing position did not come back as it did in the single-field view, so I had to find my place again.",
            second="I repeated the gesture at {label}. The recorder showed focus on {actual_focus}; the original interaction ended on {expected_focus}. Its {field} entry also differs.", detail="{label}"),
    },
    "theme_tracks_editor_context": {
        "candidate_execution_failed": _STOPPED,
        "image_not_inserted": observation(
            first="I chose an accepted image and it did not appear in the copy. The picture editor could not approve the sheet.",
            second="I selected {file} again at {label}. The sheet logged {actual_actions} insertions; the original interaction logged {expected_actions}.", detail="{file}"),
        "unsupported_image_was_inserted": observation(
            first="The sheet inserted an attachment the field's uploader does not accept. The picture editor had to remove it from the copy.",
            second="I selected {file} again at {label}. That unsupported attachment produced {actual_actions} document actions.", detail="{file}"),
        "image_delivered_to_stale_context": observation(
            first="I chose an image from the toolbar and the resulting copy did not contain the insertion I made in the single-field view. The picture editor could not approve the sheet.",
            second="I repeated the upload of {file} at {label}. The recorder logged {actual_actions} insertions; the original interaction logged {expected_actions}.", detail="{file}"),
        "image_chooser_kept_old_configuration": observation(
            first="I switched fields and opened the image chooser, but its file selection did not match that field's uploader. The picture editor could not select the intended image.",
            second="I opened it again at {label}. That interaction belonged to {expected_owner}, and your sheet opened {actual_dialogs} file dialogs.", detail="{expected_owner}"),
        "image_chooser_unavailable": observation(
            first="I pressed the image button and the file chooser did not open. The picture editor could not attach the photograph.",
            second="I repeated {label} for {expected_owner}. The recorder saw {actual_dialogs} file dialogs.", detail="{label}"),
        "link_input_unavailable": observation(
            first="I pressed the link button and no link input opened. I could not add the citation to the copy.",
            second="I repeated {label} for {expected_owner}. The recorder saw {actual_dialogs} link inputs.", detail="{label}"),
        "link_dialog_opened_in_another_field": observation(
            first="I pressed the link control and did not get the link input for the field I was editing. I could not finish that citation.",
            second="I repeated {label}. The link input belonged to {expected_owner} in the original interaction; your sheet opened {actual_dialogs} inputs.", detail="{expected_owner}"),
        "format_display_described_another_field": observation(
            first="I moved between copy fields and the toolbar's formatting display did not describe the text in front of me. I could not tell which style the next press would change.",
            second="I replayed {record}. At {label}, the most recent document notification came from {source}; the toolbar display differs from the original recording.", detail="{label}"),
    },
    "unavailable_context_is_inert": {
        "candidate_execution_failed": _STOPPED,
        "unavailable_field_was_edited": observation(
            first="A toolbar action changed copy while there was no editable current field. That bypassed the desk's review state.",
            second="I repeated {record}. At {label}, the recorder logged {actual_actions} document actions during that unavailable state.", detail="{label}"),
        "unavailable_field_opened_a_dialog": observation(
            first="The toolbar opened an editing input while there was no editable current field. The reviewer was taken into an interaction they could not use.",
            second="I replayed {label} in {record}; the recorder's {field} entry records the interaction during that unavailable state.", detail="{label}"),
        "controls_did_not_recover": observation(
            first="I returned to an editable field and the toolbar did not carry out the next interaction as it had before. I could not resume the copy review.",
            second="I repeated {label} in {record}. The {field} entry differs from the original interaction after service was available again.", detail="{label}"),
        "availability_display_was_stale": observation(
            first="The toolbar's available controls disagreed with the sheet's current editing state. The reviewer was offered controls they could not use correctly.",
            second="I inspected the strip at {label}. It showed {active_controls} enabled controls in {record}.", detail="{label}"),
        "unowned_toolbar_retained_style": observation(
            first="The current field was gone, but the toolbar still displayed a field's formatting. The reviewer could not tell what the strip was describing.",
            second="I inspected {label} in {record}. The formatting display was still populated with no current field.", detail="{label}"),
    },
    "shared_control_lifecycle": {
        "candidate_execution_failed": _STOPPED,
        "shared_surface_accumulated_widgets": observation(
            first="The sheet accumulated toolbar components as the layout was mounted. The copy area was being consumed again.",
            second="I counted them at {label}: {bars} bars, {pickers} picker wrappers and {image_inputs} image inputs.", detail="{label}"),
        "shared_surface_missing_component": observation(
            first="A toolbar component was missing from the production sheet. I could not use the layout as it appeared in the desk recording.",
            second="I counted the components at {label}: {bars} bars and {pickers} picker wrappers.", detail="{label}"),
        "dynamic_control_did_not_act": observation(
            first="A control on the production sheet did not perform the interaction I made in the desk recording. The layout review stopped there.",
            second="I repeated {label} in {record}. The sheet logged {actual_actions} document actions; the recording logged {expected_actions}.", detail="{label}"),
        "dynamic_control_repeated_action": observation(
            first="One interaction with a production-sheet control ran more than once. I had to undo the extra work before continuing the layout review.",
            second="I repeated {label} in {record}. The sheet logged {actual_actions} document actions; the recording logged {expected_actions}.", detail="{label}"),
        "dynamic_control_used_stale_context": observation(
            first="A control on the production sheet acted with the wrong field context. Its result differed from the same interaction in the desk recording.",
            second="I repeated {label} in {record}. The sheet logged {actual_actions} document actions against {expected_actions} in the recording, but the resulting component or document state differs.", detail="{label}"),
    },
}
