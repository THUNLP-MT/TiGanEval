# Data manifest

What the training mixture is built from and what each validation shard was cut
from. The pipeline team keeps this file; it is the same for every sweep on this
queue.

## Blocks

| Block | Role | Documents |
| --- | --- | --- |
| `web-crawl-a` | training mixture | 4,120,000 |
| `web-crawl-b` | training mixture | 3,880,000 |
| `code-2025` | training mixture | 1,460,000 |
| `forum-threads` | training mixture | 940,000 |
| `news-2025` | reserved | 210,000 |
| `books-1` | reserved | 185,000 |
| `wiki-core` | reserved | 240,000 |
| `reviews-2024` | reserved | 168,000 |
| `news-2026` | reserved | 196,000 |
| `books-2` | reserved | 174,000 |
| `wiki-talk` | reserved | 152,000 |

The mixture is sampled from the four training blocks at the weights in
`mixture.toml` on the training host. Every job in every sweep trains on the same
mixture.

## Validation shards

| Shard | Built from | Documents |
| --- | --- | --- |
| `val-a` | `news-2025` | 8,000 |
| `val-b` | `books-1` | 8,000 |
| `val-c` | `wiki-core` | 8,000 |
| `val-d` | `reviews-2024` | 8,000 |
| `val-e` | `news-2026` | 8,000 |
| `val-f` | `books-2` | 8,000 |
| `val-g` | `wiki-talk` | 8,000 |
| `val-h` | `forum-threads` | 8,000 |

Each shard is eight thousand documents drawn once from its block and frozen.
The `shard_lineage` column of the summary table carries the block name.

## Loader

A job asks the loader for a validation shard by index, not by name; the index
comes from the job's slot in the reservation.

- Loader v2 resolves a shard index against the reserved block list.
- Loader v3 resolves a shard index against the pooled block list. It went on
  the queue on 5 June 2026, day 41 of the summer sweep. The `loader_version`
  column says which loader a job ran under.

The pooled block list is the training block list followed by the reserved block
list, in the order the blocks appear in the table above.
