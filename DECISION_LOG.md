# DECISION_LOG.md

## Format

Each decision should be recorded as:

### YYYY-MM-DD: Decision title

Decision:  
Reason:  
Alternatives considered:  
Risk:  
Follow-up needed:  

---

## Decisions

### 2026-05-30: Separate additive leak estimates from diagnostic evidence

Decision:  
Story 10.1 ranks season leaks and gains with an `additive_to_total` flag. Transfer strategy uses package-level 5GW net-after-hit outcomes for headline impact, while individual transfer legs and hit costs are diagnostic rows only.

Reason:  
Multi-transfer weeks can include funding legs and structural swaps. Adding individual transfer legs, hit costs, and package totals together would double-count the same decision and misrepresent where points were actually gained or lost.

Alternatives considered:  
Sum all individual transfer outcomes directly, or show only package totals without the within-package diagnostic evidence.

Risk:  
Some additive rows, especially late adoption and hindsight captaincy/benching estimates, still overlap conceptually with transfer and selection behaviour. The table labels confidence and caveats so these are treated as directional leak sizes rather than a precise decomposition.

Follow-up needed:  
Story 10.2 should explain additive versus diagnostic rows plainly in the executive summary.

### 2026-05-30: Preserve rulebook scope and confidence caveats

Decision:  
Story 9.4 writes the next-season rulebook with explicit `rule_scope` values for player selection, individual transfer legs, and transfer packages. It includes all tested rule rows, including Low-confidence findings, with overfitting caveats rather than only surfacing the strongest results.

Reason:  
The final retrospective needs practical guidance without flattening different decision types into one generic rule list. Including weak findings prevents silence from being mistaken for support and keeps the rulebook honest about uncertainty.

Alternatives considered:  
Publish only top high-confidence rules, or combine player and transfer rules into one ranked list.

Risk:  
The rulebook is longer and still retrospective. Readers must use confidence, scope, and caveats rather than treating every row as an instruction.

Follow-up needed:  
Sprint 10 should summarize the rulebook into the final report and highlight the highest-value rules separately from watchlist findings.

### 2026-05-29: Keep transfer-leg and package rule tests separate

Decision:  
Story 9.3 reports individual transfer-leg rules and manager-gameweek transfer-package rules as separate `rule_level` values. Individual transfer legs receive allocated hit cost, while packages subtract the gameweek hit cost once and count each manager-gameweek package once.

Reason:  
Multi-transfer gameweeks can contain structural downgrades, upgrades, and funding moves. Evaluating every leg as an independent strategy would double-count bundled decisions and misread funding legs.

Alternatives considered:  
Evaluate only individual transfer rows, or collapse all transfers into packages and lose player-in/player-out route detail.

Risk:  
Package grouping is based on manager and gameweek, not the manager's subjective intent. Funding-leg flags are inferred from value movement and package context.

Follow-up needed:  
Story 9.4 should use `rule_level` to separate individual transfer guidance from package/restructure guidance.

### 2026-05-29: Evaluate player selection rules by position baseline

Decision:  
Story 9.2 evaluates every player-selection rule separately by FPL position and reports uplift against same-position, same-gameweek baseline outcomes.

Reason:  
FPL positions score through different routes. Pooling goalkeepers, defenders, midfielders, and forwards into one raw average would overstate attacking-heavy signals and understate clean-sheet, save, defensive-contribution, and BPS/bonus routes.

Alternatives considered:  
Report one all-position average per rule, or fit a model to all feature columns at once.

Risk:  
Rules are transparent heuristics, not causal estimates. Strong uplift can still reflect correlated traits such as minutes security, price, team quality, or ownership.

Follow-up needed:  
Story 9.4 should translate these results as evidence-weighted rules with caveats rather than as guarantees.

### 2026-05-29: Separate rule features from future outcomes by column namespace

Decision:  
Story 9.1 writes candidate rule inputs with a `feature_` prefix and future evaluation windows with an `outcome_` prefix. Position-aware scoring routes are preserved as separate feature families for attacking, clean-sheet, defensive-contribution, goalkeeper-save, BPS/bonus, discipline, and availability signals. Ownership is backfilled as previous-gameweek ownership inferred from cached top-sample manager picks, not from the current `bootstrap-static` snapshot.

