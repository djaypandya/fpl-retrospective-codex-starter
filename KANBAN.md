# KANBAN.md

## Board rules

This board tracks stories, not individual tasks.

Tasks belong inside `BACKLOG.md` under each story.

`BACKLOG.md` remains the detailed source of truth.  
`KANBAN.md` is the human review board.

Codex must update this file whenever a story changes status.

## Status meanings

- Backlog: valid story, not ready yet
- Ready: dependencies are satisfied and the story can start
- In Progress: Codex is currently working on it
- In Review: implementation is complete and human review is needed
- Done: acceptance criteria and checks have passed
- Blocked: work cannot continue without a decision, missing input, or failed dependency

## WIP limits

- Maximum In Progress stories: 1
- Maximum In Review stories: 3

Codex must not start a new story if another story is In Progress.

---

# Current Sprint Board

Current sprint: Sprint 10 - Final report

## Backlog

| Story | Epic | Size | Dependency | Notes |
|---|---|---:|---|---|
| None |  |  |  |  |

## Ready

| Story | Epic | Size | Goal |
|---|---|---:|---|
| None |  |  |  |

## In Progress

| Story | Epic | Started | Current task |
|---|---|---|---|
| None |  |  |  |

## In Review

| Story | Epic | Checks run | Human review needed |
|---|---|---|---|
| 10.2 Create final executive summary | Epic 10 | final summary content validation; referenced outputs check; confidence qualification check; compileall | Yes |

## Done

| Story | Epic | Completed | Outputs |
|---|---|---|---|
| 10.1 Create season gap and leak summary | Epic 10 | 2026-05-30 | season_gap_leak_summary.csv; season_gap_waterfall.png |
| 9.4 Generate plain-English rules for next season | Epic 9 | 2026-05-30 | next_season_rulebook.csv |
| 9.3 Test transfer-style rules | Epic 9 | 2026-05-30 | transfer_rule_candidates.csv; transfer_rule_packages.csv; transfer_rule_enriched.csv |
| 9.2 Test simple player selection rules | Epic 9 | 2026-05-29 | player_selection_rule_candidates.csv |
| 9.1 Create candidate rule features | Epic 9 | 2026-05-29 | candidate_rule_features.csv |
| 8.2 Compare transfer behaviour | Epic 8 | 2026-05-29 | manager_transfer_enriched.csv; transfer_behaviour_benchmark.csv |
| 8.4 Compare squad structure and team exposure | Epic 8 | 2026-05-29 | manager_squad_structure_gameweek.csv; squad_structure_benchmark.csv |
| 8.3 Compare player adoption timing | Epic 8 | 2026-05-29 | player_adoption_timing.csv |
| 8.1 Build manager behaviour summary | Epic 8 | 2026-05-29 | manager_behaviour_summary.csv |
| 7.5 Evaluate benching and starting XI decisions | Epic 7 | 2026-05-29 | my_benching_review.csv; my_benching_gameweek_summary.csv |
| 7.4 Evaluate captaincy | Epic 7 | 2026-05-29 | my_captaincy_review.csv; captaincy_delta.png |
| 7.3 Classify transfer decisions | Epic 7 | 2026-05-29 | my_transfer_decision_labels.csv; my_transfer_group_decision_labels.csv |
| 7.2 Add transfer process features | Epic 7 | 2026-05-29 | my_transfer_process_features.csv |
| 7.1 Evaluate transfer outcomes | Epic 7 | 2026-05-29 | my_transfer_outcomes.csv |
| 6.2 Reconstruct my squad each gameweek | Epic 6 | 2026-05-29 | my_squad_gameweek.csv |
| 6.1 Build my gameweek timeline | Epic 6 | 2026-05-29 | my_gameweek_timeline.csv |
| 5.3 Create fixture difficulty table | Epic 5 | 2026-05-29 | fixture_difficulty.csv |
| 5.2 Create team strength table | Epic 5 | 2026-05-29 | team_strength.csv |
| 5.1 Create player-gameweek features table | Epic 5 | 2026-05-29 | player_gw_features.csv |
| 3.1 Fetch top-N standings pages | Epic 3 | 2026-05-28 | top_n_standings_smoke.csv; standings smoke raw pages |
| 3.2 Create reproducible rank-stratified sample | Epic 3 | 2026-05-28 | top_n_sample_managers.csv; top_n_sample_rank_distribution.csv |
| 3.3 Validate sample quality | Epic 3 | 2026-05-28 | top_n_sample_summary.csv; top_n_sample_rank_distribution.png |
| 4.1 Fetch manager history and transfers | Epic 4 | 2026-05-28 | manager_history.csv; manager_chips.csv; manager_transfers.csv; manager_fetch_failures.csv |
| 4.2 Fetch manager picks by gameweek | Epic 4 | 2026-05-29 | manager_picks.csv; manager_picks_entry_history.csv; manager_automatic_subs.csv; manager_picks_failures.csv |

## Blocked

| Story | Epic | Blocker | Decision needed |
|---|---|---|---|
| None |  |  |  |

---

# Sprint Progress

| Sprint | Stories Planned | Done | In Review | Blocked | Progress |
|---|---:|---:|---:|---:|---:|
| Sprint 1 | 2 | 2 | 0 | 0 | 100% |
| Sprint 2 | 4 | 4 | 0 | 0 | 100% |
| Sprint 3 | 3 | 3 | 0 | 0 | 100% |
| Sprint 4 | 2 | 2 | 0 | 0 | 100% |
| Sprint 5 | 3 | 3 | 0 | 0 | 100% |
| Sprint 6 | 2 | 2 | 0 | 0 | 100% |
| Sprint 7 | 5 | 5 | 0 | 0 | 100% |
| Sprint 8 | 4 | 4 | 0 | 0 | 100% |
| Sprint 9 | 4 | 4 | 0 | 0 | 100% |
| Sprint 10 | 2 | 1 | 1 | 0 | 100% |

---

# Epic Progress

| Epic | Stories Done | Stories Total | Progress | Status |
|---|---:|---:|---:|---|
| Epic 1: Project skeleton and decision framework | 2 | 2 | 100% | Done |
| Epic 2: Fetch and cache core FPL data | 4 | 4 | 100% | Done |
| Epic 3: Build representative top-N sample | 3 | 3 | 100% | Done |
| Epic 4: Fetch manager histories, transfers, and picks | 2 | 2 | 100% | Done |
| Epic 5: Build analytical tables | 3 | 3 | 100% | Done |
| Epic 6: Reconstruct my season | 2 | 2 | 100% | Done |
| Epic 7: Evaluate my decisions | 5 | 5 | 100% | Done |
| Epic 8: Compare me against the top-N sample | 4 | 4 | 100% | Done |
| Epic 9: Build decision rules under uncertainty | 4 | 4 | 100% | Done |
| Epic 10: Build final retrospective report | 1 | 2 | 100% | Active |

---

# Last Update

Date: 2026-05-30  
Updated by: ChatGPT  
Summary: Story 10.2 moved to In Review after adding the final executive summary section to the notebook. Sprint 10 remains open pending human acceptance of Story 10.2.  
Next recommended story: Review Story 10.2 and accept it if the final summary is useful.
