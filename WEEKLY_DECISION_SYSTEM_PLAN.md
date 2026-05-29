# WEEKLY_DECISION_SYSTEM_PLAN.md

## Purpose

This file is the next-phase plan for Codex.

The existing project has largely completed the retrospective analysis. The new objective is to convert that retrospective into a concrete weekly Fantasy Premier League decision process that can be used during the next season.

The end product should not be another descriptive report. It should be a practical decision engine that helps manager `816200` answer four weekly questions:

1. How do I narrow down the player pool each gameweek to identify potential transfer candidates?
2. How do I determine which player in my team to replace?
3. How do I determine whether it is justifiable to pay a transfer cost of `-4`, `-8`, or `-12` to bring in 2, 3, or 4 extra players beyond my available free transfers?
4. How do I determine who to captain?

All recommendations must be based only on information that would have been available before the gameweek deadline from FPL API data and derived leakage-safe features.

---

# Important review of current repo state

The current repo already contains the foundations needed for this next phase:

- `AGENTS.md` defines the working style, WIP limits, data rules, API assumptions, and anti-leakage modelling principles.
- `PLANS.md` defines the original retrospective objective and epics.
- `STATUS.md` shows the project has completed almost all original stories through Epic 10, with Story 10.2 in review.
- `KANBAN.md` shows that core outputs already exist for player features, team strength, fixture difficulty, manager picks, transfer outcomes, captaincy, benching, top-N benchmarking, and rule candidates.
- `src/fpl_retro/features.py` already builds leakage-safe player features, including rolling points, minutes, starts, xG/xA/xGI, clean sheets, saves, BPS, bonus, defensive contribution, and per-90 route metrics.
- `src/fpl_retro/rules.py` already builds candidate rule features and player-selection rule flags using position-aware scoring routes, team features, fixture features, ownership proxies, and future outcome windows.
- `src/fpl_retro/evaluation.py` already contains captaincy and benching review logic using pre-GW scores and position-aware scoring routes.

The gap is product design:

The current analysis explains what happened and creates useful rule candidates. The next phase must turn those assets into a weekly, step-by-step decision workflow.

---

# Next-phase final objective

## User story

As an FPL manager using team ID `816200`, I want a weekly decision system grounded in retrospective evidence from a large sample of strong managers, so that I can make repeatable transfer, hit, and captaincy decisions next season without relying on vibes, recency bias, or hindsight.

## Final acceptance criteria

The system must produce a weekly decision pack with four sections:

1. **Transfer Candidate Shortlist**
   - Starts from all available FPL players.
   - Filters down to a manageable candidate pool.
   - Ranks candidates by role security, position-specific scoring route, fixture outlook, team strength, price/value, and top-sample adoption signal where available.
   - Explains why each candidate is on the shortlist.

2. **Replace/Sell Candidate Review**
   - Reviews the players currently in manager `816200`'s squad.
   - Identifies weak links by position, role security, fixture outlook, team context, opportunity cost, price slot, and likely bench/starting role.
   - Separates `sell now`, `hold`, and `monitor`.

3. **Hit Justification Engine**
   - Evaluates transfer packages, not just individual transfer legs.
   - Tests `0 hit`, `-4`, `-8`, and `-12` scenarios where enough transfer candidates exist.
   - Calculates expected 1GW, 3GW, and 5GW payoff versus hit cost.
   - Adds a confidence label and clear reason for whether the hit is justified.
   - Distinguishes strategic hits from emotional/reactionary hits.

4. **Captaincy Decision Review**
   - Ranks captain candidates in the current squad.
   - Uses ceiling, minutes security, fixture quality, team attack strength, route-to-points, and top-sample behaviour where available.
   - Recommends a primary captain, vice captain, and avoid list.
   - Shows whether the choice is safe, aggressive, or unnecessary risk.

## Final outputs

Codex should create these outputs:

