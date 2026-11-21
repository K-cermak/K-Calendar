from typing import Literal, get_args

# The shared palette of calendars, events and tags (SPEC 11). The frontend has the values per theme.
PaletteColor = Literal[
    "red",
    "orange",
    "amber",
    "lime",
    "green",
    "teal",
    "cyan",
    "blue",
    "indigo",
    "violet",
    "pink",
    "brown",
    "graphite",
]

PALETTE: tuple[str, ...] = get_args(PaletteColor)
