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
    span = abs(now.at[rival, "live_pts"] - now.at[me, "live_pts"]) or 1
    close = abs(was.at[rival, "live_pts"] - was.at[me, "live_pts"]) < span * 0.35
    ax.text(-0.02 if close else -0.08,
            (was.at[rival, "live_pts"] + was.at[me, "live_pts"]) / 2 - (span * 0.10 if close else 0),
            f"{int(gap_before)} points", fontsize=12.5, color=MUTED,
            va="top" if close else "center", ha="left" if close else "right")
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
    tripled = (df[df.multiplier == 3].groupby("name").entry.nunique()
               if (df.multiplier == 3).any() else {})
    for i, (_, r) in enumerate(cap.iterrows()):
        extra = ""
        t = int(tripled.get(r["name"], 0)) if len(tripled) else 0
        if t:
            extra = f", {t} of them tripled him"
        ax.text(r.managers + 1.6, i, f"returned {int(r.gw_points)} points{extra}",
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


CHIP_NAMES = {"wildcard": "wildcard", "freehit": "free hit",
              "3xc": "triple captain", "bboost": "bench boost"}


def slide_transfer_activity(tx_pm, me):
    """Only the managers who actually moved; the title carries how many did not."""
    d = tx_pm[tx_pm.transfers > 0].sort_values("transfers", ascending=False)
    colours = [YOU if e == me else (TOP if c else REST)
               for e, c in zip(d.entry, d.chip.fillna(""))]
    labels = [f"{m}  ({CHIP_NAMES.get(c, c)})" if c else m
              for m, c in zip(d.manager, d.chip.fillna(""))]
    fig = bars(labels, d.transfers.tolist(), colours, figsize=(9.6, 4.0),
               xlabel="Transfers made this gameweek")
    ax = fig.axes[0]
    for i, (_, r) in enumerate(d.iterrows()):
        if r.hit_cost:
            ax.text(r.transfers + 1.5, i, f"paid {int(r.hit_cost)} points",
                    va="center", fontsize=11, color=INK_2)
    ax.set_xlim(0, max(d.transfers) * 1.45)
    return svg(fig)


def slide_bandwagon(bootstrap, df, n, next_gw, highlight_name=None):
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
    key = highlight_name or "Sangar"
    colours = [TOP if key in l else REST for l in labels]
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


def slide_projection(b, me, ppu):
    """Points banked against points still to come, so the real race is visible.

    A raw table mid-gameweek flatters whoever has played more of their squad.
    The lighter segment is every remaining player scoring the league average,
    which is a levelling assumption, not a forecast.
    """
    d = b.nlargest(10, "projected").sort_values("projected")
    fig, ax = plt.subplots(figsize=(10.2, 5.0))
    y = range(len(d))
    banked = d.live_pts.tolist()
    to_come = (d.projected - d.live_pts).tolist()
    colours = [YOU if e == me else REST for e in d.entry]
    ax.barh(list(y), banked, height=0.62, color=colours, zorder=3, label="Points banked")
    # 2px surface gap keeps the two segments from reading as one bar.
    ax.barh(list(y), to_come, height=0.62, left=[v + 0.9 for v in banked],
            color=[TOP if e == me else "#efe7e0" for e in d.entry], zorder=3,
            label="Still to come, at the league average")
    ax.set_yticks(list(y)); ax.set_yticklabels(d.manager.tolist(), fontsize=11.5)
    for tick, e in zip(ax.get_yticklabels(), d.entry):
        if e == me:
            tick.set_color(INK); tick.set_fontweight("bold")
    for i, (bk, tot) in enumerate(zip(banked, d.projected)):
        ax.text(tot + 3, i, f"{int(tot)}", va="center", fontsize=11.5,
                color=INK, fontweight="bold" if d.entry.iloc[i] == me else "normal")
        ax.text(bk / 2, i, f"{int(bk)}", va="center", ha="center", fontsize=10.5,
                color="white" if d.entry.iloc[i] == me else INK_2)
    ax.set_xticks([]); ax.set_xlim(0, max(d.projected) * 1.13)
    ax.set_ylim(-1.15, len(d) - 0.4)
    ax.legend(frameon=False, fontsize=11.5, loc="lower right", ncols=2,
              bbox_to_anchor=(1.0, -0.11))
    return svg(fig)


def slide_contributors(df, me):
    d = df[(df.entry == me) & (df.multiplier > 0)].copy()
    d["scored"] = d.multiplier * d.gw_points
    d = d[d.played].sort_values("scored", ascending=False)
    labels = [f"{r['name']}{' (C)' if r.is_captain else ''}  ({r.club})" for _, r in d.iterrows()]
    colours = [YOU if r.scored >= 10 else REST for _, r in d.iterrows()]
    fig = bars(labels, d.scored.tolist(), colours, figsize=(9.4, 3.9),
               xlabel="Points each has given you in Gameweek 2")
    fig.axes[0].set_xlim(0, max(d.scored) * 1.2)
    return svg(fig)


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


def template_headline(tmpl, blanks, df, me) -> str:
    """Headline whichever way the template actually went this week.

    When most of the popular players deliver, a contrarian squad loses ground
    even in a good week, and that is the story worth leading with.
    """
    delivered = len(tmpl) - blanks
    owned = sum(1 for e in tmpl.element if e in set(df[df.entry == me].element))
    if delivered > blanks:
        return (f"The template delivered: {delivered} of the 15 beat 2 points, "
                f"and you own {owned}")
    return f"{blanks} of the 15 most-owned players scored 2 points or fewer"


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
    if prev is not None and gap_before is not None:
        verb = ("cut the gap to" if gap_now < gap_before else
                "lost ground to" if gap_now > gap_before else "held the gap to")
        out.append((f"You {verb} {when}: {gap_before} points became {gap_now}",
                    slide_gap_closed(b, prev, me, old_leader), foot))
    out += [
        ((f"{int((df.multiplier == 3).sum())} of the {n} managers tripled {my_cap}, "
          f"and he returned {cap_pts} points"
          if (df.multiplier == 3).sum() >= 3 else
          f"{my_cap} was captained by {cap_n} of {n} managers and returned {cap_pts} points"),
         slide_captains(df, me), foot),
        (template_headline(tmpl, blanks, df, me),
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
    counts = b[b.chip.notna() & (b.chip != "")].chip.value_counts()
    if len(counts) and counts.iloc[0] >= 3:
        chip = counts.index[0]
        label = CHIP_NAMES.get(chip, chip).title()
        ranks = sorted(int(r) for r in b[b.chip == chip]["rank"])
        if len(ranks) > 5:
            # Listing eleven positions is unreadable; the spread is the point.
            head = f"everywhere from {ordinal(ranks[0])} to {ordinal(ranks[-1])}"
        else:
            head = ", ".join(ordinal(r) for r in ranks[:-1]) + f" and {ordinal(ranks[-1])}"
        out.insert(4, (
            f"The {len(ranks)} managers who played a {label} finished {head}",
            slide_standings(b, me, highlight=lambda r, c=chip: r.chip == c),
            foot + f" Orange marks the managers who played a {label}."))
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
    prev_src = REPO / "outputs" / f"league_{args.league}_gw{args.gw - 1}"
    prev_picks = prev_src / "picks_long.csv"
    if prev_picks.exists():
        before = pd.read_csv(prev_picks).groupby("entry").element.apply(set)
        after = df.groupby("entry").element.apply(set)
        net = {e: len(after[e] - before.get(e, set())) for e in after.index}
        tx_pm["transfers"] = tx_pm.entry.map(net).fillna(tx_pm.transfers).astype(int)
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
        _top = max(bootstrap["elements"], key=lambda e: e["transfers_in_event"])
        top_buy = _top["web_name"]
        top_buy_owners = int(df[df.element == _top["id"]].entry.nunique())
        top5_ranks = sorted(int(r) for r in b[b.grp == "top5"]["rank"])
        in_top4 = sum(1 for r in top5_ranks if r <= 4)

        # Once matches have been played, a raw table flatters whoever has played
        # more of their squad, so project every squad out to the same point.
        scored = df[df.played & (df.multiplier > 0)]
        ppu = float((scored.multiplier * scored.gw_points).sum() / scored.multiplier.sum())
        units_left = df[~df.played & (df.multiplier > 0)].groupby("entry").multiplier.sum()
        b["units_left"] = b.entry.map(units_left).fillna(0)
        b["projected"] = (b.live_pts + b.units_left * ppu).round(0)
        b["proj_rank"] = b.projected.rank(ascending=False, method="min").astype(int)
        my = b[b.entry == me].iloc[0]
        my_contrib = df[(df.entry == me) & (df.multiplier > 0) & df.played].copy()
        my_contrib["scored"] = my_contrib.multiplier * my_contrib.gw_points
        top2 = my_contrib.nlargest(2, "scored")

        slides = []
        if played:
            moved = ""
            if prev is not None:
                pr = int(prev[prev.entry == me]["rank"].iloc[0])
                moved = f" from {ordinal(pr)}" if pr != int(my["rank"]) else ""
            slides += [
                (f"You have climbed{moved} to {ordinal(int(my['rank']))} of {n}",
                 slide_standings(b, me, label="Total points so far this season"), foot),
                (f"But you are {ordinal(int(my.proj_rank))} once you count who still has "
                 f"players to play",
                 slide_projection(b, me, ppu),
                 foot + " The lighter bar assumes every remaining player scores the "
                        "league average. It levels the comparison; it is not a forecast."),
                (f"{' and '.join(top2['name'])} have given you "
                 f"{int(top2.scored.sum())} of your {int(my_contrib.scored.sum())} points",
                 slide_contributors(df, me), foot),
            ]
        tripled = int((df.multiplier == 3).sum())
        cap_title = (f"{tripled} of the {n} managers played a Triple Captain, all on {top_cap}"
                     if tripled >= 3 else
                     f"{top_cap} is captain for {top_cap_n} of the {n} managers")
        slides += [
            (cap_title, slide_captains(df, me), foot),
            (f"{quiet} of the {n} managers made no change to their squad",
             slide_transfer_activity(tx_pm, me),
             foot + " Counted as net squad changes, not transfer-log entries."),
            (f"The game is buying {top_buy}, and {top_buy_owners} of the {n} here own him",
             slide_bandwagon(bootstrap, df, n, next_gw, top_buy),
             foot + f" Orange marks {top_buy}, the most-bought player in the game."),
            (f"{in_top4} of the five most consistent managers are already in the top four",
             slide_standings(b, me, highlight=lambda r: r.grp == "top5",
                             label="Total points so far this season"),
             foot + " Orange marks the five most consistent managers."),
            (f"They still put £{mid_gap:.0f}m more than you into midfield",
             slide_allocation(b, me), foot),
        ]
        my_bench_pts = int(df[(df.entry == me) & (df.multiplier == 0)].gw_points.sum())
        if my_bench_pts >= 8:
            slides.insert(3, (
                f"Your bench has scored {my_bench_pts} points you cannot use",
                slide_my_bench(df, me), foot))

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
                                  blanks, bench_pts, remaining, args.gw)
    else:
        appendix = build_early_appendix(b, df, hist, tmpl, tx_pm, bootstrap, me,
                                        mid_gap, top5, args.gw, played, len(fixtures), prev)

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
                         gw, played, total_matches, prev=None) -> str:
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

    scored = df[df.played & (df.multiplier > 0)]
    ppu = float((scored.multiplier * scored.gw_points).sum() / scored.multiplier.sum()) \
        if len(scored) else 0.0
    prev_line = ""
    if prev is not None:
        pr = int(prev[prev.entry == me]["rank"].iloc[0])
        pp = int(prev[prev.entry == me].live_pts.iloc[0])
        prev_line = (f", up from {ordinal_word(pr)} on {pp}" if pr != int(my["rank"])
                     else f", from {pp} points")
    starters = df[df.multiplier > 0]
    played_by = starters[starters.played].groupby("entry").size()
    my_played = int(played_by.get(me, 0))
    my_total = int((starters.entry == me).sum())
    counts = starters.groupby("entry").size().to_frame("total")
    counts["played"] = played_by.reindex(counts.index).fillna(0).astype(int)
    fewest = counts.played.idxmin()
    least_played_name = b[b.entry == fewest].manager.iloc[0]
    least_played_n = int(counts.at[fewest, "played"])
    my_tx = int(tx_pm[tx_pm.entry == me].transfers.iloc[0])
    my_chip = tx_pm[tx_pm.entry == me].chip.iloc[0]
    if my_tx == 0:
        my_moves_line = "You made no change to your squad."
        my_group_line = "You were in the larger group if that is the majority, and stood still."
    else:
        ins = tx_pm[tx_pm.entry == me]["in"].iloc[0]
        outs = tx_pm[tx_pm.entry == me]["out"].iloc[0]
        chip_bit = f" You played your {CHIP_NAMES.get(my_chip, my_chip)}." if my_chip else ""
        my_moves_line = (f"You made {my_tx} change{'s' if my_tx != 1 else ''}: "
                         f"{ins} in, {outs} out.{chip_bit}")
        my_group_line = "You were among those who moved."
    proj_table = table([
        {"cells": [int(r.proj_rank), r.manager, int(r.live_pts), int(r.units_left),
                   int(r.projected)], "me": r.entry == me}
        for _, r in b.nlargest(10, "projected").iterrows()],
        ["Projected", "Manager", "Points now", "Players still to play", "Projected total"])

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
<p><span class="k">{played} of the {total_matches} matches</span> in Gameweek {gw} have been played.
You are {ordinal_word(int(my['rank']))} of {n} on {int(my.live_pts)} points{prev_line}. {my_moves_line}</p>
{standings}

<h2>Why second place is not really second place</h2>
<p>A mid-gameweek table flatters whoever happens to have played more of their squad. You have had
{my_played} of your {my_total} starters play. {least_played_name} has had {least_played_n}.</p>
<p>To compare fairly, give every manager's remaining players the league average of
{ppu:.1f} points each and see where the table lands. On that basis you are
<span class="k">{ordinal_word(int(my.proj_rank))}</span>, not {ordinal_word(int(my['rank']))}.</p>
{proj_table}
<p>This is a levelling assumption, not a forecast. It does not know which players are left or who
they face. Its only job is to stop you reading a lead that is really just a scheduling accident.</p>
<p>This is the same trap I fell into in Gameweek 1, when I told you the finishing order was settled
after checking only the managers nearest you. Karan Yohannan then gained 25 points in the final
match and climbed from fifteenth to join you. The fix is to always count what is still to come
across the whole table.</p>

<h2>The league mostly stood still</h2>
<p><span class="k">{quiet} of the {n} managers made no change to their squad.</span>
{len(movers)} moved. {my_group_line}</p>
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
<p><span class="k">{top_global[0]['web_name']} is the most-bought player in the game right now</span>,
on {top_global[0]['transfers_in_event']:,} transfers in after scoring
{top_global[0]['event_points']} points this gameweek. In your league he is owned by
{int(owners.get(top_global[0]['id'], 0))} of the {n} managers.</p>
<p><span class="k">The national number is never your number.</span> Your rank depends only on these 22
people, so a move that looks enormous across the whole game can be almost invisible here. Bandwagons
also move faster than a transfer can pay for itself: Sangaré led this list two weeks ago on about
176,000 buyers and is now on {sangare['transfers_in_event']:,}, owned by {s_owners} of your {n}.</p>

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
                   remaining, gw=None) -> str:
    """Appendix for a completed gameweek. Every claim is computed, not written
    by hand, so it cannot carry last week's facts into this week's report."""
    my = b[b.entry == me].iloc[0]
    n = len(b)
    leader = b.nsmallest(1, "rank").iloc[0]
    avg = b.live_pts.mean()
    delta = my.live_pts - avg
    versus_avg = (f"above it by {delta:.1f}" if delta >= 0
                  else f"below it by {abs(delta):.1f}")

    def table(rows, head):
        h = "".join(f"<th>{c}</th>" for c in head)
        out = []
        for r in rows:
            cls = " class='me'" if r.get("me") else ""
            out.append(f"<tr{cls}>" + "".join(f"<td>{v}</td>" for v in r["cells"]) + "</tr>")
        return f"<table><thead><tr>{h}</tr></thead><tbody>{''.join(out)}</tbody></table>"

    # --- what changed since the previous snapshot -------------------------
    movement = ""
    if prev is not None and (prev.entry == me).any():
        pr = int(prev[prev.entry == me]["rank"].iloc[0])
        pp = int(prev[prev.entry == me].live_pts.iloc[0])
        direction = ("climbed from" if int(my["rank"]) < pr else
                     "slipped from" if int(my["rank"]) > pr else "held")
        movement = (f" You {direction} {ordinal_word(pr)} on {pp} points at my previous look."
                    if direction != "held"
                    else f" You held {ordinal_word(pr)}, from {pp} points.")
    gap_note = ""
    if gap_before is not None and old_leader is not None:
        old_name = b[b.entry == old_leader].manager.iloc[0]
        verb = ("closed" if gap_now < gap_before else
                "widened" if gap_now > gap_before else "held")
        gap_note = (f"<p>Against {old_name}, who led at my previous look, the gap "
                    f"<span class=\"k\">{verb} from {gap_before} points to {gap_now}"
                    f"</span>.</p>")

    prev_pts = dict(zip(prev.entry, prev.live_pts)) if prev is not None else {}
    standings = table([
        {"cells": [int(r["rank"]), r.manager, int(r.live_pts),
                   f"+{int(r.live_pts - prev_pts[r.entry])}" if r.entry in prev_pts else "&mdash;",
                   (r.chip or "&mdash;").replace("bboost", "Bench Boost").replace(
                       "wildcard", "Wildcard").replace("freehit", "Free Hit").replace(
                       "3xc", "Triple Captain") if isinstance(r.chip, str) else "&mdash;"],
         "me": r.entry == me}
        for _, r in b.sort_values("rank").iterrows()],
        ["#", "Manager", "Season points", "This gameweek", "Chip"])

    # --- the template -----------------------------------------------------
    delivered = tmpl[tmpl.gw_points > 2].sort_values("gw_points", ascending=False)
    club_note = ""
    if len(delivered) and delivered.club.nunique() <= 2:
        clubs = " and ".join(sorted(delivered.club.unique()))
        club_note = (f" Every one of them plays for {clubs}. If you did not own "
                     f"{clubs} players this week, you had a bad week.")
    tmpl_rows = table([
        {"cells": [r["name"], r.pos, r.club, f"{r.own_pct:.0f}%", f"{r.eo_pct:.0f}%",
                   int(r.gw_points),
                   "Yes" if r.element in set(df[df.entry == me].element) else "No"],
         "me": r.element in set(df[df.entry == me].element)}
        for _, r in tmpl.sort_values("gw_points", ascending=False).iterrows()],
        ["Player", "Position", "Club", "Owned by", "Counting captains", "Points", "You own?"])

    # --- my squad ---------------------------------------------------------
    squad = df[df.entry == me].copy()
    squad["counted"] = squad.multiplier * squad.gw_points
    squad = squad.sort_values("gw_points", ascending=False)
    started = squad[squad.multiplier > 0]
    top_scorers = started.nlargest(3, "gw_points")
    scorer_line = ", ".join(f"{r['name']} {int(r.gw_points)}" for _, r in top_scorers.iterrows())
    dearest = started.nlargest(2, "price")
    dear_line = (f"Your two most expensive starters, {' and '.join(dearest['name'])}, cost "
                 f"£{dearest.price.sum():.1f}m together and scored "
                 f"{int(dearest.gw_points.sum())} points between them.")
    bench = squad[squad.multiplier == 0].nlargest(2, "gw_points")
    bench_line = ", ".join(f"{r['name']} got {int(r.gw_points)}" for _, r in bench.iterrows())
    would_be = int(my.live_pts) + bench_pts
    bb_rank = int((b.live_pts > would_be).sum()) + 1
    squad_rows = table([
        {"cells": [r["name"], r.pos, r.club, f"£{r.price:.1f}m",
                   "Captain" if r.is_captain else ("Started" if r.multiplier else "Bench"),
                   int(r.gw_points), int(r.counted)],
         "me": bool(r.multiplier)}
        for _, r in squad.iterrows()],
        ["Player", "Position", "Club", "Price", "Role", "Scored", "Counted for you"])

    # --- chips ------------------------------------------------------------
    chip_section = ""
    played_chips = b[b.chip.notna() & (b.chip != "")]
    if len(played_chips):
        rows = ", ".join(f"{r.manager} ({CHIP_NAMES.get(r.chip, r.chip)})"
                         for _, r in played_chips.iterrows())
        best_no_chip = b[b.chip.isna()].nsmallest(1, "rank").iloc[0]
        chip_section = f"""
<h2>Chips</h2>
<p>{len(played_chips)} manager{'s' if len(played_chips) != 1 else ''} played a chip this week:
{rows}. The best manager who kept theirs is {best_no_chip.manager} in
{ordinal_word(int(best_no_chip['rank']))}.</p>
<p>Everyone gets the same chips. Playing one early is a bet on a high-scoring week. It does not make
those managers better, it means they have one fewer left, and you still hold yours.</p>
"""

    top_rows = table([
        {"cells": [i + 1, r.manager, f"{int(r.median_rank):,}",
                   int(b[b.entry == r.entry]["rank"].iloc[0]),
                   int(b[b.entry == r.entry].live_pts.iloc[0])],
         "me": r.entry == me}
        for i, (_, r) in enumerate(hist[hist.seasons >= 4].nsmallest(6, "median_rank").iterrows())],
        ["#", "Manager", "Median finish", "Rank now", "Season points"])
    t5 = sorted(int(b[b.entry == e]["rank"].iloc[0]) for e in top5.entry)
    t5_line = ", ".join(ordinal_word(r) for r in t5[:-1]) + f" and {ordinal_word(t5[-1])}"

    gw_label = f"Gameweek {gw}" if gw else "the gameweek"
    text = f"""
<h2>How {gw_label} finished</h2>
<p>You finished <span class="k">{ordinal_word(int(my['rank']))} of {n} on
{int(my.live_pts)} season points</span>. The league averaged {avg:.1f}, so you are
{versus_avg}.{movement}</p>
{gap_note}
<p>{leader.manager} leads on {int(leader.live_pts)}.</p>
{standings}

<h2>What the template did</h2>
<p>The template is the group of players most managers own.
<span class="k">{blanks} of the 15 most-owned players scored 2 points or fewer</span>, and the
average was {tmpl.gw_points.mean():.1f}.</p>
{tmpl_rows}
<p>{len(delivered)} of them beat 2 points.{club_note}</p>
<p>Your own captain, {my_cap}, was owned by {tmpl[tmpl.name == my_cap].own_pct.iloc[0]:.0f}% of the
league and captained by {cap_n} of {n} managers. He returned
<span class="k">{cap_pts} points</span>, which the armband turned into {cap_pts * 2} for you.</p>

<h2>Your own team</h2>
{squad_rows}
<p>Your points came mostly from {scorer_line}. {dear_line}</p>
<p><span class="k">Your bench scored {bench_pts} points you could not use.</span> {bench_line}. Had
you played a Bench Boost this week you would be on {would_be} points and
{ordinal_word(bb_rank)}.</p>
{chip_section}
<h2>What the best managers did</h2>
<p>I ranked every manager by their median finish over the last five seasons, because the median
rewards being good every year rather than one lucky season.</p>
{top_rows}
<p>The five most consistent managers sit {t5_line}. <span class="k">A single gameweek tells you
almost nothing about who is good.</span></p>
<p>The durable pattern is the money. Those five carry about
£{b[b.entry.isin(top5.entry)].MID.mean():.1f}m in midfield against your £{my.MID:.1f}m, a gap of
<span class="k">£{mid_gap:.1f}m</span>, and keep defence near
£{b[b.entry.isin(top5.entry)].DEF.mean():.1f}m against your £{my.DEF:.1f}m.</p>

<h2>Where the numbers come from</h2>
<p>The official Fantasy Premier League API, pulled after every match in {gw_label} finished. Rebuild
them with <code>scripts/league_report.py</code> then <code>scripts/league_story.py</code>. The raw
responses are archived under <code>data/snapshots/</code>, because the API deletes them when the
season rolls over.</p>
"""
    return f'<div class="appendix"><h1>Appendix</h1>{textwrap.dedent(text)}</div>'


if __name__ == "__main__":
    main()
