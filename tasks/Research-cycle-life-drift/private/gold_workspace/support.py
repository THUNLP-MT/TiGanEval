"""Reading the tester's export back on to one scale, and the rack it ran on."""


def instrument_gain(context, receipt):
    """How much the tester was reading high or low when it wrote this session.

    The sealed cell is certified, so the reading it gave at the top of the
    session is the whole of the tester's scale error for that session.
    """

    return receipt["reference_cell_ah"] / context["reference_cell_ah"]


def retirement_line(context):
    return context["rated_capacity_ah"] * context["retirement_fraction"]


def retirement_cycle(context, receipt, cell):
    """The first capacity check below the line once the scale is put back."""

    line = retirement_line(context)
    gain = instrument_gain(context, receipt)
    for cycle, amp_hours in cell["checkpoints"]:
        if amp_hours / gain < line:
            return cycle
    return None


def bay_of(context, channel):
    for bay, entry in context["rack"].items():
        if channel in entry["channels"]:
            return bay
    return None


def qualification_bay(context):
    """The bay the build's own temperature is held at, whatever a log says."""

    wanted = context["qualification_temperature_c"]
    for bay, entry in context["rack"].items():
        if entry["setpoint_c"] == wanted:
            return bay
    return None


def cycle_lives(context, receipts):
    """Every cell's life, gathered by the chamber it sat in and the charge it took."""

    gathered = {}
    for receipt in receipts:
        for cell in receipt["observed"]["cells"]:
            key = (bay_of(context, cell["channel"]), receipt["protocol"])
            gathered.setdefault(key, []).append(retirement_cycle(context, receipt, cell))
    return gathered


def mean(values):
    values = [value for value in (values or ()) if value is not None]
    return sum(values) / len(values) if values else None


def arms(context, receipts):
    bay = qualification_bay(context)
    gathered = cycle_lives(context, receipts)
    return (mean(gathered.get((bay, "standard"))), mean(gathered.get((bay, "stepped"))))


def effect_range(context, receipts):
    """Everything the difference at the build's temperature could still be."""

    low, high = context["lot_life_window_cycles"]
    standard, stepped = arms(context, receipts)
    if standard is not None and stepped is not None:
        return [stepped - standard, stepped - standard]
    if stepped is not None:
        return [stepped - high, stepped - low]
    if standard is not None:
        return [low - standard, high - standard]
    return [low - high, high - low]


def hours_left(context, receipts):
    if receipts:
        return receipts[-1]["channel_hours_remaining_after"]
    return context["channel_hours_remaining"]
