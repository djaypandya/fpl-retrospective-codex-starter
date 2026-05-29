# NEXT_SEASON_DECISION_PROCESS_CLARIFICATION.md

## Why this clarification exists

Codex has started building Epic 11, the Weekly Decision System. The current season is already over. The goal is **not** to create a tool that retrospectively recommends transfers for the completed season as if we were still playing it.

The goal is to use the completed season as a training and evidence base to build a **next-season decision process**.

That process should be grounded in what worked across the representative sample of managers, not only in manager `816200`'s own decisions.

---

# Critical objective

Build a repeatable weekly FPL decision process for next season using historical evidence from the sampled manager cohort.

The process must answer:

1. How should I narrow the full player pool each gameweek into a credible transfer watchlist?
2. How should I decide which player in my squad is most replaceable?
3. How should I decide whether a hit is justified, including `-4`, `-8`, and `-12` scenarios?
4. How should I decide who to captain?

The output should be a **process and rule system**, not just a one-off historical recommendation.

---

# Sample-manager grounding requirement

Use the sampled manager cohort as the evidence base.

The intended cohort is the `1000` sampled managers from the representative top-N sample. If the current repo contains fewer than 1000 sampled managers because of smoke-test limits or missing cached data, Codex must:

1. Report the actual available sample size.
2. Use the available sample only for development/smoke testing.
3. Keep function parameters and config ready for the intended 1000-manager sample.
4. Clearly label any outputs from smaller samples as low confidence.

Do not let the system become a personalised model of only manager `816200`.

Manager `816200` should be used for:

- applying the decision process to a real squad;
- reviewing personal historical leaks;
- showing how the process would guide this manager;
- identifying where personal behaviour differed from the sample.

The sampled managers should be used for:

- learning candidate-selection rules;
- learning sell/hold thresholds;
- learning transfer package and hit thresholds;
- learning captaincy patterns;
- calibrating confidence levels;
- identifying which behaviours actually worked across many managers.

---

# Important distinction: application vs learning

The weekly decision pack has two layers:

## 1. Learned rule layer

This layer learns from historical sampled-manager behaviour and outcomes.

It should answer questions such as:

- What player profiles did strong managers buy before they performed well?
- What player profiles did strong managers sell before they underperformed?
- Which transfer-package patterns paid back a hit over 1GW, 3GW, and 5GW windows?
- What score threshold historically justified a `-4`?
- What much higher threshold historically justified a `-8` or `-12`?
- What captaincy profiles were most reliable?
- When did differential captaincy work versus fail?

## 2. Weekly application layer

This layer applies those learned rules to a specific squad and target gameweek.

For development, manager `816200` and historical `target_gw` values can be used as test cases. But the purpose of those test cases is to prove that the decision process works and is leakage-safe, not to optimise for the already-finished season.

---

# What Codex must change or verify before continuing

Before continuing past Story 12.1, Codex must audit the Epic 11 code and outputs against this clarification.

Specifically, Codex must check:

1. **Transfer candidate shortlist**
   - Does it merely rank players using hand-chosen weights?
   - Or are the weights/thresholds backed by historical sampled-manager evidence?
   - If currently hand-chosen, keep them as v1 heuristics but add a plan to calibrate them using sample-manager backtests.

2. **Sell candidate review**
   - Does it only score manager `816200`'s squad using generic risk scores?
   - Or does it compare each owned player against historically successful sell/hold patterns from the sampled cohort?
   - If currently generic, add a sample-backed calibration step.

3. **Transfer pair and package review**
   - Does it evaluate upgrade scores at package level?
   - Does it estimate whether hit costs were historically paid back by comparable packages among sampled managers?
   - The `-4`, `-8`, and `-12` thresholds must be conservative and sample-backed.

4. **Captaincy decision**
   - Does it only rank current squad players by heuristic score?
   - Or does it incorporate sampled-manager captaincy behaviour and post-hoc payoff evidence?
   - Captaincy rules should identify safe/template, balanced, aggressive/differential, and avoid scenarios.

5. **Backtests**
   - Sprint 14 should not be optional polish. It is the validation layer that converts heuristics into evidence-backed process rules.
   - The final system is not acceptable unless it reports how well the rules performed historically across the sampled cohort.

---

# Required outputs for the next-season process

In addition to current weekly output tables, Codex should create rule-calibration outputs:

```text
outputs/tables/learned_candidate_shortlist_rules.csv
outputs/tables/learned_sell_hold_rules.csv
outputs/tables/learned_hit_threshold_rules.csv
outputs/tables/learned_captaincy_rules.csv
outputs/tables/next_season_weekly_decision_checklist.csv
```

Each learned rule table should include:

- `rule_id`
- `decision_area`
- `plain_english_rule`
- `sample_size`
- `sample_manager_count`
- `rank_band_coverage`
- `evidence_window` such as 1GW, 3GW, or 5GW
- `mean_outcome`
- `median_outcome`
- `baseline_outcome`
- `uplift_vs_baseline`
- `confidence`
- `when_to_use`
- `when_to_ignore`
- `risk_of_overfitting`

---

# Revised acceptance criteria for Epic 11

Epic 11 is only complete when the system can produce both:

1. A **weekly decision pack** for a target gameweek and squad.
2. A **next-season decision process** based on learned rules from the sampled manager cohort.

The final output must include:

- a player-pool narrowing process;
- a sell/hold process;
- a hit-justification process;
- a captaincy process;
- sample-backed confidence labels;
- an explicit statement of sample size and limitations;
- a one-page weekly checklist that the user can follow next season.

---

# Required design principle

Do not optimise for the finished season.

Use the finished season to discover rules that would have been reasonable **at the time of each deadline** and that appear to hold up across many managers.

The core question is not:

```text
What would have scored most points last season with hindsight?
```

The core question is:

```text
Given only the data available before each deadline, what process repeatedly led strong managers toward better transfer, hit, and captaincy decisions?
```

---

# Prompt for Codex before continuing

Use this prompt before accepting Story 12.1 or starting Story 12.2:

```text
Pause Epic 11 implementation and read NEXT_SEASON_DECISION_PROCESS_CLARIFICATION.md.

The Weekly Decision System must be a next-season decision process learned from the sampled manager cohort, not a retrospective optimiser for the completed season.

Before continuing, audit the work completed in Stories 11.1, 11.2, 11.3, and 12.1.

Report:
1. Which parts already use evidence from the sampled managers.
2. Which parts are currently heuristic-only.
3. Which parts rely mainly on manager 816200 rather than the sampled cohort.
4. Whether Story 12.1 should be accepted as Done, revised, or accepted with a follow-up calibration story.
5. What changes are needed before implementing Story 12.2.

Do not implement new functionality until this audit is complete.
```
