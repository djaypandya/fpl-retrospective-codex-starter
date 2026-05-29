# BACKLOG.md

## Story status labels

- Backlog
- Ready
- In Progress
- In Review
- Done
- Blocked

## Size labels

- XS: tiny change
- S: small notebook or config story
- M: meaningful data pipeline step
- L: too big, split before starting
- XL: invalid, must be broken down

---

# Epic 1: Project skeleton and decision framework

## Story 1.1: Create notebook config and folder structure

Status: Done  
Epic: Epic 1  
Sprint: Sprint 1  
Size: S  
Priority: High  
Depends on: None  
Human review: Required

### User story

As a data analyst, I want a config section at the top of the notebook, so that I can change team ID, top-N threshold, sample size, season, and cache settings in one place.

### Acceptance criteria

- Config variables exist for `MY_TEAM_ID`, `TOP_N`, `SAMPLE_SIZE`, `SEASON_GWS`, `RANDOM_SEED`, `CACHE_ENABLED`, `REQUEST_SLEEP_SECONDS`.
- Folder paths are created using `pathlib`.
- Running the cell twice does not break anything.
- Notebook prints a config summary.

### Tasks

- [x] Create project folders if missing.
- [x] Create notebook file if missing.
- [x] Add markdown project objective.
- [x] Add config code cell.
- [x] Add folder creation code.
- [x] Add validation printout.

### Implementation task breakdown

- [x] Confirm existing notebook and folders.
- [x] Replace placeholder setup cell with final config section.
- [x] Ensure setup creates all required raw, processed, table, and chart folders.
- [x] Add a clear config summary printout.
- [x] Run the setup cell twice to verify idempotency.
- [x] Verify required folders exist after execution.

### Checks

- [x] Running the setup cell twice succeeds.
- [x] Required folders exist.
- [x] Config values are printed correctly.

### Definition of done

- Notebook section exists.
- Folder structure exists.
- `STATUS.md` is updated.
- `KANBAN.md` is updated.

---

## Story 1.2: Define decision quality framework

Status: Done  
Epic: Epic 1  
Sprint: Sprint 1  
Size: S  
Priority: High  
Depends on: Story 1.1  
Human review: Required

### User story

As an FPL analyst, I want clear decision quality categories, so that I do not confuse good decisions with good outcomes.

### Acceptance criteria

The notebook defines:

- Good process, good outcome
- Good process, bad outcome
- Bad process, good outcome
- Bad process, bad outcome

### Tasks

- [x] Add markdown explanation of process quality versus outcome quality.
- [x] Add hindsight leakage warning.
- [x] Create `DECISION_QUALITY_LABELS` dictionary.
- [x] Add simple display of labels.

### Implementation task breakdown

- [x] Add a notebook markdown section for the decision quality framework.
- [x] Define the process/outcome distinction without using future information.
- [x] Add an explicit hindsight leakage warning.
- [x] Add `DECISION_QUALITY_LABELS` with exactly four categories.
- [x] Display the labels in a readable table.
- [x] Run validation checks for label count and readability.

### Checks

- [x] Dictionary has exactly four labels.
- [x] Labels are human-readable.

### Definition of done

- Framework section exists.
- Labels are defined.
- `STATUS.md` and `KANBAN.md` are updated.

---

# Epic 2: Fetch and cache core FPL data

## Story 2.1: Build API fetch and cache helpers

Status: Done  
Epic: Epic 2  
Sprint: Sprint 2  
Size: M  
Priority: High  
Depends on: Story 1.1  
Human review: Required

### User story

As a notebook user, I want reusable API helper functions, so that every endpoint can be fetched consistently and safely.

### Acceptance criteria

- `fetch_json(url, cache_path=None, force_refresh=False)` exists.
- Cached JSON loads when available.
- API response errors are handled.
- Successful responses are saved.
- A smoke test works.

### Tasks

- [x] Create `src/fpl_retro/cache.py`.
- [x] Create `src/fpl_retro/api.py`.
- [x] Implement `fetch_json`.
- [x] Add notebook section.
- [x] Add smoke test.
- [x] Save example cached response.
- [x] Update project files.

### Implementation task breakdown

- [x] Inspect existing helper modules before editing.
- [x] Implement JSON cache load/save helpers.
- [x] Implement `fetch_json(url, cache_path=None, force_refresh=False)`.
- [x] Add a notebook section for API/cache smoke testing.
- [x] Run a bootstrap-static smoke test through the helper.
- [x] Verify saved JSON reloads from cache.
- [x] Validate expected bootstrap keys.

### Checks

- [x] API response status is 200.
- [x] JSON file is saved.
- [x] Cached JSON reloads.
- [x] Expected bootstrap keys exist.

### Definition of done

- Acceptance criteria met.
- Checks pass.
- Story moved to In Review.
- `STATUS.md` and `KANBAN.md` updated.

---

## Story 2.2: Fetch and process bootstrap-static

Status: Done  
Epic: Epic 2  
Sprint: Sprint 2  
Size: M  
Priority: High  
Depends on: Story 2.1  
Human review: Required

### User story

As an FPL analyst, I want player, team, and gameweek metadata, so that all later tables can be joined to meaningful names and positions.

### Acceptance criteria

- Fetches `bootstrap-static`.
- Creates `players_df`, `teams_df`, `events_df`, and `element_types_df`.
- Player table includes player ID, web name, team name, position, price, selected by percent, form, points, minutes, and expected metrics where available.
- Saves processed CSVs.

### Tasks

- [x] Load bootstrap JSON through cache helper.
- [x] Create dataframes.
- [x] Join player team and position names.
- [x] Keep defensive column selection for missing fields.
- [x] Save processed CSVs.
- [x] Display shapes and heads.

### Implementation task breakdown