```text
outputs/tables/weekly_transfer_candidate_shortlist.csv
outputs/tables/weekly_sell_candidate_review.csv
outputs/tables/weekly_transfer_package_review.csv
outputs/tables/weekly_captaincy_decision.csv
outputs/tables/weekly_decision_pack_summary.csv
outputs/charts/weekly_candidate_score_breakdown.png
outputs/charts/weekly_hit_payoff_curve.png
outputs/charts/weekly_captaincy_score_breakdown.png
```

It should also create reusable code in:

```text
src/fpl_retro/weekly_decision_system.py
```

And add a notebook section:

```text
notebooks/fpl_season_retrospective.ipynb
```

with the heading:

```text
## 11 Weekly Decision System
```

---

# First-principles design

## The system should mimic the actual weekly decision sequence

A manager does not begin with a model output. A manager begins with a squad and must decide whether anything is worth changing.

The weekly order should be:

```text
1. What does my current squad look like for this gameweek?
2. Which positions or players are creating the biggest weakness?
3. Which outside players are genuinely better options?
4. Is the improvement large enough to spend a free transfer?
5. Is the improvement large enough to spend points on a hit?
6. Who should captain from the resulting squad?
```

## Do not optimise for hindsight-perfect points

The system must use only pre-deadline information:

- prior rolling player features
- prior team strength
- upcoming fixtures
- price
- position
- prior sample ownership/adoption where available
- manager `816200`'s current squad before transfers
- free transfers and bank if available

Invalid inputs:

- current GW actual points
- future points
- final season totals
- future ownership
- final rank

## Separate ranking from decision thresholds

Ranking answers:

```text
Who looks best?
```

Decision thresholds answer:

```text
Is the upgrade worth acting on?
```

Codex must not treat every high-ranked player as a transfer recommendation. The system must compare candidate improvement against the player being replaced and against transfer cost.

---

# New Epic 11: Weekly Decision System

## Epic user story

As an FPL manager, I want the retrospective data converted into a weekly decision system, so that each gameweek I can narrow candidates, identify weak links, evaluate hits, and choose a captain using rules that were tested against historical top-manager behaviour.

## Epic acceptance criteria

- The system accepts a target gameweek, manager ID, free transfers, and optional bank.
- The system builds a current-squad view for manager `816200` at that gameweek.
- The system creates a candidate pool from all players using only pre-GW data.
- The system scores candidates using evidence-backed features.
- The system scores current squad players as potential sells.
- The system builds transfer package scenarios and evaluates whether hits are justified.
- The system ranks captaincy options.
- The system produces a readable weekly decision pack.
- Every score includes component columns and an explanation column.
- Every recommendation includes confidence and limitations.

## Epic definition of done

The notebook can run:

```python
from fpl_retro.weekly_decision_system import build_weekly_decision_pack

weekly_pack = build_weekly_decision_pack(
    target_gw=10,
    manager_id=816200,
    free_transfers=1,
    bank=0.0,
)
```

and produce the five output tables listed above.

---

# Sprint 11: Weekly decision engine foundation

## Sprint goal

Create the reusable weekly decision-system module and basic decision-pack orchestration.

---

## Story 11.1: Create weekly decision-system skeleton

Status: Ready  
Epic: Epic 11  
Sprint: Sprint 11  
Size: S  
Priority: High  
Depends on: Story 10.2 review or existing processed outputs  
Human review: Required

### User story

As a manager, I want one function that orchestrates the weekly decision pack, so that I can call it for a target gameweek without manually stitching together tables.

### Acceptance criteria

- Creates `src/fpl_retro/weekly_decision_system.py`.
- Adds a public function `build_weekly_decision_pack(...)`.
- Function arguments include:
  - `target_gw`
  - `manager_id=816200`
  - `free_transfers=1`
  - `bank=0.0`
  - optional dataframes or file paths
- Returns a dictionary of DataFrames.
- Adds clear docstrings.
- Adds validation that required inputs exist.

### Tasks

