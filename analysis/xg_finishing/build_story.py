"""Build the charts for the 'xG vs Goals: buy the xG, fade the overperformance' story.

Charts go simple to complex:
  1 (relationship) xG tracks goals over a season, but barely in a single match
  2 (persistence)  finishing over/underperformance does not repeat (odd vs even halves)
  3 (the payoff)   trailing xG predicts forward goals ~2x better than trailing goals;
                   trailing overperformance predicts nothing

Everything is leak-free: trailing/forward windows use only played matches (minutes>=45),
strictly before / from the decision match, in each player's own time order.
Run from the repo root:  python3 analysis/xg_finishing/build_story.py
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, pearsonr

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(REPO, "outputs", "charts")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    'figure.dpi': 110, 'savefig.dpi': 150, 'font.size': 11,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.titlesize': 13, 'axes.titleweight': 'bold',
    'axes.edgecolor': '#888', 'xtick.color': '#555', 'ytick.color': '#555',
    'axes.labelcolor': '#333', 'text.color': '#222', 'font.family': 'DejaVu Sans',
})
GREY, MUTED = '#B7BEC7', '#6C7A89'
XG_C = '#2E86C1'    # xG (the hero signal)
GOAL_C = '#6C7A89'  # raw goals (the noisy old way)
OP_C = '#C0392B'    # overperformance (the trap)
REF = '#B7BEC7'
GATE = 45


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("saved", path)


D = pd.read_csv(os.path.join(REPO, "data/processed/player_gw_features.csv"))
played = D[D.minutes >= GATE].copy()

# ---------------------------------------------------------------------------
# Chart 1: xG tracks goals over a season, not in a single match
# ---------------------------------------------------------------------------
season = (played.groupby('web_name')
          .agg(G=('goals_scored', 'sum'), xG=('expected_goals', 'sum'),
               m=('minutes', 'size')).query('m>=10'))
r_match = pearsonr(played.expected_goals, played.goals_scored)[0]
r_season = pearsonr(season.xG, season.G)[0]

fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.6))
# left: single match
ax = axes[0]
jx = played.expected_goals + np.random.default_rng(0).normal(0, 0.015, len(played))
jy = played.goals_scored + np.random.default_rng(1).normal(0, 0.06, len(played))
ax.scatter(jx, jy, s=7, color=GREY, alpha=0.25, edgecolor='none')
lim = [0, max(played.expected_goals.max(), played.goals_scored.max()) + 0.2]
ax.plot(lim, lim, color=OP_C, lw=1.3, ls='--')
ax.set_xlim(0, 2.2); ax.set_ylim(-0.2, 3.3)
ax.set_title("One match: mostly luck")
ax.set_xlabel("xG in the match"); ax.set_ylabel("Goals in the match")
ax.text(0.05, 0.93, f"r = {r_match:.2f}", transform=ax.transAxes, fontsize=12,
        color='#333', fontweight='bold')
# right: player-season
ax = axes[1]
ax.scatter(season.xG, season.G, s=26, color=XG_C, alpha=0.55, edgecolor='white', linewidth=0.4)
lim = [0, season[['xG', 'G']].values.max() + 2]
ax.plot(lim, lim, color=OP_C, lw=1.3, ls='--')
ax.set_xlim(0, lim[1]); ax.set_ylim(0, lim[1])
ax.set_title("One season: xG tells the truth")
ax.set_xlabel("Season xG"); ax.set_ylabel("Season goals")
ax.text(0.05, 0.93, f"r = {r_season:.2f}", transform=ax.transAxes, fontsize=12,
        color='#333', fontweight='bold')
ax.text(0.97, 0.06, "dashed line = goals equal xG", transform=ax.transAxes,
        fontsize=8.5, color=MUTED, ha='right')
fig.suptitle("xG matches goals over a season, not in a single game",
             fontsize=13, fontweight='bold', x=0.02, ha='left')
fig.tight_layout(rect=[0, 0, 1, 0.95])
save(fig, "xgf_01_xg_tracks_goals.png")

# ---------------------------------------------------------------------------
# Chart 2: over/underperformance does not repeat (odd vs even matches)
# ---------------------------------------------------------------------------
rows = []
for pid, g in D.sort_values(['player_id', 'gameweek']).groupby('player_id'):
    g = g[g.minutes >= GATE]
    if len(g) < 10 or g.position_short.iloc[0] not in ('MID', 'FWD'):
        continue
    odd, even = g.iloc[::2], g.iloc[1::2]
    rows.append((g.web_name.iloc[0],
                 odd.goals_scored.sum() - odd.expected_goals.sum(),
                 even.goals_scored.sum() - even.expected_goals.sum()))
sh = pd.DataFrame(rows, columns=['name', 'op_odd', 'op_even'])
r_sh = spearmanr(sh.op_odd, sh.op_even).correlation

fig, ax = plt.subplots(figsize=(6.8, 5.4))
ax.axhline(0, color=REF, lw=1)
ax.axvline(0, color=REF, lw=1)
lo, hi = -7, 8
ax.plot([lo, hi], [lo, hi], color=OP_C, lw=1.2, ls='--', zorder=1)
ax.text(hi, hi, "  if finishing were a skill", color=OP_C, fontsize=9, va='center')
ax.scatter(sh.op_odd, sh.op_even, s=34, color=OP_C, alpha=0.5, edgecolor='white', linewidth=0.4, zorder=2)
ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
ax.set_xlabel("Over/underperformance in odd matches (goals - xG)")
ax.set_ylabel("Over/underperformance in even matches")
ax.set_title("A hot finishing half says almost nothing about the other half", pad=30)
ax.text(0, 1.03, f"Each dot is an attacker. The cloud is round, not diagonal.  Correlation = {r_sh:+.2f}",
        transform=ax.transAxes, fontsize=10, color=MUTED)
save(fig, "xgf_02_overperformance_noise.png")

# ---------------------------------------------------------------------------
# build walk-forward windows for chart 3
# ---------------------------------------------------------------------------
def windows(df, k=4):
    rows = []
    for pid, g in df.sort_values(['player_id', 'gameweek']).groupby('player_id'):
        g = g[g.minutes >= GATE]
        if len(g) < 2 * k:
            continue
        G, X, pos, gw = (g.goals_scored.values, g.expected_goals.values,
                         g.position_short.values, g.gameweek.values)
        for i in range(k, len(g) - k + 1):
            rows.append((pos[i], gw[i], G[i-k:i].mean(), X[i-k:i].mean(),
                         G[i-k:i].mean() - X[i-k:i].mean(), G[i:i+k].mean(),
                         G[i:i+k].mean() - X[i:i+k].mean()))
    return pd.DataFrame(rows, columns=['pos', 'gw', 'tG', 'tX', 'tOP', 'fG', 'fOP'])

att = windows(D, 4)
att = att[att.pos.isin(['MID', 'FWD'])].copy()

def block_boot(df, fn, B=1500, seed=0):
    rng = np.random.default_rng(seed)
    gws = df.gw.unique()
    gp = {t: s for t, s in df.groupby('gw')}
    base = fn(df)
    acc = [fn(pd.concat([gp[t] for t in rng.choice(gws, len(gws), replace=True)], ignore_index=True))
           for _ in range(B)]
    return base, np.percentile(acc, 2.5), np.percentile(acc, 97.5)

signals = [
    ("Recent xG\n(last 4 games)", lambda d: spearmanr(d.tX, d.fG).correlation, XG_C),
    ("Recent goals\n(last 4 games)", lambda d: spearmanr(d.tG, d.fG).correlation, GOAL_C),
    ("Recent overperformance\n(goals above xG)", lambda d: spearmanr(d.tOP, d.fOP).correlation, OP_C),
]
res = [(lab, *block_boot(att, fn), col) for lab, fn, col in signals]

# ---------------------------------------------------------------------------
# Chart 3: which recent signal predicts the next 4 games (goals) best
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.6, 4.4))
y = np.arange(len(res))[::-1]
for yi, (lab, b, lo, hi, col) in zip(y, res):
    ax.barh(yi, b, color=col, height=0.58, zorder=2)
    ax.plot([lo, hi], [yi, yi], color='#333', lw=1.6, zorder=3)
    ax.text(hi + 0.012 if b >= 0 else lo - 0.012, yi + 0.34, f"{b:+.2f}",
            va='center', ha='left' if b >= 0 else 'right', fontsize=11, color='#333', fontweight='bold')
ax.axvline(0, color=MUTED, lw=1.2)
ax.set_yticks(y)
ax.set_yticklabels([r[0] for r in res], fontsize=10.5)
ax.set_xlim(-0.12, 0.46)
ax.set_xlabel("How well the recent signal ranks the next 4 games (higher is better)")
ax.set_title("Recent xG predicts future goals; a hot finishing streak predicts nothing", pad=30)
ax.text(0, 1.03, "Attackers, full 2025/26 season. Black lines show the 95% range.",
        transform=ax.transAxes, fontsize=10, color=MUTED)
save(fig, "xgf_03_signal_strength.png")

print("\nall charts built.")
