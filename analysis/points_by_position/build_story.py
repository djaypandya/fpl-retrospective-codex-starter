"""Build the charts for the 'where do points come from, and value by position' story.

Charts go simple to complex:
  1 (composition) where each position's points come from (share of positive points)
  2 (the flip)    absolute points per starter vs points per pound, side by side
  3 (mechanism)   price vs season points scatter -> defenders sit in the value corner

The FPL point components are rebuilt from the 2025/26 scoring rules and validated
against total_points (99.65% exact match; gaps are double-gameweek edge cases).
Run from the repo root:  python3 analysis/points_by_position/build_story.py
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

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
# position colours (consistent across all three charts)
PC = {'GKP': '#E08E0B', 'DEF': '#3F9A56', 'MID': '#8E44AD', 'FWD': '#C0392B'}
POS = ['GKP', 'DEF', 'MID', 'FWD']
PNAME = {'GKP': 'Goalkeepers', 'DEF': 'Defenders', 'MID': 'Midfielders', 'FWD': 'Forwards'}


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("saved", path)


# ---------------------------------------------------------------------------
# Rebuild point components from FPL 2025/26 rules
# ---------------------------------------------------------------------------
D = pd.read_csv(os.path.join(REPO, "data/processed/player_gw_features.csv"))
pos = D.position_short
appr = np.where(D.minutes >= 60, 2, np.where(D.minutes > 0, 1, 0))
comp = pd.DataFrame({
    'pos': pos, 'player_id': D.player_id, 'price': D.price,
    'minutes': D.minutes, 'total_points': D.total_points, 'played': D.played,
    'Appearance': appr,
    'Goals': D.goals_scored * pos.map({'GKP': 6, 'DEF': 6, 'MID': 5, 'FWD': 4}).fillna(4),
    'Assists': D.assists * 3,
    'Clean sheets': D.clean_sheets * pos.map({'GKP': 4, 'DEF': 4, 'MID': 1, 'FWD': 0}).fillna(0),
    'Saves': D.saves // 3,
    'Defensive contribution': D.defensive_contribution_threshold_met.fillna(0).astype(int) * 2,
    'Bonus': D.bonus,
    'Deductions': (np.where(pos.isin(['GKP', 'DEF']), -(D.goals_conceded // 2), 0)
                   + D.yellow_cards * -1 + D.red_cards * -3 + D.own_goals * -2
                   + D.penalties_missed * -2 + D.penalties_saved * 5),
})
POSITIVE = ['Appearance', 'Goals', 'Assists', 'Clean sheets', 'Saves',
            'Defensive contribution', 'Bonus']

# ---------------------------------------------------------------------------
# Chart 1: where each position's points come from (share of positive points)
# ---------------------------------------------------------------------------
g = comp.groupby('pos')[POSITIVE].sum().reindex(POS)
share = g.div(g.sum(1), axis=0) * 100
# colour: appearance is grey context; attacking warm; defensive cool; bonus gold
CMAP = {'Appearance': '#C7CED6', 'Goals': '#C0392B', 'Assists': '#E67E22',
        'Clean sheets': '#3F9A56', 'Saves': '#2E86C1',
        'Defensive contribution': '#8E44AD', 'Bonus': '#D4AC0D'}
fig, ax = plt.subplots(figsize=(9.2, 4.6))
y = np.arange(len(POS))[::-1]
left = np.zeros(len(POS))
for c in POSITIVE:
    vals = share[c].values
    ax.barh(y, vals, left=left, color=CMAP[c], height=0.62, edgecolor='white', linewidth=0.7)
    for yi, (v, l) in enumerate(zip(vals, left)):
        if v >= 6:
            ax.text(l + v / 2, y[yi], f"{v:.0f}", ha='center', va='center',
                    fontsize=9, color='white', fontweight='bold')
    left += vals
ax.set_yticks(y)
ax.set_yticklabels([PNAME[p] for p in POS], fontsize=11)
ax.set_xlim(0, 100)
ax.set_xlabel("Share of a position's positive points (%)")
ax.set_title("Where the points come from changes with the shirt", pad=30)
ax.text(0, 1.03, "Keepers and defenders earn from clean sheets and defending. Forwards earn from goals.",
        transform=ax.transAxes, fontsize=10, color=MUTED)
handles = [Patch(facecolor=CMAP[c], label=c) for c in POSITIVE]
ax.legend(handles=handles, frameon=False, fontsize=8.5, ncol=4,
          loc='lower center', bbox_to_anchor=(0.5, -0.30))
ax.set_xticks([0, 25, 50, 75, 100])
save(fig, "pos_01_composition.png")

# ---------------------------------------------------------------------------
# per-player season aggregates for value
# ---------------------------------------------------------------------------
pl = comp.groupby(['player_id', 'pos']).agg(
    pts=('total_points', 'sum'), mins=('minutes', 'sum'),
    price=('price', 'median')).reset_index()
starters = pl[pl.mins >= 900].copy()
absol = starters.groupby('pos').pts.mean().reindex(POS)
value = (starters.assign(ppm=starters.pts / starters.price)
         .groupby('pos').ppm.mean().reindex(POS))

# ---------------------------------------------------------------------------
# Chart 2: the flip - absolute points vs points per pound
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.4))
cols = [PC[p] for p in POS]
for ax, series, title, unit in [
    (axes[0], absol, "Most points per player", "season points"),
    (axes[1], value, "Most points per pound", "points per £1m")]:
    bars = ax.bar([PNAME[p].split()[0] for p in POS], series.values, color=cols, width=0.66)
    for b, v in zip(bars, series.values):
        ax.text(b.get_x() + b.get_width() / 2, v + max(series) * 0.015,
                f"{v:.0f}" if unit == 'season points' else f"{v:.1f}",
                ha='center', fontsize=10, color='#333', fontweight='bold')
    ax.set_title(title)
    ax.set_ylabel(unit)
    ax.set_ylim(0, max(series) * 1.16)
    ax.margins(x=0.04)
# highlight the reversal: FWD best-ish on left, worst on right; DEF/GK opposite
axes[0].annotate("Forwards lead", xy=(3, absol['FWD']), xytext=(1.4, absol.max() * 1.06),
                 fontsize=9, color=PC['FWD'],
                 arrowprops=dict(arrowstyle='->', color=PC['FWD']))
axes[1].annotate("but forwards trail", xy=(3, value['FWD']), xytext=(1.2, value.max() * 1.06),
                 fontsize=9, color=PC['FWD'],
                 arrowprops=dict(arrowstyle='->', color=PC['FWD']))
fig.suptitle("The ranking flips when you weigh points against price",
             fontsize=13, fontweight='bold', x=0.02, ha='left')
fig.text(0.02, 0.905, "Regular starters (900+ minutes), full 2025/26 season",
         fontsize=10, color=MUTED, ha='left')
fig.tight_layout(rect=[0, 0, 1, 0.9])
save(fig, "pos_02_absolute_vs_value.png")

# ---------------------------------------------------------------------------
# Chart 3: mechanism - price vs season points, defenders in the value corner
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.6, 5.2))
for p in POS:
    s = starters[starters.pos == p]
    ax.scatter(s.price, s.pts, s=26, color=PC[p], alpha=0.55,
               edgecolor='white', linewidth=0.4, label=PNAME[p])
# average value line (points per pound = overall mean), as a faint reference
mean_ppm = (starters.pts / starters.price).mean()
xx = np.linspace(starters.price.min(), starters.price.max(), 50)
ax.plot(xx, mean_ppm * xx, color=MUTED, lw=1.2, ls='--', zorder=0)
ax.text(starters.price.max(), mean_ppm * starters.price.max(),
        "  average value", color=MUTED, fontsize=9, va='center')
ax.set_xlabel("Price (£m)")
ax.set_ylabel("Season points")
ax.set_title("Cheap defenders sit above the value line; pricey forwards fall below it", pad=30)
ax.text(0, 1.03, "Each dot is a regular starter. Above the dashed line is better than average value.",
        transform=ax.transAxes, fontsize=10, color=MUTED)
ax.legend(frameon=False, fontsize=9, loc='upper left')
save(fig, "pos_03_value_scatter.png")

print("\nall charts built.")