- [x] Inspect cached bootstrap-static structure.
- [x] Add notebook section to load bootstrap JSON through `fetch_json`.
- [x] Create `players_df`, `teams_df`, `events_df`, and `element_types_df`.
- [x] Join team and position names into `players_df`.
- [x] Select player columns defensively when optional expected metrics are missing.
- [x] Save processed CSVs to `data/processed/`.
- [x] Run shape, key, join, and output-file checks.

### Checks

- [x] Expected top-level keys exist.
- [x] Players table has rows.
- [x] Team and position joins succeed.
- [x] Output CSVs exist.

### Definition of done

- Processed metadata tables exist.
- Checks pass.
- Board and status updated.

---

## Story 2.3: Fetch fixtures

Status: Done  
Epic: Epic 2  
Sprint: Sprint 2  
Size: S  
Priority: High  
Depends on: Story 2.1, Story 2.2  
Human review: Required

### User story

As an FPL analyst, I want match and fixture data, so that I can estimate team strength and fixture difficulty.

### Acceptance criteria

- Fetches all fixtures.
- Creates `fixtures_df`.
- Adds home and away team names.
- Saves processed CSV.

### Tasks

- [x] Load fixtures JSON through cache helper.
- [x] Create fixtures dataframe.
- [x] Join home and away team names.
- [x] Save CSV.
- [x] Display shape and missing event count.

### Implementation task breakdown

- [x] Add notebook section for fixture processing.
- [x] Load fixtures JSON through `fetch_json`.
- [x] Create `fixtures_df`.
- [x] Join home and away team names from `teams_df`.
- [x] Save `data/processed/fixtures.csv`.
- [x] Run row count, key column, join, and output-file checks.

### Checks

- [x] Fixture table has rows.
- [x] Team joins work.
- [x] Key columns exist.

### Definition of done

- `data/processed/fixtures.csv` exists.
- Checks pass.
- Board and status updated.

---

## Story 2.4: Fetch gameweek live player data

Status: Done  
Epic: Epic 2  
Sprint: Sprint 2  
Size: M  
Priority: High  
Depends on: Story 2.1, Story 2.2  
Human review: Required

### User story

As an FPL analyst, I want player performance by gameweek, so that I can evaluate player choices and transfer outcomes.

### Acceptance criteria

- Fetches `event/{gw}/live` for every gameweek.
- Creates one long `gw_live_df`.
- Includes player ID, gameweek, total points, minutes, goals, assists, clean sheets, bonus, BPS, and expected metrics where available.
- Saves raw and processed data.

### Tasks

- [x] Loop over `SEASON_GWS`.
- [x] Fetch and cache each gameweek live endpoint.
- [x] Flatten player stats.
- [x] Join player names and metadata.
- [x] Save CSV.
- [x] Print summary.

### Implementation task breakdown

- [x] Add notebook section for gameweek live player data.
- [x] Create raw cache paths under `data/raw/gw_live/`.
- [x] Fetch and cache `event/{gw}/live` for each gameweek in `SEASON_GWS`.
- [x] Flatten each player `stats` payload into one row per player-gameweek.
- [x] Preserve FPL scoring-driver columns where available.
- [x] Join player names, team and position metadata.
- [x] Save `data/processed/gw_live.csv`.
- [x] Run gameweek coverage, row-count, join and output-file checks.

### Checks

- [x] Expected gameweeks present.
- [x] Row counts look plausible.
- [x] Player metadata join works.
- [x] Output CSV exists.

### Definition of done

- `data/processed/gw_live.csv` exists.
- Checks pass.
- Board and status updated.

---

# Epic 3: Build representative top-N sample

## Story 3.1: Fetch top-N standings pages

Status: Done  
Epic: Epic 3  
Sprint: Sprint 3  
Size: M  
Priority: High  
Depends on: Story 2.1  
Human review: Required

### User story

As a data analyst, I want to fetch standings pages from the Overall league, so that I can identify candidate managers inside the top N.

### Acceptance criteria

- Uses overall league ID `314`.
- Handles 50 managers per page.
- Calculates pages needed from `TOP_N`.
- Supports smoke test mode and full-fetch mode.
- Caches each page.

### Tasks

- [x] Add overall league config.
- [x] Implement page fetch function.
- [x] Add smoke test pages.
- [x] Extract standings results.
- [x] Save candidates smoke CSV.

### Implementation task breakdown

- [x] Add Sprint 3 notebook section for Overall league standings.
- [x] Define `OVERALL_LEAGUE_ID`, `STANDINGS_PAGE_SIZE`, smoke/full mode controls, and pages-needed calculation from `TOP_N`.
- [x] Implement a standings page URL/helper function.
- [x] Fetch and cache smoke standings pages.
- [x] Flatten standings results into candidate manager rows.
- [x] Save the smoke candidate table to `data/processed/`.
- [x] Validate manager ID, rank, page number, and row-count checks.

### Checks

- [x] Smoke pages fetch successfully.
- [x] Candidate rows include manager ID and rank.
- [x] Page numbers are preserved.

### Definition of done

- Candidate standings table exists.
- Checks pass.
- Board and status updated.

---

## Story 3.2: Create reproducible rank-stratified sample

Status: Done  
Epic: Epic 3  
Sprint: Sprint 3  
Size: M  
Priority: High  
Depends on: Story 3.1  
Human review: Required

### User story

As an FPL analyst, I want a reproducible stratified sample, so that my insights are not distorted by only studying one rank band.

### Acceptance criteria

- Defines rank bands.
- Samples managers from each band.
- Uses `RANDOM_SEED`.
- Supports `SAMPLE_SIZE`.
- Outputs final sample manager IDs.
- Keeps `MY_TEAM_ID` separate.

### Tasks

- [x] Define rank bands.
- [x] Implement rank band assignment.
- [x] Implement sample allocation.
- [x] Sample reproducibly.
- [x] Save sample managers.
- [x] Save sample rank distribution.

### Implementation task breakdown

