# STATUS.md

## Current project state

Current epic: Epic 11  
Current sprint: Sprint 12  
Current story: Story 12.3 - Build transfer package and hit justification engine  
Current mode: Story in review; waiting for human acceptance  
Last updated: 2026-05-30

## Completed stories

Story 1.1: Create notebook config and folder structure
Story 1.2: Define decision quality framework
Story 2.1: Build API fetch and cache helpers
Story 2.2: Fetch and process bootstrap-static
Story 2.3: Fetch fixtures
Story 2.4: Fetch gameweek live player data
Story 3.1: Fetch top-N standings pages
Story 3.2: Create reproducible rank-stratified sample
Story 3.3: Validate sample quality
Story 4.1: Fetch manager history and transfers
Story 4.2: Fetch manager picks by gameweek
Story 5.1: Create player-gameweek features table
Story 5.2: Create team strength table
Story 5.3: Create fixture difficulty table
Story 6.1: Build my gameweek timeline
Story 6.2: Reconstruct my squad each gameweek
Story 7.1: Evaluate transfer outcomes
Story 7.2: Add transfer process features
Story 7.3: Classify transfer decisions
Story 7.4: Evaluate captaincy
Story 7.5: Evaluate benching and starting XI decisions
Story 8.1: Build manager behaviour summary
Story 8.2: Compare transfer behaviour
Story 8.3: Compare player adoption timing
Story 8.4: Compare squad structure and team exposure
Story 9.1: Create candidate rule features
Story 9.2: Test simple player selection rules
Story 9.3: Test transfer-style rules
Story 9.4: Generate plain-English rules for next season
Story 10.1: Create season gap and leak summary
Story 10.2: Create final executive summary
Story 11.1: Create weekly decision-system skeleton
Story 11.2: Build current-squad context for a target gameweek
Story 11.3: Build transfer candidate shortlist
Story 12.1: Build sell candidate review
Story 12.1a: Calibrate candidate and sell rules from sampled cohort
Story 12.2: Match transfer candidates to sell candidates

## In-progress story

None.

## In-review story

Story 12.3: Build transfer package and hit justification engine

## Next ready story

None in the current sprint. Sprint 12 has no remaining unstarted stories.

## Blockers

None.

## Important notes

- Final analysis must be relative to manager team ID `816200`.
- Use rank-stratified sampling for top-N manager sample.
- Avoid hindsight leakage.
- Downstream transfer analysis must distinguish individual transfer legs from gameweek transfer packages and avoid double-counting both as separate strategic point impacts.
- Player selection, captaincy, benching, and transfer rules must use position-aware scoring-route context rather than xGI alone.
- Use cached API responses.
- Prefer helper modules in `src/fpl_retro/` and keep the notebook readable.
- Kanban tracks story-level progress only.
- Tasks are tracked inside `BACKLOG.md`.
- The Weekly Decision System phase is planned as Epic 11 across Sprints 11-14.
- Weekly Decision System work must use pre-deadline information only and must not use current-GW actual points, future outcomes, final ranks, or future ownership in recommendation scoring.
- Weekly hit recommendations must be conservative and package-level, not isolated individual transfer-leg decisions.
- The Weekly Decision System must be a next-season decision process learned from the sampled manager cohort, not a retrospective optimiser for the completed season.
- Story 12.1 is accepted only as a v1 application-layer sell review; Story 12.1a must add sampled-cohort calibration before transfer pair matching begins.

## Latest run summary

Story 12.3 created `weekly_transfer_package_review.csv` and `weekly_hit_payoff_curve.png` from affordable transfer pairs and historical transfer package evidence. Checks passed and the story is in review. Sprint 13 has not been started.
