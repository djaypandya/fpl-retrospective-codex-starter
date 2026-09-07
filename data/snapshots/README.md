# Season data archive

The Fantasy Premier League API has no history. When a season rolls over, most of
what it served is **destroyed or rewritten in place**. There is no archive
endpoint, no `?season=` parameter, and no way to ask for it later.

This folder is the archive. Everything in it was captured live and cannot be
re-fetched once the season ends.

## What is actually at risk

| Endpoint | What happens at rollover | Recoverable later? |
|---|---|---|
| `event/{gw}/live` | **Wiped.** Per-player, per-gameweek scores and their point-by-point breakdown | **No** |
| `entry/{id}/event/{gw}/picks` | **Wiped.** Every manager's line-up, captain and bench order | **No** |
| `entry/{id}/transfers` | **Wiped.** The full transfer log with prices paid | **No** |
| `entry/{id}/history` | The per-gameweek `current` array is wiped; one summary line survives in `past` | Partly |
| `leagues-classic/{id}/standings` | Resets to empty; no per-gameweek table is kept | **No** |
| `bootstrap-static` | Player totals reset to zero, prices reset, and element ids are reassigned to **different players** | **No** |
| `fixtures` | Replaced wholesale by next season's fixtures | **No** |

The element-id reassignment is the nastiest one. An `element` id that means
Haaland this season can mean somebody else next season. Only the `code` field is
stable across seasons, which is why the squad-building script joins on `code`.

## Layout

```
data/snapshots/
  2026-27/
    index.json                        every capture in the season, newest last
    gw01/
      2026-08-25T0031Z/               one capture, never overwritten
        manifest.json                 what, when, gameweek state, checksums
        bootstrap-static.json.gz
        fixtures.json.gz
        event-01-live.json.gz
        league-14074-standings.json.gz
        entries/46116/entry.json.gz
        entries/46116/history.json.gz
        entries/46116/transfers.json.gz
        entries/46116/picks-gw01.json.gz
    gw03/
      2026-09-08T0900Z/
```

Three rules make this trustworthy:

1. **Captures are immutable.** A capture folder is named for the moment it was
   taken and is never written to again. Taking a second capture in the same
   gameweek adds a folder; it does not replace one.
2. **Every file is checksummed.** `manifest.json` records a SHA-256 of the
   uncompressed bytes. `verify` re-checks all of them.
3. **The gameweek state is recorded.** The manifest stores whether the gameweek
   was `finished` and `data_checked`, and how many matches had been played, so a
   mid-gameweek capture can never be mistaken for a final one.

Files are gzipped at maximum compression with the timestamp zeroed, so
re-capturing unchanged data produces identical bytes rather than a noisy diff.
A full 22-manager capture is about **190 KB**, so a whole season of fortnightly
snapshots costs roughly **4 MB**.

## Commands

Take a capture (defaults to every manager in the league):

```bash
python3.12 scripts/snapshot.py capture --league 14074 --gw 2 --note "after GW2 deadline"
```

See what you hold:

```bash
python3.12 scripts/snapshot.py list
```

Re-check every stored checksum:

```bash
python3.12 scripts/snapshot.py verify
```

Rebuild any past gameweek's report from the archive alone:

```bash
python3.12 scripts/snapshot.py restore --gw 1 --into outputs/league_14074_gw1/raw
python3.12 scripts/league_report.py --league 14074 --entry 46116 --gw 1
```

That last pair is the point of the whole thing. It was tested by deleting the
live cache, rebuilding it from the archive, and confirming the regenerated
`budget.csv` and `template.csv` matched the originals exactly.

## Suggested cadence

Fortnightly is enough for the season-long picture, but two moments are worth
capturing regardless of the calendar:

- **Right after a gameweek is marked `data_checked`.** That is when scores and
  bonus points are final. A capture taken before then is provisional.
- **Right before the final gameweek deadline of the season.** After the season
  ends the wipe happens with no warning, and anything not captured is gone.

Capture the gameweek you are currently in. `event/{gw}/live` and the picks
endpoints are per-gameweek, so a fortnightly cadence archives roughly half the
gameweeks in full detail while `bootstrap-static` and `history` still give you a
continuous record of prices, ownership and running scores.