- [ ] Inspect existing processed output names and schemas.
- [ ] Create `weekly_decision_system.py`.
- [ ] Add small helper `_require_columns`.
- [ ] Add small helper `_safe_numeric`.
- [ ] Add `build_weekly_decision_pack` stub that wires the later outputs.
- [ ] Add placeholder return keys for candidate shortlist, sell review, package review, captaincy decision, and summary.
- [ ] Add notebook section `## 11 Weekly Decision System`.
- [ ] Add smoke test with empty or minimal placeholder data.

### Checks

- [ ] Module imports successfully.
- [ ] `build_weekly_decision_pack` exists.
- [ ] Function returns the expected dictionary keys.
- [ ] Notebook section exists.

### Definition of done

- Skeleton exists.
- No retrospective functionality is broken.
- `BACKLOG.md`, `KANBAN.md`, `SPRINTS.md`, and `STATUS.md` are updated if Codex is managing the board.

### Codex prompt

```text
Create the foundation for a weekly decision system.

Before coding, read:
- AGENTS.md
- STATUS.md
- KANBAN.md
- BACKLOG.md
- WEEKLY_DECISION_SYSTEM_PLAN.md

Implement Story 11.1 only.

Create `src/fpl_retro/weekly_decision_system.py` with a public function:

build_weekly_decision_pack(target_gw, manager_id=816200, free_transfers=1, bank=0.0, **dataframes_or_paths)

For now, make the function validate inputs and return a dictionary with these keys:
- transfer_candidate_shortlist
- sell_candidate_review
- transfer_package_review
- captaincy_decision
- weekly_summary

Add helper functions but do not implement the full scoring logic yet.

Add a notebook section called `## 11 Weekly Decision System` that imports and smoke-tests the function.

Run lightweight checks:
- module imports
- function exists
- return keys exist

Stop after this story and update project management files.
```

---

## Story 11.2: Build current-squad context for a target gameweek

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 11  
Size: M  
Priority: High  
Depends on: Story 11.1, Story 6.2  
Human review: Required

### User story

As a manager, I want the system to understand my current squad for a target gameweek, so that transfer and captaincy decisions are grounded in the actual players I own.

### Acceptance criteria

- Builds a current squad table for `manager_id` and `target_gw`.
- Uses `my_squad_gameweek.csv` or equivalent reconstructed squad data.
- Includes starter/bench status, squad position, player price, player team, player position, prior player metrics, team strength, and fixture outlook.
- Adds derived fields:
  - `is_likely_starter`
  - `squad_role`
  - `price_slot`
  - `current_squad_priority_score`
- Does not use current gameweek outcome points.

### Tasks

- [ ] Load or accept squad dataframe.
- [ ] Filter to `manager_id` and `target_gw`.
- [ ] Validate one squad of 15 players where data exists.
- [ ] Add current squad role fields.
- [ ] Add pre-GW score components.
- [ ] Return `current_squad_context` internally.

### Checks

- [ ] Exactly one row per player in the squad.
- [ ] No current GW outcome is used as a feature.
- [ ] Captain and vice-captain fields are preserved if present.

### Codex prompt

```text
Implement Story 11.2 only.

Add logic to `weekly_decision_system.py` that builds current squad context for a target gameweek.

Use existing reconstructed squad outputs, preferably `my_squad_gameweek.csv` or the dataframe used in the notebook for Story 6.2.

Requirements:
- Filter by `manager_id` and `target_gw`.
- Include player, team, position, price, starter/bench status, prior player features, team strength, and fixture outlook.
- Add derived columns for `squad_role`, `price_slot`, `is_likely_starter`, and `current_squad_priority_score`.
- Do not use current GW actual points as a decision feature.
- Update `build_weekly_decision_pack` so it includes `current_squad_context` in the returned dictionary.

