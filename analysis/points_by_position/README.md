# Where do points come from, and which position is best value? (data story)

Decomposes every player's FPL points into its scoring parts for the full 2025/26 season, then
compares positions on absolute points versus points per pound. Point components are rebuilt
from the 2025/26 scoring rules and validated against `total_points` (99.65% exact match; the
gaps are double-gameweek appearance/bonus edge cases). This is a census of all 841 players, so
the numbers are facts about the season, not estimates.

- **Charts:** `build_story.py` builds three PNGs into `outputs/charts/` (prefix `pos_`)
- **The story:** `points_by_position_story.md`

## Headline
Forwards and midfielders score the most points per player, but goalkeepers and defenders
return the most points per pound. The best value of all is premium defenders, lifted by the
new 2025/26 defensive-contribution points. Build the spine (keeper plus defenders) on value,
and spend the premium on one or two attacking match-winners.

## The three charts
1. `pos_01_composition.png` — share of each position's positive points by scoring action.
2. `pos_02_absolute_vs_value.png` — the ranking flips: most points per player vs per £1m.
3. `pos_03_value_scatter.png` — price vs season points; cheap defenders sit above the value line.

## Run
```bash
# from the repo root
python3 analysis/points_by_position/build_story.py   # rebuild the three charts
```

## Data
- `data/processed/player_gw_features.csv` (raw per-GW event columns + price + position)
- Points rebuilt with position-specific goal and clean-sheet values, saves at 1 per 3,
  defensive contribution = 2 pts when the threshold is met, and goals conceded at -1 per 2 for
  keepers and defenders. Value uses per-player season points divided by median price; "regular
  starter" = season minutes >= 900.
