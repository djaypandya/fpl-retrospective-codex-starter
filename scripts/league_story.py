"""Build a low-cognitive-load PDF data story for a mini-league manager.

Every slide carries one takeaway title and one chart. Read only the titles and
you still get the whole story. Detail and caveats live in the appendix.

Design follows the Storytelling With Data process: takeaway titles rather than
topic labels, one job per visual, colour used only to carry meaning (blue = you,
orange = the most consistent managers, grey = everyone else), and clutter removed.
The palette is the validated default categorical pair; it clears the lightness,
chroma, colour-vision-deficiency and contrast checks on a light surface.

Run::

    python3.12 scripts/league_story.py --league 14074 --entry 46116 --gw 1

Reads ``outputs/league_<id>_gw<n>/`` (produced by ``league_report.py``) and
writes ``LEAGUE_GW1_DATA_STORY.pdf``.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import textwrap
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Validated categorical palette (light surface). Colour carries meaning only.
YOU = "#2a78d6"      # slot 1, blue
TOP = "#eb6834"      # slot 2, orange
REST = "#d5d3cd"     # context grey, deliberately recessive
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "axes.spines.bottom": False,
    "xtick.bottom": False, "ytick.left": False,
})


def svg(fig) -> str:
    """Render a figure to inline SVG, dropping the XML preamble."""
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    out = buf.getvalue()
    return out[out.index("<svg"):]


def bars(labels, values, colours, *, fmt="{:.0f}", figsize=(11.2, 5.2),
         xlabel="", note_idx=None, note=""):
    """One horizontal bar per manager, sorted by the caller, labelled at the end.

    Horizontal bars because the categories are names: they stay readable without
    rotating text, and ordering does the ranking work the eye needs.
    """
    fig, ax = plt.subplots(figsize=figsize)
    y = range(len(labels))
    ax.barh(list(y), values, color=colours, height=0.68, zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=11.5)
    ax.invert_yaxis()
    ax.set_xticks([])
    span = max(values) - min(0, min(values))
    for i, (v, c) in enumerate(zip(values, colours)):
        weight = "bold" if c in (YOU, TOP) else "normal"
        ax.text(v + span * 0.012, i, fmt.format(v), va="center", ha="left",
                fontsize=11.5, color=INK if c in (YOU, TOP) else INK_2, fontweight=weight)
    for lab, c, tick in zip(labels, colours, ax.get_yticklabels()):
        if c == YOU:
            tick.set_color(INK); tick.set_fontweight("bold")
    ax.set_xlim(0, max(values) * 1.14)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11, color=MUTED, labelpad=10)
    if note_idx is not None:
        ax.annotate(note, xy=(values[note_idx], note_idx), xytext=(28, 0),
                    textcoords="offset points", va="center", fontsize=11.5,
                    color=YOU, fontweight="bold")
    return fig


def slide_standings(b, me, *, highlight=None, label=None):
    """Ranked bar of the table. `highlight` picks out a second group in orange."""
    d = b.sort_values("live_pts", ascending=False)
    colours = []
    for _, r in d.iterrows():
        if r.entry == me:
            colours.append(YOU)
        elif highlight is not None and highlight(r):
            colours.append(TOP)
        else:
            colours.append(REST)
    return svg(bars(d.manager.tolist(), d.live_pts.tolist(), colours,
                    xlabel=label or "Points in Gameweek 1"))


def slide_gap_closed(b, prev, me, rival, left_label="First look", right_label="Final"):
    """Slope chart: two points in time is exactly what a slope chart is for."""
    now = b.set_index("entry"); was = prev.set_index("entry")
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    for eid, colour in [(me, YOU), (rival, REST)]:
        y0, y1 = was.at[eid, "live_pts"], now.at[eid, "live_pts"]
        ax.plot([0, 1], [y0, y1], color=colour, linewidth=3.4, zorder=3,
                solid_capstyle="round")
        ax.scatter([0, 1], [y0, y1], s=110, color=colour, zorder=4)
        name = now.at[eid, "manager"]
        ax.text(-0.06, y0, f"{name}   {int(y0)}", ha="right", va="center",
                fontsize=12.5, color=INK if colour == YOU else INK_2,
                fontweight="bold" if colour == YOU else "normal")
        ax.text(1.06, y1, f"{int(y1)}", ha="left", va="center", fontsize=12.5,
                color=INK if colour == YOU else INK_2,
                fontweight="bold" if colour == YOU else "normal")
    for x, lab in [(0, left_label), (1, right_label)]:
        ax.text(x, ax.get_ylim()[1], lab, ha="center", va="bottom",
                fontsize=12.5, fontweight="bold", color=INK)
    gap_before = was.at[rival, "live_pts"] - was.at[me, "live_pts"]
    gap_now = now.at[rival, "live_pts"] - now.at[me, "live_pts"]
    ax.annotate("", xy=(1.02, now.at[rival, "live_pts"]), xytext=(1.02, now.at[me, "live_pts"]),
                arrowprops=dict(arrowstyle="<->", color=YOU, linewidth=1.5))
    ax.text(1.22, (now.at[rival, "live_pts"] + now.at[me, "live_pts"]) / 2,
            f"{int(gap_now)} points", fontsize=12.5, color=YOU, fontweight="bold", va="center")
    ax.annotate("", xy=(-0.02, was.at[rival, "live_pts"]), xytext=(-0.02, was.at[me, "live_pts"]),
                arrowprops=dict(arrowstyle="<->", color=MUTED, linewidth=1.5))
    ax.text(-0.08, (was.at[rival, "live_pts"] + was.at[me, "live_pts"]) / 2,
            f"{int(gap_before)} points", fontsize=12.5, color=MUTED, va="center", ha="right")
    ax.set_xlim(-0.62, 1.62); ax.set_xticks([]); ax.set_yticks([])
    return svg(fig)


def slide_captains(df, me):
    """How many managers captained each player, with what each one returned."""
    n = df.entry.nunique()
    cap = (df[df.is_captain].groupby(["name", "gw_points"], as_index=False)
           .entry.nunique().rename(columns={"entry": "managers"})
           .sort_values("managers", ascending=False))
    mine = df[(df.entry == me) & df.is_captain].name.iloc[0]
    colours = [YOU if r["name"] == mine else REST for _, r in cap.iterrows()]
    labels = [f"{r['name']}" for _, r in cap.iterrows()]
    fig = bars(labels, cap.managers.tolist(), colours, figsize=(10.2, 4.4),
               xlabel="Managers who captained him")
    ax = fig.axes[0]
    for i, (_, r) in enumerate(cap.iterrows()):
        ax.text(r.managers + 1.6, i, f"returned {int(r.gw_points)} points",
                va="center", fontsize=11.5, color=INK_2)
    ax.set_xlim(0, n * 1.15)
    return svg(fig)


def slide_template_returns(tmpl, me_owns):
    """Every template player's return, so the blank is impossible to miss."""
    d = tmpl.sort_values("gw_points", ascending=False)
    colours = [TOP if p <= 2 else REST for p in d.gw_points]
    labels = [f"{r['name']}  ({r.club})" for _, r in d.iterrows()]
    fig = bars(labels, d.gw_points.tolist(), colours, figsize=(10.4, 5.6),
               xlabel="Points scored by the league's 15 most-owned players")
    ax = fig.axes[0]
    ax.set_xlim(0, max(d.gw_points) * 1.2)
    return svg(fig)


