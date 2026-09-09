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


DEFCON_THRESHOLD = {"DEF": 10, "MID": 12, "FWD": 12}   # goalkeepers cannot earn it
POSNAME = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def load_defcon(gws: list[int]) -> pd.DataFrame:
    """One row per player per gameweek, with whether he cleared his threshold.

    Defensive actions and DEFCON points are different things. A club can rack
    up actions across eleven players and have nobody reach a threshold, which
    earns nothing. Both are returned so the gap can be shown.
    """
    bs = json.load(gzip.open(sorted(SNAP.glob("gw03/*/bootstrap-static.json.gz"))[-1]))
    meta = {e["id"]: (e["team"], e["element_type"], e["web_name"]) for e in bs["elements"]}
    name = {t["id"]: t["name"] for t in bs["teams"]}
    short = {t["id"]: t["short_name"] for t in bs["teams"]}
    rows = []
    for gw in gws:
        live = json.load(gzip.open(sorted(SNAP.glob(f"gw{gw:02d}/*/event-{gw:02d}-live.json.gz"))[-1]))
        for x in live["elements"]:
            m = meta.get(x["id"])
            if not m:
                continue
            team, et, who = m
            pos = POSNAME[et]
            st = x["stats"]
            dc = st.get("defensive_contribution", 0)
            rows.append(dict(gw=gw, player=who, team=name[team], short=short[team], pos=pos,
                             mins=st["minutes"], dc=dc,
                             hit=int(dc >= DEFCON_THRESHOLD.get(pos, 10 ** 9))))
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


def chart_defcon_teams(t: pd.DataFrame, mine: set[str]) -> str:
    """Ranked by the measure that actually pays, with raw actions alongside."""
    d = t.sort_values("hits", ascending=True)
    fig, ax = plt.subplots(figsize=(10.0, 6.3))
    colours = [YOU if r.short in mine else REST for _, r in d.iterrows()]
    ax.barh(range(len(d)), d.hits, color=colours, height=0.68, zorder=3)
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels(d.team, fontsize=10.5)
    for tick, sc in zip(ax.get_yticklabels(), d.short):
        if sc in mine:
            tick.set_color(INK); tick.set_fontweight("bold")
    for i, (_, r) in enumerate(d.iterrows()):
        ax.text(r.hits + 0.15, i, f"{int(r.hits)}", va="center", fontsize=10.5, color=INK)
        ax.text(r.hits + 0.85, i, f"from {int(r.actions)} defensive actions",
                va="center", fontsize=9.5, color=MUTED)
    ax.set_xticks([]); ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, d.hits.max() * 2.6)
    ax.set_xlabel("Times a player cleared his DEFCON threshold, Gameweeks 1 to 3",
                  fontsize=11, color=MUTED, labelpad=10)
    ax.spines["left"].set_visible(False)
    return svg(fig)


def chart_defcon_positions(t: pd.DataFrame, mine_players: pd.DataFrame) -> str:
    """Where each club's DEFCON points come from, with your own earners named."""
    d = t.sort_values("hits", ascending=True)
    fig, ax = plt.subplots(figsize=(10.6, 6.3))
    y = range(len(d))
    ax.barh(list(y), d.def_hits, color=YOU, height=0.66, zorder=3, label="from defenders")
    ax.barh(list(y), d.mid_hits, left=[v + 0.06 for v in d.def_hits], color=TOP,
            height=0.66, zorder=3, label="from midfielders")
    ax.set_yticks(list(y)); ax.set_yticklabels(d.team, fontsize=10.5)
    owned = set(mine_players.team)
    for tick, name in zip(ax.get_yticklabels(), d.team):
        if name in owned:
            tick.set_color(INK); tick.set_fontweight("bold")
    for i, (_, r) in enumerate(d.iterrows()):
        yours = mine_players[(mine_players.team == r.team) & (mine_players.hits > 0)]
        if len(yours):
            label = ", ".join(f"{x.player} {int(x.hits)}" for _, x in yours.iterrows())
            ax.text(r.hits + 0.3, i, f"you own {label}", va="center", fontsize=9.5,
                    color=INK, fontweight="bold")
        elif r.team in owned:
            ax.text(r.hits + 0.3, i, "you own nobody earning it here", va="center",
                    fontsize=9.5, color=MUTED)
    ax.set_xticks([]); ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, d.hits.max() * 3.0)
    ax.set_xlabel("DEFCON threshold hits, split by position", fontsize=11, color=MUTED, labelpad=10)
    ax.set_ylim(-0.8, len(d) + 1.4)
    ax.legend(frameon=False, fontsize=11, loc="upper right", ncols=2,
              bbox_to_anchor=(1.0, 1.06))
    ax.spines["left"].set_visible(False)
    return svg(fig)


