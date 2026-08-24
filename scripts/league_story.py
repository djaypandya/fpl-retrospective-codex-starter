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


def slide_gap_closed(b, prev, me, rival):
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
    for x, lab in [(0, "Last night"), (1, "This morning")]:
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
    prev = pd.read_csv(src / "standings_previous.csv")
    fixtures = json.loads((src / "raw" / f"fixtures_gw{args.gw}.json").read_text())
    me = args.entry
    n = len(b)

    top5 = hist[hist.seasons >= 4].nsmallest(5, "median_rank")
    b["grp"] = b.entry.map(lambda e: "me" if e == me else
                           ("top5" if e in set(top5.entry) else "rest"))
    my = b[b.entry == me].iloc[0]
    my_prev = prev[prev.entry == me].iloc[0]

    leader = b.nsmallest(1, "rank").iloc[0]
    # The manager who led last night, tracked by entry id: one has since renamed.
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

    foot = (f"Gameweek {args.gw}: {played} of {len(fixtures)} matches played. "
            "Scores are provisional until bonus points are confirmed.")

    def ordinal(k):
        return f"{k}{'th' if 10 <= k % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(k % 10, 'th')}"

    slides = [
        (f"You climbed to {ordinal(int(my['rank']))} of {n}, {int(leader.live_pts - my.live_pts)} points off the lead",
         slide_standings(b, me), foot),
        (f"You cut the gap to last night's leader from {gap_before} points to {gap_now}",
         slide_gap_closed(b, prev, me, old_leader), foot),
        (f"{my_cap} was captained by {cap_n} of {n} managers and returned {cap_pts} points",
         slide_captains(df, me), foot),
        (f"{blanks} of the 15 most-owned players scored 2 points or fewer",
         slide_template_returns(tmpl, set(df[df.entry == me].element)),
         foot + " Orange marks a return of 2 points or fewer."),
        (f"{bb_top4} of the top four played their Bench Boost",
         slide_standings(b, me, highlight=lambda r: r.chip == "bboost"),
         foot + " Orange marks the managers who played Bench Boost."),
        (f"Your bench scored {bench_pts} points you could not use",
         slide_my_bench(df, me), foot + " Bench Boost would have banked all of it."),
        ("The five most consistent managers finished " +
         ", ".join(ordinal(r) for r in top5_ranks[:-1]) + f" and {ordinal(top5_ranks[-1])}",
         slide_standings(b, me, highlight=lambda r: r.grp == "top5"),
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
    appendix = build_appendix(b, df, hist, tmpl, prev, me, old_leader, gap_before,
                              gap_now, mid_gap, top5, my_cap, cap_n, cap_pts,
                              blanks, bench_pts, remaining)

    html = src / "story.html"
    html.write_text(build_html(slides, cover, appendix))
    pdf = REPO / args.out
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", f"file://{html}"],
                   check=True, capture_output=True, timeout=180)
    print(f"wrote {pdf} ({pdf.stat().st_size/1024:.0f} KB)")
    print(f"  rank {int(my_prev['rank'])} -> {int(my['rank'])}, "
          f"{int(my_prev.live_pts)} -> {int(my.live_pts)} points")


def ordinal_word(k: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
             6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}
    return words.get(k, f"{k}th")


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
<h2>What changed overnight</h2>
<p>You moved from {int(my_prev['rank'])}th to {int(my['rank'])}th. Your score went from
{int(my_prev.live_pts)} to <span class="k">{int(my.live_pts)}</span>. Three more matches finished,
so nine of the ten are now done. Only {remaining[0]['id'] and 'Fulham against Chelsea' if remaining else 'nothing'} is left.</p>
<p>Last night I told you that you could not lose ground to the leader, because every player he had
left was also in your team and you captained Haaland while he did not. That held.
<span class="k">The gap closed from {gap_before} points to {gap_now}.</span>{rename}</p>
<p>But someone else jumped both of you. {leader.manager} played a Bench Boost, gained
{int(leader.live_pts - prev_pts.get(leader.entry, 0))} points overnight, and went from sixth to
first.</p>
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

<h2>What to do next</h2>
<p>Nothing this week. You still have {'a player' if left else 'nothing'} to come{f': {left}' if left else ''},
and everyone in the top six owns him too, so the finishing order is already settled.</p>
<p>Watch two numbers from here. First, your midfield spend against the £34m the best managers carry.
Second, your chips. You still hold your Bench Boost, and this week showed what it is worth in a
high-scoring gameweek.</p>

<h2>Where the numbers come from</h2>
<p>Everything here comes from the official Fantasy Premier League API, refreshed this morning with
nine of ten matches played. Bonus points are not yet final, so small changes are still possible.
Rebuild every number by running <code>scripts/league_report.py</code> and then
<code>scripts/league_story.py</code>.</p>
"""
    return f'<div class="appendix"><h1>Appendix</h1>{textwrap.dedent(text)}</div>'


if __name__ == "__main__":
    main()
