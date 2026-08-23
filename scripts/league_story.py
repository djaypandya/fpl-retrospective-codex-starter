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


def slide_standings(b, me):
    d = b.sort_values("live_pts", ascending=False)
    colours = [YOU if e == me else REST for e in d.entry]
    return svg(bars(d.manager.tolist(), d.live_pts.tolist(), colours,
                    xlabel="Points so far in Gameweek 1"))


def slide_still_to_play(b, me):
    d = b.sort_values("pct_left", ascending=False)
    colours = [YOU if e == me else REST for e in d.entry]
    return svg(bars(d.manager.tolist(), d.pct_left.tolist(), colours,
                    fmt="{:.0f}%", xlabel="Share of your score still to be played"))


def slide_head_to_head(df, me, rival):
    """A two-column dot chart: who each of us still has on the pitch."""
    rival_name = df[df.entry == rival].manager.iloc[0]
    mine = dict(df[(df.entry == me) & (df.multiplier > 0) & (~df.played)]
                .set_index("name").multiplier)
    theirs = dict(df[(df.entry == rival) & (df.multiplier > 0) & (~df.played)]
                  .set_index("name").multiplier)
    players = sorted(set(mine) | set(theirs), key=lambda p: (-mine.get(p, 0), p))

    fig, ax = plt.subplots(figsize=(10.4, 5.0))
    for i, p in enumerate(players):
        for x, (src, colour) in enumerate([(mine, YOU), (theirs, REST)]):
            m = src.get(p, 0)
            if m:
                ax.scatter(x, i, s=560, color=colour, zorder=3)
                ax.text(x, i, f"{m}x" if m > 1 else "", ha="center", va="center",
                        fontsize=11, color="white", fontweight="bold", zorder=4)
            else:
                ax.scatter(x, i, s=560, facecolor="none", edgecolor="#e6e4de",
                           linewidth=1.6, zorder=3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["You", rival_name], fontsize=13, fontweight="bold")
    ax.xaxis.set_ticks_position("top"); ax.xaxis.set_label_position("top")
    ax.tick_params(axis="x", colors=INK, pad=12, length=0)
    ax.set_yticks(range(len(players)))
    ax.set_yticklabels(players, fontsize=12)
    ax.invert_yaxis()
    ax.set_xlim(-0.6, 1.9); ax.set_ylim(len(players) - 0.4, -0.9)
    ax.text(1.62, 0, "2x = captain,\nscores double", fontsize=10.5, color=MUTED,
            va="center", ha="left")
    return svg(fig)


def slide_template(b, me):
    d = b.sort_values("template_owned", ascending=False)
    colours = [YOU if e == me else REST for e in d.entry]
    return svg(bars(d.manager.tolist(), d.template_owned.tolist(), colours,
                    xlabel="How many of the league's 15 most-owned players each manager holds"))


def slide_midfield(b, me):
    d = b.sort_values("MID", ascending=False)
    colours = [YOU if e == me else (TOP if g == "top5" else REST)
               for e, g in zip(d.entry, d.grp)]
    return svg(bars(d.manager.tolist(), d.MID.tolist(), colours, fmt="£{:.1f}m",
                    xlabel="Spend on midfielders in the starting eleven"))


def slide_defence(b, me):
    d = b.sort_values("DEF", ascending=True)
    colours = [YOU if e == me else (TOP if g == "top5" else REST)
               for e, g in zip(d.entry, d.grp)]
    fig = bars(d.manager.tolist(), d.DEF.tolist(), colours, fmt="£{:.1f}m",
               xlabel="Spend on defenders in the starting eleven")
    ax = fig.axes[0]
    ax.axvline(17.0, color=MUTED, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)
    ax.text(17.25, -0.85, "£17m", fontsize=11, color=MUTED, va="center")
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