- [x] Verify candidate standings input is large enough for `SAMPLE_SIZE`.
- [x] Define rank bands for top-N managers.
- [x] Assign candidates to rank bands.
- [x] Allocate sample sizes across rank bands.
- [x] Sample reproducibly with `RANDOM_SEED`.
- [x] Keep `MY_TEAM_ID` separate from sampled comparison managers.
- [x] Save sample manager and rank distribution outputs.

### Blocker

Resolved on 2026-05-28. Cached standings pages 1-1600 were parsed into `data/processed/top_n_standings_candidates.csv`, giving 79,996 unique candidate managers for the current top-80K threshold.

### Revision notes

- [x] Revised allocation to enforce at least 30 sampled managers per non-empty rank band after validation showed the `1-1k` band had only 13 managers.

### Checks

- [x] Sample does not exceed available candidates.
- [x] Rank bands are assigned correctly.
- [x] Output files exist.

### Definition of done

- `top_n_sample_managers.csv` exists.
- Checks pass.
- Board and status updated.

---

## Story 3.3: Validate sample quality

Status: Done  
Epic: Epic 3  
Sprint: Sprint 3  
Size: S  
Priority: Medium  
Depends on: Story 3.2  
Human review: Required

### User story

As an analyst, I want to validate the sample distribution, so that I know whether the top-N sample is representative enough for comparison.

### Acceptance criteria

- Shows count per rank band.
- Shows min, median, max rank.
- Shows total points distribution.
- Flags under-sampled bands.
- Produces one chart.

### Tasks

- [x] Create rank band count table.
- [x] Create summary by rank band.
- [x] Add low sample warning.
- [x] Save chart.

### Implementation task breakdown

- [x] Load sample managers and distribution outputs from Story 3.2.
- [x] Validate sample ranks and required columns.
- [x] Create rank band quality summary with rank and total-points statistics.
- [x] Flag rank bands with fewer than 30 sampled managers.
- [x] Regenerate sample after adding 17 more `1-1k` managers to meet the 30-manager threshold.
- [x] Save sample quality summary CSV.
- [x] Save one sample quality chart.

### Checks

- [x] No impossible ranks.
- [x] Chart exists.
- [x] Summary CSV exists.

### Definition of done

- Sample quality summary exists.
- Checks pass.
- Board and status updated.

---

# Epic 4: Fetch manager histories, transfers, and picks

## Story 4.1: Fetch manager history and transfers

Status: Done  
Epic: Epic 4  
Sprint: Sprint 4  
Size: M  
Priority: High  
Depends on: Story 3.2  
Human review: Required

### User story

As a data analyst, I want manager-level history and transfers, so that I can evaluate rank movement, points, hits, chips, and transfer behaviour.

### Acceptance criteria

- Fetches `entry/{team_id}/history`.
- Fetches `entry/{team_id}/transfers`.
- Works for my team and sample teams.
- Caches by manager ID.
- Handles failed fetches by logging them.

### Tasks

- [x] Implement manager history fetch.
- [x] Implement manager transfer fetch.
- [x] Create manager list.
- [x] Fetch my team and sample teams.
- [x] Normalise history, chips, transfers.
- [x] Save processed outputs and failures.

### Implementation task breakdown

- [x] Inspect existing API/cache helpers and sample manager output.
- [x] Add reusable manager history and transfer fetch helpers.
- [x] Create a manager list containing `MY_TEAM_ID` plus sampled manager IDs.
- [x] Cache each manager history and transfer response under `data/raw/managers/`.
- [x] Normalise history current rows, chips rows, and transfer rows.
- [x] Save processed manager history, chips, transfers, manager list, and failures.
- [x] Run manager data validation checks.

### Checks

- [x] My team ID appears.
- [x] Gameweeks are present.
- [x] Failure count is logged.
- [x] Output CSVs exist.

### Definition of done

- Manager history, chips, and transfer tables exist.
- Checks pass.
- Board and status updated.

---

## Story 4.2: Fetch manager picks by gameweek

Status: Done  
Epic: Epic 4  
Sprint: Sprint 4  
Size: M  
Priority: High  
Depends on: Story 4.1  
Human review: Required

### User story

As an FPL analyst, I want each manager's picks by gameweek, so that I can analyse captaincy, benching, formation, and player ownership among strong managers.

### Acceptance criteria

- Fetches `entry/{team_id}/event/{gw}/picks`.
- Gets picks for my team across all gameweeks.
- Gets picks for sampled teams across all gameweeks.
- Caches responses.
- Handles failures.
- Preserves captain, vice-captain, multiplier, and position.

### Tasks

- [x] Add `MAX_MANAGERS_FOR_PICKS` config for smoke testing.
- [x] Implement picks fetch function.
- [x] Loop through managers and gameweeks.
- [x] Normalise picks.
- [x] Join metadata.
- [x] Save outputs and failures.

### Implementation task breakdown

- [x] Inspect manager list and existing manager-data helper patterns.
- [x] Add configurable `MAX_MANAGERS_FOR_PICKS` smoke/full-run guard.
- [x] Add reusable picks URL, fetch, and normalisation helpers.
- [x] Fetch and cache picks for `MY_TEAM_ID` across all gameweeks.
- [x] Fetch and cache picks for sampled managers across all gameweeks within the configured run limit.
- [x] Preserve picks, automatic substitutions, captain, vice-captain, multiplier, chip, and position fields where available.
- [x] Join player metadata.
- [x] Save processed picks and failure outputs.
- [x] Run manager-picks validation checks.

### Blocker

Resolved on 2026-05-29. The manager picks run was completed outside Codex and validated afterward. Processed picks outputs exist for 1,001 managers and 38,037 manager-gameweeks, with one 404 failure logged.

### Checks

- [x] My team has picks.
- [x] Typical manager-gameweek has 15 picks.
- [x] Captain and vice-captain flags exist.
- [x] Failure table exists.

### Definition of done

- `manager_picks.csv` exists.
- Checks pass.
- Board and status updated.

---

# Epic 5: Build analytical tables

## Story 5.1: Create player-gameweek features table

