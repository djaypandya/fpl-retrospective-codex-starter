"""Archive raw Fantasy Premier League API responses before the season erases them.

Most FPL endpoints are destroyed or rewritten when the season rolls over. Once
that happens the data is gone: there is no archive endpoint and no way to ask
for last season's picks. This script captures the endpoints that matter into
immutable, timestamped, gzipped folders you can come back to years later.

What is at risk, and why each endpoint is captured:

===========================  ====================================================
endpoint                     what happens at season rollover
===========================  ====================================================
bootstrap-static             player totals reset to zero, prices reset, and
                             element ids are reassigned to different players
fixtures                     replaced wholesale by the new season's fixtures
event/{gw}/live              WIPED. Per-player, per-gameweek scores and their
                             point-by-point breakdown are gone for good
entry/{id}/event/{gw}/picks  WIPED. You cannot recover any manager's line-up
entry/{id}/history           the per-gameweek `current` array is wiped; only a
                             one-line summary survives in `past`
entry/{id}/transfers         WIPED. The full transfer log disappears
leagues-classic/{id}         standings reset; no per-gameweek history is kept
===========================  ====================================================

Layout (immutable: a capture is never overwritten, only added to)::

    data/snapshots/2026-27/gw01/2026-08-25T1030Z/
        manifest.json                  what was captured, when, and checksums
        bootstrap-static.json.gz
        fixtures.json.gz
        event-01-live.json.gz
        league-14074-standings.json.gz
        entries/46116/picks-gw01.json.gz
        entries/46116/history.json.gz
        entries/46116/transfers.json.gz

Usage::

    python3.12 scripts/snapshot.py capture --league 14074 --gw 1
    python3.12 scripts/snapshot.py list
    python3.12 scripts/snapshot.py verify
    python3.12 scripts/snapshot.py restore --gw 1 --into outputs/league_14074_gw1/raw

`restore` rebuilds the cache layout that ``league_report.py`` reads, so any past
gameweek's report can be regenerated exactly, long after the API has moved on.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://fantasy.premierleague.com/api"
REPO = Path(__file__).resolve().parents[1]
SNAPSHOTS = REPO / "data" / "snapshots"
POLITE_DELAY = 0.25  # seconds between requests, to stay a good citizen


def _ssl_context() -> ssl.SSLContext:
    """Python.org builds ship without linked root certificates, so use certifi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch(path: str) -> bytes:
    req = urllib.request.Request(f"{API}/{path}", headers={"User-Agent": "fpl-archive/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as r:
        return r.read()


def season_for(gw_deadline: str) -> str:
    """FPL seasons span two calendar years; a July+ deadline starts the new one."""
    d = datetime.fromisoformat(gw_deadline.replace("Z", "+00:00"))
    start = d.year if d.month >= 7 else d.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def write_gz(dest: Path, payload: bytes) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the gzip byte-identical for identical input, so a re-capture
    # of unchanged data does not show up as a spurious diff.
    with gzip.GzipFile(dest, "wb", compresslevel=9, mtime=0) as fh:
        fh.write(payload)
    return {"bytes_raw": len(payload), "bytes_stored": dest.stat().st_size,
            "sha256": hashlib.sha256(payload).hexdigest()}


def read_gz(src: Path) -> bytes:
    with gzip.GzipFile(src, "rb") as fh:
        return fh.read()


def capture(league: int, gw: int, entries: list[int] | None, note: str) -> Path:
    bootstrap_raw = fetch("bootstrap-static/")
    bootstrap = json.loads(bootstrap_raw)
    event = next(e for e in bootstrap["events"] if e["id"] == gw)
    season = season_for(event["deadline_time"])

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    out = SNAPSHOTS / season / f"gw{gw:02d}" / stamp
    files: dict[str, dict] = {}

    def grab(name: str, path: str) -> bytes | None:
        try:
            payload = fetch(path)
        except Exception as exc:  # a missing manager or league should not abort
            files[name] = {"url": path, "error": str(exc)}
            return None
        files[name] = {"url": path, **write_gz(out / name, payload)}
        time.sleep(POLITE_DELAY)
        return payload

    files["bootstrap-static.json.gz"] = {
        "url": "bootstrap-static/", **write_gz(out / "bootstrap-static.json.gz", bootstrap_raw)}
    grab("fixtures.json.gz", "fixtures/")
    grab(f"event-{gw:02d}-live.json.gz", f"event/{gw}/live/")

    if entries is None:
        standings_raw = grab(f"league-{league}-standings.json.gz",
                             f"leagues-classic/{league}/standings/")
        entries = ([r["entry"] for r in json.loads(standings_raw)["standings"]["results"]]
                   if standings_raw else [])
    else:
        grab(f"league-{league}-standings.json.gz", f"leagues-classic/{league}/standings/")

    for eid in entries:
        grab(f"entries/{eid}/entry.json.gz", f"entry/{eid}/")
        grab(f"entries/{eid}/history.json.gz", f"entry/{eid}/history/")
        grab(f"entries/{eid}/transfers.json.gz", f"entry/{eid}/transfers/")
        grab(f"entries/{eid}/picks-gw{gw:02d}.json.gz", f"entry/{eid}/event/{gw}/picks/")

    fixtures = json.loads(read_gz(out / "fixtures.json.gz"))
    gw_fixtures = [f for f in fixtures if f["event"] == gw]
    manifest = {
        "season": season,
        "gameweek": gw,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note,
        "league": league,
        "entries": entries,
        "gameweek_state": {
            "deadline_time": event["deadline_time"],
            "finished": event["finished"],
            "data_checked": event["data_checked"],
            "average_entry_score": event["average_entry_score"],
            "highest_score": event["highest_score"],
        },
        "matches": {
            "total": len(gw_fixtures),
            "started": sum(f["started"] for f in gw_fixtures),
            "finished": sum(f["finished"] for f in gw_fixtures),
        },
        "files": files,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    reindex(season)
    return out


def reindex(season: str) -> Path:
    """Rebuild the season index so captures are findable without walking folders."""
    root = SNAPSHOTS / season
    rows = []
    for man in sorted(root.glob("gw*/*/manifest.json")):
        m = json.loads(man.read_text())
        stored = sum(f.get("bytes_stored", 0) for f in m["files"].values())
        rows.append({
            "gameweek": m["gameweek"],
            "captured_at": m["captured_at"],
            "path": str(man.parent.relative_to(SNAPSHOTS)),
            "matches": f"{m['matches']['finished']}/{m['matches']['total']} finished",
            "finished": m["gameweek_state"]["finished"],
            "data_checked": m["gameweek_state"]["data_checked"],
            "entries": len(m["entries"]),
            "files": len(m["files"]),
            "bytes_stored": stored,
            "note": m.get("note", ""),
        })
    rows.sort(key=lambda r: (r["gameweek"], r["captured_at"]))
    index = root / "index.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"season": season, "captures": rows}, indent=2))
    return index


def cmd_list(season: str | None) -> None:
    seasons = [season] if season else sorted(p.name for p in SNAPSHOTS.glob("*") if p.is_dir())
    if not seasons:
        print("no snapshots yet")
        return
    for s in seasons:
        idx = SNAPSHOTS / s / "index.json"
        if not idx.exists():
            reindex(s)
        data = json.loads(idx.read_text())
        total = sum(c["bytes_stored"] for c in data["captures"])
        print(f"\n{s}  —  {len(data['captures'])} captures, {total/1024:.0f} KB stored")
        print(f"  {'GW':>3}  {'captured':<20} {'matches':<14} {'checked':<8} {'KB':>6}  note")
        for c in data["captures"]:
            print(f"  {c['gameweek']:>3}  {c['captured_at'][:19]:<20} {c['matches']:<14} "
                  f"{str(c['data_checked']):<8} {c['bytes_stored']/1024:>6.0f}  {c['note']}")


def cmd_verify(season: str | None) -> int:
    seasons = [season] if season else sorted(p.name for p in SNAPSHOTS.glob("*") if p.is_dir())
    bad = 0
    for s in seasons:
        for man in sorted((SNAPSHOTS / s).glob("gw*/*/manifest.json")):
            m = json.loads(man.read_text())
            for name, meta in m["files"].items():
                if "sha256" not in meta:
                    continue
                path = man.parent / name
                if not path.exists():
                    print(f"MISSING  {path}"); bad += 1; continue
                if hashlib.sha256(read_gz(path)).hexdigest() != meta["sha256"]:
                    print(f"CORRUPT  {path}"); bad += 1
    print("all files verified" if not bad else f"{bad} problem(s) found")
    return bad


def cmd_restore(season: str, gw: int, into: Path, at: str | None) -> None:
    """Materialise a capture into the cache layout league_report.py reads."""
    caps = sorted((SNAPSHOTS / season / f"gw{gw:02d}").glob("*/manifest.json"))
    if not caps:
        raise SystemExit(f"no capture for {season} gw{gw}")
    man = next((c for c in caps if at and at in c.parent.name), caps[-1])
    m = json.loads(man.read_text())
    src = man.parent
    into.mkdir(parents=True, exist_ok=True)
    (into / "picks").mkdir(exist_ok=True)
    (into / "history").mkdir(exist_ok=True)

    (into / "bootstrap.json").write_bytes(read_gz(src / "bootstrap-static.json.gz"))
    fixtures = json.loads(read_gz(src / "fixtures.json.gz"))
    (into / f"fixtures_gw{gw}.json").write_text(
        json.dumps([f for f in fixtures if f["event"] == gw]))
    league = m["league"]
    league_file = src / f"league-{league}-standings.json.gz"
    if league_file.exists():
        (into / f"standings_{league}.json").write_bytes(read_gz(league_file))
    for eid in m["entries"]:
        for stem, dest in [(f"picks-gw{gw:02d}", into / "picks" / f"{eid}.json"),
                           ("history", into / "history" / f"{eid}.json")]:
            f = src / "entries" / str(eid) / f"{stem}.json.gz"
            if f.exists():
                dest.write_bytes(read_gz(f))
    print(f"restored {m['captured_at']} ({m['matches']['finished']}/{m['matches']['total']} "
          f"matches finished) -> {into}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture", help="archive the endpoints for one gameweek")
    c.add_argument("--league", type=int, required=True)
    c.add_argument("--gw", type=int, required=True)
    c.add_argument("--entries", type=int, nargs="*", default=None,
                   help="manager ids; defaults to every member of the league")
    c.add_argument("--note", default="", help="why this capture was taken")

    l = sub.add_parser("list", help="show every capture held")
    l.add_argument("--season", default=None)

    v = sub.add_parser("verify", help="re-check every stored checksum")
    v.add_argument("--season", default=None)

    r = sub.add_parser("restore", help="rebuild a gameweek's cache from the archive")
    r.add_argument("--season", default=None)
    r.add_argument("--gw", type=int, required=True)
    r.add_argument("--into", type=Path, required=True)
    r.add_argument("--at", default=None, help="pick a capture by timestamp fragment")

    args = ap.parse_args()
    if args.cmd == "capture":
        out = capture(args.league, args.gw, args.entries, args.note)
        m = json.loads((out / "manifest.json").read_text())
        stored = sum(f.get("bytes_stored", 0) for f in m["files"].values())
        errors = [k for k, v in m["files"].items() if "error" in v]
        print(f"captured {m['season']} GW{m['gameweek']} -> {out.relative_to(REPO)}")
        print(f"  {len(m['files'])} endpoints, {stored/1024:.0f} KB stored, "
              f"{m['matches']['finished']}/{m['matches']['total']} matches finished, "
              f"data_checked={m['gameweek_state']['data_checked']}")
        if errors:
            print(f"  {len(errors)} endpoint(s) failed: {errors[:5]}")
    elif args.cmd == "list":
        cmd_list(args.season)
    elif args.cmd == "verify":
        raise SystemExit(1 if cmd_verify(args.season) else 0)
    elif args.cmd == "restore":
        season = args.season or sorted(p.name for p in SNAPSHOTS.glob("*") if p.is_dir())[-1]
        cmd_restore(season, args.gw, args.into, args.at)


if __name__ == "__main__":
    main()
