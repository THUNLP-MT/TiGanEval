# Validation lots, marketplace search

Kept by the data platform on-call rota. One line a change.

- `v-2f9c` — built 11 May from the April query sample. 32,800 judged rows.
  Default lot for ranking evaluation from 11 May.
- `v-1c07` — built 2 February from the January query sample. 11,800 judged rows.
  Retired 14 June when the June crawl landed; the rows were not kept, so the lot
  cannot be rebuilt and the desk will not score on it.
- `v-8b41` — built 12 June from the June crawl. 32,800 judged rows. Same query
  mix as `v-2f9c` by intent; the judging pass was re-run from scratch because
  the June crawl changed which documents the queries return. Default lot for
  ranking evaluation from 17 August.

Both open lots are scored in eight passes of 4,100 rows each. The desk serves
the passes in order and will not sell a ninth pass of a lot.

August ranking campaign: runs r01 to r04 finished before the 17th and went
through the automatic evaluation on `v-2f9c`. Runs r05 to r08 finished after and
went through on `v-8b41`. The switch was the rota's, not the campaign's.

`trainer_version` moved from 2.7.1 to 2.8.0 on 23 August, in the middle of the
`v-8b41` group. No lot was built, retired or re-judged that week.
