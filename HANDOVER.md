# HANDOVER — FPL 2026/27 weekly decision support

Written 2026-09-30 for the next coding agent. Everything here was verified against
the repo and the live FPL API on that date. Where something is a judgement rather
than a fact, it says so.

---

## 0. Read in this order

1. **This file.** It is the current picture.
2. `data/midweek/README.md` — the one dataset that cannot be rebuilt after the fact.
3. `diary/2026-27/gw05.txt` — the user's own voice on how they think about decisions.
4. `AGENTS.md` — **but see the warning in §3.** It describes a phase of the project
   that is finished, and following it literally will send you the wrong way.
5. `/Users/djay/Documents/AGENTS.md` — the user's coding-failure-prevention rules.
   These *do* apply. Boring, clear, loud-failing code. No premature abstraction.

The user's assistant memory at
`~/.claude/projects/-Users-djay-Documents-experiments-book-to-skill-analytical-data-skill/memory/`
holds four notes that overlap with this file. If they disagree, trust this file —
it was written later and checked against the data.

---

## 1. Current state, verified 2026-09-30

**Season:** 2026/27, live. GW5 is finished. **GW6 deadline is 2026-10-10 10:00Z** —
a long gap because of the international break, so there is time to catch up.

**The user's season so far** (entry `46116`, "Numbers Don't Lie"):

| GW | Points | Bench | League avg | Note |
|----|--------|-------|-----------|------|
| 1 | 59 | 14 | 50 | |
| 2 | 80 | 14 | 81 | |
| 3 | 64 | 27 | 51 | Triple Captain played |
| 4 | 71 | 28 | 69 | Wildcard played |
| 5 | 41 | 25 | 48 | Held transfer, as planned |

Total **315**, **15th of 22** in mini-league 14074 (was 14th), 86 behind the leader
Vishal Perera on 401. Overall rank ~3.08M.

**Chips:** Triple Captain gone (GW3), Wildcard gone (GW4). **Bench Boost and Free
Hit still held.**

**The standing problem nobody has solved yet:** 108 bench points across five
gameweeks (14, 14, 27, 28, 25). That is ~21 per gameweek unused, and it has been in
the top two in the league most weeks. Raise it when it is decision-relevant; the
user has seen the number and has not yet chosen to act on it.

### Git state