Run checks for squad size, required columns, and leakage.
```

---

## Story 11.3: Build transfer candidate shortlist

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 11  
Size: M  
Priority: High  
Depends on: Story 11.1, Story 9.1  
Human review: Required

### User story

As a manager, I want a systematic way to narrow the full player pool into transfer candidates, so that I do not chase random players based on one haul or social media pressure.

### Acceptance criteria

- Starts from `candidate_rule_features.csv` or equivalent dataframe.
- Filters to `target_gw`.
- Excludes players already owned unless a `include_owned=True` debug flag is passed.
- Excludes players with weak minutes/security unless explicitly flagged as punts.
- Scores all players using:
  - role security
  - position-relevant route-to-points
  - fixture outlook
  - team strength
  - price/value
  - prior top-sample ownership/adoption signal where available
- Produces a ranked shortlist by position and overall.
- Adds explanation fields.

### Tasks

- [ ] Load candidate rule features.
- [ ] Filter to target GW.
- [ ] Exclude current squad players.
- [ ] Add candidate score components.
- [ ] Add total candidate score.
- [ ] Add candidate tier: `strong`, `viable`, `punt`, `avoid`.
- [ ] Add explanation text.
- [ ] Save `weekly_transfer_candidate_shortlist.csv`.

### Checks

- [ ] Output includes candidates from multiple positions where available.
- [ ] Owned players are excluded by default.
- [ ] Score components are bounded and interpretable.
- [ ] No future outcome columns are used in candidate score.

### Codex prompt

```text
Implement Story 11.3 only.

Build the transfer candidate shortlist for a target gameweek.

Use existing `candidate_rule_features.csv` or equivalent in-memory dataframe.

For each player not already in the current squad, calculate:
- role_security_score
- route_to_points_score
- fixture_score
- team_strength_score
- price_value_score
- ownership_or_adoption_score where available
- transfer_candidate_score

The score must use pre-GW feature columns only. Do not use `outcome_` columns or current GW actual points.

Create columns:
- target_gw
- player_id
- web_name
- team_name
- position_short
- price
- transfer_candidate_score
- candidate_tier
- reason_summary
- risk_summary

Save:
outputs/tables/weekly_transfer_candidate_shortlist.csv

Update `build_weekly_decision_pack` to return this table.

Run checks for owned-player exclusion, no outcome-column usage, and score completeness.
```

---

# Sprint 12: Sell decisions and transfer package evaluation

## Sprint goal

Convert candidate ranking into actual transfer decisions by comparing outside players against current squad players and transfer costs.

---

## Story 12.1: Build sell candidate review

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 12  
Size: M  
Priority: High  
Depends on: Story 11.2  
Human review: Required

### User story

As a manager, I want to know which player in my squad is most replaceable, so that I avoid selling good assets after one bad score.

### Acceptance criteria

- Reviews all current squad players.
- Scores each player as `sell`, `hold`, or `monitor`.
- Uses:
  - weak fixture outlook
  - weak role security
  - weak position-relevant route score
  - poor team strength
  - bad value for price slot
  - opportunity cost compared with outside candidates
  - squad role and benchability
- Explains why a player is or is not a sell.

### Tasks

- [ ] Start from current squad context.
- [ ] Add sell-risk score components.
- [ ] Add opportunity-cost comparison to candidate pool.
- [ ] Add recommendation labels.
- [ ] Save `weekly_sell_candidate_review.csv`.

### Checks

- [ ] All current squad players appear.
- [ ] Strong players with bad one-week outcomes are not automatically sell candidates.
- [ ] Output contains explanation and confidence columns.

### Codex prompt

```text
Implement Story 12.1 only.

Build a sell candidate review for the current squad.

For each owned player, calculate:
- role_risk_score
- fixture_risk_score
- team_context_risk_score
- route_to_points_weakness_score
- price_slot_opportunity_cost_score
- bench_or_starting_role_modifier
- sell_priority_score

Then assign:
- sell_now
- monitor
- hold

The logic must avoid using current GW outcome points. It must not sell a good asset solely because of one blank.