def slide_my_bench(df, me):
    d = df[(df.entry == me) & (df.multiplier == 0)].sort_values("gw_points", ascending=False)
    labels = [f"{r['name']}  ({r.pos})" for _, r in d.iterrows()]
    fig = bars(labels, d.gw_points.tolist(), [TOP] * len(d), figsize=(9.0, 3.8),
               xlabel="Points your bench scored that did not count")
    fig.axes[0].set_xlim(0, max(d.gw_points) * 1.2)
    return svg(fig)


def slide_transfer_activity(tx_pm, me):
    """Only the managers who actually moved; the title carries how many did not."""
    d = tx_pm[tx_pm.transfers > 0].sort_values("transfers", ascending=False)
    colours = [YOU if e == me else (TOP if c else REST)
               for e, c in zip(d.entry, d.chip.fillna(""))]
    labels = [f"{m}{'  (wildcard)' if c else ''}" for m, c in zip(d.manager, d.chip.fillna(""))]
    fig = bars(labels, d.transfers.tolist(), colours, figsize=(9.6, 4.0),
               xlabel="Transfers made this gameweek")
    ax = fig.axes[0]
    for i, (_, r) in enumerate(d.iterrows()):
        if r.hit_cost:
            ax.text(r.transfers + 1.5, i, f"paid {int(r.hit_cost)} points",
                    va="center", fontsize=11, color=INK_2)
    ax.set_xlim(0, max(d.transfers) * 1.45)
    return svg(fig)


def slide_bandwagon(bootstrap, df, n, next_gw):
    """What the whole game bought, against what this league actually bought.

    Two different measures, so only one goes on the axis. The league count sits
    beside each bar as a direct label rather than on a second scale.
    """
    el = {e["id"]: e for e in bootstrap["elements"]}
    club = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    top = sorted(bootstrap["elements"], key=lambda e: -e["transfers_in_event"])[:8]
    owners = df.groupby("element").entry.nunique()
    labels, values, league_counts = [], [], []
    for e in top:
        labels.append(f"{e['web_name']}  ({club[e['team']]})")
        values.append(e["transfers_in_event"] / 1000)
        league_counts.append(int(owners.get(e["id"], 0)))
    colours = [TOP if "Sangar" in l else REST for l in labels]
    fig = bars(labels, values, colours, fmt="{:.0f}k", figsize=(10.2, 4.8),
               xlabel=f"Transfers in across the whole game, for Gameweek {next_gw}")
    ax = fig.axes[0]
    for i, c in enumerate(league_counts):
        ax.text(max(values) * 1.16, i, f"{c} of {n} own him here",
                va="center", fontsize=11.5, color=INK_2)
    ax.set_xlim(0, max(values) * 1.62)
    return svg(fig)


def slide_squad_value(b, me):
    """Where every manager's money sits, so the shape difference is visible."""
    d = b.sort_values("MID", ascending=False)
    colours = [YOU if e == me else (TOP if g == "top5" else REST)
               for e, g in zip(d.entry, d.grp)]
    return svg(bars(d.manager.tolist(), d.MID.tolist(), colours, fmt="£{:.1f}m",
                    xlabel="Spend on midfielders in the starting eleven"))