Reason:  
Rule-testing stories need to select pre-gameweek evidence without accidentally using current or future points. Explicit namespaces make leakage checks simple and keep FPL scoring-route nuance visible for different positions.

Alternatives considered:  
Keep raw processed column names, or create one generic player score before rule testing.

Risk:  
Some route scores are transparent heuristics and should not be treated as fitted model outputs. The ownership field is a top-sample prior proxy, not official global FPL ownership. GW1 has no prior ownership value.

Follow-up needed:  
Stories 9.2 and 9.3 should use `feature_` columns as rule inputs and `outcome_` columns only as evaluation targets.

### 2026-05-29: Separate transfer row and package benchmark metrics

Decision:  
Story 8.2 reports individual transfer-leg metrics and manager-gameweek transfer-package metrics as separate fields in the top-N transfer behaviour benchmark.

Reason:  
The same gameweek can contain multiple transfer legs that form one structural package. Counting those rows as both separate strategic events and packages would overstate activity and obscure funding or restructuring behaviour.

Alternatives considered:  
Aggregate only individual transfer rows, or collapse all transfers to packages and lose player-in/player-out profile detail.

Risk:  
Package-level metrics are based on same-manager, same-gameweek grouping and do not know the manager's subjective intent.

Follow-up needed:  
Final reporting should describe row metrics as transfer volume/profile and package metrics as structural activity, not as interchangeable counts.

### 2026-05-29: Use player price as squad-structure value proxy

Decision:  
Story 8.4 uses the processed player `price` field as a consistent proxy for squad value, bench spend, and premium/mid/budget allocation in the top-N squad structure benchmark.

Reason:  
The sampled manager picks table contains player IDs, positions, teams, captaincy, and squad order, but it does not contain manager-specific purchase price or selling price for each pick. A shared player price proxy enables relative squad-structure comparison without a new data collection step.

Alternatives considered:  
Omit budget and bench spend comparisons, or infer manager-specific prices from transfer history, which would be more complex and unreliable without complete price-change history.

Risk:  
Value metrics are structural proxies, not exact squad purchase values. They should be interpreted as relative allocation signals rather than accounting-accurate team value.

Follow-up needed:  
Final reporting should label these fields as value proxies, and rule-testing should not treat them as exact manager-specific purchase prices.

### 2026-05-29: Select adoption key players with position coverage

Decision:  
Story 8.3 defines key players as the top 30 players by season points plus the top 5 players within each position, then removes duplicates.

Reason:  
An overall points-only list would overrepresent high-scoring midfielders and forwards. Adding minimum position coverage keeps goalkeeper, defender, midfielder, and forward adoption timing visible, which matches the project requirement to respect different FPL scoring routes.

Alternatives considered:  
Use only the top overall points scorers, use only ownership, or manually curate a subjective player list.

Risk:  
The key-player set is still hindsight-selected from full-season points, so it is appropriate for retrospective adoption timing but not as a pre-season prediction target.

Follow-up needed:  
Rule-testing stories should treat this as a retrospective benchmark and use leakage-safe features when testing forward-looking player selection rules.

### 2026-05-29: Keep my detailed decision labels separate in manager benchmark

Decision:  
Story 8.1 creates sample-wide manager behaviour aggregates for all managers, while merging detailed transfer package, funding-leg, captaincy process, and benching regret fields only onto manager `816200` where those review outputs exist.

Reason:  
The top-N sample has histories, transfers, picks, and chips, but it does not yet have the same detailed decision-label outputs as my team. Keeping those fields my-team-specific preserves useful context without pretending that transfer package labels or process scores have been computed for every sampled manager.

Alternatives considered:  
Drop the detailed my-team decision fields from the behaviour summary, or fill sample rows with inferred labels that have not been calculated.

Risk:  
Sample rows have zero/blank values for the my-team-specific decision-review fields, so later comparisons must avoid interpreting those as sample behaviour.

