"""Track non-Premier-League matches so fixture congestion can be measured.

The FPL API only knows about the 380 league games, so European and cup midweeks
have to be recorded by hand in ``data/midweek/<season>.csv`` (see the README
there). This script joins that file to the league fixtures and the per-gameweek
live data, and answers:

    which clubs came into this gameweek short of rest, and did it show up in
    their players' minutes and points?

Run::

    python3 scripts/midweek.py congestion --gw 4
    python3 scripts/midweek.py add --date 2026-09-17 --comp "Europa League" \
        --stage "League phase MD1" --home Bournemouth --away Genk --pl BOU
    python3 scripts/midweek.py impact --gw 4
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEASON = "2026-27"
MIDWEEK = REPO / "data" / "midweek" / f"{SEASON}.csv"
SNAPSHOTS = REPO / "data" / "snapshots" / SEASON
FIELDS = ["date", "competition", "stage", "home", "away",
          "home_score", "away_score", "pl_clubs", "source", "confirmed"]


def latest_snapshot(gw: int | None = None) -> Path:
    """Newest capture, preferring one for `gw` but falling back to any."""
    pats = [f"gw{gw:02d}/*/manifest.json"] if gw else []
    pats.append("gw*/*/manifest.json")
    for pat in pats:
        caps = sorted(SNAPSHOTS.glob(pat))
        if caps:
            return caps[-1].parent
    raise SystemExit("no snapshots found; run scripts/snapshot.py capture first")


def read_gz(p: Path):
    with gzip.GzipFile(p, "rb") as fh:
        return json.load(fh)


def load_rows() -> list[dict]:
    if not MIDWEEK.exists():
        return []
    with MIDWEEK.open() as fh:
        return [r for r in csv.DictReader(fh) if r.get("date")]


def clubs_of(row: dict) -> list[str]:
    return [c.strip() for c in (row.get("pl_clubs") or "").split(";") if c.strip()]


def kickoff(f: dict) -> datetime | None:
    return (datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00"))
            if f.get("kickoff_time") else None)


def cmd_add(a) -> None:
    new = dict(date=a.date, competition=a.comp, stage=a.stage or "", home=a.home or "",
               away=a.away or "", home_score=a.home_score or "", away_score=a.away_score or "",
               pl_clubs=";".join(a.pl), source=a.source or "manual",
               confirmed=a.confirmed or "fixture-only")
    exists = MIDWEEK.exists()
    MIDWEEK.parent.mkdir(parents=True, exist_ok=True)
    with MIDWEEK.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerow(new)
    print(f"added {new['date']} {new['competition']} — {new['pl_clubs']}")


def congestion(gw: int) -> list[dict]:
    """Rest days and recent match load for every club playing in `gw`."""
    snap = latest_snapshot(gw)
    bs = read_gz(snap / "bootstrap-static.json.gz")
    short = {t["id"]: t["short_name"] for t in bs["teams"]}
    fixtures = read_gz(snap / "fixtures.json.gz")
    mid = load_rows()

    # every match each club has played, league and non-league, as (date, label)
    log: dict[str, list[tuple[datetime, str]]] = {}
    for f in fixtures:
        ko = kickoff(f)
        if not ko:
            continue
        for tid, opp in ((f["team_h"], f["team_a"]), (f["team_a"], f["team_h"])):
            log.setdefault(short[tid], []).append((ko, f"PL GW{f['event']} v {short[opp]}"))
    for r in mid:
        try:
            d = datetime.fromisoformat(r["date"]).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        for c in clubs_of(r):
            log.setdefault(c, []).append((d, f"{r['competition']} {r['stage']}".strip()))

    out = []
    for f in sorted((x for x in fixtures if x["event"] == gw), key=lambda x: x["kickoff_time"] or ""):
        ko = kickoff(f)
        for tid in (f["team_h"], f["team_a"]):
            c = short[tid]
            prior = sorted((d, lab) for d, lab in log.get(c, []) if d < ko)
            last = prior[-1] if prior else None
            # a non-PL match in the 10 days before this kick-off is the congestion event
            recent_cup = [(d, lab) for d, lab in prior
                          if not lab.startswith("PL ") and (ko - d).days <= 10]
            out.append(dict(
                club=c, gw=gw, kickoff=ko,
                rest_days=(ko - last[0]).days if last else None,
                last_match=last[1] if last else "-",
                matches_14d=sum(1 for d, _ in prior if (ko - d).days <= 14),
                midweek=recent_cup[-1][1] if recent_cup else "",
                midweek_gap=(ko - recent_cup[-1][0]).days if recent_cup else None))
    return out


def cmd_congestion(a) -> None:
    rows = congestion(a.gw)
    print(f"=== GW{a.gw} REST AND MATCH LOAD ===")
    print(f"{'club':6}{'kickoff':12}{'rest':>5}{'m/14d':>6}  {'last match before this one':34} {'midweek gap':>11}")
    for r in sorted(rows, key=lambda r: (r["rest_days"] is None, r["rest_days"])):
        gap = f"{r['midweek_gap']}d" if r["midweek_gap"] is not None else ""
        print(f"{r['club']:6}{r['kickoff'].strftime('%a %d %b'):12}"
              f"{str(r['rest_days']) if r['rest_days'] is not None else '-':>5}{r['matches_14d']:>6}  "
              f"{r['last_match'][:34]:34} {gap:>11}")
    holes = [r for r in rows if r["rest_days"] is not None and r["rest_days"] >= 9]
    if holes:
        print("\nLong gaps — check whether a midweek match is missing from the CSV:")
        for r in holes:
            print(f"  {r['club']}: {r['rest_days']} days since {r['last_match']}")


def cmd_impact(a) -> None:
    """Did short rest show up in minutes? Descriptive only — tiny n, no inference."""
    snap = latest_snapshot(a.gw)
    bs = read_gz(snap / "bootstrap-static.json.gz")
    short = {t["id"]: t["short_name"] for t in bs["teams"]}
    el = {e["id"]: e for e in bs["elements"]}
    live = {e["id"]: e["stats"] for e in read_gz(snap / f"event-{a.gw:02d}-live.json.gz")["elements"]}
    rest = {r["club"]: r for r in congestion(a.gw)}

    print(f"=== GW{a.gw}: MINUTES BY CLUB, AGAINST REST ===")
    print(f"{'club':6}{'rest':>5}{'midweek':>9}  {'starters(>=60m)':>15}{'sub/partial':>12}{'pts/played':>11}")
    for c, r in sorted(rest.items(), key=lambda kv: (kv[1]["rest_days"] is None, kv[1]["rest_days"])):
        ids = [i for i, e in el.items() if short[e["team"]] == c]
        played = [i for i in ids if live.get(i, {}).get("minutes", 0) > 0]
        if not played:
            continue
        full = sum(1 for i in played if live[i]["minutes"] >= 60)
        pts = sum(live[i]["total_points"] for i in played)
        print(f"{c:6}{str(r['rest_days']):>5}{('yes' if r['midweek'] else '-'):>9}  "
              f"{full:>15}{len(played)-full:>12}{pts/len(played):>11.2f}")
    print("\nDescriptive only: one gameweek, 20 clubs, no control for opponent or "
          "home/away. Accumulate several gameweeks before reading anything into it.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="record a non-PL match")
    p.add_argument("--date", required=True)
    p.add_argument("--comp", required=True)
    p.add_argument("--stage")
    p.add_argument("--home")
    p.add_argument("--away")
    p.add_argument("--home-score", dest="home_score")
    p.add_argument("--away-score", dest="away_score")
    p.add_argument("--pl", nargs="+", required=True, help="FPL short codes, e.g. MCI ARS")
    p.add_argument("--source")
    p.add_argument("--confirmed")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("congestion", help="rest days and match load for a gameweek")
    p.add_argument("--gw", type=int, required=True)
    p.set_defaults(func=cmd_congestion)

    p = sub.add_parser("impact", help="minutes and points against rest, descriptive")
    p.add_argument("--gw", type=int, required=True)
    p.set_defaults(func=cmd_impact)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
