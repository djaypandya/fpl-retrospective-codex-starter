# Do expected stats add value for shortlisting? (data story)

Tests whether trailing expected stats (xGI) and the ICT index add value on top of the
baseline stack (minutes gate, form, fixtures, ownership) for picking players over the next
4 to 8 gameweeks. Walk-forward and leak-free: predictors use only gameweeks strictly before
the decision gameweek. Uses the full 2025/26 player-gameweek census.

- **Panel builder:** `panel.py` (one row per eligible decision-GW, player; trailing predictors + forward points)
- **Rigorous test:** `model.py` (Spearman ranking skill, GW-block bootstrap, incremental OLS, out-of-sample walk-forward)
- **Charts:** `build_story.py` builds six PNGs into `outputs/charts/` (prefix `xstat_`)
- **The story:** `expected_stats_story.md`

## Headline
For attackers, expected involvement (xGI) out-predicts recent form over the next 4 to 8
gameweeks, and the edge grows with the horizon. ICT carries the same information as xGI, so
you only need one. Form and xGI work best together. For defenders and keepers, xGI barely
helps; fixtures and expected goals conceded matter instead. The edge is real but modest,
about half a point per game per attacker at the top of the shortlist, measured on one season.

## Run
```bash
# from the repo root
python3 analysis/expected_stats_value/model.py         # numbers behind the story
python3 analysis/expected_stats_value/build_story.py   # rebuild the six charts
```

## Data
- `data/processed/player_gw_features.csv` (leak-safe `_prior` trailing features)
- `data/processed/fixture_difficulty.csv` (upcoming-window difficulty, joined on team + gameweek)