Status: Done  
Epic: Epic 5  
Sprint: Sprint 5  
Size: M  
Priority: High  
Depends on: Story 2.4  
Human review: Required

### User story

As an analyst, I want one row per player per gameweek, so that I can calculate form, trend, and future outcomes.

### Acceptance criteria

- Builds `player_gw_features_df`.
- Includes actual points and raw stats.
- Adds rolling historical features using only prior data.
- Avoids leakage from the same or future gameweek.

### Tasks

- [x] Create player-gameweek table.
- [x] Add rolling points.
- [x] Add rolling minutes.
- [x] Add rolling xGI where available.
- [x] Add season-to-date fields.
- [x] Save output.

### Implementation task breakdown

- [x] Inspect `gw_live.csv` columns and existing feature helpers.
- [x] Add reusable player-gameweek feature builder.
- [x] Preserve actual points and raw stats as outcomes.
- [x] Add prior-only rolling points, minutes, and xGI features.
- [x] Add prior-only season-to-date points, minutes, and starts where available.
- [x] Add prior-only rolling attacking, defensive contribution, clean-sheet, goalkeeper, bonus/BPS, and discipline features.
- [x] Add prior-only role stability, threshold-rate, and per-90 features.
- [x] Save `data/processed/player_gw_features.csv`.
- [x] Regenerate `data/processed/player_gw_features.csv`.
- [x] Run expanded leakage, shape, key, scoring-column, derived-rate, and output-file checks.

### Checks

- [x] GW1 rolling features are null or zero.
- [x] Rolling features use shift before rolling.
- [x] Output CSV exists.
- [x] Scoring-driver rolling features use only prior gameweeks.
- [x] Per-90 and threshold-rate features are finite or null, never infinite.

### Definition of done

- Player features table exists.
- Leakage checks pass.
- Board and status updated.

---

## Story 5.2: Create team strength table

Status: Done  
Epic: Epic 5  
Sprint: Sprint 5  
Size: M  
Priority: High  
Depends on: Story 2.3  
Human review: Required

### User story

As an analyst, I want team strength metrics by gameweek, so that player and transfer rules account for the quality of the player's club.

### Acceptance criteria

- Builds team attacking and defensive strength using fixture results.
- Uses only matches before the gameweek being predicted.
- Includes home and away splits if feasible.
- Includes rolling goals for, goals against, clean sheets, and xG-like stats if available.

### Tasks

- [x] Convert fixtures into team-perspective rows.
- [x] Calculate rolling strength metrics.
- [x] Create one row per team per gameweek.
- [x] Save output.

### Implementation task breakdown

- [x] Inspect `fixtures.csv` columns and gameweek coverage.
- [x] Add reusable team-strength feature builder.
- [x] Convert completed fixtures into one row per team-match.
- [x] Add prior-only rolling goals for, goals against, clean sheets, and expected goals where available.
- [x] Add prior-only home/away split metrics where feasible.
- [x] Create one row per team per gameweek.
- [x] Save `data/processed/team_strength.csv`.
- [x] Run leakage, shape, key, gameweek, and output-file checks.

### Checks

- [x] No current gameweek result leaks into pre-GW strength.
- [x] Each team has each gameweek.
- [x] Output CSV exists.

### Definition of done

- Team strength table exists.
- Leakage checks pass.
- Board and status updated.

---

## Story 5.3: Create fixture difficulty table

Status: Done  
Epic: Epic 5  
Sprint: Sprint 5  
Size: M  
Priority: High  
Depends on: Story 5.2  
Human review: Required

### User story

As an analyst, I want fixture difficulty features, so that transfer and selection rules account for upcoming opponent quality.

### Acceptance criteria

- Builds upcoming fixture difficulty for each team and gameweek.
- Includes FPL difficulty rating.
- Includes opponent team strength.
- Includes next 1, 3, and 5 fixture outlook.
- Handles blanks and doubles.

### Tasks

- [x] Build future fixture windows.
- [x] Add FPL difficulty.
- [x] Add opponent strength.
- [x] Add blank and double indicators.
- [x] Save output.

### Implementation task breakdown

- [x] Inspect `fixtures.csv` and `team_strength.csv` join keys and double/blank coverage.
- [x] Add reusable fixture difficulty feature builder.
- [x] Convert fixtures into team-perspective future fixture rows.
- [x] Join opponent prior team-strength features.
- [x] Aggregate next 1, 3, and 5 fixture outlook windows.
- [x] Add blank and double indicators.
- [x] Save `data/processed/fixture_difficulty.csv`.
- [x] Run home/away, blank/double, shape, key, leakage, and output-file checks.

### Checks

- [x] Home and away difficulty are handled correctly.
- [x] Blanks and doubles are not silently dropped.
- [x] Output CSV exists.

### Definition of done

- Fixture outlook table exists.
- Checks pass.
- Board and status updated.

---

# Epic 6: Reconstruct my season

## Story 6.1: Build my gameweek timeline

Status: Done  
Epic: Epic 6  
Sprint: Sprint 6  
Size: M  
Priority: High  
Depends on: Story 4.2  
Human review: Required

### User story

As an FPL manager, I want a weekly timeline of my season, so that I can identify where my season changed.

### Acceptance criteria

- Filters manager history to `MY_TEAM_ID`.
- Adds chips.
- Adds transfers and hits.
- Adds captain points.
- Adds bench points.
- Adds rank movement.

### Tasks

- [x] Filter manager history.
- [x] Add chip usage.
- [x] Add transfer counts and names.
- [x] Add captain and vice-captain.
- [x] Add bench points.
- [x] Add rank movement.
- [x] Save timeline.

### Implementation task breakdown

- [x] Inspect manager history, chips, transfers, picks, and player feature schemas.
- [x] Add reusable timeline builder for manager `816200`.
- [x] Aggregate weekly transfer counts, transfer costs, and transfer player names.
- [x] Add chip usage by gameweek.
- [x] Add captain, vice-captain, captain points, and bench points from picks.
- [x] Add gameweek and overall rank movement.
- [x] Save `data/processed/my_gameweek_timeline.csv`.
- [x] Run row-count, gameweek, captain, bench, rank movement, and output-file checks.

