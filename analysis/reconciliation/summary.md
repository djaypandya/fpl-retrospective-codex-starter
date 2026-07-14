# Reconciliation summary

**Resolved truth: the analyses do not contradict each other. The simple rule beat a prediction model and a no-transfer baseline in one simulation, but it lost to manager 816200's actual transfer choices in a different replay. The evidence supports a qualitative hierarchy of skilled human > simple rule approximately model > passivity.**

The two headline gaps are not the same currency. The **159-point** gap is a paired mean full-strategy season result across 40 starting squads from GW8 to GW34. The **197-point** gap is a sum across 45 candidate-available incoming-player holding windows for one manager. They must not be added, subtracted, ratioed, or compared as magnitudes. Only their directions and rankings can be reconciled.

## The apparent contradiction

The bank-aware replay asked whether a mechanical transfer rule could beat this manager's actual incoming players. It replayed 46 non-chip transfers and scored 45 rows where the rule had a candidate. The actual incoming players scored **784** holding-window points. The rule picks scored **587**, so the rule trailed by **197**.

The notebook asked a different question. It compared complete weekly strategies from 40 sampled starting squads. In the rerun, the no-transfer baseline averaged **1,481**, the Engine averaged **1,680**, and the highest-recent-points strategy averaged **1,839** from GW8 to GW34. The Engine beat hold by **199** with a paired 95% range of **+31 to +406**. The simple strategy beat the Engine by **159**, equivalent to Engine minus simple of **-159**, with a paired 95% range of **-271 to -62**.

Those findings can both be true because the opponent changed:

- In the notebook, the simple rule faced a model and a no-transfer strategy.
- In the replay, the simple rule faced a skilled human's actual buys.

## What the notebook numbers mean

### Availability and form

The notebook's **0.79 to 0.20** form collapse was reproduced from `data/processed/player_gw_features.csv`.

For a player-decision row at gameweek `t`:

- Recent form is total FPL points over `t-3` through `t`.
- The target is total FPL points over `t+1` through `t+4`.
- Decision gameweeks run from 4 through 34.
- A row must have player data in all four history and all four target gameweeks.

Across **23,911** complete rows, Spearman correlation between recent points and next-four-gameweek points was **0.7899**, which rounds to **0.79**.

The notebook panel labelled as players who play is reproduced by requiring at least **180 trailing minutes** over the same four-gameweek history. It is a prior availability screen, not a filter on realized future play. Across **6,786** screened rows, Spearman was **0.2030**, which rounds to **0.20**.

The five equal-count recent-form group means also match the notebook closely:

| Group | Notebook all | Recomputed all | Notebook screened | Recomputed screened |
|---|---:|---:|---:|---:|
| Lowest | 0.46 | 0.461 | 9.21 | 9.209 |
| Low | 0.58 | 0.576 | 10.41 | 10.419 |
| Mid | 2.15 | 2.153 | 11.30 | 11.289 |
| High | 8.02 | 8.025 | 12.10 | 12.099 |
| Highest | 11.93 | 11.930 | 13.54 | 13.542 |

The small hundredth-point differences come from hardcoded display rounding. The underlying rank correlations reproduce exactly to the notebook's shown precision.

### Prediction rank link

`src/fpl_retro/v0_1_engine.py` builds walk-forward predictions for decision GWs 8 through 34. Training uses only decision rows whose four-gameweek target is fully observed before the test decision. A logistic availability gate predicts the chance of playing at least 60 minutes next GW. A player is a likely starter when predicted probability is at least 0.5. Among that pool, a Ridge model ranks conditional next-four-gameweek points.

The notebook's ranking values and GW-block bootstrap ranges match the engine output:

| Ranker among predicted likely starters | Spearman vs realized next-4-GW points | 95% range |
|---|---:|---:|
| Engine | 0.268 | 0.247 to 0.289 |
| Recent minutes | 0.163 | 0.138 to 0.189 |
| Recent points | 0.151 | 0.120 to 0.182 |
| Fixtures only | 0.132 | 0.095 to 0.169 |
| Value | 0.068 | 0.035 to 0.101 |

This is a ranking test, not a decision-value test.

### Full strategy simulation

`src/fpl_retro/v1_engine.py` starts from 40 sampled GW8 squads using seed 1 and simulates GW8 through GW34. It uses formation-legal starting XIs, bench order, auto-subs, captain doubling, banked free transfers capped at two, transfer hits, and reconstructed prices. Chips are excluded.

The strategy labels mean:

- **Engine:** conditional predicted points for transfers after the availability gate, and availability-weighted predicted points for selection and captaincy.
- **Simple rule:** highest recent four-gameweek points among predicted likely starters for transfers, selection, and captaincy.
- **Hold:** no transfers. It still uses the Engine for squad selection and captaincy, so it is precisely a no-transfer baseline, not literal inactivity on every weekly choice.

The full v1 run was rerun during this reconciliation and matched the notebook exactly:

| Strategy | Mean GW8-34 total across 40 starts |
|---|---:|
| Hold squad | 1,481 |
| Engine | 1,680 |
| Simple recent-points strategy | 1,839 |

The isolated decision-layer comparisons also matched:

| Layer | Engine minus best simple | 95% range | Reading |
|---|---:|---:|---|
| Transfers | -33 | -155 to +53 | Tie, range crosses zero |
| Squad selection | -28 | -56 to -5 | Engine loss |
| Captaincy | -23 | -49 to -1 | Engine loss |

These layer tests hold the other decisions fixed. They are not additive, so **-33 -28 -23 is not a decomposition that must equal -159**.

