"""Find managers with a stronger long-run record than a benchmark set.

The question this answers: whose squad is worth studying? Current rank is a
poor guide three gameweeks into a season, because it is mostly luck. A median
finish across several seasons is much harder to fake.

Rather than trying to identify content creators from third-party lists, which
depends on someone else's data being current and correctly attributed, this
walks the game's own Overall league, pulls each manager's season history from
the official API, and keeps those whose median finish beats a threshold you
set. Every result is verifiable from the API alone.

Run::

    python3.12 scripts/find_elite_managers.py --pages 4 --median-better-than 151489
"""

from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.request
from pathlib import Path
from statistics import median

import pandas as pd

API = "https://fantasy.premierleague.com/api"
REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / "outputs" / "elite_managers" / "raw"
DELAY = 0.2


def _ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def get(url: str, cache: Path) -> dict | None:
    if cache.exists() and cache.stat().st_size > 0:
        return json.loads(cache.read_text())
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fpl-research/1.0"})
        with urllib.request.urlopen(req, timeout=45, context=_ctx()) as r:
            payload = json.load(r)
    except Exception:
        return None
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload))
    time.sleep(DELAY)
    return payload


def overall_top(pages: int) -> list[dict]:
    """The game's own Overall league, which ranks every entry by total points."""
    out = []
    for page in range(1, pages + 1):
        d = get(f"{API}/leagues-classic/314/standings/?page_standings={page}",
                CACHE / f"overall_p{page}.json")
        if not d:
            break
        out.extend(d["standings"]["results"])
    return out


def profile(entry: int, seasons: int) -> dict | None:
    h = get(f"{API}/entry/{entry}/history/", CACHE / "history" / f"{entry}.json")
    if not h:
        return None
    past = h.get("past", [])[-seasons:]
    ranks = [p["rank"] for p in past if p.get("rank")]
    if len(ranks) < 3:
        return None  # too little history to call anyone consistent
    chips = h.get("chips", [])
    return {
        "entry": entry,
        "seasons": len(ranks),
        "median_rank": int(median(ranks)),
        "best_rank": min(ranks),
        "worst_rank": max(ranks),
        "history": "; ".join(f"{p['season_name'][2:]}:{p['rank'] // 1000}k" for p in past),
        "chips_played": ", ".join(f"{c['name']}(GW{c['event']})" for c in chips) or "none",
        "wildcard_gw": next((c["event"] for c in chips if c["name"] == "wildcard"), None),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pages", type=int, default=4, help="pages of 50 from the Overall league")
    ap.add_argument("--median-better-than", type=int, required=True,
                    help="keep managers whose median finish is below this")
    ap.add_argument("--seasons", type=int, default=5)
    ap.add_argument("--require-wildcard", action="store_true")
    args = ap.parse_args()

    top = overall_top(args.pages)
    print(f"pulled {len(top)} entries from the Overall league")

    rows = []
    for i, r in enumerate(top, 1):
        p = profile(r["entry"], args.seasons)
        if not p:
            continue
        p.update(manager=r["player_name"], team_name=r["entry_name"],
                 current_rank=r["rank"], current_points=r["total"])
        rows.append(p)
        if i % 50 == 0:
            print(f"  checked {i}/{len(top)}")

    df = pd.DataFrame(rows)
    print(f"with at least 3 past seasons: {len(df)}")
    keep = df[df.median_rank < args.median_better_than]
    if args.require_wildcard:
        keep = keep[keep.wildcard_gw.notna()]
    keep = keep.sort_values("median_rank")

    out = REPO / "outputs" / "elite_managers"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "candidates.csv", index=False)
    keep.to_csv(out / "qualified.csv", index=False)
    print(f"\nqualified (median better than {args.median_better_than:,}"
          f"{', wildcard played' if args.require_wildcard else ''}): {len(keep)}")
    cols = ["entry", "manager", "team_name", "seasons", "median_rank", "best_rank",
            "history", "wildcard_gw", "current_points"]
    print(keep.head(20)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