### Checks

- [x] One row per gameweek.
- [x] Captain exists for each available gameweek.
- [x] Output CSV exists.

### Definition of done

- My season timeline exists.
- Checks pass.
- Board and status updated.

---

## Story 6.2: Reconstruct my squad each gameweek

Status: Done  
Epic: Epic 6  
Sprint: Sprint 6  
Size: M  
Priority: High  
Depends on: Story 6.1, Story 5.3  
Human review: Required

### User story

As an FPL manager, I want to see my squad, starters, bench, and captain each week, so that I can review selection quality.

### Acceptance criteria

- Creates one row per player per GW for my team.
- Labels starter versus bench.
- Adds captain/vice-captain.
- Adds player GW points.
- Adds pre-GW player, team, and fixture features.

### Tasks

- [x] Filter picks to my team.
- [x] Add starter and bench flags.
- [x] Add captain/vice-captain.
- [x] Add actual points.
- [x] Add pre-GW player features.
- [x] Add team and fixture features.
- [x] Save enriched picks.

### Implementation task breakdown

- [x] Inspect picks, player features, team strength, fixture difficulty, and team lookup schemas.
- [x] Add reusable enriched squad builder for manager `816200`.
- [x] Filter picks to my team and normalise gameweek/player keys.
- [x] Add starter, bench, captain, vice-captain, and effective multiplier fields.
- [x] Join actual player gameweek points and prior-only player features.
- [x] Join prior-only team strength features.
- [x] Join fixture difficulty outlook features.
- [x] Save `data/processed/my_squad_gameweek.csv`.
- [x] Run 15-pick, captain, vice-captain, join completeness, leakage-column, key, and output-file checks.

### Checks

- [x] 15 picks per gameweek unless data missing.
- [x] Exactly one captain per gameweek.
- [x] Exactly one vice-captain per gameweek.
- [x] Output CSV exists.

### Definition of done

- My enriched picks table exists.
- Checks pass.
- Board and status updated.

---

# Epic 7: Evaluate my decisions

## Story 7.1: Evaluate transfer outcomes

Status: Done  
Epic: Epic 7  
Sprint: Sprint 7  
Size: M  
Priority: High  
Depends on: Story 5.1, Story 4.1  
Human review: Required

### User story

As an FPL manager, I want to know which transfers gained or lost points over different horizons, so that I can understand whether my transfer strategy worked.

### Acceptance criteria

- Calculates transfer-in and transfer-out points over 1 GW, 3 GWs, 5 GWs, and rest of season.
- Calculates net gain fields.
- Documents hit allocation assumption.

### Tasks

- [x] Filter transfers to my team.
- [x] Add player names.
- [x] Calculate future points for players in and out.
- [x] Calculate net gains.
- [x] Save review table.

### Implementation task breakdown

- [x] Inspect transfer, timeline, player, and player-gameweek schemas.
- [x] Add reusable transfer outcome review builder.
- [x] Filter raw transfers to manager `816200`.
- [x] Add transfer-in and transfer-out names and prices.
- [x] Calculate transfer-in and transfer-out points for 1 GW, 3 GW, 5 GW, and rest of season.
- [x] Calculate gross and hit-adjusted net gains.
- [x] Document hit allocation assumption in output columns and notebook text.
- [x] Save `outputs/tables/my_transfer_outcomes.csv`.
- [x] Run horizon arithmetic, name completeness, hit allocation, shape/key, and output-file checks.

### Checks

- [x] Transfer horizons are calculated correctly.
- [x] No missing names for valid players.
- [x] Output CSV exists.

### Definition of done

- My transfer review exists.
- Checks pass.
- Board and status updated.

---

## Story 7.2: Add transfer process features

Status: Done  
Epic: Epic 7  
Sprint: Sprint 7  
Size: M  
Priority: High  
Depends on: Story 7.1, Story 5.3  
Human review: Required

### User story

As an FPL manager, I want to know whether a transfer was reasonable at the time, so that I can distinguish bad process from bad luck.

### Acceptance criteria

- Adds pre-GW features for player in and player out.
- Uses only pre-decision data.
- Adds difference features.

### Tasks

- [x] Add player rolling features.
- [x] Add team strength.
- [x] Add fixture outlook.
- [x] Add difference metrics.
- [x] Save output.

### Implementation task breakdown

- [x] Inspect transfer outcome, player feature, team strength, and fixture difficulty schemas.
- [x] Add reusable transfer process feature builder.
- [x] Join player-in and player-out prior-only features for the transfer gameweek.
- [x] Join team strength prior-only features for player-in and player-out teams.
- [x] Join upcoming fixture outlook features for player-in and player-out teams.
- [x] Calculate `in - out` difference features.
- [x] Save `outputs/tables/my_transfer_process_features.csv`.
- [x] Run row-count, key, join completeness, difference arithmetic, leakage, and output-file checks.

### Checks

- [x] Features use decision GW correctly.
- [x] No current GW outcome leakage.
- [x] Output CSV exists.

### Definition of done

- Transfer process table exists.
- Leakage checks pass.
- Board and status updated.

---

## Story 7.3: Classify transfer decisions

Status: Done  
Epic: Epic 7  
Sprint: Sprint 7  
Size: M  
Priority: High  
Depends on: Story 7.2  
Human review: Required

### User story

As an FPL manager, I want each transfer classified, so that I can see whether my bad outcomes came from bad process or variance.

### Acceptance criteria

- Creates simple transparent process score.
- Creates outcome score.
- Assigns one of four decision quality labels.
- Adds gameweek transfer-group scores and labels for multi-transfer restructuring.
- Flags possible funding-leg transfers inside positive transfer groups.
- Adds position-aware scoring-route signals so defenders, goalkeepers, midfielders, and forwards are not judged only by xGI.
- Does not claim false certainty.

