# FPL Weekly Decision Cockpit

`fpl_cockpit.html` is a single-file, offline decision dashboard for an FPL deadline. It presents the existing weekly decision system; it does not replace or retrain that system.

## Build it

From the repository root, run:

```bash
python3.12 dashboard/build_cockpit.py --target-gw 10
```

The default entry is `816200` and the default output is `dashboard/fpl_cockpit.html`. The builder derives the bank and free-transfer wallet from the prior gameweek timeline. Override them only when the live wallet is more accurate:

```bash
python3.12 dashboard/build_cockpit.py \
  --target-gw 10 \
  --entry-id 816200 \
  --free-transfers 2 \
  --bank 1.4
```

Use `--no-regen` to read the cached decision tables without first calling `build_weekly_decision_pack`. Use `--self-test` to assert the offline contract, squad/table counts, captain recommendation, hero affordability, JSON safety, and both availability classes:

```bash
python3.12 dashboard/build_cockpit.py --target-gw 10 --self-test
```

## Weekly refresh

1. Run the repository's existing ETL through the processed squad, timeline, player-prior, fixture-difficulty, fixture, and player tables.
2. Refresh the live bootstrap snapshot at `data/raw/bootstrap_static_smoke.json`. For an upcoming deadline, its `status`, playing chance, and news fields automatically feed every availability dot. Historical builds deliberately suppress the current snapshot and use target-GW minutes priors, preventing later injury news from leaking backwards.
3. Build the deadline cockpit with the new `--target-gw`. The script attempts to regenerate the weekly decision pack before reading it.
4. Open `dashboard/fpl_cockpit.html` directly. It needs no server, network connection, font, image, or chart library.
5. Read any provenance warning in the footer. If regeneration fails, the builder uses cached tables only where they contain the requested gameweek; unmatched panels say that data is insufficient.

Bank is normalized once to £m. If `bank_value` exists it is preferred; otherwise the timeline's tenths-based `bank` is divided by ten. Free transfers are reconstructed from prior transfers, chip weeks preserve the wallet, the wallet is capped at five, and the 2025/26 GW16 AFCON top-up is applied. Pass `--free-transfers` if next season's rules change.

## Signal hierarchy

Availability is the universal gate. Attacking xGI or the relevant position route, price value, and known forward fixtures provide the evidence below it. Recent form is deliberately muted context because it was the weaker retrospective signal. The saved captaincy row supplies the recommendation; because that table does not contain a full XI leaderboard, the remaining owned alternatives use the explicitly permitted availability-gated prior points-per-90 comparison and are labelled as such.

Chip meters and lineup swap prompts are clearly labelled scan heuristics. They use only target-gameweek prior features and forward fixture data, never realized target-gameweek performance.
