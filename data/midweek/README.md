# Midweek / non-Premier-League matches

Why this file exists: **the FPL API carries no fixtures outside the Premier
League.** `fixtures.json` has only the 380 league games. Congestion effects —
rotation, reduced minutes, tired legs — come from cup and European midweeks that
the API never mentions, so they have to be recorded here by hand each week.

## Schema (`2026-27.csv`)

| column | meaning |
|---|---|
| `date` | ISO date of the match |
| `competition` | e.g. `UEFA Champions League`, `EFL Cup` |
| `stage` | e.g. `League phase MD1`, `Round 2` |
| `home` / `away` | club names as reported by the source |
| `home_score` / `away_score` | blank until confirmed |
| `pl_clubs` | semicolon-separated FPL **short codes** (`MCI`, `ARS`, …) — this is the join key |
| `source` | where the row came from |
| `confirmed` | `confirmed` = date + teams + score verified; `fixture-only` = teams and date verified, score not; `dates-only` = the round's window is known but individual ties are not |

Only `date` and `pl_clubs` are required for congestion analysis. Scores are
nice-to-have.

## English clubs in Europe, 2026/27

- **Champions League**: Arsenal, Man City, Man United, Aston Villa, Liverpool
- **Europa League**: Bournemouth, Sunderland, Crystal Palace
- **Conference League**: Brighton

## Known competition windows

| window | competition | note |
|---|---|---|
| 24–25 Aug 2026 | EFL Cup R2 | 11 PL clubs not in Europe |
| 8–10 Sep 2026 | UCL MD1 | falls between GW3 and GW4 |
| from 16 Sep 2026 | Europa League league phase begins | falls between GW4 and GW5 |
| 13–14 Oct 2026 | UCL MD2 | |

## Weekly routine

Run this alongside the snapshot capture, every gameweek:

```
python3 scripts/snapshot.py capture --league 14074 --gw N
python3 scripts/midweek.py congestion --gw N     # what to add, and the rest-day table
```

`congestion` prints which clubs have unexplained long gaps between league games
— those are the weeks where a midweek match is probably missing from the CSV.