def slide_allocation(b, me):
    """Grouped bars: two series, so a legend is present and both are labelled."""
    pos = ["FWD", "MID", "DEF", "GKP"]
    names = {"GKP": "Goalkeeper", "DEF": "Defence", "MID": "Midfield", "FWD": "Attack"}
    mine = b[b.entry == me][pos].iloc[0]
    top = b[b.grp == "top5"][pos].mean()
    fig, ax = plt.subplots(figsize=(10.8, 5.0))
    y = range(len(pos)); h = 0.34
    ax.barh([i + h / 2 for i in y], mine.values, height=h, color=YOU, label="You", zorder=3)
    ax.barh([i - h / 2 for i in y], top.values, height=h, color=TOP,
            label="Top 5 managers", zorder=3)
    for i, (m, t) in enumerate(zip(mine.values, top.values)):
        ax.text(m + 0.5, i + h / 2, f"£{m:.1f}m", va="center", fontsize=11.5, color=INK)
        ax.text(t + 0.5, i - h / 2, f"£{t:.1f}m", va="center", fontsize=11.5, color=INK)
    ax.set_yticks(list(y)); ax.set_yticklabels([names[p] for p in pos], fontsize=13)
    ax.set_xticks([]); ax.set_xlim(0, 48); ax.set_ylim(len(pos) - 0.4, -1.15)
    ax.legend(frameon=False, fontsize=12, loc="upper right", ncols=2,
              bbox_to_anchor=(1.0, 1.10))
    # Bracket the midfield gap out to the right, clear of both value labels.
    gap = top["MID"] - mine["MID"]
    ax.annotate("", xy=(41.5, 1 + h / 2), xytext=(41.5, 1 - h / 2),
                arrowprops=dict(arrowstyle="<->", color=TOP, linewidth=1.4))
    ax.text(42.4, 1, f"£{gap:.1f}m\ngap", fontsize=12.5, color=TOP,
            fontweight="bold", va="center", ha="left", linespacing=1.35)
    return svg(fig)


# ---------------------------------------------------------------------------
CSS = """
@page { size: 297mm 167mm; margin: 0; }
* { box-sizing: border-box; }
body { margin:0; background:#fcfcfb; color:#0b0b0b;
  font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; -webkit-print-color-adjust:exact; }
.slide { width:297mm; height:167mm; padding:15mm 17mm 10mm; page-break-after:always;
  display:flex; flex-direction:column; overflow:hidden; }
h1.title { font-size:27px; line-height:1.25; font-weight:700; margin:0 0 6mm;
  letter-spacing:-0.4px; max-width:88%; }
.figure { flex:1; display:flex; align-items:center; justify-content:center; min-height:0; }
.figure svg { max-width:100%; max-height:100%; height:auto; }
.foot { font-size:10.5px; color:#898781; margin-top:4mm; }
.cover { justify-content:center; }
.cover .eyebrow { font-size:13px; letter-spacing:2.4px; text-transform:uppercase;
  color:#898781; margin-bottom:7mm; }
.cover h1 { font-size:50px; line-height:1.1; font-weight:700; margin:0 0 6mm;
  letter-spacing:-1.2px; max-width:78%; }
.cover p { font-size:16px; color:#52514e; margin:0; max-width:66%; line-height:1.55; }
.rule { width:56px; height:4px; background:#2a78d6; margin-bottom:8mm; }
.appendix { width:297mm; padding:15mm 17mm; page-break-before:always; }
.appendix h1 { font-size:30px; margin:0 0 3mm; letter-spacing:-0.5px; }
.appendix h2 { font-size:17px; margin:9mm 0 3mm; color:#0b0b0b; }
.appendix p { font-size:12.5px; line-height:1.62; color:#22221f; max-width:225mm; margin:0 0 3mm; }
table { border-collapse:collapse; font-size:11px; margin:3mm 0 4mm;
  width:100%; max-width:225mm; }
th { text-align:left; border-bottom:1.5px solid #0b0b0b; padding:4px 9px 4px 0;
  font-weight:700; }
td { border-bottom:1px solid #eceae4; padding:4px 9px 4px 0; color:#22221f; }
tr.me td { background:#eaf2fd; font-weight:700; }
.k { color:#2a78d6; font-weight:700; }
.note { font-size:11.5px; color:#52514e; border-left:3px solid #d5d3cd;
  padding-left:9px; margin:4mm 0; line-height:1.6; }
"""


def build_html(slides, cover, appendix) -> str:
    body = [f'<div class="slide cover"><div class="rule"></div>'
            f'<div class="eyebrow">{cover["eyebrow"]}</div>'
            f'<h1>{cover["title"]}</h1><p>{cover["sub"]}</p></div>']
    for title, chart, foot in slides:
        body.append(f'<div class="slide"><h1 class="title">{title}</h1>'
                    f'<div class="figure">{chart}</div>'
                    f'<div class="foot">{foot}</div></div>')
    body.append(appendix)
    return f"<style>{CSS}</style>" + "".join(body)


