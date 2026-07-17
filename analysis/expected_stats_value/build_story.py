"""Build the six simple charts for the expected-stats data story.

Charts go from simple to complex:
  1 (univariate)   how lumpy weekly attacker points are  -> motivates a steadier signal
  2 (bivariate)    which trailing signal predicts the next 4 GWs best, for attackers
  3 (segmented)    the same test split by position: attackers vs defenders/GK
  4 (horizon)      the xGI-minus-form edge at 4 and 8 gameweeks, with error bars
  5 (payoff)       forward points of your top-8 attacker picks by form vs xGI vs blend
  6 (case study)   Bruno Guimaraes: form went cold while involvement stayed warm
Run from the repo root:  python3 analysis/expected_stats_value/build_story.py
"""
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from panel import build, D
from model import sp, block_boot

OUT = os.path.join(REPO, "outputs", "charts")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    'figure.dpi': 110, 'savefig.dpi': 150, 'font.size': 11,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.titlesize': 13, 'axes.titleweight': 'bold',
    'axes.edgecolor': '#888', 'xtick.color': '#555', 'ytick.color': '#555',
    'axes.labelcolor': '#333', 'text.color': '#222', 'font.family': 'DejaVu Sans',
})
GREY   = '#B7BEC7'
MUTED  = '#6C7A89'
FORM_C = '#6C7A89'   # recent form (the old way)
XGI_C  = '#8E44AD'   # expected involvement (the hero signal)
ICT_C  = '#B79CD8'   # ICT (almost the same as xGI)
FIX_C  = '#E08E0B'   # fixtures
BLEND_C = '#3F9A56'  # form + xGI together (the practical win)
BAD    = '#C0392B'

def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("saved", path)

# panels
p4 = build(4)
att4 = p4[p4.pos.isin(["MID", "FWD"])].copy()
defn4 = p4[p4.pos.isin(["DEF", "GKP"])].copy()

# ----------------------------------------------------------------------------
# Chart 1: weekly attacker points are lumpy (histogram)
# ----------------------------------------------------------------------------
wk = D[(D.position_short.isin(["MID", "FWD"])) & (D.minutes >= 45)]["total_points"]
fig, ax = plt.subplots(figsize=(7.2, 4.0))
ax.hist(wk, bins=range(-2, 22), color=GREY, edgecolor='white')
ax.axvline(wk.mean(), color=BAD, lw=2)
ax.text(wk.mean() + 0.4, ax.get_ylim()[1]*0.9, f"average {wk.mean():.1f}", color=BAD, fontsize=10)
ax.set_title("Most weeks an attacker scores little. Big weeks are rare.")
ax.set_xlabel("Points in one gameweek (attackers who played)")
ax.set_ylabel("Number of gameweeks")
ax.set_yticks([])
save(fig, "xstat_01_points_are_lumpy.png")

# ----------------------------------------------------------------------------
# Chart 2: which trailing signal predicts the next 4 GWs best (attackers)
# ----------------------------------------------------------------------------
sig = [("Recent form (3 games)", "form3", FORM_C),
       ("Recent form (5 games)", "form5", FORM_C),
       ("ICT index", "ict", ICT_C),
       ("Expected involvement (xGI)", "xgi", XGI_C)]
r = block_boot(att4, {k: (lambda d, c=c: sp(d, c)) for _, c, _ in sig for k in [c]}, B=1000)
fig, ax = plt.subplots(figsize=(7.6, 4.0))
y = np.arange(len(sig))
for i, (lab, c, col) in enumerate(sig):
    b, lo, hi = r[c]
    ax.barh(i, b, color=col, height=0.6, zorder=2)
    ax.plot([lo, hi], [i, i], color='#333', lw=1.6, zorder=3)
    ax.text(hi + 0.006, i, f"{b:.2f}", va='center', fontsize=10, color='#333')
ax.set_yticks(y)
ax.set_yticklabels([s[0] for s in sig])
ax.set_xlabel("How well the signal ranks the next 4 gameweeks (higher is better)")
ax.set_title("For attackers, expected involvement beats recent form")
ax.set_xlim(0, 0.24)
ax.invert_yaxis()
save(fig, "xstat_02_signal_strength_attackers.png")

# ----------------------------------------------------------------------------
# Chart 3: split by position (attackers vs defenders/GK)
# ----------------------------------------------------------------------------
def three(df):
    rr = block_boot(df, {"form5": lambda d: sp(d, "form5"),
                         "xgi": lambda d: sp(d, "xgi"),
                         "fix": lambda d: -sp(d, "fdr")}, B=800)  # easier fixtures -> more points
    return {k: rr[k][0] for k in rr}
A, Dd = three(att4), three(defn4)
labels = ["Recent form", "Expected\ninvolvement (xGI)", "Easy fixtures"]
keys = ["form5", "xgi", "fix"]
cols = [FORM_C, XGI_C, FIX_C]
fig, ax = plt.subplots(figsize=(7.8, 4.2))
x = np.arange(2)
w = 0.26
for j, (k, col) in enumerate(zip(keys, cols)):
    vals = [A[k], Dd[k]]
    ax.bar(x + (j-1)*w, vals, width=w, color=col, zorder=2,
           label=labels[j].replace("\n", " "))
    for xi, v in zip(x + (j-1)*w, vals):
        ax.text(xi, v + 0.004, f"{v:.2f}", ha='center', fontsize=9, color='#333')
