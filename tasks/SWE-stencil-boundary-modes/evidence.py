'Owner persona, belief, and Observation contexts for SWE-stencil-boundary-modes.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Wren, the research engineer who runs the nightly imaging batch; she looks "
    "at the rendered tiles, the mosaic the coastline and terrain teams assemble "
    "from them and the batch console, not at the rendering code."
)

USER_BELIEF = """The 9am mosaic went out with a two-pixel dead frame around the harbour tiles again, and the coastline team can see the seams running straight through the water. They have stopped using this quarter's imagery and gone back to last quarter's, which is the second time this year.

My reading is that the pass leaves the edge of a tile sitting at the fill value whenever the kernel's window runs off it, so what I want is a boundary setting on the pass: on the harbour render, take the index round to the far side of the tile instead of filling zeros.

Done, for me, is a morning where the harbour tiles stitch into the mosaic with nothing showing along the joins, and the other passes that run on that box come back with the same tiles they came back with the night before."""

OBSERVATION_SCENE = "Morning review of the nightly imaging batch"


_BATCH_STOPPED = observation(
    first=(
        "The batch did not get through last night's list. The render log stops part "
        "way down it, so there is no mosaic to hand the teams this morning and no "
        "way for me to say which regions we are missing."
    ),
    second=(
        "I started the harbour night again on your build and it stops there too. The "
        "batch console holds one line where the tiles should be: {error}"
    ),
    detail="{error}",
)


