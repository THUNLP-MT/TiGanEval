"""The plate review notebook: the number, its range, and the next rig day."""

from support import day_sheet, effect_and_half_width, ledger_lines, selected_plate


def analyze(context, receipts):
    effect, half = effect_and_half_width(context, receipts)
    return {
        "plate": selected_plate(context),
        "effect_K": effect,
        "effect_range_K": [effect - half, effect + half],
        "measurements": ledger_lines(receipts),
    }


def next_collection(context, receipts):
    sheet = day_sheet(context, receipts)
    return "stop" if not sheet else {"day": sheet}