def slide_risk(risk):
    d = risk.copy()
    d["cost"] = d.net.abs()
    d = d.sort_values("cost", ascending=False).head(8)
    colours = [TOP if c == "LIV" else REST for c in d.club]
    labels = [f"{n}  ({c})" for n, c in zip(d.name, d.club)]
    fig = bars(labels, d.cost.tolist(), colours, fmt="{:.2f}",
               xlabel="Ground you lose for every point this player scores")
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
    risk = pd.read_csv(src / "exposure.csv")
    me = args.entry

    left = df[~df.played & (df.multiplier > 0)].groupby("entry").multiplier.sum()
    total = df[df.multiplier > 0].groupby("entry").multiplier.sum()
    b["pct_left"] = b.entry.map((100 * left / total).round(0)).fillna(0)
    b["template_owned"] = b.entry.map(
        df[df.element.isin(set(tmpl.element))].groupby("entry").size()).fillna(0).astype(int)
    top5 = hist[hist.seasons >= 4].nsmallest(5, "median_rank")
    b["grp"] = b.entry.map(lambda e: "me" if e == me else
                           ("top5" if e in set(top5.entry) else "rest"))

    my = b[b.entry == me].iloc[0]
    leaders = b.nlargest(2, "live_pts")
    rival = int(leaders[leaders.entry != me].iloc[0].entry)
    gap = int(leaders.live_pts.max() - my.live_pts)
    live_risk = risk[(~risk.played) & (risk.my_mult == 0)]
    mid_gap = b[b.grp == "top5"].MID.mean() - my.MID

    foot = f"Gameweek {args.gw}, 6 of 10 matches played. Scores are not final."
    slides = [
        (f"You sit {int(my['rank'])}th of {len(b)}, {gap} points behind the leaders",
         slide_standings(b, me), foot),
        ("Half your points are still to come, and the leaders have almost none left",
         slide_still_to_play(b, me), foot),
        ("Every player the leader has left is also in your team",
         slide_head_to_head(df, me, rival), foot + " You captain Haaland. He does not."),
        (f"You own only {int(my.template_owned)} of the league's 15 most-popular players",
         slide_template(b, me), foot),
        ("You spend the second-least on midfield in the whole league",
         slide_midfield(b, me), foot + " Orange marks the five most consistent managers."),
        ("The five most consistent managers all keep defence under £17m",
         slide_defence(b, me), foot + " Orange marks those five managers."),
        (f"Those managers put £{mid_gap:.0f}m more than you into midfield",
         slide_allocation(b, me), foot),
        ("Your two biggest remaining risks both play for Liverpool",
         slide_risk(live_risk), foot + " Orange marks Liverpool players."),
    ]
    cover = {
        "eyebrow": f"Gameweek {args.gw} &middot; Buy-in Baller League",
        "title": "How your team stacks up",
        "sub": (f"{my.manager} &middot; {len(b)} managers. Read the titles alone and you have "
                "the whole story. The appendix holds the detail."),
    }
    appendix = build_appendix(b, df, hist, tmpl, live_risk, me, rival, gap, mid_gap, top5)

    html = REPO / "outputs" / f"league_{args.league}_gw{args.gw}" / "story.html"
    html.write_text(build_html(slides, cover, appendix))
    pdf = REPO / args.out
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", f"file://{html}"],
                   check=True, capture_output=True, timeout=180)
    print(f"wrote {pdf} ({pdf.stat().st_size/1024:.0f} KB) and {html}")