### Tasks

- [x] Define process scoring rules.
- [x] Calculate process score.
- [x] Calculate outcome-correct flag.
- [x] Assign labels.
- [x] Save labelled table.
- [x] Add group-level transfer package scores.
- [x] Flag funding-leg transfers.
- [x] Add position-aware scoring-route score.
- [x] Save group review table.

### Implementation task breakdown

- [x] Inspect transfer process feature schema and existing decision quality labels.
- [x] Add reusable transfer decision classifier.
- [x] Score process using only prior player/team features and upcoming fixture differences.
- [x] Score outcome using 5-GW hit-adjusted net points.
- [x] Assign one of the four `DECISION_QUALITY_LABELS`.
- [x] Add confidence labels without claiming false certainty.
- [x] Save `outputs/tables/my_transfer_decision_labels.csv`.
- [x] Run label, row/key, score arithmetic, outcome arithmetic, confidence, notebook, and output-file checks.
- [x] Group transfers by manager and gameweek.
- [x] Aggregate group process, outcome, points, hit, and value movement fields.
- [x] Assign group-level decision quality labels.
- [x] Join group labels back to individual transfer rows.
- [x] Flag individual downgrade/funding legs in positive transfer groups.
- [x] Add position-aware process scoring for clean sheets, goals conceded, defensive contribution, saves, BPS, and bonus routes.
- [x] Save `outputs/tables/my_transfer_group_decision_labels.csv`.
- [x] Run group row-count, aggregation, label, funding-leg, position-route, and output-file checks.

### Checks

- [x] Labels come from `DECISION_QUALITY_LABELS`.
- [x] Count by label is displayed.
- [x] Output CSV exists.
- [x] Group labels come from `DECISION_QUALITY_LABELS`.
- [x] Group aggregates reconcile to transfer rows.
- [x] Funding-leg flags are present.
- [x] Position-route scores are present and bounded.

### Definition of done

- Labelled transfer review exists.
- Checks pass.
- Board and status updated.

---

## Story 7.4: Evaluate captaincy

Status: Done  
Epic: Epic 7  
Sprint: Sprint 7  
Size: M  
Priority: High  
Depends on: Story 6.2  
Human review: Required

### User story

As an FPL manager, I want to evaluate my captaincy choices against reasonable alternatives, so that I know whether I was too safe, too risky, or unlucky.

### Acceptance criteria

- Identifies my captain each gameweek.
- Identifies best player in my squad.
- Identifies reasonable captain candidate using pre-GW features.
- Candidate scoring uses position-aware scoring routes and captaincy-specific ceiling indicators, not xGI alone.
- Calculates captaincy gain/loss.
- Saves chart.

### Tasks

- [x] Identify captains and vice-captains.
- [x] Calculate actual captain points.
- [x] Calculate best squad and best starter alternatives.
- [x] Build pre-GW candidate score with position-aware scoring-route inputs.
- [x] Save review and chart.

### Implementation task breakdown

- [x] Inspect my squad reconstruction and prior player feature schemas.
- [x] Add reusable captaincy review builder.
- [x] Identify one captain and one vice-captain per gameweek.
- [x] Calculate actual captain base points and extra captaincy points.
- [x] Calculate best actual squad and best actual starter alternatives.
- [x] Build a leakage-safe pre-GW candidate score using form, ceiling, minutes security, fixture context, and position-aware scoring routes.
- [x] Calculate deltas against best squad, best starter, and recommended pre-GW candidate.
- [x] Save `outputs/tables/my_captaincy_review.csv`.
- [x] Save `outputs/charts/captaincy_delta.png`.
- [x] Run captain/vice counts, row/key, delta arithmetic, score bounds, notebook, and output-file checks.

### Checks

- [x] One captain per gameweek.
- [x] Deltas calculate correctly.
- [x] Candidate score avoids current-GW outcome leakage and includes position-aware route signals.
- [x] Chart exists.

### Definition of done

- Captaincy review exists.
- Checks pass.
- Board and status updated.

---

## Story 7.5: Evaluate benching and starting XI decisions

Status: Done  
Epic: Epic 7  
Sprint: Sprint 7  
Size: M  
Priority: Medium  
Depends on: Story 6.2  
Human review: Required

### User story

As an FPL manager, I want to know whether I left too many playable points on the bench, so that I can improve squad structure and weekly selection.

### Acceptance criteria

- Calculates points on bench by gameweek.
- Identifies benched players who outscored starters.
- Separates unavoidable bench points from questionable bench points.
- Uses position-aware pre-GW expectations when judging whether a benching was questionable.
- Shows recurring patterns.

### Tasks

- [x] Calculate bench points.
- [x] Identify questionable benching using position-aware player context.
- [x] Identify high-regret benching.
- [x] Save review table.
- [x] Display top regrets.

### Implementation task breakdown

- [x] Inspect my squad reconstruction and prior player feature schemas.
- [x] Add reusable benching review builder.
- [x] Add formation-valid starter replacement logic.
- [x] Calculate bench points by gameweek.
- [x] Calculate bench regret against worst formation-valid replaceable starter.
- [x] Identify questionable benching using position-aware pre-GW selection scores.
- [x] Identify high-regret benching.
- [x] Save `outputs/tables/my_benching_review.csv`.
- [x] Save `outputs/tables/my_benching_gameweek_summary.csv`.
- [x] Run bench count, row/key, aggregation, score-bound, category, notebook, and output-file checks.

### Checks

- [x] Bench players are correctly identified.
- [x] Questionable bench flags use pre-GW features, not actual points alone.
- [x] Output CSV exists.

### Definition of done

- Bench review exists.
- Checks pass.
- Board and status updated.

---

# Epic 8: Compare me against the top-N sample

## Story 8.1: Build manager behaviour summary

Status: Done  
Epic: Epic 8  
Sprint: Sprint 8  
Size: M  
Priority: High  
Depends on: Story 4.2  
Human review: Required

### User story