Save:
outputs/tables/weekly_sell_candidate_review.csv

Update `build_weekly_decision_pack` to return this table.

Run checks that all 15 squad players are included and score components are present.
```

---

## Story 12.2: Match transfer candidates to sell candidates

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 12  
Size: M  
Priority: High  
Depends on: Story 11.3, Story 12.1  
Human review: Required

### User story

As a manager, I want each transfer candidate compared against realistic players to sell, so that I can identify actual upgrades rather than attractive players with no route into my team.

### Acceptance criteria

- Builds possible transfer pairs from sell candidates and buy candidates.
- Respects position constraints unless a broader multi-transfer package changes formation or structure.
- Respects affordability using bank and sell price where available.
- Calculates upgrade score:
  - buy score minus sell score
  - fixture swing improvement
  - route-to-points improvement
  - role-security improvement
  - team-strength improvement
  - price/value impact
- Adds recommendation label.

### Tasks

- [ ] Build valid single-transfer pairs.
- [ ] Check affordability.
- [ ] Calculate upgrade components.
- [ ] Rank upgrades.
- [ ] Save candidate pair table.

### Checks

- [ ] No impossible position swaps are recommended for single transfers.
- [ ] Unaffordable transfers are flagged or excluded.
- [ ] Upgrade score is interpretable.

### Codex prompt

```text
Implement Story 12.2 only.

Create a transfer-pair table that compares each realistic buy candidate against each realistic sell candidate.

For single transfers:
- Default to same-position swaps.
- Check affordability using `bank`, sell price, and buy price where available.
- Flag unaffordable pairs rather than silently dropping everything.

Calculate:
- upgrade_candidate_score_delta
- fixture_swing_delta
- role_security_delta
- route_to_points_delta
- team_strength_delta
- value_delta
- transfer_pair_score
- transfer_pair_recommendation

Save:
outputs/tables/weekly_transfer_pair_review.csv

Update `build_weekly_decision_pack` to include transfer pair review.

Do not build multi-transfer packages yet.
```

---

## Story 12.3: Build transfer package and hit justification engine

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 12  
Size: M  
Priority: High  
Depends on: Story 12.2, Story 9.3  
Human review: Required

### User story

As a manager, I want to know whether a `-4`, `-8`, or `-12` is justified, so that I only spend points when the package-level expected benefit is strong enough.

### Acceptance criteria

- Builds packages for:
  - no transfer
  - one transfer
  - two transfers
  - three transfers
  - four transfers
- Calculates hit cost based on `free_transfers`.
- Evaluates package-level benefit, not just isolated transfer legs.
- Uses 1GW, 3GW, and 5GW expected payoff proxies.
- Incorporates evidence from historical transfer package rules where available.
- Adds recommendation:
  - `do_not_take_hit`
  - `free_transfer_only`
  - `hit_justified_low_confidence`
  - `hit_justified_medium_confidence`
  - `hit_justified_high_confidence`
- Includes explanation.

### Tasks

- [ ] Generate feasible packages from top transfer pairs.
- [ ] Avoid duplicate sold or bought players within a package.
- [ ] Estimate total package upgrade score.
- [ ] Calculate hit cost.
- [ ] Calculate net package value after hit.
- [ ] Add historical evidence modifier from transfer rule candidates if available.
- [ ] Save `weekly_transfer_package_review.csv`.

### Checks

- [ ] Package hit cost is correct for free transfer count.
- [ ] No package has duplicate bought or sold players.
- [ ] Package-level score is not just sum of individual rows without hit cost.
- [ ] Output includes `-4`, `-8`, and `-12` scenarios where feasible.

### Codex prompt

```text
Implement Story 12.3 only.

Build a transfer package and hit justification engine.

Inputs:
- current squad context
- transfer candidate shortlist
- sell candidate review
- transfer pair review
- free_transfers
- bank
- historical transfer rule outputs if available

Generate feasible transfer packages up to 4 transfers.

