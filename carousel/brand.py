"""One-place brand controls for the FPL Retrospective Lab carousel."""

from pathlib import Path


W, H = 1080, 1350
MARGIN = 84

# Dark, warm, and deliberately distinct from the red MBA reference skin.
BG = (10, 13, 16)
WARM_WHITE = (244, 239, 228)
MUTED = (143, 151, 152)
DARK_GREY = (42, 52, 54)
MID_GREY = (79, 92, 93)
ACCENT = (0, 215, 133)
CARD_WHITE = (250, 250, 248)

SANS = "/System/Library/Fonts/Avenir.ttc"
SANS_FALLBACK = "/System/Library/Fonts/HelveticaNeue.ttc"

HEADER_SEASON = "FPL · 2025/26"
FOOTER_LEFT = "FPL Retrospective Lab"
FOOTER_CENTER = "Data: 2025/26 Premier League season"
FOOTER_RIGHT = "@fpl.retro.lab"

ROOT = Path(__file__).resolve().parent
CHARTS_DIR = ROOT / "charts"
STORIES_DIR = ROOT / "stories"
OUTPUTS_DIR = ROOT / "outputs"

# Avenir collection indices mirror the proven reference renderer's weight choices.
FONT_INDEX_REGULAR = 0
FONT_INDEX_ITALIC = 1
FONT_INDEX_DEMI = 4
FONT_INDEX_HEAVY = 8

SIZE_TITLE = 88
SIZE_TITLE_SMALL = 70
SIZE_HEADLINE = 45
SIZE_BODY = 38
SIZE_CHECKLIST = 35
SIZE_KICKER = 26
SIZE_LABEL = 23
SIZE_CAPSULE = 22
SIZE_CAPTION = 24
SIZE_FOOTER = 20