As an analyst, I want one summary row per manager, so that I can compare behaviour across the sample.

### Acceptance criteria

- Creates metrics for final points, final rank, transfers, hits, bench points, captaincy, chips, value, bank, and formation.
- Includes transfer package metrics, funding-leg counts, and position-aware transfer label summaries for my team where available.
- Adds rank band and `is_me`.

### Tasks

- [x] Aggregate manager history.
- [x] Aggregate transfers and hits.
- [x] Aggregate transfer groups and possible funding-leg flags for my team where available.
- [x] Aggregate captaincy.
- [x] Aggregate bench points.
- [x] Add rank band and my-team flag.
- [x] Save summary.

### Checks

- [x] My row exists.
- [x] Sample rows exist.
- [x] My row includes transfer group/funding-leg fields if Story 7.3 outputs exist.
- [x] Output CSV exists.

### Definition of done

- Manager behaviour summary exists.
- Checks pass.
- Board and status updated.

---

## Story 8.2: Compare transfer behaviour

Status: Done  
Epic: Epic 8  
Sprint: Sprint 8  
Size: M  
Priority: High  
Depends on: Story 8.1, Story 5.3  
Human review: Required

### User story

As an FPL manager, I want to compare my transfer behaviour to top managers, so that I can tell whether I was too aggressive, too passive, or poorly timed.

### Acceptance criteria

- Compares transfers per manager.
- Compares hit frequency.
- Compares transfer timing.
- Compares fixture swing targeting.
- Compares player-in profiles.
- Separates individual transfer rows from gameweek transfer packages where group data is available.
- Compares position-specific transfer profiles instead of one generic xGI-led profile.

### Tasks

- [x] Enrich sampled transfers with pre-GW features.
- [x] Aggregate transfer profile by manager.
- [x] Aggregate transfer package profile by manager where possible.
- [x] Add position-level player-in and player-out profile summaries.
- [x] Calculate sample percentiles.
- [x] Compare my team against percentiles.
- [x] Save benchmark.

### Checks

- [x] My benchmark row exists.
- [x] Percentiles calculated.
- [x] Individual transfer metrics and transfer package metrics are not double-counted.
- [x] Output CSV exists.

### Definition of done

- Transfer benchmark exists.
- Checks pass.
- Board and status updated.

---

## Story 8.3: Compare player adoption timing

Status: Done  
Epic: Epic 8  
Sprint: Sprint 8  
Size: M  
Priority: High  
Depends on: Story 4.2, Story 2.4  
Human review: Required

### User story

As an FPL manager, I want to know whether I was late to important players, so that I can improve how quickly I update next season.

### Acceptance criteria

- Identifies key season players.
- Calculates first ownership GW for me and sampled managers.
- Calculates adoption delay.
- Estimates points lost by delay.
- Reports adoption timing by position/role where useful so defensive and goalkeeper routes are not hidden by attacker-heavy metrics.

### Tasks

- [x] Identify key players.
- [x] Calculate first owned GW.
- [x] Calculate sample median adoption.
- [x] Calculate my delay.
- [x] Estimate points after median until my adoption.
- [x] Add position and scoring-route context for key players.
- [x] Save review.

### Checks

- [x] Key players have valid IDs.
- [x] Adoption dates are plausible.
- [x] Output CSV exists.

### Definition of done

- Player adoption review exists.
- Checks pass.
- Board and status updated.

---

## Story 8.4: Compare squad structure and team exposure

Status: Done  
Epic: Epic 8  
Sprint: Sprint 8  
Size: M  
Priority: Medium  
Depends on: Story 4.2, Story 5.3  
Human review: Required

### User story

As an FPL manager, I want to compare my squad structure to strong managers, so that I can see whether I allocated budget and team exposure well.

### Acceptance criteria

- Compares position allocation.
- Compares premium/mid/budget allocation.
- Compares exposure to strong teams.
- Compares exposure to good fixture runs.
- Compares bench spend.
- Connects structure findings to transfer package/funding-leg context where relevant.

### Tasks

- [x] Build manager squad structure by GW.
- [x] Aggregate to season summary.
- [x] Compare my team to percentiles.
- [x] Flag whether transfer packages materially changed squad structure.
- [x] Save benchmark.

### Checks

- [x] My team appears.
- [x] Sample appears.
- [x] Output CSV exists.

### Definition of done

- Squad structure benchmark exists.
- Checks pass.
- Board and status updated.

---

# Epic 9: Build robust decision rules under uncertainty

## Story 9.1: Create candidate rule features

Status: Done  
Epic: Epic 9  
Sprint: Sprint 9  
Size: M  
Priority: High  
Depends on: Story 5.3  
Human review: Required

### User story

As an analyst, I want candidate rule features for player selection and transfers, so that rules can be tested systematically.

### Acceptance criteria

- Includes player rolling points, xGI proxy, rolling minutes, team strength, fixture difficulty, price band, position, ownership, form, blank/double indicators, and position-specific scoring-route features.
- Includes future 1GW, 3GW, and 5GW outcomes.
- Preserves separate feature families for attacking, clean-sheet, defensive-contribution, goalkeeper save, BPS/bonus, discipline, and availability routes.

### Tasks

- [x] Merge player, team, and fixture features.
- [x] Add position-specific scoring-route feature families.
- [x] Add future outcome columns.
- [x] Separate feature columns from outcome columns.
- [x] Save table.

### Checks

- [x] Pre-GW features do not include current GW outcome.
- [x] Position-specific feature families are present.
- [x] Future outcome columns are clearly labelled.
- [x] Output CSV exists.

### Definition of done

- Candidate rule features exist.
- Leakage checks pass.
- Board and status updated.

---

## Story 9.2: Test simple player selection rules

Status: Done  
Epic: Epic 9  
Sprint: Sprint 9  
Size: M  
Priority: High  
Depends on: Story 9.1  
Human review: Required

### User story

As an FPL manager, I want to know which player characteristics predicted future points, so that I can choose better players next season.

