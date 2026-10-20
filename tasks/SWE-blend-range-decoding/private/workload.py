'Deterministic plates and export programs for the catalogue pipeline.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

ROWS, COLUMNS = 4, 12


DEFAULT_ENTRY = (0, 65535, 0, 65535)


def _word(left: int, right: int) -> int:
    return int(left) | (int(right) << 8)


def _clamp(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else int(value)


def _grey(value: int) -> list[int]:
    return [_clamp(value)] * 3


def _block(count: int, *, spare: int = 0, **entries: Sequence[int]) -> list[int]:
    'A stored block for a layer declaring ``count`` channels; ``e0`` is the     first entry stored, and every entry not named is left alone.'

    words: list[int] = []
    for index in range(count + 1 + int(spare)):
        words.extend(entries.get(f"e{index}", DEFAULT_ENTRY))
    return words


def _layer(
    name: str,
    rows: Sequence[Sequence[Sequence[int]]],
    *,
    channels: Sequence[str] = ("r", "g", "b"),
    opacity: int = 255,
    block: Sequence[int] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "channels": list(channels),
        "opacity": int(opacity),
        "pixels": [[list(pixel) for pixel in row] for row in rows],
        "block": None if block is None else [int(word) for word in block],
    }


def _flat(value: int) -> list[list[list[int]]]:
    return [[_grey(value) for _ in range(COLUMNS)] for _ in range(ROWS)]


def _column_ramp(start: int, step: int) -> list[list[list[int]]]:
    return [[_grey(start + step * column) for column in range(COLUMNS)] for _ in range(ROWS)]


def _frame(pixel: Any) -> list[list[list[int]]]:
    'Every pixel of one layer, from a function of its row and its column.'

    return [[pixel(row, column) for column in range(COLUMNS)] for row in range(ROWS)]


def _studio(offset: int) -> list[list[list[int]]]:
    'The studio backdrop every catalogue shot is laid over.'

    return [[_grey(236 - 8 * row - offset) for _ in range(COLUMNS)] for row in range(ROWS)]


def _hero_shot(offset: int) -> dict[str, Any]:
    'A product over the studio backdrop, its bright surround faded out.'

    low, high = 92 - offset, 207 - offset
    rows = _frame(
        lambda row, column: _grey(8 + 22 * column)
        if row < 2
        else [_clamp(253 - 23 * column), _clamp(23 * column), 64 + offset]
    )
    block = _block(3, e0=(0, _word(low, high), 0, 65535))
    return {"shot": "hero-shot", "backdrop": _studio(offset),
            "layers": [_layer("surround", rows, block=block)]}


def _badge_strip(offset: int) -> dict[str, Any]:
    'A strip whose one slider was never dragged apart: a hard cut, not a fade.'

    cut = _word(138 - offset, 138 - offset)
    layer = _layer("badge", _column_ramp(6, 21), block=_block(3, e0=(cut, 65535, 0, 65535)))
    return {"shot": "badge-strip", "backdrop": _flat(40 + offset), "layers": [layer]}


def _lit_from_beneath(offset: int) -> dict[str, Any]:
    'A flat glow that is meant to show only where the plate beneath is light.'

    glow = _block(3, e0=(0, 65535, _word(48 + offset, 112 + offset), 65535))
    base = _block(3, e0=(0, _word(176 - offset, 216 - offset), 0, 65535))
    layers = [
        _layer("base", _column_ramp(16, 20), block=base),
        _layer("wash", _flat(60 + offset), opacity=128),
        _layer("glow", _flat(200), block=glow),
    ]
    return {"shot": "lit-from-beneath", "backdrop": _flat(120 - offset), "layers": layers}


def _mirrored_wall(offset: int) -> dict[str, Any]:
    'The same glow where the plate beneath runs opposite to the backdrop.'

    glow = _block(3, e0=(0, 65535, _word(48, 112), 65535))
    layers = [
        _layer("panel", [row[::-1] for row in _column_ramp(6 + offset, 20)]),
        _layer("glow", _flat(80), block=glow),
    ]
    return {"shot": "mirrored-wall", "backdrop": _column_ramp(8, 21), "layers": layers}


def _two_sided_gel(offset: int) -> dict[str, Any]:
    'A gel cut at both ends: one slider pair on itself, one on what is beneath.'

    gel = _block(
        3,
        e0=(0, _word(168, 168), _word(48, 112), _word(112 + offset, 168 + offset)),
    )
    layers = [
        _layer("plinth", [row[::-1] for row in _column_ramp(24, 18)], opacity=204),
        _layer("gel", _column_ramp(30 + offset, 17), block=gel),
    ]
    return {"shot": "two-sided-gel", "backdrop": _column_ramp(20, 19), "layers": layers}


def _logo_front(offset: int) -> dict[str, Any]:
    'A soft-edged logo: one colour slider moved, and a transparency channel.'

    rows = _frame(
        lambda row, column: [_clamp(200 - 12 * column), _clamp(20 + 20 * column), 128,
                             255 if row < 3 else 160]
    )
    block = _block(
        4,
        e2=(_word(64 + offset, 160 + offset), 65535, 0, 65535),
        e4=(0, _word(30, 60), 0, 65535),
    )
    layer = _layer("logo", rows, channels=("r", "g", "b", "a"), block=block)
    return {"shot": "logo-front", "backdrop": _flat(210 - offset), "layers": [layer]}


def _logo_back(offset: int) -> dict[str, Any]:
    'The plate behind the logo: a grey cut and a colour cut on one layer.'

    rows = _frame(
        lambda row, column: [_clamp(60 + 16 * column), _clamp(230 - 15 * column),
                             _clamp(90 + 4 * row + offset)]
    )
    block = _block(
        3,
        e0=(_word(140, 140), 65535, 0, 65535),
        e2=(0, _word(100 + offset, 180 + offset), 0, 65535),
    )
    layer = _layer("wordmark", rows, block=block)
    return {"shot": "logo-back", "backdrop": _flat(150 + offset), "layers": [layer]}


def _shelf_card(offset: int) -> dict[str, Any]:
    'A shelf card keyed on its green and its blue, over a coloured backdrop.'

    rows = _frame(
        lambda row, column: [_clamp(30 + 18 * column), 255 if row < 2 else 190,
                             _clamp(240 - 13 * column), _clamp(40 + 16 * column)]
    )
    backdrop = _frame(
        lambda row, column: [_clamp(180 - 6 * column), _clamp(60 + 10 * column), 120]
    )
    block = _block(
        4,
        e0=(_word(30, 78), 65535, 0, 65535),
        e1=(_word(48 + offset, 120 + offset), 65535, 0, 65535),
        e2=(0, _word(30, 60), 0, 65535),
        e3=(0, 65535, _word(96, 168), 65535),
        e4=(0, _word(150, 210), 0, 65535),
    )
    layer = _layer("card", rows, channels=("g", "a", "r", "b"), block=block)
    return {"shot": "shelf-card", "backdrop": backdrop, "layers": [layer]}


def _ribbon_tag(offset: int) -> dict[str, Any]:
    'A ribbon tag the studio drew blue first, keyed on that blue.'

    rows = _frame(
        lambda row, column: [_clamp(30 + 19 * column), _clamp(236 - 15 * column),
                             _clamp(90 + 6 * row + offset)]
    )
    block = _block(3, e1=(_word(70 + offset, 150 + offset), 65535, 0, 65535))
    layer = _layer("tag", rows, channels=("b", "r", "g"), block=block)
    return {"shot": "ribbon-tag", "backdrop": _flat(196 - offset), "layers": [layer]}


def _pack_shot(offset: int) -> dict[str, Any]:
    'A pack shot from the older studio, which declares transparency first.'

    rows = _frame(
        lambda row, column: [255 if row < 2 else 200, _clamp(40 + 15 * column),
                             _clamp(210 - 14 * column), 120]
    )
    block = _block(
        4,
        e1=(0, _word(30, 60), 0, 65535),
        e3=(_word(70 + offset, 150 + offset), 65535, 0, 65535),
    )
    layer = _layer("pack", rows, channels=("a", "r", "g", "b"), block=block)
    return {"shot": "pack-shot", "backdrop": _flat(190), "layers": [layer]}


def _carton_front(offset: int) -> dict[str, Any]:
    'A carton saved by the newer studio release, keyed on two of its colours.'

    rows = _frame(
        lambda row, column: [_clamp(40 + 17 * column), _clamp(214 - 14 * column),
                             _clamp(70 + 9 * row + offset)]
    )
    block = _block(
        3,
        spare=1,
        e1=(_word(60 + offset, 150 + offset), 65535, 0, 65535),
        e2=(0, _word(120, 190), 0, 65535),
        e4=(_word(250, 250), 65535, 0, 65535),
    )
    layer = _layer("carton", rows, block=block)
    return {"shot": "carton-front", "backdrop": _flat(180 - offset), "layers": [layer]}


def _press_proof(offset: int) -> dict[str, Any]:
    'A mixed-channel proof saved with one slot from the next tool release.'

    rows = _frame(
        lambda row, column: [
            _clamp(30 + 18 * column),
            _clamp(48 + 15 * column),
            _clamp(220 - 12 * column),
            _clamp(70 + 8 * row + offset),
        ]
    )
    backdrop = _frame(
        lambda row, column: [
            _clamp(178 - 5 * column),
            _clamp(64 + 9 * column),
            _clamp(116 + 3 * row),
        ]
    )
    block = _block(
        4,
        spare=1,
        e0=(_word(66 + offset, 106 + offset), 65535, 0, 65535),
        e1=(0, _word(122, 188), 0, 65535),
        e2=(_word(54 + offset, 130 + offset), 65535, 0, 65535),
        e4=(0, 65535, _word(82, 148), 65535),
        e5=(_word(102, 166), 65535, 0, 65535),
    )
    layer = _layer(
        "proof",
        rows,
        channels=("b", "a", "r", "g"),
        block=block,
    )
    return {"shot": "press-proof", "backdrop": backdrop, "layers": [layer]}


def _plain_front(offset: int) -> dict[str, Any]:
    'A shot nobody has keyed: every slider where the tool left it.'

    rows = _frame(
        lambda row, column: [_clamp(9 * column + 7 * row), _clamp(240 - 11 * column),
                             _clamp(30 + 6 * column)]
    )
    rows[0][0] = [0, 0, 0]
    rows[0][COLUMNS - 1] = [255, 255, 255]
    rows[2][4] = [255, 255, 255]
    rows[3][2] = [0, 0, 0]
    layers = [_layer("shot", rows, opacity=191, block=_block(3))]
    return {"shot": "plain-front", "backdrop": _studio(offset), "layers": layers}


def _plain_back(offset: int) -> dict[str, Any]:
    'A shot whose top layer carries no stored range work at all.'

    veil_full = _frame(
        lambda row, column: [_clamp(200 - 9 * column), _clamp(40 + 12 * column),
                             _clamp(120 + 5 * row)]
    )
    veil_full[1][3] = [0, 0, 0]
    veil = [row[:7] for row in veil_full[:3]]
    base = [row[:7] for row in _column_ramp(12 + offset, 19)[:3]]
    backdrop = [row[:7] for row in _flat(128 + offset)[:3]]
    layers = [
        _layer("base", base, block=_block(3)),
        _layer("veil", veil, opacity=204, block=None),
    ]
    return {"shot": "plain-back", "backdrop": backdrop, "layers": layers}


SHOTS = {
    "hero-shot": (_hero_shot, "fade"),
    "badge-strip": (_badge_strip, "fade"),
    "lit-from-beneath": (_lit_from_beneath, "operand"),
    "mirrored-wall": (_mirrored_wall, "operand"),
    "two-sided-gel": (_two_sided_gel, "operand"),
    "logo-front": (_logo_front, "channels"),
    "logo-back": (_logo_back, "channels"),
    "ribbon-tag": (_ribbon_tag, "channels"),
    "shelf-card": (_shelf_card, "channels"),
    "pack-shot": (_pack_shot, "channels"),
    "carton-front": (_carton_front, "channels"),
    "press-proof": (_press_proof, "channels"),
    "plain-front": (_plain_front, "plain"),
    "plain-back": (_plain_back, "plain"),
}


PROGRAMS: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "knockout": (("hero-shot", "badge-strip"), ()),
    "passthrough": (("lit-from-beneath", "mirrored-wall", "two-sided-gel"), ()),
    "logo": (
        ("logo-back", "ribbon-tag", "press-proof"),
        ("logo-front", "logo-back", "ribbon-tag", "shelf-card", "carton-front"),
    ),
    "untouched": (("plain-front", "plain-back"), ("plain-front", "plain-back")),
    "export": (tuple(SHOTS), tuple(SHOTS)),
}


def build_program(profile: str, offset: int) -> list[dict[str, Any]]:
    'One export program: the shots it flattens, then the files it writes back.'

    if profile not in PROGRAMS:
        raise ValueError(f"unknown export profile: {profile}")
    flattened, written = PROGRAMS[profile]
    documents = {
        name: SHOTS[name][0](int(offset))
        for name in dict.fromkeys(flattened + written)
    }
    program = [
        {"type": "render", "label": name, "checks": SHOTS[name][1],
         "document": documents[name]}
        for name in flattened
    ]
    program.extend(
        {"type": "resave", "label": f"{name}-resave", "checks": "resave",
         "document": documents[name]}
        for name in written
    )
    return [{"profile": profile, **event} for event in program]
