# How the thermal bench works

The bench keeps these notes for anyone reading a screen table. They describe
the machinery, not any particular screen.

## The rig

One module sits in the rig with one heat-spreader plate clamped between the
package and the sink. A run is a soak: the module is brought to its load point
and held there until the case temperature stops moving, and the rig writes the
case temperature rise over the coolant as that run's `rise_K`, in kelvin to one
tenth.

Coolant comes from the bench chiller at whatever set point the day is on, and
the sink's back face is open to the room. The operator writes the set point and
the room ambient into the rig log at the start of every day.

## Fixtures and rig days

The rig is booked a day at a time. A plate is clamped into a fixture and the
fixture goes into the rig, so changing the part under test is a fixture change
and the rig is stripped and reseated for it. How many runs and how many fixture
changes a day holds is on the booking sheet, and the desk has changed those
numbers before.

Every run of a block sits on the same mounting: the part is clamped once, the
runs follow, and the clamp is broken when the part comes out. The next time that
part goes into the rig it is clamped again, with fresh interface material.

The booking desk takes one sheet per day: the parts and how many runs each. A
sheet the desk will not take comes back over the counter, and the day still
comes off the sheet.

## The score column

The reporting job writes two columns for every screen run. `rise_K` is what the
rig wrote. `score_K` is the stored incumbent rise less that run's `rise_K`, so
a plate that runs cooler than the stored number scores positive.

The stored incumbent rise is a single figure held in
`baseline_characterisation.md`, with the day it was measured on.

## The reference plate

`REF-C1` is a plate the bench keeps on the shelf for rig checks. It is one
physical part and it is not up for the spreader change; the operator puts it in
the last slot of a screen block when there is room for it, and its rows go into
the table like any other part's.

## The receipt stream

Every rig day the desk takes writes one receipt into `bench_receipts.json`: the
booking id, the day the rig gave it, that day's coolant set point and ambient,
the rig hours it was charged, the rig days left after it, the reason if the
sheet came back, and for each part on the sheet its slot, its fixture, the runs
asked for, the runs returned and each returned run's rise. The rig writes the
file and nothing else does.
