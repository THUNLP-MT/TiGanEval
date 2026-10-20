# Handheld firmware 4.2 — release note

Owner: Nadia Okonjo, device platform. Signed off 8 July 2026.

## What changed

Capture gain on the three reflectance channels (`refl_a`, `refl_b`, `refl_c`)
goes from 1.0 to **1.6**. Nothing else in the capture path moves: edge density,
skew, contrast, blur and tilt come off the same stages as on 4.1.

The change came out of the dusty-bay complaints. Yard and night crews had been
holding units at arm's length to get a read off a scuffed label, and the
support queue carried 340 tickets about it in the spring. At 1.6 the windows
come back inside the range the sensor was specified for on a dusty label.

The gain setting lives on the device, and a unit works to its own scale in
service: a unit on 4.2 to 4.2's setting, a unit on 4.1 to 4.1's.

## Rollout

Staged from **13 July 2026**, dusty bays first because that is where the
complaints came from, then whatever else the depot could take offline. The
register carries the firmware each unit is on. At the close of this window 265
of the 780 units in service are on 4.2.

## Export

Platform did not change the capture exporter for this release. It stamps every
row it writes with a `stage`, which is either `corrected` or `as_captured`, and
that column has been on the export since the 3.8 days.

## Bench check

The reference card is a fixed target on a stand. The annotation desk will
capture it on either firmware and return the rows, at counter prices, so a
depot can see what its own units write.
