# xG vs Goals: buy the xG, fade the overperformance (data story)

Tests how xG relates to goals, whether finishing over/underperformance persists, and which
recent signal best predicts an attacker's forward goals. Walk-forward and leak-free: trailing
and forward windows use only played matches (minutes >= 45), strictly before / from the decision
match, in each player's own time order. Uses the full 2025/26 player-gameweek census.

- **Charts:** `build_story.py` builds three PNGs into `outputs/charts/` (prefix `xgf_`)
- **The story:** `xg_finishing_story.md`

## Headline
xG matches goals over a season (r = 0.93) but barely within a single match (r = 0.60). Finishing
over/underperformance does not repeat (odd-vs-even split-half correlation +0.03), so a hot streak
is mostly luck. For picking attackers, recent xG ranks the next four games about twice as well as
recent goals (+0.35 vs +0.19 Spearman), while recent overperformance predicts nothing (-0.02).
Buy the xG, fade the overperformance.

## The three charts
1. `xgf_01_xg_tracks_goals.png` — xG vs goals at match level (loose) vs season level (tight).
2. `xgf_02_overperformance_noise.png` — odd vs even overperformance; the cloud is round, not diagonal.
3. `xgf_03_signal_strength.png` — recent xG vs recent goals vs recent overperformance for forward goals, with 95% ranges.

## Run
```bash
# from the repo root
python3 analysis/xg_finishing/build_story.py   # rebuild the three charts
```

## Data
- `data/processed/player_gw_features.csv` (`expected_goals` = match xG incl. penalties, `goals_scored`, `minutes`, `position_short`)
- Played match = minutes >= 45; trailing/forward windows = mean over k played matches; overperformance = goals - xG; attackers = MID + FWD.
