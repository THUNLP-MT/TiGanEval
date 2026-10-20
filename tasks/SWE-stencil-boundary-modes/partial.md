I run the nightly imaging batch. Below is my comment on the boundary plan in COAST-412, which I wrote and which is right as far as it goes; I need you to carry it the rest of the way.

Yesterday's 9am mosaic went out with a two-pixel dead frame around the harbour tiles. The coastline team can see the seams through the water and is back on last quarter's imagery.

My reading was that `tilekit/sweep.py` leaves a tile's edge at `cval` where the kernel's window runs off it: on the harbour render in `project_records/coast-blur-rerender.json`, take the index round to the far side instead of filling zeros.

Once your change is in, what I want to see tomorrow morning is the harbour tiles stitching into the mosaic with nothing showing along the joins, and the other passes in that list, which run tonight, coming back exactly as they did last night.