_PASS_RAISED = observation(
    first=(
        "One pass in last night's list came back as an error instead of a tile and "
        "the box moved on without it, so the region it covers is a hole in this "
        "morning's mosaic and the team that works from it has nothing."
    ),
    second=(
        "Ran the list again on your build and it stops in the same place, on {job}, "
        "with the pass raising rather than rendering: {error}"
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "every_cell_is_produced": {
        "candidate_execution_failed": _BATCH_STOPPED,
        "pass_ended_with_an_error": _PASS_RAISED,
        "cells_left_unproduced": observation(
            first=(
                "A tile in last night's list came back with cells the pass never "
                "produced. They still hold what their canvas started with, so that tile "
                "will not match its neighbouring render. I have not isolated which "
                "region it belongs to from this first review."
            ),
            second=(
                "I re-rendered it on your build and counted: {unproduced} cells of {job} "
                "that this pass should produce were never written."
            ),
            detail="{unproduced}",
        ),
        "cell_produced_more_than_once": observation(
            first=(
                "A pass took several times as long as it used to last night and the "
                "console's coverage map shows cells being rendered over and over. On a "
                "full region that is the batch running past its window and into the day."
            ),
            second=(
                "Watched {job} go through on your build: the cell at row {row}, column "
                "{col} was written {writes} times."
            ),
            detail="{writes}",
        ),
        "frame_cell_overwritten": observation(
            first=(
                "A pass's write log includes cells in the plain band it is meant to leave "
                "as the canvas supplied them, all the way round the tile. The final cells "
                "can still look unchanged when the pass writes the same values back, but "
                "the log no longer shows that band being preserved."
            ),
            second=(
                "Re-rendered {job} on your build, the one whose setting reads {modes}: "
                "its write log has {writes} entries at row {row}, column {col} in that "
                "plain band, even if the final cell value is unchanged."
            ),
            detail="{job}",
        ),
        "constant_axis_band_overwritten": observation(
            first=(
                "A region whose config names an edge setting for each direction "
                "separately has write-log entries in the band along one pair of its "
                "sides. That band is meant to keep the canvas cells it started with; "
                "writing the same values back can leave the picture unchanged while "
                "still losing that preservation guarantee."
            ),
            second=(
                "Went back to {job} on your build, whose config reads {modes}: row {row}, "
                "column {col} is in the band the pass should leave alone, and its write "
                "log has {writes} entries there even if the final value is unchanged."
            ),
            detail="{modes}",
        ),
    },
    "boundary_reads_match_the_contract": {
        "candidate_execution_failed": _BATCH_STOPPED,
        "pass_ended_with_an_error": _PASS_RAISED,
        "edge_cell_disagrees_with_the_contract": observation(
            first=(
                "A tile no longer registers against the strip the old renderer produced "
                "for the same ground. Along the edge they share the two disagree cell for "
                "cell, so the mosaic has a seam straight down the join and the terrain "
                "team is back on last quarter's imagery for that whole region."
            ),
            second=(
                "Put the two side by side on your build at row {row}, column {col} of "
                "{job}: yours reads {produced} where the old renderer has {expected}, "
                "with the boundary written as {modes}."
            ),
            detail="{expected}",
        ),
        "out_of_reach_read_not_filled": observation(
            first=(
                "A tile came back carrying values that are nowhere in the ground it "
                "covers. The cells at its edge, where the kernel reaches further than the "
                "tile has cells to give it, come out as numbers that region has never "
                "produced, and the team that works from it has stopped trusting the whole "
                "tile."
            ),
            second=(
                "Looked at {job} on your build at row {row}, column {col}: it renders "
                "{produced} where the strip's own cells come to {expected}."
            ),
            detail="{produced}",
        ),
    },
    "axes_are_mapped_independently": {
        "candidate_execution_failed": _BATCH_STOPPED,
        "pass_ended_with_an_error": _PASS_RAISED,
        "axis_modes_swapped": observation(
            first=(
                "One of the swath bands came back behaving as though its two boundary "
                "rules had been put on the wrong axes, with the rule that belongs east "
                "to west running north to south instead. Everything near the top of the "
                "band is smeared, there is a hard line down the antimeridian, and the "
                "orbit team reads that band every morning."
            ),
            second=(
                "Rendered {job} on your build. The config has the boundary as {modes}, and "
                "the tile that came back is the one this ground gives under {swapped}."
            ),
            detail="{swapped}",
        ),
        "mode_spelling_changes_the_tile": observation(
            first=(
                "Two passes in last night's list were the same job, written out two "
                "different ways in the config because the orbit team keeps both "
                "spellings, and they produced two different tiles. Whichever one we "
                "publish, half the mosaic is built from the one we did not."
            ),
            second=(
                "Compared them on your build at row {row}, column {col} of {job}: one "
                "spelling gives {one_reading} and the other gives {other_reading}."
            ),
            detail="{other_reading}",
        ),
        "corner_cell_disagrees_with_the_contract": observation(
            first=(
                "The four tiles that meet at the corner of the swath do not agree where "
                "they touch. Each one is right through the middle and wrong in the "
                "corner, and that corner sits over the shipping lane, which is the part "
                "the orbit team actually looks at."
            ),
            second=(
                "Read the corner of {job} on your build, row {row}, column {col}: it "
                "renders {produced} where the ground there comes to {expected}."
            ),
            detail="{expected}",
        ),
    },
    "refuses_rather_than_substitutes": {
        "candidate_execution_failed": _BATCH_STOPPED,
        "unusable_mode_setting_produced_a_tile": observation(
            first=(
                "This is what put us in the quarantine review to begin with. A config "
                "came back from batch duty with a boundary nobody recognises, the pass "
                "rendered a tile anyway, and it was four days before we found out the "
                "region had gone into the published mosaic unfiltered."
            ),
            second=(
                "Tried it again on your build: {job} carries {setting} and still comes "
                "back with a tile instead of stopping."
            ),
            detail="{setting}",
        ),
        "out_of_reach_coefficient_read_produced_a_tile": observation(
            first=(
                "The weighted pass whose coefficient table shipped a row short came back "
                "with a tile. It used to stop and tell us, which is how we caught it the "
                "first time; now the region looks plausible and is filtered with numbers "
                "that are not the ones we set."
            ),
            second=(
                "Ran {job} on your build: the kernel asks for row {asked_row} of a table "
                "with {table_rows} rows in it, and the pass renders the tile regardless."
            ),
            detail="{asked_row}",
        ),
        "frame_buffer_cell_type_produced_a_tile": observation(
            first=(
                "A region whose config and whose frame buffer name two different cell "
                "types went through last night and handed a tile over. The box keeps that "
                "buffer so the region survives from one night to the next, so now the two "
                "disagree about what that region is and there is a tile in this morning's "
                "mosaic nobody can say is the cell type the region is published in. The "
                "coastline team has stopped taking that region until we can."
            ),
            second=(
                "Ran {job} again on your build: it hands a tile back in {produced_dtype} "
                "cells, for a region whose config declares {declared_dtype} and whose "
                "frame buffer holds {buffer_dtype}."
            ),
            detail="{produced_dtype}",
        ),
        "frame_buffer_shape_produced_a_tile": observation(
            first=(
                "A region was rendered into a frame buffer that is not the size of its "
                "tile. The returned tile cannot be the region the box handed over, and "
                "the kept region is now out of step with this morning's mosaic."
            ),
            second=(
                "Ran {job} again on your build: its frame buffer is {buffer_shape} and "
                "the tile is {tile_shape}, but the pass still hands a tile back."
            ),
            detail="{buffer_shape}",
        ),
        "refused_job_wrote_before_stopping": observation(
            first=(
                "A pass stopped on a config it could not use and returned no tile, but "
                "its write log is not empty. The rejected attempt had already started "
                "producing cells before it reported the error."
            ),
            second=(
                "Ran {job} again on your build: before it stopped, its write log recorded "
                "{writes} cell writes, starting at row {row}, column {col}."
            ),
            detail="{writes}",
        ),
        "refused_job_left_the_buffer_changed": observation(
            first=(
                "A pass stopped on a config it could not use, which is right, but the "
                "frame buffer the box keeps for that region is not what it was before "
                "the attempt. Tonight's render for that region starts from something "
                "nobody meant to write."
            ),
            second=(
                "Checked the buffer after {job} stopped on your build: row {row}, column "
                "{col} held {kept} before the attempt and holds {found} after it."
            ),
            detail="{found}",
        ),
    },
    "recorded_passes_keep_their_output": {
        "candidate_execution_failed": _BATCH_STOPPED,
        "pass_ended_with_an_error": _PASS_RAISED,
        "declared_dtype_not_kept": observation(
            first=(
                "A tile came back with cells the mosaic service will not take. The job "
                "says what that region's cells are and what arrived is something else, "
                "so the region was turned away at ingest and the night is short a tile."
            ),
            second=(
                "Looked at what {job} handed over on your build: the tile is "
                "{produced_dtype} where the job asks for {declared_dtype}."
            ),
            detail="{produced_dtype}",
        ),
        "frame_buffer_not_updated": observation(
            first=(
                "A pass handed back the current tile but left the frame buffer the box "
                "keeps for that region on the previous night's values. The next night "
                "will start from a different region than the one published today."
            ),
            second=(
                "Checked the kept buffer after {job} on your build: row {row}, column "
                "{col} should hold {expected} from this render and still holds {found}."
            ),
            detail="{found}",
        ),
        "kept_margin_overwritten": observation(
            first=(
                "The region we keep a frame buffer for came back with its margin gone. "
                "That margin is the previous night's render and we do not pay to render "
                "it twice, so this morning the outer band of the region is blank where "
                "there used to be ground."
            ),
            second=(
                "Compared the buffer with what {job} handed back on your build: row "
                "{row}, column {col} held {expected} and comes back {produced}."
            ),
            detail="{expected}",
        ),
        "default_tile_changed": observation(
            first=(
                "One of the passes that has been running untouched for months rendered a "
                "different tile last night. Nobody asked for that region to change, and "
                "the teams read week-over-week differences straight off those tiles."
            ),
            second=(
                "Re-rendered {job} on your build: row {row}, column {col} comes out "
                "{produced} where that pass has always given {expected}."
            ),
            detail="{expected}",
        ),
    },
}
