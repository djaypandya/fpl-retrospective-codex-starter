# SPRINTS.md

## Sprint rules

A sprint is a small batch of stories that produces a reviewable project increment.

Recommended sprint size:

- 2 to 4 stories
- One clear outcome
- No more than one epic boundary unless necessary

Codex may complete stories inside a sprint one at a time.

Codex must stop at the end of each story and update:

- `BACKLOG.md`
- `KANBAN.md`
- `STATUS.md`
- `DECISION_LOG.md` if needed

Codex must not start the next sprint without human approval.

---

# Sprint 1: Project foundation

## Sprint goal

Create the project skeleton, notebook setup, and decision quality framework.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 1.1 Create notebook config and folder structure | Epic 1 | S | Done |
| 1.2 Define decision quality framework | Epic 1 | S | Done |

## Sprint acceptance criteria

- Project folders exist.
- Notebook exists.
- Config section exists.
- Decision quality framework exists.
- `STATUS.md` and `KANBAN.md` reflect progress.

## Sprint review checklist

- [x] Can the notebook setup cells run twice safely?
- [x] Is the project structure clean?
- [x] Are decision labels clear?
- [x] Is the next sprint ready?

---

# Sprint 2: Core FPL data foundation

## Sprint goal

Fetch and cache the base FPL data needed for all later analysis.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 2.1 Build API fetch and cache helpers | Epic 2 | M | Done |
| 2.2 Fetch and process bootstrap-static | Epic 2 | M | Done |
| 2.3 Fetch fixtures | Epic 2 | S | Done |
| 2.4 Fetch gameweek live player data | Epic 2 | M | Done |

## Sprint acceptance criteria

- API caching works.
- Static data is processed.
- Fixtures are processed.
- Gameweek live player data is available.
- Basic data validation checks pass.

## Sprint review checklist

- [x] Does cache loading work?
- [x] Do processed tables have expected rows and columns?
- [x] Does the notebook remain readable?
- [x] Are data outputs saved in expected locations?

---

# Sprint 3: Representative top-N sample

## Sprint goal

Create and validate a rank-stratified sample of top-N managers.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 3.1 Fetch top-N standings pages | Epic 3 | M | Done |
| 3.2 Create reproducible rank-stratified sample | Epic 3 | M | Done |
| 3.3 Validate sample quality | Epic 3 | S | Done |

## Sprint acceptance criteria

- Top-N candidate managers are available.
- Rank-stratified sampling works.
- Sample quality is visible to human reviewer.

---

# Sprint 4: Manager data collection

## Sprint goal

Fetch histories, transfers, chips, and picks for my team and the sampled managers.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 4.1 Fetch manager history and transfers | Epic 4 | M | Done |
| 4.2 Fetch manager picks by gameweek | Epic 4 | M | Done |

## Sprint acceptance criteria

- Manager histories exist.
- Transfers exist.
- Picks exist.
- Failures are logged.

---

# Sprint 5: Analytical feature tables

## Sprint goal

Build reusable analytical tables for player features, team strength, and fixture outlook.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 5.1 Create player-gameweek features table | Epic 5 | M | Done |
| 5.2 Create team strength table | Epic 5 | M | Done |
| 5.3 Create fixture difficulty table | Epic 5 | M | Done |

## Sprint acceptance criteria

- Leakage-safe player features exist.
- Leakage-safe team strength exists.
- Fixture outlook exists.

---

# Sprint 6: Reconstruct my season

## Sprint goal

Create a clean week-by-week reconstruction of team ID 816200.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 6.1 Build my gameweek timeline | Epic 6 | M | Done |
| 6.2 Reconstruct my squad each gameweek | Epic 6 | M | Done |

## Sprint acceptance criteria

- My season timeline exists.
- My enriched picks exist.

---

# Sprint 7: Evaluate my decisions

## Sprint goal

Evaluate transfers, captaincy, benching, and decision quality.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 7.1 Evaluate transfer outcomes | Epic 7 | M | Done |
| 7.2 Add transfer process features | Epic 7 | M | Done |
| 7.3 Classify transfer decisions | Epic 7 | M | Done |
| 7.4 Evaluate captaincy | Epic 7 | M | Done |
| 7.5 Evaluate benching and starting XI decisions | Epic 7 | M | Done |

## Sprint acceptance criteria

- Transfer review exists.
- Captaincy review exists.
- Bench review exists.
- Decision labels exist.

---

# Sprint 8: Benchmark against top-N sample

## Sprint goal