def chart_xgc_vs_defcon(a: pd.DataFrame, t: pd.DataFrame, mine: set[str]):
    """Does defending more mean defending badly? Returns the svg and the correlation."""
    m = a.merge(t[["short", "hits", "actions"]], on="short")
    m["hits_pg"] = m.hits / m.games
    r = m.xgc_pg.corr(m.hits_pg)
    fig, ax = plt.subplots(figsize=(10.6, 5.8))
    mx, my = m.xgc_pg.mean(), m.hits_pg.mean()
    ax.axvline(mx, color="#e6e4de", lw=1.2, zorder=1)
    ax.axhline(my, color="#e6e4de", lw=1.2, zorder=1)
    # Give every label a free slot: try offsets in turn and take the first that
    # does not land on a label already drawn. A single fixed nudge sends two
    # colliding labels to the same place, which is how BOU and HUL ended up
    # printed on top of each other.
    xr = m.xgc_pg.max() - m.xgc_pg.min()
    yr = m.hits_pg.max() - m.hits_pg.min()
    xu, yu = xr / 640, yr / 330          # roughly one point, in data units
    candidates = [(9, -3), (-11, -3), (9, 14), (-11, 14), (9, -20), (-11, -20)]
    placed: list[tuple[float, float]] = []
    for _, row in m.sort_values(["xgc_pg", "hits_pg"]).iterrows():
        c = YOU if row.short in mine else REST
        ax.scatter(row.xgc_pg, row.hits_pg, s=120, color=c, zorder=3)
        dx, dy = candidates[0]
        for cx, cy in candidates:
            lx, ly = row.xgc_pg + cx * xu, row.hits_pg + cy * yu
            if all(abs(px - lx) > xr * 0.045 or abs(py - ly) > yr * 0.030
                   for px, py in placed):
                dx, dy = cx, cy
                break
        ax.annotate(row.short, (row.xgc_pg, row.hits_pg), textcoords="offset points",
                    xytext=(dx, dy), fontsize=10.5, ha="right" if dx < 0 else "left",
                    color=INK if row.short in mine else INK_2,
                    fontweight="bold" if row.short in mine else "normal")
        placed.append((row.xgc_pg + dx * xu, row.hits_pg + dy * yu))
    ax.set_xlabel("Expected goals conceded per game  \u2192  worse defence",
                  fontsize=11, color=MUTED, labelpad=9)
    ax.set_ylabel("DEFCON hits per game  \u2191  more defensive points",
                  fontsize=11, color=MUTED, labelpad=9)
    ax.annotate("the corner you want:\nsolid defence, plenty of DEFCON",
                (m.xgc_pg.min(), m.hits_pg.max()), textcoords="offset points",
                xytext=(-6, 26), ha="left", va="top", fontsize=10.5,
                color=INK_2, fontweight="bold", linespacing=1.4)
    ax.scatter([], [], s=120, color=YOU, label="clubs you own players from")
    ax.scatter([], [], s=120, color=REST, label="everyone else")
    ax.legend(frameon=False, fontsize=11, loc="upper center",
              bbox_to_anchor=(0.5, -0.13), ncols=2)
    return svg(fig), r, m


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

    # --- DEFCON -----------------------------------------------------------
    dc = load_defcon(args.gws)
    played = dc[dc.mins > 0]
    t = played.groupby(["team", "short"], as_index=False).agg(
        actions=("dc", "sum"), hits=("hit", "sum"))
    bypos = played.pivot_table(index="team", columns="pos", values="hit",
                               aggfunc="sum").fillna(0).reset_index()
    for c in ("DEF", "MID"):
        if c not in bypos:
            bypos[c] = 0
    t = t.merge(bypos[["team", "DEF", "MID"]], on="team").rename(
        columns={"DEF": "def_hits", "MID": "mid_hits"})

    squad = pd.read_csv(REPO / "outputs/gw4_wildcard/squad_locked.csv")
    owned = set(zip(squad.player, squad.club))
    mine_players = played.groupby(["player", "team", "pos"], as_index=False).agg(
        mins=("mins", "sum"), dc=("dc", "sum"), hits=("hit", "sum"))
    mine_players = mine_players[[(r.player, r.team) in owned for _, r in mine_players.iterrows()]]
    mine_players["dc90"] = (mine_players.dc / mine_players.mins * 90).round(2)

    top_dc = t.nlargest(1, "hits").iloc[0]
    most_actions = t.nlargest(1, "actions").iloc[0]
    fwd_hits = int(played[played.pos == "FWD"].hit.sum())
    def_hits = int(played[played.pos == "DEF"].hit.sum())
    mid_hits = int(played[played.pos == "MID"].hit.sum())
    my_earners = mine_players[mine_players.hits > 0].sort_values("hits", ascending=False)
    scatter_dc, corr, merged = chart_xgc_vs_defcon(a, t, mine)
    tidy = merged.nsmallest(3, "xgc_pg").nlargest(1, "hits_pg").iloc[0]

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
        (f"{top_dc.team} turn defending into points more often than anyone",
         chart_defcon_teams(t, mine),
         f"{span}. A player earns 2 DEFCON points when he clears his threshold in a match: "
         f"10 defensive actions for a defender, 12 for a midfielder or forward. "
         f"{most_actions.team} make the most defensive actions at {int(most_actions.actions)}, "
         f"but that is not the same as earning points for them."),
        (f"Defenders earn DEFCON {def_hits / max(mid_hits, 1):.1f} times as often as midfielders, "
         f"and forwards never do",
         chart_defcon_positions(t, mine_players),
         f"{span}. Across the whole league defenders cleared their threshold {def_hits} times, "
         f"midfielders {mid_hits} times and forwards {fwd_hits}. Your own players are named "
         f"beside their club."),
        (("Defending more does not mean defending badly" if abs(corr) < 0.3 else
          ("The clubs that earn most DEFCON are the ones under most pressure" if corr > 0 else
           "The best defences also earn the most DEFCON")),
         scatter_dc,
         f"{span}. The link between conceding chances and earning DEFCON is "
         f"{'weak' if abs(corr) < 0.3 else 'moderate' if abs(corr) < 0.6 else 'strong'} "
         f"(correlation {corr:+.2f} across 20 clubs). {tidy.team} sit closest to the corner "
         f"you want: a tight defence that still banks defensive points."),
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
    t.to_csv(out_dir / "defcon_by_team.csv", index=False)
    played.to_csv(out_dir / "defcon_player_gameweek.csv", index=False)
    mine_players.sort_values(["pos", "hits"], ascending=[True, False]).to_csv(
        out_dir / "defcon_my_squad.csv", index=False)
    print("\nyour squad's DEFCON record:")
    print(mine_players.sort_values(["pos", "dc90"], ascending=[True, False])[
        ["player", "pos", "team", "mins", "dc90", "hits"]].to_string(index=False))
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