For each package, calculate:
- transfers_count
- hit_cost = max(transfers_count - free_transfers, 0) * 4
- package_candidate_score_gain
- package_fixture_swing_gain
- package_role_security_gain
- package_route_to_points_gain
- package_team_strength_gain
- package_expected_1gw_gain_proxy
- package_expected_3gw_gain_proxy
- package_expected_5gw_gain_proxy
- package_net_1gw_after_hit
- package_net_3gw_after_hit
- package_net_5gw_after_hit
- hit_recommendation
- confidence
- reason_summary

Important:
Evaluate packages, not only individual transfer legs.

Save:
outputs/tables/weekly_transfer_package_review.csv
outputs/charts/weekly_hit_payoff_curve.png

Update `build_weekly_decision_pack` to return this table.
```

---

# Sprint 13: Captaincy decision and weekly output pack

## Sprint goal

Add weekly captaincy decision support and produce the final weekly decision pack.

---

## Story 13.1: Build weekly captaincy decision table

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 13  
Size: M  
Priority: High  
Depends on: Story 11.2, Story 7.4  
Human review: Required

### User story

As a manager, I want a weekly captaincy ranking, so that I can choose captain and vice captain using a repeatable process.

### Acceptance criteria

- Scores only current squad players.
- Prioritises likely starters.
- Uses:
  - ceiling
  - route-to-points
  - minutes security
  - fixture quality
  - team attack strength
  - sample captaincy behaviour if available
- Recommends captain and vice captain.
- Labels recommendation type:
  - safe/template
  - balanced
  - aggressive/differential
  - avoid
- Explains each candidate.

### Tasks

- [ ] Reuse or adapt captaincy scoring from `evaluation.py`.
- [ ] Add top-sample captaincy signal if available.
- [ ] Rank current squad players.
- [ ] Select captain and vice captain.
- [ ] Save `weekly_captaincy_decision.csv`.

### Checks

- [ ] Only owned players are included.
- [ ] Non-playing or low-minutes players are penalised.
- [ ] Recommended captain and vice captain are different players.
- [ ] No current-GW outcome is used.

### Codex prompt

```text
Implement Story 13.1 only.

Build a weekly captaincy decision table for the target gameweek.

Use current squad context and adapt the pre-GW captain candidate logic from existing `evaluation.py` where useful.

For each owned player, calculate:
- captain_ceiling_score
- captain_role_security_score
- captain_fixture_score
- captain_team_attack_score
- captain_route_to_points_score
- captain_sample_behaviour_score where available
- captain_total_score
- captain_label: safe/template, balanced, aggressive/differential, avoid
- reason_summary
- risk_summary

Recommend:
- primary captain
- vice captain

Save:
outputs/tables/weekly_captaincy_decision.csv
outputs/charts/weekly_captaincy_score_breakdown.png

Update `build_weekly_decision_pack` to return this table.
```

---

## Story 13.2: Create final weekly decision pack summary

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 13  
Size: M  
Priority: High  
Depends on: Story 12.3, Story 13.1  
Human review: Required

### User story

As a manager, I want a concise weekly decision summary, so that I can take action without reading every table.

### Acceptance criteria

- Produces one summary table with:
  - target GW
  - recommended action
  - best free-transfer option
  - whether a hit is justified
  - max hit level justified
  - captain recommendation
  - vice captain recommendation
  - top three buy candidates
  - top three sell candidates
  - main risks
  - confidence
- Adds readable notebook output.
- Saves summary table.

### Tasks

- [ ] Combine outputs from all weekly decision components.
- [ ] Choose best action pathway.
- [ ] Add summary narrative fields.
- [ ] Save summary table.
- [ ] Add notebook display section.

### Checks

- [ ] Summary matches underlying tables.
- [ ] Hit recommendation matches package review.
- [ ] Captain recommendation matches captaincy decision table.
- [ ] Output CSV exists.

### Codex prompt

```text
Implement Story 13.2 only.

