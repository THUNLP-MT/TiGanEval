# Tile rendering for the nightly imaging batch

`tilekit/` renders one raster tile per job. The batch box runs a list of jobs
each night, hands every rendered tile to the mosaic service, and the mosaic
service stitches the tiles of a region into one image the coastline, terrain
and swath teams work from.

- `tilekit/contract.py` ships in the mosaic service's release and is shared
  with the legacy renderer this package replaced, so it stays as it is. It owns
  `Grid` and `Canvas`, the boundary vocabulary `MODES` and `map_index`, the
  window types and `infer_window`, the kernel library `KERNELS`, the job-config
  reader `load_job`, and `trace_writes`.
- `tilekit/sweep.py` is ours: `run(spec, operands, out=None)`, the pass itself.
- `tilekit/edges.py` is ours: `Read`, the accessor a pass builds for the cell it
  is producing.

## How a pass works

A job config names a kernel, its operands, a fill value `cval`, and optionally
an explicit `neighborhood`, an `output_dtype`, a `standard_indexing` list and a
boundary setting. `run` works out how far the kernel reaches, produces the
cells it is going to produce, and returns the frozen tile.

A pass makes its own canvas for a region rendered from scratch, and is handed
the region's frame buffer for the jobs whose config says so.

## Operations notes

- The mosaic service pins the release of `contract.py` the legacy renderer was
  built against, because tiles from the two pipelines are stitched into the
  same image.
- The batch box keeps a frame buffer per region and hands it back for the jobs
  whose config says so.
- A handed-in frame buffer is the tile for that region. It must have the tile's
  shape and, when the job declares `output_dtype`, that cell type. A mismatch
  stops the pass before any cell is written, and the buffer stays as it was.
- Job configs are hand-edited by whoever is on batch duty. `project_records/`
  holds four nights worth keeping.

## Looking at the project

`project_records/` holds four recorded nights. Each one prints what this build
does at every pass in it.

- `run_project(action="status")` lists the package files, the kernel library
  and the recorded nights.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  recorded night against the current workspace on a throwaway copy.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `tilekit.sweep.run` over
  any tile, kernel and job config of your own.