ax.set_xticks(x)
ax.set_xticklabels(["Attackers (MID, FWD)", "Defenders and keepers"])
ax.set_ylabel("How well the signal ranks\nthe next 4 gameweeks")
ax.set_title("Expected involvement helps attackers. Fixtures help defenders.")
ax.legend(frameon=False, fontsize=9, loc='upper right')
ax.set_ylim(0, 0.22)
save(fig, "xstat_03_by_position.png")

# ----------------------------------------------------------------------------
# Chart 4: the xGI-minus-form edge grows over the horizon
# ----------------------------------------------------------------------------
pts = []
for N in [4, 8]:
    a = build(N); a = a[a.pos.isin(["MID", "FWD"])]
    rr = block_boot(a, {"d": lambda x: sp(x, "xgi") - sp(x, "form5")}, B=1000)
    pts.append((N, *rr["d"]))
fig, ax = plt.subplots(figsize=(6.6, 4.0))
xs = [0, 1]
for xi, (N, b, lo, hi) in zip(xs, pts):
    ax.plot([xi, xi], [lo, hi], color=XGI_C, lw=2)
    ax.plot(xi, b, 'o', color=XGI_C, ms=10)
    ax.text(xi + 0.06, b, f"+{b:.2f}", va='center', color=XGI_C, fontsize=11)
ax.axhline(0, color=MUTED, lw=1.2, ls='--')
ax.text(1.35, 0.002, "no edge", color=MUTED, fontsize=9, va='bottom')
ax.set_xticks(xs)
ax.set_xticklabels(["Next 4 gameweeks", "Next 8 gameweeks"])
ax.set_ylabel("Extra ranking skill from xGI\nover recent form")
ax.set_title("The edge from xGI is real, and it grows over a longer window")
ax.set_xlim(-0.3, 1.7)
ax.set_ylim(-0.01, 0.09)
save(fig, "xstat_04_edge_by_horizon.png")

# ----------------------------------------------------------------------------
# Chart 5: practical payoff of top-8 attacker picks
# ----------------------------------------------------------------------------
a = att4.dropna(subset=["form5", "xgi"]).copy()
for c in ["form5", "xgi"]:
    a[c + "_z"] = (a[c] - a[c].mean()) / a[c].std()
a["blend"] = a["form5_z"] + a["xgi_z"]
def topk_fwd(df, col, k=8):
    out = [g.nlargest(k, col)["fwd"].mean() for t, g in df.groupby("t") if len(g) >= k + 2]
    return np.mean(out)
vals = [topk_fwd(a, "form5"), topk_fwd(a, "xgi"), topk_fwd(a, "blend")]
avg = att4["fwd"].mean()
fig, ax = plt.subplots(figsize=(7.0, 4.0))
names = ["Pick by\nrecent form", "Pick by\nxGI", "Pick by\nform + xGI"]
colors = [FORM_C, XGI_C, BLEND_C]
bars = ax.bar(names, vals, color=colors, zorder=2, width=0.6)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width()/2, v + 0.03, f"{v:.2f}", ha='center', fontsize=11, color='#333')
ax.axhline(avg, color=MUTED, lw=1.4, ls='--')
ax.text(1, avg - 0.14, f"average attacker {avg:.2f}", color=MUTED, fontsize=9, ha='center')
ax.set_ylabel("Points per game over the next 4 gameweeks")
ax.set_title("Your top 8 attackers score more when xGI helps choose them")
ax.set_ylim(avg - 0.6, max(vals) + 0.4)
save(fig, "xstat_05_top8_payoff.png")

# ----------------------------------------------------------------------------
# Chart 6: Bruno Guimaraes case study
# ----------------------------------------------------------------------------
g = D[D.player_id == 488].sort_values("gameweek")
gw = g["gameweek"].values
form = g["total_points_roll3_mean_prior"].values
ict = g["ict_index_roll3_mean_prior"].values
fig, ax = plt.subplots(figsize=(8.2, 4.2))
ax.axvspan(18.5, 21.5, color=GREY, alpha=0.35, zorder=0)
ax.plot(gw, form, '-o', color=FORM_C, ms=4, lw=2, label="Recent form (points, last 3 games)")
ax.plot(gw, ict, '-o', color=XGI_C, ms=4, lw=2, label="Involvement (ICT, last 3 games)")
ax.text(20, ax.get_ylim()[1]*0.94, "3 big weeks:\nGW19-21", ha='center', fontsize=9, color='#333')
ax.annotate("Going in: form cold (1.7),\ninvolvement still warm (5.9)",
            xy=(19, 5.9), xytext=(23.5, 11.5), fontsize=9, color='#333',
            arrowprops=dict(arrowstyle='->', color='#888'))
ax.set_xlabel("Gameweek")
ax.set_ylabel("Trailing 3-game average")
ax.set_title("Bruno's form went cold, but his involvement stayed warm")
ax.legend(frameon=False, fontsize=9, loc='upper left')
save(fig, "xstat_06_bruno.png")

print("\nall charts built.")
