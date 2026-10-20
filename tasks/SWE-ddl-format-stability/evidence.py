'The owner of the migration formatter, and what she reports after a review.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Selin, a reviewer on the schema team; she runs the formatter over the "
    "migrations directory and reads what comes out — the files, the diffs, and "
    "the per-statement account it prints — not the formatter's code."
)

USER_BELIEF = """I want our migrations formatted so that a pull request which adds a column reads as adding a column. My reviewers are the ones paying for this: we approve schema changes by eye, and today a one-column change and a rewritten table look the same in the diff — one changed line in both cases — so things get waved through that nobody has actually read.

Done means I can run the formatter over the directory, commit the result once, and from then on every migration diff shows only what its author actually changed. And I have to be able to trust it: what a file says after the formatter has been over it must be what it said before."""

OBSERVATION_SCENE = "Migration review"


_DID_NOT_RUN = observation(
    first=(
        "I pointed the formatter at the migrations directory to prepare the clean-up "
        "commit, but the run did not produce a complete formatted directory. I cannot "
        "hand a partial or missing result to my reviewers, so the clean-up is still "
        "blocked."
    ),
    second=(
        "Ran it again from a clean checkout and started checking the result at "
        "`{label}`. The run still did not leave a complete formatted directory that I "
        "can put up for review."
    ),
    detail="{label}",
)