The notebook's separate captain comparison uses manager 816200's real squads over 24 non-chip GWs. It captured **183** captain points for the actual picks, **199** for the Engine choice, and **204** for highest recent points. Those are single captain-player points, not doubled season totals and not the same sample as the 40-start simulation.

## The common replay yardstick

The new computation adds a true no-transfer baseline to the bank-aware replay. For each scored transfer at GW `T`, the baseline keeps the outgoing player and sums that player's `total_points` over the actual incoming player's same inclusive holding window `[T, hold_end]`. Missing player-gameweek rows count as zero, matching the replay.

All totals below use the same **45 candidate-available non-chip transfer rows**:

| Approach | Total holding-window points | Mean per transfer window |
|---|---:|---:|
| Manager 816200 actual incoming players | **784** | **17.42** |
| Simple bank-aware form rule | **587** | **13.04** |
| Keep the outgoing player | **534** | **11.87** |

On this one scale:

- The human choices led the rule by **197** points.
- The rule led doing nothing by **53** points.
- The human choices led doing nothing by **250** points.

This directly establishes **human > rule > no transfer** for the replay sample.

## Why the model was not put on the replay scale

The v0.1 and v1 engine exposes per-player walk-forward scores only for its published decision window. A leak-free shift from decision GW `t` to transfer GW `T=t+1` does not cover the manager's early transfers or late GW36 to GW38 transfers. Extending the model would require a new training and prediction design outside the locked engine, while a partial result would look more complete than it is.

The model replay placement was therefore skipped. The hierarchy shows the model beside the rule only as a **qualitative transfer-layer tie from the separate 40-start simulation**. It does not assign the model a replay total.

## Where the analyses agree

### Signal agreement

The notebook finds a **+0.20** Spearman link between recent points and next-four-gameweek points after the trailing-minutes screen. The replay story reports a **+0.19** Spearman link between trailing form and next-four-gameweek goals. The targets differ, points versus goals, so the estimates are not identical measurements. Both are small and support the same practical reading: recent FPL points are weak for separating players once availability is handled.

The replay story also reports **+0.35** for trailing xGI versus next-four-gameweek goals. That prior-study number was traced to `analysis/transfer_rule_replay_bank/transfer_rule_bank_story.md` but was not independently recomputed here.

### Failure-mode agreement

The notebook's Engine was **23 captain points per simulated season behind** the simple rule, with the 95% range below zero. The notebook interprets this as a safe model missing large captain hauls.

In the replay, **11 of 46** actual incoming players failed at least one locked rule filter. This includes upside or return-to-role cases that a mechanical prior-minutes screen cannot choose. Both analyses therefore point to the same limitation: a safe availability rule can miss ceiling when role changes, injury returns, or haul potential matter.

## Resolved unified truth

The contradiction is illusory. The evidence supports this operating view:

**Skilled human > simple rule approximately model > no transfer.**

- The human sits above the rule on the common one-manager transfer replay.
- The rule and model are approximately tied for transfers in the strategy simulation because their paired range crosses zero.
- The simple rule beats the model on the complete simulated strategy because selection and captaincy also matter.
- Both active approaches beat the relevant hold baseline in the notebook frame, while the rule also beats the outgoing-player hold baseline on the replay frame.

The simple rule is a strong, cheap **floor**. It improves on passivity and matches a more complex model on transfer decisions. It is not a **ceiling**. A good human can add value through availability updates, role changes, package context, and upside judgment that the rule does not encode.

## Risks and limitations

- This is one manager and one season. The human advantage is descriptive and can include luck.
- Replay holding windows ignore starting-XI use, captaincy, benching, transfer hits, and whether a counterfactual player would start.
- The replay uses a per-leg bank cap, not a joint package optimizer. Four actual buys used cash released by another same-GW leg.
- Only 35 of 46 actual incoming players passed all locked rule filters.
- The simulation reconstructs prices, ignores half-profit selling, and does not fully reproduce every FPL constraint.
- The layer comparisons are isolated experiments, not additive accounting.
- The 0.20 points target and 0.19 goals target are related but different outcomes.
- The **159 simulation gap and 197 replay gap are not comparable magnitudes**.

## Source trace

| Claim | Status | Source |
|---|---|---|
| Replay human 784, rule 587 | Recomputed and matched | `replay_bank_results.csv` |
| Replay no-transfer 534 | New computation | Raw manager transfers plus `player_gw_features.csv` |
| Form 0.7899 to 0.2030 | Recomputed | `player_gw_features.csv`, engine-equivalent panel |
| Form-bin means | Recomputed, matches display rounding | `player_gw_features.csv` |
| Ranker 0.268, 0.163, 0.151, 0.132, 0.068 and ranges | Engine output matched | `v0_1_engine.py` |
| Simulation 1,481, 1,680, 1,839 and paired gaps | Full rerun matched | `v1_engine.py` |
| Layer -33, -28, -23 and ranges | Full rerun matched | `v1_engine.py` |
| Captain 183, 199, 204 | Full rerun matched | `v1_engine.py` |
| Form-to-goals +0.19 and xGI-to-goals +0.35 | Reported prior study, not rerun here | Bank replay story |
| Eleven actual buys outside rule pool | Recomputed | `replay_bank_results.csv` |

`weekly_decision_system.py`, `transfer_outcomes.py`, `evaluation.py`, `benchmark.py`, and `rules.py` support other retrospective and weekly decision workflows. They do not generate the notebook's hardcoded simulation headlines. `factor_screen.py` builds incremental ranking tests and cites the v1 Engine's 0.268 rank result, but it is not the source of the 40-start season totals.