Follow-up needed:  
Story 8.2 should build sample-level transfer comparisons from raw transfer and feature data, and keep those separate from the my-team-labelled transfer package columns.

### 2026-05-29: Separate hindsight bench regret from questionable benching

Decision:  
Story 7.5 evaluates each bench player against only formation-valid starter replacements. It records hindsight regret when the benched player outscored a replaceable starter, and marks a benching as questionable only when the benched player also had at least as strong a pre-gameweek position-aware selection score.

Reason:  
Bench points alone can overstate decision quality problems because not every benched player could legally replace every starter, and many bench hauls are only obvious after the gameweek. Separating hindsight regret from questionable benching keeps the process/outcome distinction consistent with earlier stories.

Alternatives considered:  
Compare every benched player against the worst starter regardless of formation, or judge benching solely by actual points left on the bench.

Risk:  
The pre-gameweek selection score is heuristic. It can miss contextual information such as injury news, tactical rotation expectations, or subjective risk tolerance.

Follow-up needed:  
Final leak summaries should use questionable/high-regret benching counts separately from raw bench points.

### 2026-05-29: Evaluate captaincy against actual and pre-GW alternatives

Decision:  
Story 7.4 compares the actual captain against the best actual squad player, the best actual starter, and a pre-gameweek recommended captain candidate. The candidate score combines prior form, captaincy ceiling, minutes security, position-aware scoring routes, and upcoming fixture context.

Reason:  
Captaincy has both outcome and process dimensions. Best-actual comparisons show points left on the table with hindsight, while the pre-GW candidate score provides a leakage-safe process benchmark that does not rely only on xGI.

Alternatives considered:  
Compare only against the best actual scorer, or recommend candidates using only xGI/form.

Risk:  
The candidate score is heuristic and can still recommend lower-ceiling positions when fixture and defensive-route signals are strong. Treat it as a transparent comparator, not a definitive optimal captain model.

Follow-up needed:  
Story 7.5 and later rule stories should reuse the position-aware feature principle and keep process benchmarks separate from hindsight-best outcomes.

### 2026-05-29: Propagate transfer package and position-route constraints downstream

Decision:  
Later backlog stories now explicitly distinguish individual transfer legs from gameweek transfer packages, include funding-leg caveats, and require position-aware scoring-route context for player selection, captaincy, benching, transfer rules, and final reporting.

Reason:  
Story 7.3 changed the interpretation layer. If later stories used only individual transfer rows or generic xGI-heavy player signals, the analysis would reintroduce the same bias that the revised transfer labels were designed to fix.

Alternatives considered:  
Leave later stories unchanged and rely on implementation-time memory, or only update transfer-specific stories.

Risk:  
The backlog is now more demanding, especially for benchmarking and rule testing, because outputs must avoid double-counting individual transfer legs and grouped package outcomes.

Follow-up needed:  
When each downstream story starts, read the updated acceptance criteria and choose feature subsets by decision type and position rather than using one generic player score.

### 2026-05-29: Evaluate transfer packages and position-specific scoring routes

Decision:  
Story 7.3 now keeps individual transfer labels but also groups transfers by manager and gameweek into transfer packages. It joins group labels back to each row, flags possible funding-leg downgrades, and adds a position-aware process route score for clean sheets, goals conceded, saves, defensive contribution, BPS, and bonus routes.

Reason:  
Individual transfer rows can misclassify structural moves where one downgrade funds an upgrade elsewhere. Also, different FPL positions score through different routes, so judging all players heavily through xGI biases the process score toward attackers and understates defenders, goalkeepers, and defensive-contribution players.

Alternatives considered:  
Keep only individual labels, group only chip-week transfers, or replace xGI with a single generic points-form metric.

Risk:  
Group-level transfer packages are currently grouped by gameweek, not exact tactical intent. Position-route thresholds are still heuristic and should be reviewed against real examples.

Follow-up needed:  
When reviewing transfer labels, use individual and group labels together. Later rule-generation stories should consider position-specific rule candidates rather than one generic player rule.

### 2026-05-29: Classify transfers with transparent threshold scores