Create a weekly decision pack summary.

Use:
- transfer candidate shortlist
- sell candidate review
- transfer package review
- captaincy decision

Produce one summary table with:
- target_gw
- recommended_action
- best_free_transfer
- hit_justification_summary
- max_hit_level_justified
- captain_recommendation
- vice_captain_recommendation
- top_buy_candidates
- top_sell_candidates
- biggest_risks
- confidence
- plain_english_summary

Save:
outputs/tables/weekly_decision_pack_summary.csv

Add a readable notebook display under `## 11 Weekly Decision System`.

Run consistency checks against underlying tables.
```

---

# Sprint 14: Backtest the weekly decision process

## Sprint goal

Test whether the weekly decision process would have made sensible historical recommendations under uncertainty.

---

## Story 14.1: Backtest weekly candidate shortlist quality

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 14  
Size: M  
Priority: High  
Depends on: Story 11.3  
Human review: Required

### User story

As a manager, I want to know whether the weekly shortlist would have surfaced useful players historically, so that I trust the shortlist next season.

### Acceptance criteria

- Runs the shortlist logic across historical gameweeks.
- Measures forward 1GW, 3GW, and 5GW points of shortlisted players versus non-shortlisted players by position.
- Measures adoption among top-N managers where available.
- Labels confidence by sample size and uplift consistency.

### Codex prompt

```text
Implement Story 14.1 only.

Backtest the transfer candidate shortlist across historical gameweeks.

For each gameweek, generate candidate scores using only pre-GW features.

Evaluate:
- top 5 by position
- top 10 overall
- candidate tiers

Compare against same-position baselines using future 1GW, 3GW, and 5GW outcomes that are already separated as outcome columns.

Save:
outputs/tables/weekly_candidate_shortlist_backtest.csv

Do not use future outcomes to build the shortlist, only to evaluate it after the fact.
```

---

## Story 14.2: Backtest hit justification thresholds

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 14  
Size: M  
Priority: High  
Depends on: Story 12.3  
Human review: Required

### User story

As a manager, I want hit thresholds to be based on historical evidence, so that I know when a `-4`, `-8`, or `-12` is actually worth it.

### Acceptance criteria

- Uses historical transfer packages from sampled managers where available.
- Compares package features to actual 1GW, 3GW, and 5GW net outcomes.
- Estimates practical thresholds for hit justification.
- Produces conservative rules for free transfer, `-4`, `-8`, and `-12`.

### Codex prompt

```text
Implement Story 14.2 only.

Backtest hit justification thresholds using historical transfer packages where available.

Use sampled manager transfer data and existing transfer rule outputs.

Estimate what package-level feature strength was historically needed to overcome:
- 0 point cost
- -4
- -8
- -12

Create conservative thresholds for:
- free transfer only
- -4 justified
- -8 justified
- -12 justified

Save:
outputs/tables/hit_threshold_backtest.csv

Update the package review logic to reference these thresholds if the output exists.
```

---

## Story 14.3: Backtest captaincy decision quality

Status: Backlog  
Epic: Epic 11  
Sprint: Sprint 14  
Size: M  
Priority: High  
Depends on: Story 13.1  
Human review: Required

### User story

As a manager, I want to know whether the captaincy scoring process would have made reasonable decisions historically, so that I can trust it next season.

### Acceptance criteria

- Runs captaincy scoring across manager `816200`'s historical squads.
- Compares recommended captain against actual captain, vice captain, best starter, and best squad player.
- Measures loss/gain versus actual and reasonable alternatives.
- Labels whether the model is too safe, too aggressive, or well-calibrated.

### Codex prompt

```text
Implement Story 14.3 only.

Backtest the weekly captaincy decision process across historical gameweeks for manager 816200.

For each gameweek:
- Score the owned squad using pre-GW captaincy features.
- Recommend captain and vice captain.
- Compare to actual captain, best starter, and best squad player.