OBSERVATIONS = {
    "schema_semantics_preserved": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "schema_changed": observation(
            first=(
                "I formatted the directory with your build, put it up as one commit and "
                "read it against the originals before approving. One of the tables does "
                "not read as the table its author wrote: what the file declares now is "
                "not what the migration declared before. Approving that would have "
                "changed a live table without anyone asking for it, so I stopped the "
                "merge."
            ),
            second=(
                "Read `{label}` on your build against the copy I kept from before the "
                "formatter went near it. The two still do not describe the same table. "
                "Moving text around inside a file is fine; the table the file describes "
                "has to be the one its author wrote."
            ),
            detail="{label}",
        ),
        "statement_lost": observation(
            first=(
                "The formatted commit did not line up with the originals, so I counted "
                "statements. One migration file comes back with a different count from "
                "the original. I cannot approve a clean-up that changes how many actions "
                "the next deploy will perform."
            ),
            second=(
                "Counted them again by hand, file by file. `{label}` has "
                "{statements_before} statements in the original and does not come back "
                "holding that many. The formatted file has to come back with that same "
                "statement count."
            ),
            detail="{label}",
        ),
        "statement_no_longer_a_table": observation(
            first=(
                "Reading the formatted commit before approving it I found a statement "
                "that used to declare a table but is not read as a table definition any "
                "more. That table never gets created on the next deploy, and the job that "
                "writes to it fails in the middle of the night against a table that is "
                "not there."
            ),
            second=(
                "Formatted the directory once more and went through `{label}` from the "
                "top. Where the replay used to read a table with its columns out of that "
                "file, it now reads no table at all out of the statement that declared "
                "one. Whatever the formatter writes for a table still has to create it."
            ),
            detail="{label}",
        ),
        "formatted_output_unparsable": observation(
            first=(
                "I opened one of the formatted tables to approve it and stopped: what "
                "came back does not read as DDL any more, and the reader gives up part "
                "way through the statement. Anything that picks that file up — the "
                "deploy, the review tooling — falls over on it instead of skipping it."
            ),
            second=(
                "Pulled the formatted copy of `{label}` into an editor and tried to read "
                "it through: the reader still gives up on it, so nothing downstream can "
                "tell what the file is meant to create. Whatever the formatter writes has "
                "to still be a migration we can apply."
            ),
            detail="{label}",
        ),
    },
    "formatting_is_idempotent": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "second_pass_differs": observation(
            first=(
                "We landed the formatted directory as its own commit, and the next "
                "morning the formatter ran again and produced a different directory. So "
                "the next pull request that touched one migration arrived with "
                "reformatting churn on files nobody had edited, and the reviewer could "
                "not tell the schema change from the noise."
            ),
            second=(
                "Ran the formatter over its own output, file by file. `{label}` comes out "
                "different on that second pass. Once a file has been through the "
                "formatter, running it again should leave that file alone."
            ),
            detail="{label}",
        ),
        "output_not_deterministic": observation(
            first=(
                "I formatted the same directory twice from one checkout without changing "
                "the input, and the two runs wrote different files. I cannot commit a "
                "clean-up whose result changes from one run to the next."
            ),
            second=(
                "Repeated the same input twice on your build this morning. `{label}` came "
                "out one way on the first run and another way on the second. The same file "
                "going in has to give the same file coming out every time."
            ),
            detail="{label}",
        ),
        "output_depends_on_input_formatting": observation(
            first=(
                "I put two migrations that describe the same table beside each other, but "
                "the formatter writes them differently because their authors used "
                "different spacing and capitalisation. Reviewers reading the pair think "
                "the schema changed when only its original layout did."
            ),
            second=(
                "Put the pair up on the review screen together: `{label}` and `{partner}` "
                "still come back as different text, and the only difference between the "
                "inputs is spacing and capitalisation. A reviewer reading those two side "
                "by side should see nothing between them at all."
            ),
            detail="{label}",
        ),
    },
    "comments_preserved": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "header_comment_swallows_statement": observation(
            first=(
                "Approving the formatted commit I found a `--` note followed on the same "
                "line by extra text that begins like another SQL statement. The database "
                "treats everything after `--` as commentary, so I cannot trust that the "
                "migration text after the note will run."
            ),
            second=(
                "Ran your build again and went back through the file: in `{label}` a `--` "
                "note still runs straight on into `{swallowed}` on the same line, which "
                "is where the database stops reading. The note has to finish its line "
                "before any migration text resumes."
            ),
            detail="{swallowed}",
        ),
        "line_comment_swallows_code": observation(
            first=(
                "I was approving a formatted migration and found extra text appended to "
                "an author's `--` note on the same line. The database treats that whole "
                "tail as commentary, so the formatted file no longer keeps the note "
                "separate from the migration text around it."
            ),
            second=(
                "Stopped at `{label}` again this morning, at the line beginning "
                "`{comment}`: `{swallowed}` now sits behind it on the same line, where "
                "the database will not read it. Text outside the authored note must not "
                "be appended behind that `--`."
            ),
            detail="{comment}",
        ),
        "block_comment_split_across_lines": observation(
            first=(
                "The formatted commit sent one of the authors' block notes to our review "
                "index as separate fragments. That index works one physical output line at "
                "a time and cannot join continuations, so the reviewer after me read one "
                "fragment as a heading for the wrong column and approved the file on that "
                "reading."
            ),
            second=(
                "Looked at `{label}` again. `{comment}` still occupies more than one "
                "physical output line there. Our review index has no continuation field, "
                "so it cannot bring those lines back as one annotation."
            ),
            detail="{comment}",
        ),
        "comment_lost_or_reordered": observation(
            first=(
                "I listed the notes in a formatted migration beside the original and the "
                "sequence no longer matched. Finance reads those notes to know which "
                "columns their export depends on, so my reviewers cannot rely on a file "
                "whose notes disappear, multiply or move out of order."
            ),
            second=(
                "Listed the notes in the original and in the formatted copy of `{label}` "
                "side by side. They do not match: what comes back is not the same notes "
                "in the same order the author wrote them. Every note an author leaves has "
                "to still be present once and in that order."
            ),
            detail="{label}",
        ),
    },
    "line_width_contract": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "line_over_width_with_break_available": observation(
            first=(
                "The wide tables are still unreadable after formatting. I reviewed one "
                "this morning where a single line runs far past the width the rest of the "
                "directory keeps to, with commas sitting in it between one column and the "
                "next, so a one-column change to that table is still one enormous changed "
                "line."
            ),
            second=(
                "Measured the formatted directory line by line on your build. `{label}` "
                "still holds a line {width} characters long where the directory keeps to "
                "88, and there are commas in it that could have started a new line. A "
                "change to one column of that table should read as one changed line."
            ),
            detail="{label}",
        ),
        "body_indent_wrong": observation(
            first=(
                "One line the formatter indented uses an offset that the rest of the "
                "directory never uses. That avoidable layout change adds noise to the "
                "review and makes the real schema edit harder to find."
            ),
            second=(
                "Took an old migration and its formatted copy into a diff tool. In "
                "`{label}` there is a line sitting at {found_indent} spaces, where the "
                "rest of the directory steps in fours. Every indentation the formatter "
                "introduces has to use that same step."
            ),
            detail="{label}",
        ),
    },
    "explicit_unsupported_handling": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "statement_rows_incomplete": observation(
            first=(
                "The formatter prints a line per statement saying what it did, and I use "
                "that to decide which files still need a human read. On one file that "
                "account no longer lines up one-for-one, in order, with the statements, "
                "so I cannot tell what happened to each of them."
            ),
            second=(
                "Went down the account it printed for `{label}` against the statements "
                "in the file: it does not give me one line for each of the "
                "{statements_in_the_file} statements, in the order they appear. That "
                "account is how I pick the files that still need a human read."
            ),
            detail="{label}",
        ),
        "unsupported_statement_modified": observation(
            first=(
                "One of the statement shapes this formatter has never handled came back "
                "rewritten instead of copied through. The formatter has no reader for that "
                "shape, so I cannot verify that its rewrite is safe; I stopped the merge "
                "and read the authored statement by hand instead."
            ),
            second=(
                "Read that statement again in `{label}`. The one beginning `{opening}` "
                "still has text inside it that differs from what its author typed. A "
                "statement the formatter cannot handle has to come back unchanged inside; "
                "only whitespace surrounding the whole statement may move."
            ),
            detail="{opening}",
        ),
        "unsupported_statement_reported_formatted": observation(
            first=(
                "One of our view migrations mixes plain table definitions with statement "
                "shapes this formatter has never handled, but its account marks one of "
                "those statements as formatted. I use each row to decide what still needs "
                "a human read, so that entry makes an unhandled statement look reviewed."
            ),
            second=(
                "Checked that file's account once more. `{label}` still says "
                "`formatted` for the statement beginning `{opening}`, which the formatter "
                "cannot read as a table at all. The account has to tell me which "
                "statements it left alone, so I know what to read myself."
            ),
            detail="{label}",
        ),
        "supported_statement_reported_unsupported": observation(
            first=(
                "An ordinary table definition was written off as a shape the formatter "
                "does not handle in the account it printed. That account no longer tells "
                "me which ordinary tables the formatter handled, so my reviewers cannot "
                "use it to decide where a manual read is still needed."
            ),
            second=(
                "Went back to it this morning. In `{label}` the statement beginning "
                "`{opening}` is a plain table definition, and the account still calls it "
                "`unsupported`. The account has to say `formatted` for a table definition "
                "the formatter can read."
            ),
            detail="{label}",
        ),
    },
}