def review_slides(ns: dict):
    """The eight-slide arc used once every match in the gameweek has been played."""
    (b, df, tmpl, prev, me, n, my, leader, foot, verb, when, gap_before, gap_now,
     my_cap, cap_n, cap_pts, blanks, bench_pts, mid_gap, ordinal, old_leader) = (
        ns["b"], ns["df"], ns["tmpl"], ns["prev"], ns["me"], ns["n"], ns["my"],
        ns["leader"], ns["foot"], ns["verb"], ns["when"], ns["gap_before"],
        ns["gap_now"], ns["my_cap"], ns["cap_n"], ns["cap_pts"], ns["blanks"],
        ns["bench_pts"], ns["mid_gap"], ns["ordinal"], ns["old_leader"])
    top5_ranks = sorted(int(r) for r in b[b.grp == "top5"]["rank"])
    bb = sorted(int(r) for r in b[b.chip == "bboost"]["rank"])
    out = [
        (f"You {verb} {ordinal(int(my['rank']))} of {n}, "
         f"{int(leader.live_pts - my.live_pts)} points off the lead",
         slide_standings(b, me), foot),
    ]
    if prev is not None:
        out.append((f"You cut the gap to {when} from {gap_before} points to {gap_now}",
                    slide_gap_closed(b, prev, me, old_leader), foot))
    out += [
        (f"{my_cap} was captained by {cap_n} of {n} managers and returned {cap_pts} points",
         slide_captains(df, me), foot),
        (f"{blanks} of the 15 most-owned players scored 2 points or fewer",
         slide_template_returns(tmpl, set(df[df.entry == me].element)),
         foot + " Orange marks a return of 2 points or fewer."),
        (f"Your bench scored {bench_pts} points you could not use",
         slide_my_bench(df, me), foot),
        ("The five most consistent managers finished " +
         ", ".join(ordinal(r) for r in top5_ranks[:-1]) + f" and {ordinal(top5_ranks[-1])}",
         slide_standings(b, me, highlight=lambda r: r.grp == "top5"),
         foot + " Orange marks the five most consistent managers."),
        (f"They still put £{mid_gap:.0f}m more than you into midfield",
         slide_allocation(b, me), foot),
    ]
    if bb:
        out.insert(4, (
            f"The {len(bb)} managers who played Bench Boost finished "
            + ", ".join(ordinal(r) for r in bb[:-1]) + f" and {ordinal(bb[-1])}",
            slide_standings(b, me, highlight=lambda r: r.chip == "bboost"),
            foot + " Orange marks the managers who played Bench Boost."))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--league", type=int, default=14074)
    ap.add_argument("--entry", type=int, default=46116)
    ap.add_argument("--gw", type=int, default=1)
    ap.add_argument("--out", default="LEAGUE_GW1_DATA_STORY.pdf")
    args = ap.parse_args()

    src = REPO / "outputs" / f"league_{args.league}_gw{args.gw}"
    df = pd.read_csv(src / "picks_long.csv")
    b = pd.read_csv(src / "budget.csv")
    hist = pd.read_csv(src / "history.csv")
    tmpl = pd.read_csv(src / "template.csv")
    prev_path = src / "standings_previous.csv"
    prev = pd.read_csv(prev_path) if prev_path.exists() else None
    tx_pm = pd.read_csv(src / "transfers_by_manager.csv")
    fixtures = json.loads((src / "raw" / f"fixtures_gw{args.gw}.json").read_text())
    bootstrap = json.loads((src / "raw" / "bootstrap.json").read_text())
    me = args.entry
    n = len(b)

    top5 = hist[hist.seasons >= 4].nsmallest(5, "median_rank")
    b["grp"] = b.entry.map(lambda e: "me" if e == me else
                           ("top5" if e in set(top5.entry) else "rest"))
    my = b[b.entry == me].iloc[0]
    leader = b.nsmallest(1, "rank").iloc[0]

    # Only a gameweek with an earlier snapshot can show how the gap moved.
    my_prev = old_leader = gap_before = gap_now = None
    if prev is not None:
        my_prev = prev[prev.entry == me].iloc[0]
        # Track the earlier leader by entry id: managers rename mid-week.
        old_leader = int(prev.nsmallest(1, "rank").iloc[0].entry)
        gap_before = int(prev[prev.entry == old_leader].live_pts.iloc[0] - my_prev.live_pts)
        gap_now = int(b[b.entry == old_leader].live_pts.iloc[0] - my.live_pts)

    caps = df[df.is_captain]
    my_cap = caps[caps.entry == me].name.iloc[0]
    cap_n = int(caps[caps.name == my_cap].entry.nunique())
    cap_pts = int(df[df.name == my_cap].gw_points.iloc[0])
    blanks = int((tmpl.gw_points <= 2).sum())
    bench_pts = int(df[(df.entry == me) & (df.multiplier == 0)].gw_points.sum())
    bb_top4 = int(b.nsmallest(4, "rank").chip.eq("bboost").sum())
    mid_gap = b[b.grp == "top5"].MID.mean() - my.MID
    top5_ranks = sorted(int(r) for r in b[b.grp == "top5"]["rank"])
    played = sum(f["started"] for f in fixtures)
    remaining = [f for f in fixtures if not f["started"]]
    complete = not remaining
    verb = "finished" if complete else "climbed to"
    when = "the early leader" if complete else "last night's leader"

    foot = (f"Gameweek {args.gw} complete: all {len(fixtures)} matches played. "
            "Bonus points are provisional until the league confirms them."
            if complete else
            f"Gameweek {args.gw}: {played} of {len(fixtures)} matches played. "
            "Scores are provisional until bonus points are confirmed.")

    def ordinal(k):
        return f"{k}{'th' if 10 <= k % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(k % 10, 'th')}"

    if complete:
        slides = review_slides(locals())
    else:
        # Early in a gameweek the result says nothing yet, so the story is what
        # managers DID: who moved, who stood still, and who followed the crowd.
        n_moved = int((tx_pm.transfers > 0).sum())
        quiet = int((tx_pm.transfers == 0).sum())
        hits = tx_pm[tx_pm.hit_cost > 0]
        cap_lead = caps.groupby("name").entry.nunique().sort_values(ascending=False)
        top_cap, top_cap_n = cap_lead.index[0], int(cap_lead.iloc[0])
        sangare = next((e for e in bootstrap["elements"]
                        if e["web_name"].startswith("M.Sangar")), None)
        s_owners = int(df[df.element == sangare["id"]].entry.nunique()) if sangare else 0
        next_gw = next((e["id"] for e in bootstrap["events"] if e["is_next"]), args.gw + 1)
        cherki = max(bootstrap["elements"], key=lambda e: e["transfers_in_event"])["web_name"]
        top5_ranks = sorted(int(r) for r in b[b.grp == "top5"]["rank"])
        in_top4 = sum(1 for r in top5_ranks if r <= 4)

        slides = [
            (f"You sit {ordinal(int(my['rank']))} of {n} with {int(my.live_pts)} points",
             slide_standings(b, me, label="Total points so far this season"), foot),
            (f"{quiet} of the {n} managers made no transfer at all this week",
             slide_transfer_activity(tx_pm, me),
             foot + (f" {len(hits)} paid a points hit." if len(hits) else "")),
            (f"The Sangaré bandwagon has already cooled, and {cherki} is the new one",
             slide_bandwagon(bootstrap, df, n, next_gw),
             foot + f" Orange marks Sangaré. Only {s_owners} of {n} here owns him."),
            (f"{top_cap} is captain for {top_cap_n} of the {n} managers",
             slide_captains(df, me), foot),
            (f"{in_top4} of the five most consistent managers are already in the top four",
             slide_standings(b, me, highlight=lambda r: r.grp == "top5",
                             label="Total points so far this season"),
             foot + " Orange marks the five most consistent managers."),
            (f"They still put £{mid_gap:.0f}m more than you into midfield",
             slide_allocation(b, me), foot),
        ]

    cover = {
        "eyebrow": f"Gameweek {args.gw} &middot; Buy-in Baller League &middot; Updated",
        "title": "How your team stacks up",
        "sub": (f"{my.manager} &middot; {n} managers &middot; {played} of {len(fixtures)} matches "
                "played. Read the titles alone and you have the whole story. "
                "The appendix holds the detail."),
    }
    if complete:
        appendix = build_appendix(b, df, hist, tmpl, prev, me, old_leader, gap_before,
                                  gap_now, mid_gap, top5, my_cap, cap_n, cap_pts,
                                  blanks, bench_pts, remaining)
    else:
        appendix = build_early_appendix(b, df, hist, tmpl, tx_pm, bootstrap, me,
                                        mid_gap, top5, args.gw, played, len(fixtures))

    html = src / "story.html"
    html.write_text(build_html(slides, cover, appendix))
    pdf = REPO / args.out
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", f"file://{html}"],
                   check=True, capture_output=True, timeout=180)
    print(f"wrote {pdf} ({pdf.stat().st_size/1024:.0f} KB)")
    if my_prev is not None:
        print(f"  rank {int(my_prev['rank'])} -> {int(my['rank'])}, "
              f"{int(my_prev.live_pts)} -> {int(my.live_pts)} points")
    else:
        print(f"  rank {int(my['rank'])} of {n}, {int(my.live_pts)} points, "
              f"{played}/{len(fixtures)} matches played")