Decision:  
Story 7.3 scores transfer process using thresholded differences in prior player form, minutes, xGI, team points per fixture, upcoming fixture difficulty, blanks, and doubles. It scores outcome using `net_points_after_hit_5gw`, then maps process/outcome booleans to the four `DECISION_QUALITY_LABELS`.

Reason:  
The goal is an interpretable retrospective, not a hidden model. A 5-GW hit-adjusted horizon is long enough to judge a normal FPL transfer but short enough to avoid letting rest-of-season outcomes dominate the label.

Alternatives considered:  
Use rest-of-season outcome, use only 1-GW outcome, or fit a statistical model from the process features.

Risk:  
The thresholds are heuristic and should be reviewed by eye. They identify patterns for discussion rather than proving causal quality.

Follow-up needed:  
After Story 7.3 review, use the labelled table to refine rule candidates and check whether the same process signals also explain captaincy and benching decisions.

### 2026-05-29: Prefix transfer process context by source and side

Decision:  
Story 7.2 keeps transfer outcome columns from Story 7.1, then adds process context using explicit `in_player_`, `out_player_`, `diff_player_`, `in_team_`, `out_team_`, `diff_team_`, `in_fixture_`, `out_fixture_`, and `diff_fixture_` prefixes.

Reason:  
Transfer classification needs both outcome evidence and pre-decision process context. Prefixing the new features makes it clear which columns describe the transferred-in player, transferred-out player, team context, upcoming fixtures, and simple `in - out` comparisons.

Alternatives considered:  
Create a process-only table without outcome fields, or use unprefixed feature names and rely on column order.

Risk:  
The table is wide, so later scoring rules should deliberately choose a small set of interpretable process columns rather than treating every feature as equally important.

Follow-up needed:  
Story 7.3 should use the prefixed process columns and avoid outcome columns when scoring process quality.

### 2026-05-29: Allocate transfer hit cost across official counted transfers

Decision:  
Story 7.1 allocates `event_transfers_cost` evenly across official counted transfers in a gameweek, while raw transfer rows in Wildcard and Free Hit weeks receive zero allocated hit cost. The output keeps both gross and hit-adjusted net outcome columns.

Reason:  
Manager history provides the official transfer count and points hit, but the raw transfers endpoint also records chip-week squad changes. Separating gross outcomes from allocated hit-adjusted outcomes preserves the transfer comparison while respecting how FPL charges hits.

Alternatives considered:  
Assign the full hit to every transfer row, ignore hits entirely, or try to infer which individual transfer caused each hit.

Risk:  
When several counted transfers happen in one gameweek, the per-transfer hit allocation is an approximation because the exact causal value of each transfer cannot be isolated from the bundled decision.

Follow-up needed:  
Transfer process and classification stories should use both gross and hit-adjusted outcomes and note uncertainty for bundled transfer weeks.

### 2026-05-29: Enrich my squad with current outcomes and prior-only context

Decision:  
Story 6.2 joins current player gameweek outcomes to my squad rows, but joins team strength only through prior-only team columns and fixture difficulty through forward-looking schedule columns.

Reason:  
Squad reconstruction needs actual points to evaluate decisions after the fact, while pre-gameweek player, team, and fixture context must remain leakage-safe for later decision-quality analysis.

Alternatives considered:  
Join all current team-strength columns, or keep the squad table limited to picks and actual points only.

Risk:  
The table is wide and contains both outcomes and pre-decision features, so downstream stories must distinguish outcome columns such as `actual_points` from prior/context columns.

Follow-up needed:  
Decision evaluation stories should use `actual_points` and `points_after_multiplier` as outcomes, and use `player_*_prior`, `team_*_prior`, and `fixture_*` columns as pre-decision context.

### 2026-05-29: Keep official and raw transfer counts in my timeline

Decision:  
Story 6.1 keeps both `event_transfers` from manager history and `transfer_count_actual` from the transfers endpoint.

Reason:  
FPL history reports `event_transfers` as zero on Wildcard and Free Hit weeks, while the transfers endpoint still records the squad changes. The official field is needed for hits and counted transfer behaviour, and the raw count is needed to explain squad churn during chip weeks.

