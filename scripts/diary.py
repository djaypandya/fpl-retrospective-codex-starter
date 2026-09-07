"""Weekly reflection log — a decision journal for the season.

A diary records what happened. A decision journal records *why you decided what
you decided*, before you know the outcome, so you can grade the reasoning later
rather than only the result. Those are different things: a good call can lose and
a bad call can win. Separating them is the whole point.

Each entry is a plain .txt file under ``diary/<season>/gw<NN>.txt``. The script
pre-fills the facts it can read from the archived data — your score, rank,
captain, who delivered, what your bench did, which chips you still hold, and next
week's fixtures — so the only thing left to write is the thinking.

Run::

    python3.12 scripts/diary.py new --gw 2          # scaffold next week's entry
    python3.12 scripts/diary.py list                # show the season so far

An existing entry is never overwritten.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DIARY = REPO / "diary"
SEASON = "2026-27"
ENTRY = 46116

ALL_CHIPS = ["Wildcard", "Bench Boost", "Triple Captain", "Free Hit"]


def load_gw(gw: int, league: int) -> dict | None:
    """Pull the facts for a completed gameweek, if the report has been run."""
    src = REPO / "outputs" / f"league_{league}_gw{gw}"
    if not (src / "picks_long.csv").exists():
        return None
    df = pd.read_csv(src / "picks_long.csv")
    b = pd.read_csv(src / "budget.csv")
    mine = df[df.entry == ENTRY].copy()
    mine["counted"] = mine.multiplier * mine.gw_points
    me = b[b.entry == ENTRY].iloc[0]
    bench = mine[mine.multiplier == 0]
    return {
        "points": int(me.live_pts),
        "rank": int(me["rank"]),
        "managers": len(b),
        "league_avg": round(b.live_pts.mean(), 1),
        "captain": mine[mine.is_captain].iloc[0],
        "best": mine[mine.multiplier > 0].nlargest(3, "gw_points"),
        "worst": mine[mine.multiplier > 0].nsmallest(3, "gw_points"),
        "bench_points": int(bench.gw_points.sum()),
        "chip": me.chip if isinstance(me.chip, str) else None,
        "leader": b.nsmallest(1, "rank").iloc[0],
    }


def next_fixtures(gw: int, league: int) -> list[str]:
    """Who your current squad plays next, so the plan can be concrete."""
    src = REPO / "outputs" / f"league_{league}_gw{gw - 1}"
    raw = src / "raw" / "bootstrap.json"
    if not raw.exists():
        return []
    bs = json.loads(raw.read_text())
    short = {t["id"]: t["short_name"] for t in bs["teams"]}
    fx_path = REPO / "data" / "raw"
    fixtures = None
    for cand in sorted(fx_path.glob("fixtures_2026_27_*.json"), reverse=True):
        fixtures = json.loads(cand.read_text())
        break
    if not fixtures:
        return []
    df = pd.read_csv(src / "picks_long.csv")
    clubs = set(df[(df.entry == ENTRY) & (df.multiplier > 0)].team_id)
    out = []
    for f in fixtures:
        if f["event"] != gw:
            continue
        for side, opp, home in [(f["team_h"], f["team_a"], True), (f["team_a"], f["team_h"], False)]:
            if side in clubs:
                out.append(f"{short[side]} {'v' if home else 'at'} {short[opp]} "
                           f"(difficulty {f['team_h_difficulty'] if home else f['team_a_difficulty']})")
    return sorted(set(out))


def scaffold(gw: int, league: int) -> str:
    prev = load_gw(gw - 1, league)
    lines = [
        "=" * 72,
        f"SEASON {SEASON}   GAMEWEEK {gw}   written {date.today().isoformat()}",
        "=" * 72,
        "",
    ]

    if prev:
        cap = prev["captain"]
        lines += [
            f"-- WHAT HAPPENED IN GW{gw - 1} (filled in automatically) " + "-" * 12,
            "",
            f"  Score            {prev['points']} points",
            f"  League position  {prev['rank']} of {prev['managers']}   "
            f"(league average {prev['league_avg']})",
            f"  Leader           {prev['leader'].manager} on {int(prev['leader'].live_pts)}",
            f"  Captain          {cap['name']} scored {int(cap.gw_points)}, "
            f"counted {int(cap.gw_points * cap.multiplier)}",
            f"  Chip played      {prev['chip'] or 'none'}",
            f"  Bench left       {prev['bench_points']} points unused",
            "",
            "  Best three       " + ", ".join(
                f"{r['name']} {int(r.gw_points)}" for _, r in prev["best"].iterrows()),
            "  Worst three      " + ", ".join(
                f"{r['name']} {int(r.gw_points)}" for _, r in prev["worst"].iterrows()),
            "",
        ]

    fixtures = next_fixtures(gw, league)
    if fixtures:
        lines += [f"-- YOUR CLUBS IN GW{gw} " + "-" * 34, ""]
        lines += [f"  {f}" for f in fixtures]
        lines += [""]

    lines += [
        f"-- LOOKING BACK AT GW{gw - 1} " + "-" * 30,
        "",
        "  What I got right, and was it for the right reason?",
        "    ",
        "",
        "  What I got wrong, and was it the decision or just the outcome?",
        "    ",
        "",
        "  Calls I made and the reasoning behind each one:",
        "    ",
        "",
        f"-- PLAN FOR GW{gw} " + "-" * 40,
        "",
        "  Transfers (and why, or why not):",
        "    ",
        "",
        "  Captain:",
        "    ",
        "",
        "  Chips (still holding: " + ", ".join(ALL_CHIPS) + "):",
        "    ",
        "",
        "  What I am deliberately NOT doing, and why:",
        "    ",
        "",
        "-- PREDICTIONS TO GRADE NEXT WEEK " + "-" * 25,
        "",
        "  Write these as things that can turn out false. Next week's entry",
        "  checks them, which is how you find out if your reasoning is any good",
        "  rather than just whether the week went well.",
        "",
        "    1. ",
        "    2. ",
        "    3. ",
        "",
        "=" * 72,
    ]
    return "\n".join(lines) + "\n"


def cmd_new(gw: int, league: int) -> None:
    out = DIARY / SEASON / f"gw{gw:02d}.txt"
    if out.exists():
        raise SystemExit(f"{out.relative_to(REPO)} already exists — edit it, or delete it first")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(scaffold(gw, league))
    print(f"created {out.relative_to(REPO)}")
    print("  the facts are filled in; write the thinking into the blank lines")


def cmd_list() -> None:
    entries = sorted((DIARY / SEASON).glob("gw*.txt")) if (DIARY / SEASON).exists() else []
    if not entries:
        print("no diary entries yet")
        return
    print(f"{SEASON} season diary — {len(entries)} entries\n")
    for e in entries:
        text = e.read_text()
        written = next((l.split("written")[-1].strip() for l in text.splitlines()
                        if "written" in l), "?")
        # A section counts as filled once it has prose under its prompt.
        filled = sum(1 for l in text.splitlines()
                     if l.startswith("    ") and l.strip() and not l.strip()[0].isdigit())
        print(f"  {e.name:<12} written {written:<12} {len(text.splitlines()):>4} lines, "
              f"{filled} written lines")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="scaffold an entry for an upcoming gameweek")
    n.add_argument("--gw", type=int, required=True)
    n.add_argument("--league", type=int, default=14074)
    sub.add_parser("list", help="show the season's entries")
    args = ap.parse_args()
    if args.cmd == "new":
        cmd_new(args.gw, args.league)
    else:
        cmd_list()
if __name__ == "__main__":
    main()
