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

Sprint 10 is in progress. Story 10.1 is accepted as Done. Story 10.2 is in review after adding the final executive summary.

## Stories

| Story | Epic | Size | Status |
|---|---|---:|---|
| 10.1 Create season gap and leak summary | Epic 10 | M | Done |
| 10.2 Create final executive summary | Epic 10 | M | In Review |

## Sprint acceptance criteria

- Leak summary exists.
- Final retrospective summary exists.
- Rulebook is referenced.