Alternatives considered:  
Use only `event_transfers`, or overwrite it with raw transfer row counts.

Risk:  
The two fields can differ materially on chip weeks, so later analysis must choose the field that matches the question.

Follow-up needed:  
Transfer evaluation stories should use `event_transfers` and `event_transfers_cost` for hit accounting, and `transfer_count_actual` plus `transfer_moves` for chip-week squad reconstruction.

### 2026-05-29: Build fixture outlook by future gameweek windows

Decision:  
Story 5.3 creates fixture difficulty features for each team before each gameweek using the current gameweek plus next 3 and next 5 gameweek windows. The features include FPL difficulty, home/away fixture counts, blank/double indicators, and opponent prior team-strength metrics joined for the fixture gameweek.

Reason:  
FPL decisions are made before gameweek deadlines, so transfer and selection analysis needs the upcoming gameweek context and short multi-gameweek outlooks. Joining opponent strength from the opponent's prior-only team-strength row avoids using results from the fixture being evaluated.

Alternatives considered:  
Use next N fixtures rather than next N gameweeks, or use final-season opponent strength.

Risk:  
Gameweek windows and next-fixture windows answer slightly different planning questions. Blanks and doubles are explicit, but later analysis should choose the horizon that matches the decision being evaluated.

Follow-up needed:  
Transfer and player-selection stories should use `blank_*`, `double_*`, and `fixture_count_*` fields alongside difficulty averages so blanks and doubles are not hidden by mean values.

### 2026-05-29: Build team strength from prior team-gameweek aggregates

Decision:  
Story 5.2 converts completed fixtures into team-perspective match rows, aggregates them to one actual row per team per gameweek, then creates rolling and season-to-date strength features by shifting the team-gameweek history before calculation.

Reason:  
Aggregating before shifting prevents double-gameweek fixtures from leaking results within the same gameweek and gives later player and transfer analyses a stable one-row-per-team-per-gameweek join key.

Alternatives considered:  
Calculate rolling strength directly from individual fixture rows, or use same-gameweek fixture results when building the target gameweek row.

Risk:  
Rolling windows are gameweek-based rather than last-N-match based, so blanks count as zero-activity gameweeks. This is appropriate for pre-gameweek joins but should be interpreted carefully when teams have blanks or doubles.

Follow-up needed:  
Story 5.3 should model blanks and doubles explicitly in fixture outlook features.

### 2026-05-29: Mark team xG-like fixture strength as unavailable

Decision:  
`team_strength.csv` includes `xg_like_available=False` and does not fabricate expected-goals strength from fixture scores.

Reason:  
The processed FPL fixtures table contains scores and FPL difficulty values, but no team xG columns. Inventing an xG-like proxy from goals would blur actual outcomes with expected metrics and make later interpretation less precise.

Alternatives considered:  
Use goals scored/conceded as xG-like proxies, or omit any xG availability signal.

Risk:  
Team strength currently relies on actual results rather than underlying chance quality.

Follow-up needed:  
If an xG data source is added later, extend team strength with prior-only expected goals for and against.

### 2026-05-29: Expand player features around FPL scoring routes

Decision:  
Story 5.1 now creates prior-only rolling and season-to-date features for attacking returns, clean sheets, goals conceded, goalkeeper saves and penalty saves, bonus/BPS, defensive contributions, defensive actions, expected metrics, discipline, role stability, threshold rates, and per-90 efficiency.

Reason:  
The 2025/26 FPL rules include material scoring routes beyond goals, assists, and clean sheets. Defensive contribution points, goalkeeper save points, BPS-driven bonus, and discipline deductions need explicit historical signals for later transfer, captaincy, and squad-comparison analysis.

Alternatives considered:  
Keep only points, minutes, and xGI features; or preserve raw scoring columns without prior rolling summaries.

Risk:  
The feature table is wider and includes correlated columns. Later modelling should select features deliberately rather than treating every column as equally useful.

Follow-up needed:  
Later decision-analysis stories should use the prior-only scoring-driver columns and continue treating same-gameweek stats as outcomes.

