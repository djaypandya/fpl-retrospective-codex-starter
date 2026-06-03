# PLANS.md

## Project objective

Build a Jupyter Notebook retrospective for FPL manager team ID `816200`.

The notebook should compare the manager's season against a representative sample of top-N overall managers, currently top 80K based on cached Overall league standings pages, and generate practical decision rules for next season.

The rules should use:

- team strength
- fixture difficulty
- individual player metrics
- position-specific scoring routes
- minutes security
- price
- position
- ownership where available
- transfer timing
- transfer package context
- captaincy
- benching
- chip usage

## Final outputs

The project should produce:

- `notebooks/fpl_season_retrospective.ipynb`
- `outputs/tables/my_decision_review.csv`
- `outputs/tables/my_transfer_decision_labels.csv`
- `outputs/tables/my_transfer_group_decision_labels.csv`
- `outputs/tables/top_n_sample_summary.csv`
- `outputs/tables/transfer_rule_candidates.csv`
- `outputs/tables/player_selection_rule_candidates.csv`
- `outputs/tables/next_season_rulebook.csv`
- `outputs/charts/season_gap_waterfall.png`
- `outputs/charts/transfer_quality_distribution.png`
- `outputs/charts/captaincy_delta.png`
- `outputs/charts/rule_confidence_summary.png`
- `outputs/tables/weekly_transfer_candidate_shortlist.csv`
- `outputs/tables/weekly_sell_candidate_review.csv`
- `outputs/tables/learned_candidate_shortlist_rules.csv`
- `outputs/tables/learned_sell_hold_rules.csv`
- `outputs/tables/learned_hit_threshold_rules.csv`
- `outputs/tables/learned_captaincy_rules.csv`
- `outputs/tables/next_season_weekly_decision_checklist.csv`
- `outputs/tables/weekly_transfer_pair_review.csv`
- `outputs/tables/weekly_transfer_package_review.csv`
- `outputs/tables/weekly_captaincy_decision.csv`
- `outputs/tables/weekly_decision_pack_summary.csv`
- `outputs/charts/weekly_candidate_score_breakdown.png`
- `outputs/charts/weekly_hit_payoff_curve.png`
- `outputs/charts/weekly_captaincy_score_breakdown.png`

## Epics

### Epic 1: Project skeleton and decision framework

Goal: Create project structure, config, decision quality framework, and basic notebook.

### Epic 2: Fetch and cache core FPL data

Goal: Fetch bootstrap, fixtures, and gameweek live player data.

### Epic 3: Build representative top-N sample

Goal: Sample managers from the top-N overall ranks using rank-stratified sampling.

### Epic 4: Fetch manager histories, transfers, and picks

Goal: Fetch manager-level data for team ID `816200` and the sampled managers.

### Epic 5: Build analytical tables

Goal: Create clean tables for player-gameweek features, team strength, fixture outlook, manager picks, and transfer analysis.

### Epic 6: Reconstruct my season

Goal: Build a week-by-week timeline for team ID `816200`.

### Epic 7: Evaluate my decisions

Goal: Analyse transfers, captaincy, benching, hits, and chip usage.

### Epic 8: Compare me against the top-N sample

Goal: Compare behaviour against strong managers using percentiles and rank bands.

### Epic 9: Build decision rules under uncertainty

Goal: Test candidate rules using leakage-safe historical features and future outcome windows.

### Epic 10: Build final retrospective report

Goal: Produce final summary, charts, tables, and next-season rulebook.

### Epic 11: Weekly Decision System

Goal: Convert the retrospective evidence into a reusable weekly decision system that narrows transfer candidates, reviews sell candidates, evaluates hit packages, ranks captaincy options, and produces a practical weekly decision pack for manager `816200`.

## Build order

Work through the epics in order.

Within each epic, complete one story at a time.

Do not skip ahead unless a story is blocked.

If a story is blocked, update `STATUS.md` and continue with the next unblocked story if possible.

## Milestone review points

| Milestone | Human review focus |
|---|---|
| End of Epic 2 | Does the raw FPL data look right? |
| End of Epic 3 | Is the top-N sample sensible? |
| End of Epic 4 | Did manager fetches work without too many failures? |
| End of Epic 7 | Are decision labels reasonable? |
| End of Epic 9 | Are rules useful or just obvious? |
| End of Epic 11 | Is the weekly decision system practical, conservative about hits, and free from hindsight leakage? |
