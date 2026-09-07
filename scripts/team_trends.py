"""Team-level attacking and defensive quality from the archived gameweeks.

Answers one question: which Premier League clubs are actually creating chances
and which are giving them up, separately from whether the ball has gone in yet.

Two definitions matter here:

* A team's **xG** in a gameweek is the sum of its own players' expected goals.
* A team's **xGC** is simply its opponent's xG in that match. Deriving it that
  way keeps the two sides of every fixture consistent, and avoids the trap of
  summing a per-player "expected goals conceded while on the pitch" figure,
  which double counts across eleven players.

Reads the gzipped snapshots under ``data/snapshots``, so it works offline and
still works after FPL has wiped the season.

Run::

    python3.12 scripts/team_trends.py --gws 1 2 3
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import subprocess
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SNAP = REPO / "data" / "snapshots" / "2026-27"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

YOU, TOP, REST = "#2a78d6", "#eb6834", "#d5d3cd"
INK, INK_2, MUTED, SURFACE = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.edgecolor": MUTED, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
})


def svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    out = buf.getvalue()
    return out[out.index("<svg"):]


def load(gws: list[int]) -> pd.DataFrame:
    bs = json.load(gzip.open(sorted(SNAP.glob("gw03/*/bootstrap-static.json.gz"))[-1]))
    name = {t["id"]: t["name"] for t in bs["teams"]}
    short = {t["id"]: t["short_name"] for t in bs["teams"]}
    club = {e["id"]: e["team"] for e in bs["elements"]}
    rows = []
    for gw in gws:
        live = json.load(gzip.open(sorted(SNAP.glob(f"gw{gw:02d}/*/event-{gw:02d}-live.json.gz"))[-1]))
        fx = json.load(gzip.open(sorted(SNAP.glob(f"gw{gw:02d}/*/fixtures.json.gz"))[-1]))
        xg: dict[int, float] = {}
        for x in live["elements"]:
            t = club.get(x["id"])
            if t is not None:
                xg[t] = xg.get(t, 0) + float(x["stats"]["expected_goals"])
        for f in fx:
            if f["event"] != gw:
                continue
            h, a = f["team_h"], f["team_a"]
            for side, opp, gs, gc in [(h, a, f["team_h_score"], f["team_a_score"]),
                                      (a, h, f["team_a_score"], f["team_h_score"])]:
                rows.append(dict(gw=gw, team=name[side], short=short[side], opp=short[opp],
                                 xg=xg.get(side, 0.0), xgc=xg.get(opp, 0.0),
                                 gf=gs or 0, ga=gc or 0))
    return pd.DataFrame(rows)


def summarise(d: pd.DataFrame) -> pd.DataFrame:
    a = d.groupby(["team", "short"]).agg(
        xg=("xg", "sum"), xgc=("xgc", "sum"), gf=("gf", "sum"), ga=("ga", "sum"),
        games=("gw", "size")).reset_index()
    a["xg_pg"] = a.xg / a.games
    a["xgc_pg"] = a.xgc / a.games
    a["xgd"] = a.xg - a.xgc
    a["finishing"] = a.gf - a.xg          # above zero: scoring more than the chances merit
    a["keeping"] = a.xgc - a.ga           # above zero: conceding fewer than the chances merit
    return a


def chart_map(a: pd.DataFrame, mine: set[str]) -> str:
    """Create versus concede, with the league average splitting the quadrants.

    The y axis is inverted so that up the page always means a better defence.
    That makes the top right corner unambiguously the best place to be.
    """
    fig, ax = plt.subplots(figsize=(10.6, 5.8))
    mx, my = a.xg_pg.mean(), a.xgc_pg.mean()
    ax.axvline(mx, color="#e6e4de", lw=1.2, zorder=1)
    ax.axhline(my, color="#e6e4de", lw=1.2, zorder=1)

    # Nudge a label when two clubs sit almost on top of each other.
    pts = a.sort_values(["xg_pg", "xgc_pg"]).reset_index(drop=True)
    placed: list[tuple[float, float]] = []
    for _, r in pts.iterrows():
        c = YOU if r.short in mine else REST
        ax.scatter(r.xg_pg, r.xgc_pg, s=120, color=c, zorder=3)
        dx, dy = 9, -3
        for px, py in placed:
            if abs(px - r.xg_pg) < 0.09 and abs(py - r.xgc_pg) < 0.10:
                dx, dy = -11, -14
                break
        ax.annotate(r.short, (r.xg_pg, r.xgc_pg), textcoords="offset points",
                    xytext=(dx, dy), fontsize=10.5,
                    ha="right" if dx < 0 else "left",
                    color=INK if r.short in mine else INK_2,
                    fontweight="bold" if r.short in mine else "normal")
        placed.append((r.xg_pg, r.xgc_pg))

    ax.invert_yaxis()
    ax.set_xlabel("Expected goals created per game  \u2192  better attack",
                  fontsize=11, color=MUTED, labelpad=9)
    ax.set_ylabel("Expected goals conceded per game  \u2191  better defence",
                  fontsize=11, color=MUTED, labelpad=9)

    # Corner captions positioned from the data, not from the flipped axis limits.
    x_lo, x_hi = a.xg_pg.min(), a.xg_pg.max()
    y_best, y_worst = a.xgc_pg.min(), a.xgc_pg.max()
    ax.annotate("best place to be:\ncreate a lot, concede little", (x_hi, y_best),
                textcoords="offset points", xytext=(6, 30), ha="right", va="top",
                fontsize=10.5, color=INK_2, fontweight="bold", linespacing=1.4)
    ax.annotate("create little, concede a lot", (x_lo, y_worst),
                textcoords="offset points", xytext=(-4, -22), ha="left", va="bottom",
                fontsize=10.5, color=MUTED)

    ax.scatter([], [], s=120, color=YOU, label="clubs you own players from")
    ax.scatter([], [], s=120, color=REST, label="everyone else")
    ax.legend(frameon=False, fontsize=11, loc="upper center",
              bbox_to_anchor=(0.5, -0.13), ncols=2)
    return svg(fig)


def chart_gap(a: pd.DataFrame, col: str, xlabel: str, top_label: str, bottom_label: str) -> str:
    d = a.sort_values(col, ascending=True)
    fig, ax = plt.subplots(figsize=(10.0, 6.4))
    colours = [TOP if v > 0 else YOU for v in d[col]]
    ax.barh(range(len(d)), d[col], color=colours, height=0.68, zorder=3)
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels([f"{r.team}" for _, r in d.iterrows()], fontsize=10.5)
    ax.axvline(0, color=INK, lw=1.1, zorder=4)
    for i, v in enumerate(d[col]):
        ax.text(v + (0.12 if v >= 0 else -0.12), i, f"{v:+.1f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=10.5, color=INK_2)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel(xlabel, fontsize=11, color=MUTED, labelpad=10)
    pad = max(abs(d[col])) * 0.30
    ax.set_xlim(d[col].min() - pad, d[col].max() + pad)
    # Give the two captions a clear row above the bars rather than letting them
    # sit on top of the longest one.
    ax.set_ylim(-0.8, len(d) + 0.9)
    ax.text(pad * 0.25, len(d) + 0.35, top_label, ha="left", va="center",
            fontsize=10.5, color=TOP, fontweight="bold")
    ax.text(-pad * 0.25, len(d) + 0.35, bottom_label, ha="right", va="center",
            fontsize=10.5, color=YOU, fontweight="bold")
    ax.spines["left"].set_visible(False)
    return svg(fig)


CSS = """
@page { size: 297mm 210mm; margin: 0; }
* { box-sizing: border-box; }
body { margin:0; background:#fcfcfb; color:#0b0b0b;
  font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; -webkit-print-color-adjust:exact; }