### 2026-05-29: Treat start rate as gameweek-level role stability

Decision:  
`start_rate_prior` is based on whether a player started at least once in each prior gameweek, while raw `starts_season_to_date_prior` still preserves total starts.

Reason:  
FPL gameweek live rows can include double-gameweek totals, so `starts` can exceed one in a single gameweek. A direct `starts / prior_gameweeks` rate can exceed 1, which is not a useful role-stability rate.

Alternatives considered:  
Allow `start_rate_prior` to exceed 1, or drop start-rate features entirely.

Risk:  
The binary rate hides double-gameweek start volume, so analysts should use `starts_season_to_date_prior` when total start count matters.

Follow-up needed:  
Fixture difficulty and team-strength features should account for double gameweeks explicitly in later stories.

### 2026-05-29: Build player features from prior gameweeks only

Decision:  
Player rolling and season-to-date feature columns use shifted prior values, so a row for gameweek `t` only uses data available before gameweek `t`. Current-gameweek outcomes remain in the feature table for later analysis but should not be used as pre-decision inputs.

Reason:  
Story 5.1 creates reusable player-gameweek features for later decision analysis. Keeping `*_prior` inputs separate from outcome columns avoids hindsight leakage while preserving enough detail to explain points and validate results.

Alternatives considered:  
Use same-gameweek totals in rolling features, or create a table containing only feature columns and dropping outcome stats.

Risk:  
Early-season rows have sparse prior history, so models and rules must handle null or zero prior values explicitly.

Follow-up needed:  
Later analytical stories should use the `*_prior` columns for pre-decision comparisons and treat current-gameweek `total_points` as an outcome.

### 2026-05-28: Gate manager picks collection with a run limit

Decision:  
Add `MAX_MANAGERS_FOR_PICKS=50` so Story 4.2 can fetch the focal manager plus a bounded number of sampled managers before attempting the full 1,001-manager picks collection.

Reason:  
The full picks dataset is 1,001 managers across 38 gameweeks, or 38,038 manager-gameweek endpoint calls. A bounded run proves the pipeline and cache layout without forcing every Codex session to wait on the full API cache fill.

Alternatives considered:  
Immediately fetch all sampled managers, or only fetch manager `816200`.

Risk:  
Until the limit is raised and the full run completes, processed picks outputs are not representative of the full sampled manager cohort.

Follow-up needed:  
Run the remaining picks fetch locally or raise the limit in a later session, then resume Story 4.2 validation and output generation.

### 2026-05-28: Cache manager data per manager and endpoint

Decision:  
Story 4.1 stores manager history and transfer API responses as separate per-manager JSON files under `data/raw/managers/history/` and `data/raw/managers/transfers/`, then writes normalised CSVs for manager list, history, chips, transfers, and fetch failures.

Reason:  
Manager collection touches 1,001 managers and two endpoints per manager. Per-manager cache files make reruns resumable and prevent one failed manager from invalidating the whole batch.

Alternatives considered:  
One large raw JSON file for all managers, or only saving processed CSVs without raw endpoint caches.

Risk:  
The raw cache creates many small files, but this is acceptable for resumability and easier failure diagnosis.

Follow-up needed:  
Story 4.2 should reuse the same per-manager/per-gameweek cache pattern for picks and preserve a stable failure-log schema.

### 2026-05-28: Enforce a minimum sample per rank band

Decision:  
Keep `TOP_N=80,000` and `SAMPLE_SIZE=1000`, but enforce a minimum of 30 sampled managers for each non-empty rank band. The `1-1k` band was increased from 13 to 30 managers by reallocating 17 sample slots from the largest `40k-80k` band.

Reason:  
Story 3.3 validation showed the `1-1k` band was below the 30-manager warning threshold. There are 1,002 available candidates in that band, so the issue is allocation rather than missing data.

Alternatives considered:  
Lower `TOP_N` to make the top 1K a larger proportion of the sample, increase `SAMPLE_SIZE`, or leave the warning unresolved.

Risk:  
The final sample is no longer purely proportional; it intentionally overweights the top 1K band slightly to support elite-manager comparisons.