- On branch `gw5-2026-27-plan`, clean, **pushed but not merged**.
- `main` is at the GW4 merge (PR #14).

**⚠ Two real bug fixes are stranded on the unmerged `gw5-2026-27-plan` branch.** If you
work from `main` you will be running the broken versions. Verified by diffing the two
branches:

| | on `main` | on `gw5-2026-27-plan` |
|---|---|---|
| `team_trends.py` squad source | reads the **draft** `outputs/gw4_wildcard/squad_locked.csv` (2 call sites) — reports on a squad that was never fielded | reads the snapshot's actual picks |
| `team_trends.py` `load_defcon` | player metadata pinned to the **GW3** bootstrap (2 call sites) — misses anyone registered since | newest bootstrap in the archive |
| `--squad-gw` flag | absent | present |

That branch also holds the GW5 diary entry, the GW1–4 trends refresh and
`TEAM_XG_TRENDS_GW1_4.pdf`. Merging it is the cleanest way to un-strand the fixes —
ask the user first.
- **Two PRs are open and unmerged:**
  - [#15](https://github.com/djaypandya/fpl-retrospective-codex-starter/pull/15) — OneDrive duplicate cleanup
  - this handover's PR
- Merged history: PR #12 (GW1), #13 (GW3), #14 (GW4). PR #11 (`add-decision-cockpit`)
  has been open since July and appears abandoned — ask before touching it.

---

## 2. Do these first

**① Capture the GW5 snapshot. It was never taken.**

`data/snapshots/2026-27/` holds gw01–gw04 only. GW5 has been played and there is no
archive of it. The picks, live scores and transfers are still fetchable today (I
confirmed `entry/46116/event/5/picks/` still returns data), but the API **wipes all
of it at season rollover** and there is no archive endpoint. Run:

```bash
python3 scripts/snapshot.py capture --league 14074 --gw 5 --note "GW5 final, captured late"
```

Then the report and story for GW5 (§6.3), which have also never been built.

**② Backfill the midweek log for late September.** The log covers EFL Cup R2 (24 Aug),
UCL MD1 (8–10 Sep) and Europa League MD1 (16–17 Sep), plus one future row for
Brighton's Conference League opener on 15 Oct. **Nothing is recorded for 18–30 Sep** —
EFL Cup Round 3 and Europa/Conference League MD2 both fall in that window and need
looking up. UCL MD2 is 13–14 Oct, which lands between GW6 and GW7. See §6.4.

**③ Grade the GW5 predictions in the GW6 diary.** The user wrote three falsifiable
predictions in `diary/2026-27/gw05.txt`. Verified results:
- *"I make zero transfers this gameweek"* — **held.** GW5 `event_transfers` = 0.
- *"Bench points under 20"* — **failed.** 25.
- *"Post-wildcard squad outscores the pre-wildcard squad"* — **not yet measurable.**
  Nobody built the shadow tracker. See §10.

**④ Decide what to do about the two open PRs.** Ask the user; do not merge unasked.

---

## 3. What this project actually is now

**Two phases, and `AGENTS.md` documents the wrong one.**

*Phase 1 (finished, ~May–July 2026).* A retrospective analysis of the **2025/26**
season for entry **816200**, building a walk-forward predictive "decision engine".
It reached a clear, honest, negative verdict — see §9. `AGENTS.md`, `PLANS.md`,
`BACKLOG.md`, `KANBAN.md`, `SPRINTS.md`, `STATUS.md` and `TESTING.md` all belong to
this phase. `STATUS.md` still says "Story 12.3 in review", dated 2026-05-30. There
is no live sprint. **Do not go looking for the next Ready story.**

*Phase 2 (current, since ~July 2026).* Live weekly decision support for the
**2026/27** season, entry **46116**, mini-league **14074**. Archive the data each
week, report on what the league did, keep a decision journal, and feed the user
analysis they can act on before the next deadline. This is script-driven, not
notebook-driven.

If you touch `AGENTS.md`, its §Coding rules, §Data rules, §Modelling principles and
§Communication style are all still good. It is the workflow and the entry ID that
have moved on.

---

## 4. Identity and constants — get these right

| Thing | Value | Trap |
|---|---|---|
| Current entry | **46116** | Not 816200. |
| Retrospective entry | 816200 | 2025/26 only. Mixing these up silently produces a report about the wrong person. |
| Mini-league | **14074**, classic, 22 managers | |
| Season string | `2026-27` | Used in snapshot and diary paths. |
| Snapshot root | `data/snapshots/2026-27/gwNN/<UTC stamp>/` | Immutable. Never overwrite a capture; add a new one. |
| PDF naming | `LEAGUE_GW<N>_DATA_STORY.pdf`, `TEAM_XG_TRENDS_GW1_<N>.pdf` | Repo root, committed. |
| Output dirs | `outputs/league_14074_gw<N>/`, `outputs/team_trends/` | `outputs/league_*/raw/` is gitignored. |

---

## 5. Repo map

**Scripts that matter weekly**

| Script | What it does |
|---|---|
| `snapshot.py` | Archives the API. `capture`, `list`, `verify`, `restore`. The most important script in the repo. |
| `league_report.py` | Per-GW mini-league intelligence: template, budget split, what the strongest managers do, who can hurt you. Writes CSVs to `outputs/league_14074_gw<N>/`. |
| `league_story.py` | Turns that into a slide-style HTML + PDF data story. |
| `team_trends.py` | Team xG / xGC / xGD and DEFCON analysis from the snapshots, plus the user's own squad's DEFCON record. |
| `midweek.py` | The congestion dataset. `add`, `congestion`, `impact`. |
| `diary.py` | Scaffolds the weekly decision journal. `new --gw N`, `list`. |

**Other scripts:** `build_gw1_squad.py` (season-start optimiser), `build_reference.py`
(builds `FPL_2026_27_REFERENCE.md/.pdf`), `find_elite_managers.py` (elite cohort
benchmarks in `outputs/elite_managers/`). I have not run the last two; treat their
behaviour as unverified.

**`src/fpl_retro/`** is Phase 1's library — `v0_engine.py`, `v0_1_engine.py`,
`v1_engine.py`, features, evaluation, squad/XI logic. Still useful: `v1_engine.py`
has formation-legal XI selection, bench auto-subs and captain doubling, which is
what you would reuse to score any hypothetical squad.

---

## 6. Standard operating procedures

### 6.1 The weekly cycle

Run in this order. Steps 1–2 are non-negotiable; the rest is judgement.

1. **After the deadline passes**, capture a snapshot (§6.2). Capture again after the
   last match finishes. Intermediate captures during the gameweek are welcome — they
   are the only record of in-flight states, and four GW4 captures are already archived.
2. **Log any midweek matches** that happened since the last gameweek (§6.4).
3. **Build the report and story** (§6.3).
4. **Refresh team trends** if fixtures have moved enough to matter (§6.6).
5. **Scaffold the next diary entry** and fill in what the user tells you (§6.5).
6. **Commit on a `gw<N>-2026-27-plan` branch, PR into main** (§6.7).

### 6.2 Snapshot capture

```bash
python3 scripts/snapshot.py capture --league 14074 --gw N --note "what state the GW was in"
```

92 endpoints, ~250 KB gzipped, all 22 entries, about 30 seconds. Captures are
immutable and additive — a second capture of the same gameweek creates a new
timestamped folder, it does not overwrite. That is deliberate. Always write a `--note`
saying how far through the gameweek it was.

**Why this is the most important thing you do:** at season rollover FPL destroys
per-gameweek live scores, every manager's picks, and the full transfer log. There is
no archive endpoint. If it was not captured, it is gone permanently.

Check what exists with `snapshot.py list`, and `snapshot.py verify` for checksums.
`snapshot.py restore --gw N --into outputs/league_14074_gwN/raw` rebuilds the cache
layout `league_report.py` reads, so any past gameweek's report can be regenerated
offline.

### 6.3 Report and story

```bash
rm -rf outputs/league_14074_gw<N>/raw          # force a refetch, or restore from snapshot
python3 scripts/league_report.py --league 14074 --entry 46116 --gw N
python3 scripts/league_story.py  --league 14074 --entry 46116 --gw N --out LEAGUE_GW<N>_DATA_STORY.pdf
```

`league_story.py` renders HTML then shells out to headless Chrome at
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` for the PDF. That path
is hard-coded in both `league_story.py` and `team_trends.py`; if Chrome moves, they
break with a subprocess error.

The story changes shape depending on whether the gameweek is mid-flight or complete —
mid-gameweek it projects from who still has players to play, complete it reports finals.

### 6.4 Midweek congestion log

Read `data/midweek/README.md` first. The short version: **the FPL API contains only
the 380 Premier League fixtures.** Champions League, Europa League, Conference League
and EFL Cup games are invisible to every other script here and are not recoverable
from the snapshots, so they must be recorded in the week they happen.

```bash
python3 scripts/midweek.py congestion --gw N     # rest days + 14-day load per club
python3 scripts/midweek.py add --date 2026-10-13 --comp "UEFA Champions League" \
    --stage "League phase MD2" --home Arsenal --away Olympiacos --pl ARS \
    --source uefa --confirmed fixture-only
python3 scripts/midweek.py impact --gw N          # minutes and points against rest
```

`congestion` flags clubs with a gap of 9+ days since their last match — usually that
means a midweek game is missing from the CSV. Only `date` and `pl_clubs` (FPL short
codes, semicolon-separated) are required; scores are optional.

2026/27 English clubs in Europe: **UCL** Arsenal, Man City, Man United, Aston Villa,
Liverpool · **Europa League** Bournemouth, Sunderland, Crystal Palace ·
**Conference League** Brighton (starts 15 Oct, later than the others).

This paid off immediately: UCL MD1 fell between GW3 and GW4, so Liverpool, Arsenal and
Man United all played GW4 on three days' rest. Man United started eleven players on
60+ minutes and returned 2.08 points per player used.

### 6.5 The decision diary

```bash
python3 scripts/diary.py new --gw N
```

Scaffolds `diary/2026-27/gwNN.txt` with last gameweek's facts filled in and blank
lines for the thinking. **You fill in the prose from what the user tells you, in their
first-person voice. Do not invent content.** If they have not told you their captain,
leave the captain line blank — I did exactly that for GW5 and said so.

The entry's most valuable section is the three falsifiable predictions at the bottom.
Grade them in the next week's entry.

**Known bug:** `scripts/diary.py:147` hard-codes the chip line to all four chips
(`", ".join(ALL_CHIPS)`), so every entry claims the user still holds everything. The
truth is in the API (`entry/46116/history/` → `chips`). I corrected it by hand in the
GW5 entry. Fixing it properly is a small, welcome job — read the chips from the
snapshot and subtract.

### 6.6 Team trends

```bash
python3 scripts/team_trends.py --gws 1 2 3 4 5 --out TEAM_XG_TRENDS_GW1_5.pdf
```

`--squad-gw N` picks which gameweek's locked squad the DEFCON pages report on; it
defaults to the last gameweek in `--gws`. **That flag, and the two fixes below, exist
only on `gw5-2026-27-plan` — see the warning in §1 before running this from `main`.**

This script read the user's squad from `outputs/gw4_wildcard/squad_locked.csv`, which
is a **draft proposal, not the team that was fielded** — so it was describing a squad
that never played, with Justin, Cherki and Gakpo in it and Gvardiol, Ødegaard and
Gibbs-White missing. It now reads the picks out of the snapshot. `load_defcon` also
pinned player metadata to the GW3 bootstrap and now takes the newest one.
**Generalise the lesson: the snapshot is the only source of truth for what was owned.**
Planning documents in `outputs/` and `diary/` record intentions, and the user changes
their mind between drafting and the deadline.

### 6.7 Git workflow

The established pattern, followed for GW1, GW3, GW4:

```
branch gw<N>-2026-27-plan off main  →  commit  →  push  →  gh pr create  →  merge
```

- Branch names: `gw<N>-2026-27-plan` for gameweek work, `chore/…` or `docs/…` otherwise.
- **Commit and push only when asked.** The user asks explicitly ("merge gw4 into main").
- Commit messages: explain *why*, not just what. Several paragraphs is normal here and
  matches the existing history. End with
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- PR bodies end with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Do not merge a PR unless told to. Opening one is fine.
- `gh` is authenticated and works.

### 6.8 Artifacts

The GW4 data story is published as an artifact at
`https://claude.ai/code/artifact/2ed690b9-e00e-4c94-8449-5889e292ad38`. To update it,
republish the same local HTML file path in the same conversation, or pass that URL as
`url` from a new conversation. Publishing without the URL creates a *second* artifact
and loses the link the user already has.

The build is a small script that wraps `outputs/league_14074_gw<N>/story.html` for
web, living in the session scratchpad rather than the repo — if you need it again,
expect to rewrite it. Consider promoting it into `scripts/` if the user wants a page
every week.

### 6.9 Memory

Four notes exist. Keep them current rather than adding near-duplicates:

- `fpl-retrospective-project.md` — Phase 1 findings, Phase 2 setup, open ideas
- `fpl-rival-squads-are-stale.md` — the pre-deadline ownership trap
- `fpl-midweek-congestion-tracking.md` — the standing weekly job
- `fpl-benchmark-against-absolute-not-league.md` — how the user wants to be measured

---

## 7. Data traps that have actually bitten

1. **Free Hit reverts.** A manager who free-hits has a *borrowed* squad for that
   gameweek only; next gameweek they revert to their previous team. When projecting
   what a rival will own, use their pre-free-hit squad. Missing this put nine players
   on a shortlist that the manager did not actually own.

2. **Wildcard transfer logs are noise.** During a wildcard the transfer endpoint
   records every intermediate swap, including ones later reversed — the user's GW4
   wildcard logged 19 moves for 8 actual changes. Always compute the **net set
   difference** between consecutive gameweeks' picks, never read the transfer list.

3. **Rival picks are one deadline stale until the deadline passes.** The API only
   reveals a manager's picks after the deadline. Any pre-deadline statement about what
   rivals "own" or "will captain" describes last week. This is not pedantry: in GW4 the
   user planned a differential Palmer captaincy off GW3 data showing 4 of 22 owners.
   By the deadline Palmer was owned by 11 and captained by 10 — the edge was gone
   because nine rivals read the same fixture. **Quantify an intended edge only from
   post-deadline picks.**

4. **`bootstrap-static` is a live snapshot, not history.** Its `form`, `now_cost` and
   `total_points` are current values. Using an end-of-season bootstrap as a
   time-varying signal is look-ahead bias, and it is what produced Phase 1's false
   0.79 correlation. Per-gameweek truth lives in `event-NN-live.json.gz`.

5. **`finished=false` / `data_checked=false` means bonus points are provisional.**
   Scores can still move slightly. Say so when reporting.

6. **A gameweek can be `is_current` and finished at once.** Check `finished` and the
   per-fixture `started` / `finished_provisional`, not `is_current`.

7. **OneDrive writes conflict copies.** OneDrive Sync Service runs on this Mac and
   creates `"<file> 2.ext"` duplicates. 22 had built up; two reached a commit. PR #15
   cleans them and adds a `.gitignore` rule, but **the rule only hides them from git —
   OneDrive keeps making them.** The real fix is excluding the repo from sync or moving
   it out of `~/Documents`. This matters because a conflict copy of a snapshot
   directory mid-write could corrupt an archive that cannot be refetched later.

8. **`timeout` is not installed** on this Mac. Use the Bash tool's own `timeout`
   parameter instead of the shell command.

9. **There is no per-gameweek price or global ownership in the archive.** Price is
   partially reconstructable by pooling `element_in_cost` / `element_out_cost` across
   managers' transfer logs. Ownership can only be a cohort proxy.

---

## 8. User preferences

**Who they are.** A capable analyst who reads output critically and will push back.
They think in terms of decision quality over outcomes, and they keep a written
journal with falsifiable predictions specifically to test their own reasoning. They
want a collaborator who argues, not one who agrees.

**Benchmark against an absolute, not the league.** When they worry they are
underperforming they check their scoring rate against a strong manager's long-run
average (they use FPL Harry, 62–67 per gameweek over five seasons) rather than against
this week's mini-league table. Give them the absolute benchmark — their own rolling
average, the game average, the league average — *alongside* the position. A bare
mini-league rank invites exactly the panic they are working to avoid, and they have
said explicitly they do not want to react to what other managers did.

**But do not soften numbers.** The preference is about frame of reference, not tone.
They wanted the 28-point bench in the GW4 diary and the tension it creates with
"happy with squad construction". State unflattering facts plainly.

**Correct yourself when the evidence moves.** Mid-GW4 I called Mbeumo a
"near-certain hold"; he then blanked and the market turned against him. Saying so
directly, as a correction, was received well. Do not quietly restate a softer version
of an earlier claim.

**Separate verified from inferred.** They care about provenance. Say which numbers
came from the snapshot, which from a web lookup, and which are judgement. The
`confirmed` column in the midweek CSV exists for this reason.

**Scope discipline.** They give clear, often multi-part instructions and expect all
parts done. When I noticed the duplicate files while doing something else, flagging
them as a separate task rather than fixing them inline was the right call — and they
then asked for it explicitly. Do the ask; surface adjacent problems rather than
absorbing them.

**Output style.** Tables for anything comparative. Bold the number that matters.
Lead with the finding, not the method. Caveats at the end, in one or two sentences,
not hedged through every paragraph. Plain English — the Phase 1 stories were written
to roughly a 7th-grade reading level deliberately and that house style still holds.

---

## 9. Settled analytical findings — do not re-litigate

Phase 1 ran a full arc (exploration → v0 → v0.1 → v1) and reached a negative verdict
that is documented, honest, and worth respecting:

- **Availability dominates everything.** The eye-catching 0.79 correlation between
  form and future points is an artifact of players who do not play scoring zero.
  Restricted to players actually playing, it collapses to **0.20**. Minutes are the
  lever; form is a modest edge.
- **A better predictor did not make better decisions.** The two-stage ranker was
  genuinely the best forward-points predictor among likely starters (Spearman 0.268 vs
  0.163 for "highest recent minutes"), and it still **lost** the realistic weekly
  simulation to the naive "highest recent points among likely starters" rule
  (1680 vs 1839, CI excludes zero). FPL rewards ceiling; a regularised model
  under-weights explosive tails.
- **The recommended process is the simple one:** availability filter, then highest
  recent points among likely starters, value as tiebreak.
- **Three plausible enhancements were tested and failed.** Difficulty-weighted form is
  redundant with recent points. Cohort net transfers ("smart money") are null. Forward
  fixture difficulty gives a tiny ranking signal that does not convert to points.
- **Elite ownership is not an edge.** Plain popularity beats elite-cohort effective
  ownership in every variant tested, and narrowing to a more elite cohort makes it
  worse.

**Method standards:** walk-forward only, never a random split, because rows are
temporally dependent. Purge and embargo for multi-gameweek targets. Uncertainty via
gameweek-block bootstrap, not per-row. Future *schedule* is not leakage; future
points, minutes and prices are.

---

## 10. Open threads

- **Pre- vs post-wildcard shadow tracker.** The user wants to know whether their GW4
  wildcard actually improved the squad, by scoring their old GW3 team forward each week
  alongside the real one. Feasible offline: the GW3 squad is snapshotted and
  `v1_engine.py` already does formation-legal XI, auto-subs and captain doubling. Hold
  the old squad frozen and **say plainly that it is a shadow baseline, not a
  counterfactual** — the user would have made transfers. It is GW5 prediction #2 and
  cannot be graded until it exists.
- **The bench problem.** 108 points in five gameweeks. Bench Boost is still held.
  Nobody has analysed whether the issue is squad structure, XI selection, or variance.
- **`diary.py` chip line bug** (§6.5).
- **PR #11**, open since July, probably abandoned.
- **Phase 1 docs are stale** — `STATUS.md` and friends describe a finished sprint.
  Worth archiving under a `phase1/` prefix, but ask first; they are the record of real
  work.

---

## 11. Environment notes

- Repo: `/Users/djay/Documents/fpl-retrospective-codex-starter`, git, remote
  `djaypandya/fpl-retrospective-codex-starter`.
- Python 3.12, invoked as `python3`. `numpy`, `pandas`, `scipy`, `matplotlib`,
  `certifi` available. Scripts use `certifi` for SSL because python.org builds ship
  without linked root certificates.
- API base `https://fantasy.premierleague.com/api`, no auth needed for anything used
  here. Be polite: `snapshot.py` sleeps 0.25s between requests. Send a `User-Agent`.
- Headless Chrome is the PDF renderer; the path is hard-coded (§6.3).
- A second working directory sometimes appears in session config:
  `/Users/djay/Documents/experiments/book-to-skill/analytical-data-skill`. That is a
  separate skills project, not this one, though the assistant memory for this work
  lives under its project key.