Save:
outputs/tables/weekly_captaincy_backtest.csv
outputs/charts/weekly_captaincy_backtest_delta.png

Do not use current GW actual points in the recommendation. Use actual points only for post-hoc evaluation.
```

---

# Required scoring design

Codex should use transparent scores, not black-box ML, unless specifically asked later.

## Transfer candidate score

Suggested first version:

```text
transfer_candidate_score =
  0.25 * role_security_score
+ 0.25 * route_to_points_score
+ 0.20 * fixture_score
+ 0.15 * team_strength_score
+ 0.10 * price_value_score
+ 0.05 * ownership_or_adoption_score
```

## Sell priority score

Suggested first version:

```text
sell_priority_score =
  0.25 * role_risk_score
+ 0.20 * fixture_risk_score
+ 0.20 * route_to_points_weakness_score
+ 0.15 * team_context_risk_score
+ 0.15 * opportunity_cost_score
+ 0.05 * squad_role_modifier
```

## Transfer package score

Suggested first version:

```text
package_net_5gw_after_hit =
  package_expected_5gw_gain_proxy
- hit_cost
```

Where `package_expected_5gw_gain_proxy` should blend:

- candidate score improvement
- sell-to-buy fixture swing
- role security improvement
- route-to-points improvement
- team strength improvement
- historical package rule confidence

## Captaincy score

Suggested first version:

```text
captain_total_score =
  0.30 * ceiling_score
+ 0.25 * role_security_score
+ 0.20 * fixture_score
+ 0.15 * team_attack_score
+ 0.10 * route_to_points_score
```

If top-sample captaincy behaviour is available, include it as a small modifier, not a dominant feature.

---

# Critical implementation warnings

## Do not recommend transfers just because a player is highly ranked

A player can be excellent but irrelevant if:

- they are unaffordable
- they require selling a better player
- they create structural imbalance
- they only improve the team over one week
- they require a hit that is not paid back

## Do not judge every player through attacking returns

The current project already accounts for position-specific routes. Preserve that logic.

Examples:

- Goalkeepers: saves, clean sheets, goals conceded, BPS, bonus.
- Defenders: clean sheets, defensive contribution, BPS, bonus, attacking threat.
- Midfielders: attacking returns, defensive contribution, minutes, BPS, bonus, clean sheet point.
- Forwards: attacking returns, BPS, bonus, minutes.

## Do not overfit to manager `816200`

The weekly process must be informed by:

- manager `816200`'s decision history
- top-N sample behaviour
- actual outcome windows
- general player/team/fixture features

It should not simply learn `816200`'s preferences.

## Treat hit recommendations conservatively

A hit should need stronger evidence than a free transfer.

Default principle:

```text
A -4 needs a clear multi-week edge.
A -8 needs multiple independent improvements or injury/blank/double-gameweek context.
A -12 should be rare and require extreme context.
```

---

# How Codex should start this phase

Use this prompt:

```text
Start the next phase of the FPL retrospective project: the Weekly Decision System.

Before coding, read:
- AGENTS.md
- PLANS.md
- STATUS.md
- KANBAN.md
- BACKLOG.md
- SPRINTS.md
- WEEKLY_DECISION_SYSTEM_PLAN.md

First, do not implement code.

Your task is to update the project-management files to add Epic 11 and Sprints 11-14 from WEEKLY_DECISION_SYSTEM_PLAN.md.

Specifically:
1. Add Epic 11 to PLANS.md.
2. Add Stories 11.1 to 14.3 to BACKLOG.md.
3. Add Sprints 11-14 to SPRINTS.md.
4. Update KANBAN.md so Story 11.1 is Ready only after Story 10.2 is accepted as Done, or mark it Ready if Story 10.2 has already been accepted.
5. Update STATUS.md with the next phase state.
6. Do not change source code yet.
7. Stop and summarise the plan update.
```

After that, Codex should work one story at a time using the Codex prompts embedded above.