.page { width:297mm; height:210mm; padding:14mm 16mm 9mm; page-break-after:always;
  display:flex; flex-direction:column; overflow:hidden; }
.eyebrow { font-size:11px; letter-spacing:2px; text-transform:uppercase; color:#898781;
  margin-bottom:4mm; }
h1 { font-size:26px; line-height:1.25; font-weight:700; margin:0 0 5mm;
  letter-spacing:-0.4px; max-width:90%; }
.figure { flex:1; display:flex; align-items:center; justify-content:center; min-height:0; }
.figure svg { max-width:100%; max-height:100%; height:auto; }
.foot { font-size:10.5px; color:#898781; margin-top:3mm; line-height:1.5; }
.notes { font-size:11.5px; color:#22221f; line-height:1.6; margin-top:3mm;
  border-top:1px solid #e6e4de; padding-top:3mm; }
.notes b { color:#0b0b0b; }
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gws", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--out", default="TEAM_XG_TRENDS_GW1_3.pdf")
    args = ap.parse_args()

    d = load(args.gws)
    a = summarise(d)
    mine = set(pd.read_csv(REPO / "outputs/gw4_wildcard/squad_locked.csv")
               .merge(a, left_on="club", right_on="team").short.unique())

    span = f"Gameweeks {args.gws[0]} to {args.gws[-1]}"
    foot = (f"{span}, {len(args.gws)} games per club. Expected goals measure the quality of "
            "chances, not the result. Three games is a small sample, so read this as a "
            "direction of travel rather than a settled ranking.")

    best = a.nlargest(1, "xgd").iloc[0]
    second = a.nlargest(2, "xgd").iloc[1]
    tightest = a.nsmallest(1, "xgc_pg").iloc[0]
    luckiest = a.nlargest(1, "finishing").iloc[0]
    unluckiest = a.nsmallest(1, "finishing").iloc[0]
    keeper = a.nlargest(1, "keeping").iloc[0]

    pages = [
        (f"{best.team} and {second.team} create the most and concede the least",
         chart_map(a, mine),
         foot + f" {tightest.team} have the meanest defence at {tightest.xgc_pg:.2f} expected "
                "goals conceded per game."),
        (f"{luckiest.team} are scoring {luckiest.finishing:.1f} goals more than their chances deserve",
         chart_gap(a, "finishing", "Goals scored minus expected goals, across the three games",
                   "scoring more than the chances merit", "scoring fewer than the chances merit"),
         foot + f" {unluckiest.team} sit at the other end on {unluckiest.finishing:+.1f}, "
                "which usually corrects."),
        (f"{keeper.team} have conceded {keeper.keeping:.1f} fewer goals than their chances allowed",
         chart_gap(a, "keeping", "Expected goals conceded minus goals actually conceded",
                   "conceding fewer than the chances merit", "conceding more than the chances merit"),
         foot),
    ]

    body = []
    for i, (title, fig, note) in enumerate(pages, 1):
        extra = ""
        if i == len(pages):
            extra = (f'<div class="notes"><b>How to read these.</b> Expected goals count the '
                     f'quality of chances a team creates and allows. Over a season they predict '
                     f'goals better than goals themselves do, because finishing swings around a '
                     f'lot. The two gap charts show where results have run ahead of or behind the '
                     f'underlying play, and those gaps usually shrink. '
                     f'<b>The caveat:</b> {len(args.gws)} games is a very small sample. Fixtures '
                     f'have not evened out, so a club that has played three strong opponents will '
                     f'look worse than it is. Treat this as a prompt to look closer, not a verdict.'
                     f'</div>')
        body.append(f'<div class="page"><div class="eyebrow">{span} &middot; team quality</div>'
                    f'<h1>{title}</h1><div class="figure">{fig}</div>'
                    f'<div class="foot">{note}</div>{extra}</div>')

    out_dir = REPO / "outputs" / "team_trends"
    out_dir.mkdir(parents=True, exist_ok=True)
    d.to_csv(out_dir / "team_gameweek.csv", index=False)
    a.to_csv(out_dir / "team_summary.csv", index=False)
    html = out_dir / "team_trends.html"
    html.write_text(f"<style>{CSS}</style>" + "".join(body))
    pdf = REPO / args.out
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", f"file://{html}"],
                   check=True, capture_output=True, timeout=180)
    print(f"wrote {pdf.name} ({pdf.stat().st_size/1024:.0f} KB)")
    print(a.sort_values("xgd", ascending=False)[
        ["short", "xg_pg", "xgc_pg", "xgd", "finishing", "keeping"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
