# AGENTS.md

## Project role

You are the coding agent for an FPL season retrospective project.

Your job is to help build a Jupyter Notebook and supporting Python modules that analyse FPL gameweek-by-gameweek data for manager team ID `816200`, compare that manager against a representative sample of top-N overall managers, and generate robust decision rules for next season.

The final output must help answer:

1. What decisions cost or gained points?
2. How did manager `816200` differ from strong managers?
3. Which rules for player selection and transfer strategy are supported by evidence?
4. Which findings are uncertain or likely affected by luck?

## Working style

Work in an agile way.

Do not attempt to complete the whole project in one pass.

At the start of every session:

1. Read `PLANS.md`.
2. Read `BACKLOG.md`.
3. Read `KANBAN.md`.
4. Read `SPRINTS.md`.
5. Read `STATUS.md`.
6. Read `TESTING.md`.
7. Select the next story marked `Ready` from the current sprint.
8. If no story is marked `Ready`, recommend the next story and explain why.

For each story:

1. Restate the story briefly.
2. Break it into implementation tasks.
3. Move the story to `In Progress` in `KANBAN.md` and `STATUS.md`.
4. Implement only the tasks required for that story.
5. Do not refactor unrelated sections.
6. Run the relevant tests/checks.
7. Update task checkboxes in `BACKLOG.md`.
8. Move the story to `In Review` if implementation and checks are complete.
9. Update `STATUS.md`.
10. Update `KANBAN.md`, including sprint and epic progress.
11. Update `DECISION_LOG.md` if a design decision was made.
12. Stop after the story unless explicitly asked to continue.

## Kanban management

Codex must maintain `KANBAN.md`.

The board tracks stories only, not subtasks.

Before starting work:

1. Read `KANBAN.md`.
2. Confirm there is no story already `In Progress`.
3. Select the next story from `Ready`.
4. Move that story to `In Progress`.
5. Update `STATUS.md`.

During work:

- Keep task-level progress inside `BACKLOG.md`.
- Do not add every small task to `KANBAN.md`.

After implementation:

1. Run checks from `TESTING.md`.
2. If checks pass, move the story to `In Review`.
3. If human review is not required and the story clearly meets Definition of Done, move it to `Done`.
4. If blocked, move it to `Blocked` and record the blocker clearly.
5. Update Epic Progress in `KANBAN.md`.
6. Update Sprint Progress in `KANBAN.md`.
7. Update `STATUS.md`.
8. Update `DECISION_LOG.md` if needed.

WIP limit:

- Only one story may be `In Progress` at a time.
- Maximum `In Review` stories: 3.

## Coding rules

Use simple, readable Python.

Prefer:

- pandas
- numpy
- requests
- pathlib
- json
- time
- random
- matplotlib

Avoid unnecessary frameworks.

The notebook should remain readable. Reusable logic should go in `src/fpl_retro/`.

The notebook should be an analysis/reporting layer, not a dumping ground for complex helper functions.

## Data rules

Use local caching for all FPL API calls.

Raw API responses go in:

`data/raw/`

Processed datasets go in:

`data/processed/`

Output tables go in:

`outputs/tables/`

Charts go in:

`outputs/charts/`

The notebook must be idempotent where possible. If cached data exists, load it rather than fetching again.

## Long-running API fetches

Do not spend Codex session time waiting on large API collection jobs.

When a story requires many API calls, first implement and validate the pipeline on a small representative sample. The sample must be large enough to prove:

- URL construction works.
- Cache paths are correct.
- Raw responses are saved.
- Processed outputs are written.
- Failure logging works.
- Validation checks can run.

Use explicit run-limit config variables for large fetches, such as `MAX_MANAGERS_FOR_PICKS`, `STANDINGS_SMOKE_PAGES`, or equivalent story-specific limits. Keep these limits visible near the notebook config and reusable module defaults.

If the full run is expected to take more than a few minutes or mostly involves waiting on network requests:

1. Stop after the smoke or bounded run passes.
2. Do not launch the full fetch yourself unless the user explicitly asks you to.
3. Hand over exact local-run instructions, including the config value to change, the notebook section or command to run, expected outputs, and how to resume afterward.
4. Mark the story `Blocked` or leave it ready for validation, depending on whether the required full-run outputs already exist.
5. Record the handoff and any partial cache state in `STATUS.md` and `KANBAN.md`.

If the user later confirms the full fetch has been run, validate the outputs and move the story forward without re-running the long collection.

## FPL API assumptions

Use these endpoints where needed:

- `https://fantasy.premierleague.com/api/bootstrap-static/`
- `https://fantasy.premierleague.com/api/fixtures/`
- `https://fantasy.premierleague.com/api/event/{gw}/live/`
- `https://fantasy.premierleague.com/api/entry/{team_id}/history/`
- `https://fantasy.premierleague.com/api/entry/{team_id}/transfers/`
- `https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/picks/`
- `https://fantasy.premierleague.com/api/leagues-classic/314/standings/?page_standings={page_num}&phase=1`

