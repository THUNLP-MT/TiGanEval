'Owner persona, belief, and Observation contexts for SWE-blend-range-decoding.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Nils, the tooling engineer who runs the overnight catalogue export; he "
    "reads the published pages, the batch log and what the designers send him "
    "when a source file comes back wrong, not the compositor's code."
)

USER_BELIEF = """Four hundred product pages went out on Tuesday with a white box around every shot, merchandising pulled the category, and it is still down. The designers had knocked those backgrounds out with the range sliders in their source files, and our export never looked at them.

What I want is the re-export out this week, with the keyed shots landing on the page the way they land in the design tool and the rest of the catalogue coming back exactly as it is on the pages today. My reading is that each slider is a cut-off on the layer's own grey value: below the dark number or above the light one, the pixel is not drawn. There is a first cut of that in the tree already and I want it finished and shipped.

Done, for me, is merchandising putting the category back up and the studio not sending me anything about the files afterwards."""

OBSERVATION_SCENE = "Morning review of the overnight catalogue export"


_EXPORT_STOPPED = observation(
    first=(
        "The overnight export did not complete, so I do not have a finished batch to "
        "publish or hand back to the studio this morning. The category cannot go back "
        "up from this run."
    ),
    second=(
        "I ran the batch again on your build and it again failed to complete. The last "
        "line returned in place of a finished page list was: {error}"
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "untouched_shots_come_back_unchanged": {
        "candidate_execution_failed": _EXPORT_STOPPED,
        "untouched_render_failed": observation(
            first=(
                "One of the shots nobody has keyed did not produce a usable page plate. "
                "There is no active slider work on it, so this change should not have "
                "made that ordinary shot unpublishable."
            ),
            second=(
                "Ran the untouched set again on your build: {shot}, which has nothing "
                "keyed on it, returned no usable plate and logged: {error}"
            ),
            detail="{shot}",
        ),
        "absent_block_rejected": observation(
            first=(
                "An older shot could not be flattened into a page. One of its layers was "
                "drawn before the tool stored slider work there, and that empty part of "
                "the source file should still be accepted."
            ),
            second=(
                "I picked one of them, {shot}, and put it through your build: it stops on "
                "the {layer} layer, the one with no slider work stored on it, saying "
                "{error}"
            ),
            detail="{layer}",
        ),
        "default_cut_changed_the_plate": observation(
            first=(
                "A shot with no active slider work came back different from the page that "
                "is live. This change was meant to affect the keyed shots, not alter an "
                "untouched part of the catalogue."
            ),
            second=(
                "I put the live page and your build side by side on {shot}, which has "
                "nothing keyed on it: at {at} yours prints {printed} where the page that "
                "is live has {expected}."
            ),
            detail="{at}",
        ),
        "default_block_ignored_opacity": observation(
            first=(
                "An untouched product shot came back heavier than the page that is live. "
                "The layer was already partly transparent and nobody moved its sliders, "
                "but the re-export laid it down as though it were fully opaque."
            ),
            second=(
                "Compared {shot} with the design tool at {at}: your build prints "
                "{printed}, while the tool gives {expected} with the layer opacity "
                "still in effect."
            ),
            detail="{at}",
        ),
    },
    "source_files_survive_the_export": {
        "candidate_execution_failed": _EXPORT_STOPPED,
        "resave_step_failed": observation(
            first=(
                "One of the source files the export opened was not handed back successfully. "
                "The studio cannot safely continue work on that shot until its write-back "
                "completes."
            ),
            second=(
                "I ran the write-back by hand on {shot} on your build and it stops there "
                "as well: {error}"
            ),
            detail="{error}",
        ),
        "absent_block_replaced": observation(
            first=(
                "One of the older source files came back structurally changed: a layer that "
                "stored no range block now carries one. Even an empty replacement is not the "
                "same file the studio handed us."
            ),
            second=(
                "I opened {shot} after running your build: the {layer} layer went in with "
                "no range block and came back with a block in its place."
            ),
            detail="{layer}",
        ),
        "stored_block_length_changed": observation(
            first=(
                "A source file came back with a different amount of stored slider work. "
                "The studio cannot trust that all of its original entries survived, even "
                "when the new block is still a readable shape."
            ),
            second=(
                "Checked {shot} on your build: the {layer} layer went in carrying "
                "{stored_words} words of slider work and came back carrying "
                "{written_words}."
            ),
            detail="{written_words}",
        ),
        "split_handle_collapsed": observation(
            first=(
                "A designer reopened one of her shots after the batch and the soft edge she "
                "spent an afternoon on is a hard line. Her two grips are sitting on top of "
                "each other in the returned file, so that shot needs its positions restored."
            ),
            second=(
                "I opened {shot} myself after running your build: on the {layer} layer a "
                "slider went in with its grips at {stored} and came back with them at "
                "{written}."
            ),
            detail="{written}",
        ),
        "stored_word_changed": observation(
            first=(
                "The files we hand back are not the files we opened. Slider positions have "
                "moved on their own on one of the shots, and now nobody in the studio "
                "trusts what comes out of the overnight run."
            ),
            second=(
                "I diffed {shot} before and after your build: on the {layer} layer a slider "
                "went in at {stored} and came back at {written}."
            ),
            detail="{written}",
        ),
    },
    "backdrop_cuts_read_the_plate_beneath": {
        "candidate_execution_failed": _EXPORT_STOPPED,
        "operand_render_failed": observation(
            first=(
                "One of the shots whose top layer is shaped by the plate beneath it did not "
                "produce a usable plate. That page is not ready to publish from this run."
            ),
            second=(
                "Ran your build on {shot}; its render step returned no usable plate and "
                "logged: {error}"
            ),
            detail="{error}",
        ),
        "backdrop_cuts_ignored": observation(
            first=(
                "The keyed shots do not follow the light and dark pattern of the plate under "
                "their top layer. Areas the design tool leaves exposed are covered on our "
                "page."
            ),
            second=(
                "Compared {shot} with what the tool publishes: at {at} your build prints "
                "{printed} where the tool gives {expected}, with that layer covering ground "
                "it is meant to leave alone."
            ),
            detail="{at}",
        ),
        "under_light_not_applied": observation(
            first=(
                "One of the gel shots is staying visible over the bright end of its "
                "backing plate. The studio pulled down that end of the underneath slider, "
                "and the page is behaving as though that grip were still untouched."
            ),
            second=(
                "Compared {shot} with what the tool publishes: at {at} your build prints "
                "{printed}, while the tool gives {expected} where the bright end of the "
                "plate underneath should take the gel away."
            ),
            detail="{at}",
        ),
        "backdrop_cuts_read_the_layer": observation(
            first=(
                "A designer walked me through a glow that no longer follows what is under "
                "it. Her tool varies the glow with the plate below; our version repeats the "
                "same source tone instead."
            ),
            second=(
                "Ran {shot} against the tool: at {at} your build prints {printed} and the "
                "tool gives {expected}; the visible pattern does not follow the plate below."
            ),
            detail="{at}",
        ),
        "backdrop_is_not_the_plate_beneath": observation(
            first=(
                "A three-layer shot no longer follows the plate built by its lower layers. "
                "Its glow lines up with the original empty frame instead of the result the "
                "design tool shows."
            ),
            second=(
                "Ran {shot} beside the tool: at {at} your build prints {printed} against "
                "the tool's {expected}, as though what is under that layer were still the "
                "empty frame the shot started from."
            ),
            detail="{at}",
        ),
        "layer_cuts_read_the_backdrop": observation(
            first=(
                "A layer with work on both sides of its range does not match the tool: the "
                "parts selected by the layer and by the plate beneath are landing in the "
                "wrong areas."
            ),
            second=(
                "Put {shot} next to the tool: at {at} your build prints {printed} where the "
                "tool gives {expected}; the two visible selection patterns do not line up."
            ),
            detail="{at}",
        ),
        "range_work_skipped_below_top_layer": observation(
            first=(
                "A stacked shot still has part of its surround showing through. The range "
                "work on the upper layer is landing, but the keyed layer lower in the "
                "stack looks exactly as it did before the designers cut it."
            ),
            second=(
                "Put {shot} beside the design tool: at {at} your build prints {printed} "
                "where the tool gives {expected}; the keyed layer below the top of the "
                "stack has not been cut."
            ),
            detail="{at}",
        ),
        "operand_weight_wrong": observation(
            first=(
                "The shots where a layer comes through what is under it still do not match "
                "the tool. Those are the shadows and the glows, and on the page their edges "
                "land in the wrong places, which is what the studio notices first."
            ),
            second=(
                "Went through {shot} pixel by pixel against the tool: at {at} your build "
                "prints {printed} where the tool gives {expected}."
            ),
            detail="{at}",
        ),
    },
    "split_grips_fade": {
        "candidate_execution_failed": _EXPORT_STOPPED,
        "fade_render_failed": observation(
            first=(
                "One of the knockout shots did not produce a usable page plate. Without that "
                "shot the category is not ready to go back to merchandising."
            ),
            second=(
                "I ran {shot} on your build; its render step returned no usable plate and "
                "logged: {error}"
            ),
            detail="{error}",
        ),
        "split_grips_stepped": observation(
            first=(
                "A shot with separated grips has a hard jagged outline instead of the soft "
                "edge in the design tool. That edge is why the designers dragged the grips "
                "apart in the first place."
            ),
            second=(
                "Put {shot} beside what the tool publishes: at {at} your build prints "
                "{printed} against the tool's {expected}, and the whole edge falls away in "
                "one step instead of coming down across it."
            ),
            detail="{at}",
        ),
        "fade_shape_wrong": observation(
            first=(
                "The knocked-out edge has changed, but it still is not the edge stored in the "
                "source file. A designer laid our page over her own export and the two do "
                "not sit on top of each other."
            ),
            second=(
                "Did the same with {shot}: at {at} your build prints {printed} where the "
                "tool gives {expected}."
            ),
            detail="{at}",
        ),
    },
    "entries_address_declared_channels": {
        "candidate_execution_failed": _EXPORT_STOPPED,
        "channel_render_failed": observation(
            first=(
                "A shot with colour-specific slider work did not produce a usable plate, so "
                "that product page is not ready to publish from this run."
            ),
            second=(
                "Ran {shot} on your build; its render step returned no usable plate and "
                "logged: {error}"
            ),
            detail="{error}",
        ),
        "composite_entry_applied_to_a_colour_channel": observation(
            first=(
                "A logo with both brightness and colour slider work came back with the wrong "
                "regions removed. Its colour pattern no longer matches the design tool."
            ),
            second=(
                "Ran {shot} against the tool: at {at} your build prints {printed} where the "
                "tool gives {expected}; the brightness and colour selections do not land on "
                "the same regions as the tool's."
            ),
            detail="{at}",
        ),
        "transparency_entry_applied": observation(
            first=(
                "The soft-edged logos have come back nearly gone from the page. They are "
                "the layers drawn with transparency in them, and whatever we are doing to "
                "them takes the layer away rather than shaping it."
            ),
            second=(
                "Compared {shot} with the tool: at {at} your build prints {printed} where "
                "the tool gives {expected}, on a layer whose transparency is what does the "
                "disappearing."
            ),
            detail="{at}",
        ),
        "unaddressed_entry_applied": observation(
            first=(
                "A press proof from the newer studio release differs from the design tool. "
                "Its source block contains more entries than the layer has named channels, "
                "and the returned plate changes where the tool's does not."
            ),
            second=(
                "Compared {shot} with the tool: at {at} your build prints {printed} where "
                "the tool gives {expected}; this is on a layer whose stored entries run past "
                "its named channels."
            ),
            detail="{at}",
        ),
        "colour_entries_not_applied": observation(
            first=(
                "The shots keyed on brightness look right now and the ones keyed on a "
                "colour have not moved at all. The colour-keyed part of the catalogue is "
                "still producing the same unwanted regions as before."
            ),
            second=(
                "Ran {shot} beside the tool: at {at} your build prints {printed} against "
                "the tool's {expected}, with the colour the designer keyed on making no "
                "difference to what gets drawn."
            ),
            detail="{at}",
        ),
        "composite_entry_not_applied": observation(
            first=(
                "It is the other way round on the plates the logos sit on: the colour "
                "keying is landing and the brightness keying has stopped working. The "
                "resulting logo plates come out muddy."
            ),
            second=(
                "Put {shot} next to the tool: at {at} your build prints {printed} where the "
                "tool gives {expected}, and the grey cut on that layer is doing nothing."
            ),
            detail="{at}",
        ),
        "channel_weight_wrong": observation(
            first=(
                "The shots with per-colour keying still do not match what the designers see "
                "in their tool. The colour-selected regions are still off on the page."
            ),
            second=(
                "Went through {shot} against the tool: at {at} your build prints {printed} "
                "where the tool gives {expected}."
            ),
            detail="{at}",
        ),
    },
}