Compare my patterns to strong managers.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 8.1 Build manager behaviour summary | Epic 8 | M | Done |
| 8.2 Compare transfer behaviour | Epic 8 | M | Done |
| 8.3 Compare player adoption timing | Epic 8 | M | Done |
| 8.4 Compare squad structure and team exposure | Epic 8 | M | Done |

## Sprint acceptance criteria

- Behaviour benchmark exists.
- Transfer benchmark exists.
- Adoption benchmark exists.
- Squad structure benchmark exists.

---

# Sprint 9: Decision rules

## Sprint goal

Generate evidence-based next-season decision rules.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 9.1 Create candidate rule features | Epic 9 | M | Done |
| 9.2 Test simple player selection rules | Epic 9 | M | Done |
| 9.3 Test transfer-style rules | Epic 9 | M | Done |
| 9.4 Generate plain-English rules for next season | Epic 9 | M | Done |

## Sprint acceptance criteria

- Candidate rule features exist.
- Selection rules are tested.
- Transfer rules are tested.
- Rulebook exists.

---

# Sprint 10: Final report

## Sprint goal

Turn analysis into a readable retrospective and next-season operating system.

## Preparation status

Sprint 10 is closed. Story 10.1 and Story 10.2 are accepted as Done.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 10.1 Create season gap and leak summary | Epic 10 | M | Done |
| 10.2 Create final executive summary | Epic 10 | M | Done |

## Sprint acceptance criteria

- Leak summary exists.
- Final retrospective summary exists.
- Rulebook is referenced.

---

# Sprint 11: Weekly decision engine foundation

## Sprint goal

Create the reusable weekly decision-system module and basic decision-pack orchestration.

## Preparation status

Sprint 11 is complete. Stories 11.1, 11.2, and 11.3 are accepted as Done.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 11.1 Create weekly decision-system skeleton | Epic 11 | S | Done |
| 11.2 Build current-squad context for a target gameweek | Epic 11 | M | Done |
| 11.3 Build transfer candidate shortlist | Epic 11 | M | Done |

## Sprint acceptance criteria

- Weekly decision-system skeleton exists.
- Current-squad context can be built for a target gameweek.
- Transfer candidate shortlist exists and avoids hindsight leakage.

---

# Sprint 12: Sell decisions and transfer package evaluation

## Sprint goal

Convert candidate ranking into actual transfer decisions by comparing outside players against current squad players and transfer costs.

## Preparation status

Sprint 12 is active. Stories 12.1, 12.1a, and 12.2 are accepted as Done. Story 12.3 is in review.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 12.1 Build sell candidate review | Epic 11 | M | Done |
| 12.1a Calibrate candidate and sell rules from sampled cohort | Epic 11 | M | Done |
| 12.2 Match transfer candidates to sell candidates | Epic 11 | M | Done |
| 12.3 Build transfer package and hit justification engine | Epic 11 | M | In Review |

## Sprint acceptance criteria

- Sell candidate review exists.
- Candidate shortlist and sell/hold learned-rule calibration exists.
- Transfer pair review exists.
- Transfer package and hit justification engine exists.
- Hit recommendations are package-level and conservative.

---

# Sprint 13: Captaincy decision and weekly output pack

## Sprint goal

Add weekly captaincy decision support and produce the final weekly decision pack.

## Preparation status

Sprint 13 is planned but not started. It depends on current-squad, package-review, and captaincy foundations.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 13.1 Build weekly captaincy decision table | Epic 11 | M | Backlog |
| 13.2 Create final weekly decision pack summary | Epic 11 | M | Backlog |

## Sprint acceptance criteria

- Weekly captaincy decision table exists.
- Weekly decision pack summary exists.
- Captaincy and hit recommendations match the underlying tables.

---

# Sprint 14: Backtest the weekly decision process

## Sprint goal

Test whether the weekly decision process would have made sensible historical recommendations under uncertainty.

## Preparation status

Sprint 14 is planned but not started. It depends on the implemented weekly decision process.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 14.1 Backtest weekly candidate shortlist quality | Epic 11 | M | Backlog |
| 14.2 Backtest hit justification thresholds | Epic 11 | M | Backlog |
| 14.3 Backtest captaincy decision quality | Epic 11 | M | Backlog |

## Sprint acceptance criteria

- Candidate shortlist backtest exists.
- Hit threshold backtest exists.
- Captaincy decision backtest exists.
- Backtests use future outcomes only for post-hoc evaluation, not recommendation scoring.
