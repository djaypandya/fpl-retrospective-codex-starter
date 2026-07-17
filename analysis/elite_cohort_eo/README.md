# Elite-cohort effective-ownership analysis

Tests two questions about copying strong FPL managers, using the local top-~1% manager sample
(`data/raw/managers/`), walk-forward and leak-free (cohort defined only by rank known at GW t).

- **Q1 — When is a "top manager" genuinely skilled, not lucky?** → `rank_stability.py`
- **Q2 — Does that cohort's effective ownership improve player shortlisting vs baselines?** → `eo_panel.py` (builds the panel), `eo_model.py` (primary test + bootstrap), `eo_sensitivity.py` (7 variants)

## Headline
Rank persistence over the next 4 GW is solid from ~GW6–8, so the cohort becomes a trustworthy
reference group early. But elite effective ownership is a **modest** forward-points ranking signal
(Spearman ~0.24) that is **beaten by plain whole-sample ownership in every variant**, only marginally
beats recent points (edge vanishes over 8 GW), and gets **worse** the more elite the cohort. There is
no gameweek where it becomes a real edge over free baselines. Full plain-English write-up: `eo_report.txt`.

## Run
```bash
cd analysis/elite_cohort_eo
python3 rank_stability.py     # Q1
python3 eo_model.py           # Q2 primary (builds eo_cache.pkl on first run, ~30-60s)
python3 eo_sensitivity.py     # Q2 robustness
```
`eo_cache.pkl`, `*.csv` are regenerable build artifacts.