### Acceptance criteria

- Tests simple transparent rules.
- Calculates future point uplift against position baseline.
- Tests rules separately by position/scoring route where sample size allows.
- Adds confidence labels.

### Tasks

- [x] Define binary rule flags.
- [x] Calculate rule performance.
- [x] Compare against position baseline.
- [x] Add position-specific rule families for defensive contribution, clean sheets, saves, BPS/bonus, and attacking routes.
- [x] Add confidence labels.
- [x] Save results.

### Checks

- [x] Each rule has sample size.
- [x] Position-specific rules are not pooled into a misleading all-position average without a baseline.
- [x] Confidence labels are assigned.
- [x] Output CSV exists.

### Definition of done

- Player selection rule results exist.
- Checks pass.
- Board and status updated.

---

## Story 9.3: Test transfer-style rules

Status: Done  
Epic: Epic 9  
Sprint: Sprint 9  
Size: M  
Priority: High  
Depends on: Story 9.1, Story 8.2  
Human review: Required

### User story

As an FPL manager, I want to know which types of transfers worked for top managers, so that I can improve transfer strategy next season.

### Acceptance criteria

- Tests fixture, minutes, team strength, form/xGI, position-specific scoring-route, transfer-out, transfer-package, funding-leg, and hit rules.
- Calculates mean and median net gain across 1GW, 3GW, and 5GW.
- Reports both individual transfer-row gains and gameweek transfer-package gains.
- Adds confidence labels.

### Tasks

- [x] Enrich sampled transfers.
- [x] Define transfer rule flags.
- [x] Define transfer-package and funding-leg rule flags.
- [x] Add position-specific player-in/player-out rule flags.
- [x] Calculate net gains.
- [x] Compare against baseline.
- [x] Save results.

### Checks

- [x] Each rule has count and gain metrics.
- [x] Package-level rules reconcile to grouped transfer rows and do not double-count individual legs.
- [x] Confidence labels are assigned.
- [x] Output CSV exists.

### Definition of done

- Transfer rule results exist.
- Checks pass.
- Board and status updated.

---

## Story 9.4: Generate plain-English rules for next season

Status: Done  
Epic: Epic 9  
Sprint: Sprint 9  
Size: M  
Priority: High  
Depends on: Story 9.2, Story 9.3  
Human review: Required

### User story

As an FPL manager, I want plain-English rules from the analysis, so that I can actually use them during the season.

### Acceptance criteria

- Converts rule results into practical rules.
- Includes confidence.
- Includes when to use and when to ignore the rule.
- Includes whether my season supported or violated the rule.
- Distinguishes individual transfer-leg rules from transfer-package/restructure rules.
- Includes position-specific guidance where evidence differs by position.

### Tasks

- [x] Combine rule results and my decision reviews.
- [x] Draft plain-English rules.
- [x] Include transfer group labels and funding-leg findings from Story 7.3.
- [x] Include position-specific rule caveats.
- [x] Add evidence summary.
- [x] Add confidence and overfitting risk.
- [x] Save rulebook.

### Checks

- [x] Rulebook has required columns.
- [x] Rules identify whether they apply to individual player selection, transfer packages, or position-specific decisions.
- [x] Low-confidence findings are labelled.
- [x] Output CSV exists.

### Definition of done

- Next season rulebook exists.
- Checks pass.
- Board and status updated.

---

# Epic 10: Build final retrospective report

## Story 10.1: Create season gap and leak summary

Status: Done  
Epic: Epic 10  
Sprint: Sprint 10  
Size: M  
Priority: High  
Depends on: Story 7.5, Story 8.3, Story 9.4  
Human review: Required

### User story

As an FPL manager, I want to know my biggest leaks, so that I can focus on the few behaviours that matter most.

### Acceptance criteria

- Summarises loss/gain from transfers, hits, captaincy, benching, late adoption, squad structure, and chip timing if possible.
- Uses transfer package outcomes for strategic transfer leaks and individual transfer outcomes only for within-package diagnostics.
- Produces ranked leak table.
- Produces waterfall-style chart.

### Tasks

- [x] Combine decision review tables.
- [x] Estimate points impact.
- [x] Avoid double-counting individual transfer legs and transfer package outcomes.
- [x] Include possible funding-leg caveats in transfer leak evidence.
- [x] Add confidence and evidence.
- [x] Save leak table.
- [x] Save chart.

### Checks

- [x] Leak areas have evidence.
- [x] Transfer leak estimates specify individual-row versus package-level basis.
- [x] Chart exists.
- [x] Output CSV exists.

### Definition of done

- Season leak summary exists.
- Checks pass.
- Board and status updated.

---

## Story 10.2: Create final executive summary

Status: In Review  
Epic: Epic 10  
Sprint: Sprint 10  
Size: M  
Priority: High  
Depends on: Story 10.1  
Human review: Required

### User story

As an FPL manager, I want the notebook to end with a written summary, so that the analysis turns into action.

### Acceptance criteria

- Writes a plain-English summary.
- Includes top findings, costly decision patterns, strongest patterns, rules, uncertainty note, and next-season operating system.
- Explains transfer findings using package-level outcomes first, with individual legs and funding legs as supporting context.
- Calls out position-specific lessons separately where evidence differs for goalkeepers, defenders, midfielders, and forwards.

### Tasks

- [x] Add final markdown section.
- [x] Summarise key findings.
- [x] Summarise rules.
- [x] Summarise transfer package and funding-leg lessons without double-counting.
- [x] Summarise position-specific decision lessons.
- [x] Add uncertainty warning.
- [x] Add next-season checklist.

### Checks

- [x] Summary references generated outputs.
- [x] Low-confidence claims are qualified.
- [x] Transfer claims distinguish package-level and individual-leg evidence.
- [x] Position-specific claims are not generalised across all players without evidence.
- [x] Notebook remains readable.

### Definition of done

- Final report section exists.
- Checks pass.
- Board and status updated.