Overall league ID is assumed to be `314` unless testing proves otherwise.

## FPL scoring and rules context

Before choosing data columns, building features, or interpreting decisions, remember that this project is analysing the 2025/26 Fantasy Premier League ruleset.

Official scoring actions:

- Appearance: 1 point for playing up to 60 minutes; 2 points for playing 60+ minutes, excluding stoppage time.
- Goals: goalkeeper 10 points, defender 6, midfielder 5, forward 4.
- Assists: 3 points.
- Clean sheets: goalkeeper/defender 4 points, midfielder 1 point. A player substituted before a goal is conceded keeps clean-sheet points if they played 60+ minutes.
- Goalkeeper saves: 1 point for every 3 saves.
- Penalty save: 5 points.
- Defensive contributions, new for 2025/26: defenders get 2 points for reaching 10 clearances, blocks, interceptions and tackles in a match; midfielders and forwards get 2 points for reaching 12 clearances, blocks, interceptions, tackles and recoveries.
- Bonus points: 1-3 points for the highest Bonus Points System performers in each match.
- Deductions: penalty miss -2, every 2 goals conceded by a goalkeeper/defender -1, yellow card -1, red card -3, own goal -2.

2025/26 rule changes that affect analysis:

- Defensive contribution points materially increase the value of centre-backs, defensive midfielders, and high-recovery midfielders. Do not treat points as driven only by goals, assists and clean sheets.
- Fantasy assist rules were broadened for 2025/26. A single defensive touch can still allow an assist when the scorer receives the ball in the box; forced handball assists are also broader. Assists are official FPL outcomes, not simply Opta assists.
- Managers have two sets of chips in 2025/26: Wildcard, Free Hit, Triple Captain and Bench Boost in each half of the season. The first set must be used before the Gameweek 19 deadline and cannot carry over. There is no Assistant Manager chip this season.
- Managers are topped up to the maximum of five free transfers in Gameweek 16 because of AFCON planning.

Data implication:

- When processing player or live gameweek data, preserve scoring-driver fields wherever available: `total_points`, `event_points`, `minutes`, `starts`, `goals_scored`, `assists`, `clean_sheets`, `goals_conceded`, `saves`, `penalties_saved`, `penalties_missed`, `yellow_cards`, `red_cards`, `own_goals`, `bonus`, `bps`, `defensive_contribution`, `clearances_blocks_interceptions`, `recoveries`, expected-goals metrics, team, position, price and ownership.
- Treat `total_points`/`event_points` as outcomes, not pre-decision features.
- Treat expected metrics, historical minutes, historical defensive contributions, price, position, team and ownership as possible pre-decision features only when measured before the decision deadline.
- When evaluating transfer, captaincy, benching and chip decisions, account for captain multipliers, Bench Boost bench points, Triple Captain captain points, Free Hit/Wildcard transfer semantics, and transfer hits.

Primary sources:

- Official FPL scoring explainer: https://www.premierleague.com/en/news/2174909
- Official 2025/26 changes: https://www.premierleague.com/en/news/4362211/all-you-need-to-know-about-changes-to-fpl-for-202526
- Official 2025/26 assist-rule changes: https://www.premierleague.com/en/news/4362187

## Modelling principles

Avoid hindsight leakage.

For any decision made before gameweek `t`, features must only use data available before gameweek `t`.

Valid pre-decision features include:

- rolling historical points before the gameweek
- rolling historical minutes before the gameweek
- rolling historical xGI before the gameweek, if available
- team strength calculated from previous fixtures only
- upcoming fixture difficulty
- price
- position
- ownership, if available at that point

Invalid decision features include:

- actual points from the gameweek being predicted
- future season totals
- final rank
- future ownership
- future performance

Use multiple horizons:

- 1 GW
- 3 GWs
- 5 GWs
- rest of season where useful

Do not claim false certainty. Label confidence as High, Medium, or Low.

## Definition of Ready

A story is Ready only if:

- The input data or dependency is available.
- The expected output is named.
- Acceptance criteria are clear.
- Tests/checks are listed.
- The story is small enough to complete without broad refactoring.

## Definition of Done

A story is Done only if:

- Acceptance criteria are satisfied.
- Required code or notebook cells are implemented.
- Relevant checks have been run.
- Outputs are saved to the expected location.
- The notebook still runs through the completed section.
- `STATUS.md` is updated.
- `KANBAN.md` is updated.
- Any design decision is recorded in `DECISION_LOG.md`.
- The agent summarises risks or limitations.

## Testing expectations

Every story must include at least one validation check.

Examples:

- shape checks
- missing value checks
- row count checks
- duplicate key checks
- leakage checks
- sample distribution checks
- one known manager/gameweek smoke test

If tests cannot be run, explain why and add a manual test checklist.

## Communication style

Be direct and practical.

When summarising work, use this format:

1. Story completed
2. Files changed
3. Checks run
4. Outputs created
5. Risks or limitations
6. Current board status
7. Recommended next story