def ordinal_word(k: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
             6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}
    return words.get(k, f"{k}th")


def build_early_appendix(b, df, hist, tmpl, tx_pm, bootstrap, me, mid_gap, top5,
                         gw, played, total_matches) -> str:
    next_gw = next((e["id"] for e in bootstrap["events"] if e["is_next"]), gw + 1)
    """Appendix for a gameweek still in progress: what managers did, not what scored."""
    my = b[b.entry == me].iloc[0]
    n = len(b)
    tx_pm = tx_pm.copy()
    tx_pm["chip"] = tx_pm.chip.fillna("").astype(str)
    quiet = int((tx_pm.transfers == 0).sum())
    movers = tx_pm[tx_pm.transfers > 0].sort_values("transfers", ascending=False)
    hits = movers[movers.hit_cost > 0]
    chips = movers[movers.chip != ""]
    el = {e["id"]: e for e in bootstrap["elements"]}
    club = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    owners = df.groupby("element").entry.nunique()
    sangare = next((e for e in bootstrap["elements"]
                    if e["web_name"].startswith("M.Sangar")), None)
    s_owners = int(owners.get(sangare["id"], 0)) if sangare else 0

    def table(rows, head):
        h = "".join(f"<th>{c}</th>" for c in head)
        out = []
        for r in rows:
            cls = " class='me'" if r.get("me") else ""
            out.append(f"<tr{cls}>" + "".join(f"<td>{v}</td>" for v in r["cells"]) + "</tr>")
        return f"<table><thead><tr>{h}</tr></thead><tbody>{''.join(out)}</tbody></table>"

    standings = table([
        {"cells": [int(r["rank"]), r.manager, int(r.live_pts),
                   int(tx_pm[tx_pm.entry == r.entry].transfers.iloc[0]),
                   f"&minus;{int(tx_pm[tx_pm.entry == r.entry].hit_cost.iloc[0])}"
                   if tx_pm[tx_pm.entry == r.entry].hit_cost.iloc[0] else "&mdash;",
                   f"£{r.DEF:.1f}m", f"£{r.MID:.1f}m", f"£{r.FWD:.1f}m"],
         "me": r.entry == me}
        for _, r in b.sort_values("rank").iterrows()],
        ["#", "Manager", "Points", "Transfers", "Hit", "Defence", "Midfield", "Attack"])

    moves = table([
        {"cells": [r.manager, r.transfers,
                   f"&minus;{int(r.hit_cost)}" if r.hit_cost else "&mdash;",
                   r.chip.title() if r.chip else "&mdash;", r["in"], r["out"]],
         "me": r.entry == me}
        for _, r in movers.iterrows()],
        ["Manager", "Moves", "Hit", "Chip", "In", "Out"])

    top_global = sorted(bootstrap["elements"], key=lambda e: -e["transfers_in_event"])[:8]
    band = table([
        {"cells": [e["web_name"], club[e["team"]], f"£{e['now_cost']/10:.1f}m",
                   f"{e['transfers_in_event']:,}", f"{int(owners.get(e['id'], 0))} of {n}"],
         "me": int(owners.get(e["id"], 0)) > 0 and e["id"] in set(df[df.entry == me].element)}
        for e in top_global],
        ["Player", "Club", "Price", "Bought across the game", "Owned in your league"])

    top_rows = table([
        {"cells": [i + 1, r.manager, f"{int(r.median_rank):,}",
                   int(b[b.entry == r.entry]["rank"].iloc[0]),
                   int(b[b.entry == r.entry].live_pts.iloc[0])],
         "me": r.entry == me}
        for i, (_, r) in enumerate(hist[hist.seasons >= 4].nsmallest(6, "median_rank").iterrows())],
        ["#", "Manager", "Median finish", "Rank now", "Points"])

    text = f"""
<h2>Where things stand</h2>
<p>Only <span class="k">{played} of the {total_matches} matches</span> in Gameweek {gw} have been
played, so nothing here is a result yet. Treat every score as a snapshot. What <em>is</em> settled is
what each manager chose to do, and that is what this report is about.</p>
<p>You are {int(my['rank'])}th of {n} on {int(my.live_pts)} points. You made no transfer, which was
your plan.</p>
{standings}

<h2>The league mostly stood still</h2>
<p><span class="k">{quiet} of the {n} managers made no transfer at all.</span> Only
{len(movers)} moved. You were in the larger group.</p>
{moves}
<p>{len(hits)} manager{'s' if len(hits) != 1 else ''} paid a points hit to make an extra move, costing
{int(hits.hit_cost.sum())} points between them. A hit means giving up 4 points for a transfer beyond
the free one, so it only pays if the new player beats the old one by more than 4.</p>
{"<p>" + ", ".join(f"{r.manager} played a {r.chip.title()} and made {int(r.transfers)} moves" for _, r in chips.iterrows()) + ". A wildcard allows unlimited free transfers, so it does not cost points, but it is one of only two available all season.</p>" if len(chips) else ""}
<p>A note on how this was counted. FPL reports a manager's transfer count as zero when they play a
wildcard, even if they rebuilt the whole squad. Counting that field alone would have missed
{int(chips.transfers.sum()) if len(chips) else 0} moves, so these numbers come from each manager's
full transfer log instead.</p>

<h2>The bandwagon, and who actually got on it</h2>
<p>These are the most-bought players across the entire game right now. One thing to be careful about:
this counter resets at every deadline, so with Gameweek {gw} under way it is already counting moves
being made for Gameweek {next_gw}, not the ones made for this week. The last column is what matters to
you: how many of your {n} rivals actually own each player.</p>
{band}
<p>Two things stand out, and both support the decision you made.</p>
<p><span class="k">The Sangaré bandwagon has already cooled.</span> Before the Gameweek {gw} deadline
he was being bought by about 176,000 managers. He is now down to
{sangare['transfers_in_event']:,}, and the crowd has moved to {top_global[0]['web_name']}, who is on
{top_global[0]['transfers_in_event']:,} after scoring {top_global[0]['event_points']} points. Bandwagons
move faster than a transfer can pay for itself.</p>
<p><span class="k">And the national number was never your number.</span> Sangaré is owned by
{s_owners} of your {n} rivals. A move that looks enormous across the game can be almost invisible in a
22-manager league, and your rank depends only on these 22 people.</p>

<h2>What the best managers are doing</h2>
{top_rows}
<p>The five most consistent managers are already spreading out again, which is the same pattern as
last week. Two of them sit near the top and two near the bottom. It stays too early to read anything
into it.</p>
<p>The structural difference has not moved, because you did not move. Those five carry about
£{b[b.grp == 'top5'].MID.mean():.1f}m in midfield against your £{my.MID:.1f}m, a gap of
<span class="k">£{mid_gap:.1f}m</span>. They keep defence near £{b[b.grp == 'top5'].DEF.mean():.1f}m
against your £{my.DEF:.1f}m.</p>

<h2>What to watch</h2>
<p>Your own plan was to wait for more information rather than spend a transfer, and this week's
data supports that. Fifteen managers did the same, the biggest national bandwagon reached one team
in your league, and nine of ten matches are still to play.</p>
<p>The question worth answering over the next three or four weeks is whether Sangaré's points come
from goals and assists or from defensive contributions, because those repeat at very different
rates. Defensive returns are the more repeatable of the two.</p>

<h2>Where the numbers come from</h2>
<p>The official Fantasy Premier League API, pulled during Gameweek {gw} with {played} of
{total_matches} matches played. Transfer counts come from each manager's transfer log rather than
the summary field, for the wildcard reason above. Rebuild everything with
<code>scripts/league_report.py</code> then <code>scripts/league_story.py</code>.</p>
"""
    return f'<div class="appendix"><h1>Appendix</h1>{textwrap.dedent(text)}</div>'