def build_appendix(b, df, hist, tmpl, live_risk, me, rival, gap, mid_gap, top5) -> str:
    my = b[b.entry == me].iloc[0]
    rival_name = b[b.entry == rival].manager.iloc[0]

    def table(rows, head):
        h = "".join(f"<th>{c}</th>" for c in head)
        body = "".join("<tr class='me'>" if r[0] == "__me__" else "<tr>"
                       for r in [])  # placeholder, replaced below
        out = []
        for r in rows:
            cls = " class='me'" if r.get("me") else ""
            cells = "".join(f"<td>{v}</td>" for v in r["cells"])
            out.append(f"<tr{cls}>{cells}</tr>")
        return f"<table><thead><tr>{h}</tr></thead><tbody>{''.join(out)}</tbody></table>"

    standings = table([
        {"cells": [int(r["rank"]), r.manager, int(r.live_pts), f"{r.pct_left:.0f}%",
                   f"£{r.DEF:.1f}m", f"£{r.MID:.1f}m", f"£{r.FWD:.1f}m"],
         "me": r.entry == me}
        for _, r in b.sort_values("rank").iterrows()],
        ["#", "Manager", "Points", "Still to play", "Defence", "Midfield", "Attack"])

    tmpl_rows = table([
        {"cells": [r["name"], r.pos, r.club, f"{r.own_pct:.0f}%", f"{r.eo_pct:.0f}%",
                   "Yes" if r.element in set(df[df.entry == me].element) else "No"],
         "me": r.element in set(df[df.entry == me].element)}
        for _, r in tmpl.iterrows()],
        ["Player", "Position", "Club", "Owned by", "Counting captains", "You own?"])

    top_rows = table([
        {"cells": [i + 1, r.manager, f"{int(r.median_rank):,}", r.detail],
         "me": r.entry == me}
        for i, (_, r) in enumerate(hist[hist.seasons >= 4].nsmallest(6, "median_rank").iterrows())],
        ["#", "Manager", "Median finish", "Last five seasons"])

    risk_rows = table([
        {"cells": [r["name"], r.club, f"{abs(r.net):.2f}"], "me": False}
        for _, r in live_risk.assign(c=live_risk.net.abs()).nlargest(8, "c").iterrows()],
        ["Player", "Club", "Cost to you per point"])

    text = f"""
<h2>Where you stand</h2>
<p>You are {int(my['rank'])}th of {len(b)} managers with {int(my.live_pts)} points. The leaders have
{int(my.live_pts) + gap}. That gap looks bad, but it hides something important. Only six of the ten
matches have been played. Four have not started yet.</p>
<p><span class="k">Half of your score is still to come.</span> You have six scoring units left. The
two leaders have three each. A scoring unit is one player, counted twice if you captained him.</p>
<p>Against {rival_name}, one of the two leaders, you cannot fall further behind. Every player he has
left, you also own. You captain Haaland and he does not, so Haaland earns you double what he earns
him. Only a red card could change that.</p>

<h2>The template team</h2>
<p>The template is the group of players most managers own. When you own them, you move with the
crowd. When you do not, you win or lose ground quickly. You own 6 of the 15. That puts you joint
14th of 22 for template coverage, so you are one of the more contrarian managers in this league.</p>
{tmpl_rows}
<p>Three players are yours alone in this league. Nobody else owns Vuskovic, Ampadu or Mitchell.</p>

<h2>How everyone spends their money</h2>
<p>This is the money each manager put into their starting eleven, split by position. Three managers
played Bench Boost, so I measured everyone on the same eleven slots to keep it fair.</p>
{standings}
<p>You spend <span class="k">£{my.MID:.1f}m on midfield</span>, the second-lowest in the league. You
spend <span class="k">£{my.FWD:.1f}m on attack</span>, the second-highest. That is Haaland. He costs
£15.5m, which is half your attack budget, and paying for him is why your midfield is thin.</p>

<h2>What the best managers do</h2>
<p>I ranked every manager by their median finish over the last five seasons. I used the median
because it rewards being good every year, not one lucky season. Kieren Khatri comes third, which
matches the example you gave me, so the measure is picking up the right thing.</p>
{top_rows}
<p>You sit sixth. Your best season was a 49k finish, so your ceiling is not the problem. Your
results simply swing a lot from year to year.</p>
<p>One habit stands out. <span class="k">All five of the best managers keep defence between £14.5m
and £16.5m.</span> Every single one. The rest of the league averages £20.8m. They then pour that
money into midfield, between £30.5m and £42.5m. You spend £{my.DEF:.1f}m on defence and
£{my.MID:.1f}m on midfield. That is a £{mid_gap:.1f}m midfield gap against the people who win most often.</p>
<p>Five players show up in three or more of their teams that you do not own: Bruno Fernandes,
Mbeumo, Wirtz, Schade and Calvert-Lewin. Four of those five play in midfield.</p>
<div class="note"><strong>Be careful with this.</strong> This is one gameweek. I tested whether
spending more on any position actually links to more points so far, and nothing is solid yet. Every
result could easily be chance, and the biggest attackers have not played. Check this again after ten
weeks. That is when a pattern would mean something.</div>

<h2>Your biggest risks</h2>
<p>A player hurts you when your rivals own him and you do not. I measured it by asking a simple
question: for every point this player scores, how much ground do I lose to the average rival?</p>
<p>Your largest threat already passed. <span class="k">Bruno Fernandes returned 2 points.</span> He
was owned by 64% of the league and captained by five managers. He blanked. That was a big win for
you and you did not have to do anything.</p>
<p>These players have not kicked a ball yet, so they are the live danger.</p>
{risk_rows}
<p>Three of your top seven threats play for Liverpool, in the same match against Newcastle. You own
none of them. You do own Virgil van Dijk and Szoboszlai, so a Liverpool clean sheet still pays you.</p>
<p>Two thirds of the league captained Haaland, including you. That means a big Haaland score
<em>protects</em> you more than it promotes you. You keep pace with most of the league, but you do
not gain. Your gains have to come from your other players.</p>

<h2>What to do next</h2>
<p>Do not change anything because of one gameweek. Instead, watch one number. The best managers in
your league put about £34m into midfield and keep defence near £15m. You are at £{my.MID:.1f}m and
£{my.DEF:.1f}m. Track that gap over the next few weeks. If the pattern holds once real data builds
up, moving money from defence into midfield is the single change most likely to move you up.</p>

<h2>Where the numbers come from</h2>
<p>Everything here comes from the official Fantasy Premier League API, pulled live during Gameweek 1
with six of ten matches played and none finalised. Bonus points and scores can still change. You can
rebuild every number by running <code>scripts/league_report.py</code> and then
<code>scripts/league_story.py</code>.</p>
"""
    return f'<div class="appendix"><h1>Appendix</h1>{textwrap.dedent(text)}</div>'


if __name__ == "__main__":
    main()