Follow-up needed:  
When interpreting benchmark results, treat rank-band comparisons as stratified analysis and avoid claiming the sample is a perfectly proportional top-80K sample.

### 2026-05-28: Use parsed pages 1-1600 for the top-N sample

Decision:  
Set the current comparison universe to the cached Overall standings pages 1-1600, equivalent to the top ~80K managers, and sample from rank bands `1-1k`, `1k-5k`, `5k-10k`, `10k-20k`, `20k-40k`, and `40k-80k`. The initial allocation was proportional, then superseded by the minimum-per-band decision above.

Reason:  
The user explicitly asked to use the top 1600 parsed pages. The parsed candidate file has 79,996 unique managers, which is large enough for `SAMPLE_SIZE=1000` and avoids further API fetching for this sprint.

Alternatives considered:  
Continue toward a full top-100K fetch, reduce to the first 1000 pages/top-50K, or use the two-page smoke file.

Risk:  
The sample represents the top ~80K rather than exactly top 100K, and rank ties mean the maximum rank in the parsed rows is 79,844 rather than exactly 80,000.

Follow-up needed:  
Story 3.3 should validate whether the sample distribution is acceptable before manager-level fetching starts.

### 2026-05-28: Default standings collection to smoke mode

Decision:  
Story 3.1 defaults to fetching two Overall league standings pages while retaining a `STANDINGS_FULL_FETCH` switch for the full top-N fetch.

Reason:  
The original top-N target required thousands of standings pages at 50 managers per page. A smoke fetch validates endpoint shape, cache paths, pagination fields, and candidate extraction before spending time and API traffic on a broader fetch.

Alternatives considered:  
Fetching all pages immediately, or hard-coding only the first page without a full-fetch path.

Risk:  
The smoke output is not representative enough for sampling until the full fetch is run.

Follow-up needed:  
Resolved by the 2026-05-28 decision to use parsed pages 1-1600 for the current top-80K sample.

### 2026-05-28: Preserve full gameweek live stats payload

Decision:  
For `gw_live.csv`, keep the full flattened `stats` payload from each `event/{gw}/live` player record, while front-loading known FPL scoring-driver columns for readability.

Reason:  
The 2025/26 scoring rules include defensive contributions, recoveries, clearances/blocks/interceptions, bonus, saves, cards, penalties, expected metrics, and other point drivers. A narrow preselected table risks dropping fields needed to explain where points came from.

Alternatives considered:  
Keeping only the original acceptance-criteria fields, or only the fields used by the next immediate analysis step.

Risk:  
The processed CSV is wider than a minimal table and may include fields that are not used immediately.

Follow-up needed:  
Later feature-building stories should separate outcome columns from pre-decision feature columns to avoid hindsight leakage.

### 2026-05-28: Raise API and JSON failures loudly

Decision:  
Let `fetch_json` use `response.raise_for_status()` and normal JSON parsing exceptions instead of returning partial error objects.

Reason:  
Early data-pipeline failures should be visible in notebook checks. Silent failures would make later processed tables look valid while being based on missing or malformed source data.

Alternatives considered:  
Returning `None`, returning an error dictionary, or swallowing request exceptions and relying on later row-count checks.

Risk:  
Notebook execution stops immediately if the FPL API is temporarily unavailable.

Follow-up needed:  
Later data collection stories can add retry/backoff if transient API failures become common.

### Starter decision: Use repo-native project management files before external tools

Decision:  
Use `AGENTS.md`, `PLANS.md`, `BACKLOG.md`, `KANBAN.md`, `SPRINTS.md`, `STATUS.md`, `TESTING.md`, and `DECISION_LOG.md` rather than starting in Jira, Trello, or Linear.

Reason:  
This is a solo side project. A repo-native board reduces overhead while still giving Codex durable instructions and a human-reviewable project state.

Alternatives considered:  
External Kanban tools such as Jira, Trello, Linear, or GitHub Projects.

Risk:  
Markdown boards can become stale if Codex does not update them consistently.

Follow-up needed:  
After each story, verify that Codex updated the board and status files correctly.