def build_appendix(b, df, hist, tmpl, prev, me, old_leader, gap_before, gap_now,
                   mid_gap, top5, my_cap, cap_n, cap_pts, blanks, bench_pts,
                   remaining) -> str:
    my = b[b.entry == me].iloc[0]
    my_prev = prev[prev.entry == me].iloc[0]
    n = len(b)
    leader = b.nsmallest(1, "rank").iloc[0]
    old_name_now = b[b.entry == old_leader].manager.iloc[0]
    old_name_then = prev[prev.entry == old_leader].manager.iloc[0]
    left = ", ".join(sorted(set(df[(df.entry == me) & (df.multiplier > 0) & (~df.played)].name)))

    def table(rows, head):
        h = "".join(f"<th>{c}</th>" for c in head)
        out = []
        for r in rows:
            cls = " class='me'" if r.get("me") else ""
            out.append(f"<tr{cls}>" + "".join(f"<td>{v}</td>" for v in r["cells"]) + "</tr>")
        return f"<table><thead><tr>{h}</tr></thead><tbody>{''.join(out)}</tbody></table>"

    prev_pts = dict(zip(prev.entry, prev.live_pts))
    standings = table([
        {"cells": [int(r["rank"]), r.manager, int(r.live_pts),
                   f"+{int(r.live_pts - prev_pts.get(r.entry, r.live_pts))}",
                   "Bench Boost" if r.chip == "bboost" else "&mdash;",
                   f"£{r.DEF:.1f}m", f"£{r.MID:.1f}m", f"£{r.FWD:.1f}m"],
         "me": r.entry == me}
        for _, r in b.sort_values("rank").iterrows()],
        ["#", "Manager", "Points", "Overnight", "Chip", "Defence", "Midfield", "Attack"])

    tmpl_rows = table([
        {"cells": [r["name"], r.pos, r.club, f"{r.own_pct:.0f}%", f"{r.eo_pct:.0f}%",
                   int(r.gw_points),
                   "Yes" if r.element in set(df[df.entry == me].element) else "No"],
         "me": r.element in set(df[df.entry == me].element)}
        for _, r in tmpl.sort_values("gw_points", ascending=False).iterrows()],
        ["Player", "Position", "Club", "Owned by", "Counting captains", "Points", "You own?"])

    top_rows = table([
        {"cells": [i + 1, r.manager, f"{int(r.median_rank):,}",
                   int(b[b.entry == r.entry]["rank"].iloc[0]),
                   int(b[b.entry == r.entry].live_pts.iloc[0])],
         "me": r.entry == me}
        for i, (_, r) in enumerate(hist[hist.seasons >= 4].nsmallest(6, "median_rank").iterrows())],
        ["#", "Manager", "Median finish", "Rank this week", "Points this week"])

    squad = df[df.entry == me].sort_values("gw_points", ascending=False)
    squad_rows = table([
        {"cells": [r["name"], r.pos, r.club, f"£{r.price:.1f}m",
                   "Captain" if r.is_captain else ("Started" if r.multiplier else "Bench"),
                   int(r.gw_points), int(r.multiplier * r.gw_points)],
         "me": bool(r.multiplier)}
        for _, r in squad.iterrows()],
        ["Player", "Position", "Club", "Price", "Role", "Scored", "Counted for you"])

    rename = ""
    if old_name_now != old_name_then:
        rename = (f' That manager has since renamed from &ldquo;{old_name_then}&rdquo; to '
                  f'&ldquo;{old_name_now}&rdquo;, so I tracked them by their team id rather than '
                  'their name.')

    text = f"""
<h2>How Gameweek 1 finished</h2>
<p>You finished <span class="k">{int(my['rank'])}th of {n} on {int(my.live_pts)} points</span>. The
league averaged {b.live_pts.mean():.1f}, so you beat it by {my.live_pts - b.live_pts.mean():.1f}. You
started the week sixth on {int(my_prev.live_pts)} points.</p>
<p>At my first look I told you that you could not lose ground to the leader, because every player he
had left was also in your team and you captained Haaland while he did not. That held.
<span class="k">The gap closed from {gap_before} points to {gap_now}.</span>{rename}</p>
<p>I also told you the finishing order was settled. That was half right. You did finish
{int(my['rank'])}th, but I only checked the managers immediately around you. Karan Yohannan still had
several Chelsea and Fulham players to come, gained 25 points in the last match, and climbed from
fifteenth to join you on {int(my.live_pts)}. The lesson is to check the whole table for players still
to play, not just the managers nearest you.</p>
<p>{leader.manager} won the week with {int(leader.live_pts)} after playing a Bench Boost.</p>
{standings}

<h2>The template blanked</h2>
<p>The template is the group of players most managers own. This week it failed almost everyone.
<span class="k">{blanks} of the 15 most-owned players scored 2 points or fewer.</span> The average
was {tmpl.gw_points.mean():.1f} points.</p>
{tmpl_rows}
<p>Notice who did deliver. Every one of the four template players who beat 2 points plays for
Arsenal: Calafiori, Raya, Tzolis and Gabriel. Arsenal beat Coventry 3-0. If you did not own Arsenal
players this week, you had a bad week.</p>
<p>The clearest example of the blank is your own captain. {my_cap} was owned by {tmpl[tmpl.name == my_cap].own_pct.iloc[0]:.0f}%
of the league and captained by {cap_n} of {n} managers. He returned <span class="k">{cap_pts} points</span>.
Because you doubled him, he gave you {cap_pts * 2}.</p>
<p>That sounds bad, and it was. But it hurt your rivals just as much. When a player that popular
fails, owning him costs you nothing in the league table. It only costs you against managers who
picked someone else, and almost nobody did.</p>

<h2>Your own team</h2>
{squad_rows}
<p>Your climb came from the middle of your squad, not the top. Calafiori and Ndiaye scored 9 each,
and Szoboszlai scored 8. Your two most expensive attackers, Haaland and Igor Thiago, cost
£23.5m together and scored 2 points between them, which the armband turned into 4.</p>
<p><span class="k">Your bench scored {bench_pts} points you could not use.</span> Vuskovic got 6 and
Ampadu got 5. Had you played your Bench Boost this week, you would be on
{int(my.live_pts) + bench_pts} points and sitting {ordinal_word(int((b.live_pts > my.live_pts + bench_pts).sum()) + 1)}.</p>

<h2>The chip, not the picks, decided the top</h2>
<p>Three of the top four managers played their Bench Boost this week. The best manager who did not
use a chip is {b[b.chip.isna()].nsmallest(1, 'rank').iloc[0].manager} in third.</p>
<p>Be careful how you read this. Everyone gets the same chips. Playing one early is a gamble on a
high-scoring week, and this week paid off. It does not make those managers better. It means they
have one fewer chip to use later, and you still hold yours.</p>

<h2>What the best managers did</h2>
<p>I ranked every manager by their median finish over the last five seasons, because the median
rewards being good every year rather than one lucky season.</p>
{top_rows}
<p>Look at the right-hand columns. The five most consistent managers finished all over the table
this week, from second down to twenty-first. <span class="k">One gameweek tells you almost nothing
about who is good.</span> That is exactly why you should not change your plan based on this week.</p>
<p>The durable pattern is still the money. Those five managers keep defence between £14.5m and
£16.5m and put between £30.5m and £42.5m into midfield. You spend £{my.DEF:.1f}m on defence and
£{my.MID:.1f}m on midfield. That is a <span class="k">£{mid_gap:.1f}m midfield gap</span> against the
managers who win most often, and it has not moved.</p>

<h2>What to carry into Gameweek 2</h2>
<p>Two numbers matter from here.</p>
<p>First, <span class="k">your midfield spend against the £34m the best managers carry</span>. You are
£{mid_gap:.1f}m short, and one bad week for those midfielders does not change the pattern. It is the
one structural difference between you and the managers who finish well every year.</p>
<p>Second, <span class="k">your chips</span>. You still hold your Bench Boost. Three of the four
managers who finished above you have now spent theirs. In a week where your bench scored
{bench_pts} points, that chip was worth roughly two league places, and you still have it.</p>
<p>Do not chase this week. The template blanked, your captain blanked, and you still finished fifth
and above average. That is a reasonable place to start a season.</p>

<h2>Where the numbers come from</h2>
<p>Everything here comes from the official Fantasy Premier League API, refreshed this morning with
nine of ten matches played. Bonus points are not yet final, so small changes are still possible.
Rebuild every number by running <code>scripts/league_report.py</code> and then
<code>scripts/league_story.py</code>.</p>
"""
    return f'<div class="appendix"><h1>Appendix</h1>{textwrap.dedent(text)}</div>'


if __name__ == "__main__":
    main()
