# %% [markdown]
# # Did the 2018 Loyalty Campaign Work? (Northern Lights Air)
# Analysis of the Feb–Apr 2018 enrollment promotion of an airline loyalty program:
# data cleaning, three SMART KPIs, deep-dive findings, and a 2019 forecast.
#
# Data: `Customer_Loyalty_History.csv` (16,737 members) and
# `Customer_Flight_Activity.csv` (392,936 member-month rows), in `data/`.

# %%
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'data' / 'Customer_Loyalty_History.csv').exists())
D = ROOT / 'data'
hist = pd.read_csv(D / 'Customer_Loyalty_History.csv', encoding='utf-8-sig')
flight = pd.read_csv(D / 'Customer_Flight_Activity.csv', encoding='utf-8-sig')
print(hist.shape, flight.shape)

# %% [markdown]
# ## 1. Data cleaning

# %%
# Fully duplicated activity rows would inflate every count -> drop them
print('exact duplicate rows:', flight.duplicated().sum())
flight = flight.drop_duplicates()

# Several different rows for the same member and month -> sum into one row
num = ['Total Flights', 'Distance', 'Points Accumulated', 'Points Redeemed', 'Dollar Cost Points Redeemed']
print('member-month keys with >1 row:', flight.duplicated(['Loyalty Number', 'Year', 'Month']).sum())
flight = flight.groupby(['Loyalty Number', 'Year', 'Month'], as_index=False)[num].sum()

# Negative salary -> sign typo, take the absolute value
print('negative salaries:', (hist['Salary'] < 0).sum())
hist['Salary'] = hist['Salary'].abs()

# Missing salary is systematic (all 'College' members) -> leave as missing, don't impute a mean
print(hist.loc[hist.Salary.isna(), 'Education'].value_counts())

# Empty cancellation date means "still active", not missing data
print('members with no cancellation (active):', hist['Cancellation Year'].isna().sum())

# Continuous month index makes date arithmetic simple
hist['enr_idx'] = hist['Enrollment Year'] * 12 + hist['Enrollment Month'] - 1
hist['can_idx'] = hist['Cancellation Year'] * 12 + hist['Cancellation Month'] - 1
hist['promo'] = hist['Enrollment Type'].eq('2018 Promotion')
flight['idx'] = flight['Year'] * 12 + flight['Month'] - 1

# Flights recorded before the enrollment date -> flag for review
fx = flight.merge(hist[['Loyalty Number', 'enr_idx', 'can_idx', 'promo']], on='Loyalty Number')
pre = (fx['idx'] < fx['enr_idx']) & (fx['Total Flights'] > 0)
print('flight rows with flights before enrollment:', pre.sum())

# "Active member in a month": enrolled by that month and not cancelled before it
fx['active'] = (fx['idx'] >= fx['enr_idx']) & (fx['can_idx'].isna() | (fx['idx'] <= fx['can_idx']))

# %% [markdown]
# ## 2. Enrollments and cancellations by month

# %%
enroll = hist.groupby(['Enrollment Year', 'Enrollment Month']).size().rename('enrollments')
cancel = hist.groupby(['Cancellation Year', 'Cancellation Month']).size().rename('cancellations')
cancel.index = cancel.index.set_names(['Enrollment Year', 'Enrollment Month'])
monthly = pd.concat([enroll, cancel], axis=1).fillna(0).astype(int)
monthly.index.names = ['year', 'month']
monthly = monthly.loc[2016:2018]
print(monthly.unstack(0)['enrollments'])

# %% [markdown]
# ## 3. Three SMART KPIs
# The case brief set no targets, so every target is derived from **historical data**, not from the results.

# %%
# KPI 1 - Enrollment: members joining Feb–Apr 2018; target = +25% over Feb–Apr 2017
fa = lambda y: monthly.loc[(y, [2, 3, 4]), 'enrollments'].sum()
k1_actual = int(hist['promo'].sum())
k1_target = round(fa(2017) * 1.25)
print(f'KPI1 enroll: actual={k1_actual} target>={k1_target} (Feb-Apr 2017={fa(2017)}) gap={k1_actual/k1_target-1:+.0%}')
print('historical YoY growth Feb-Apr:', f'{fa(2017)/fa(2016)-1:.1%}')

# %%
# KPI 2 - Retention: % cancelled within 10 months of joining.
# A CEILING, not a target: no worse than standard members who joined Feb–Apr 2017 (same time to cancel).
def churn_curve(mask, horizon=10):
    g = hist[mask]
    m = g['can_idx'] - g['enr_idx']
    return pd.Series({k: (m <= k).sum() / len(g) * 100 for k in range(horizon + 1)})

promo_mask = hist['promo']
std17_mask = (~hist['promo']) & hist['Enrollment Year'].eq(2017) & hist['Enrollment Month'].isin([2, 3, 4])
curve = pd.DataFrame({'promo_pct': churn_curve(promo_mask), 'standard_pct': churn_curve(std17_mask)}).round(1)
print(curve)
k2_actual, k2_ceiling = curve.loc[10, 'promo_pct'], curve.loc[10, 'standard_pct']
print(f'KPI2 churn: actual={k2_actual}% ceiling={k2_ceiling}% -> met={k2_actual <= k2_ceiling}')

# %%
# KPI 3 - Activity: flights per active member per month, Jun–Aug; target = +10% over summer 2017
act = fx[fx['active']]
def per_member(df):
    return df['Total Flights'].sum() / len(df)
summer = lambda y, df=act: df[(df.Year == y) & df.Month.isin([6, 7, 8])]
s17, s18 = per_member(summer(2017)), per_member(summer(2018))
s18_std = per_member(summer(2018, act[~act.promo]))
k3_target = round(s17 * 1.10, 2)
print(f'KPI3 summer flights/active member/month: 2017={s17:.3f} 2018={s18:.3f} (standard only 2018={s18_std:.3f}) target>={k3_target}')

smart = pd.DataFrame([
    ['Enrollment', 'Members joined Feb–Apr 2018', f'>= {k1_target}', k1_actual, k1_actual >= k1_target],
    ['Retention', '% cancelled within 10 months (ceiling)', f'<= {k2_ceiling}%', f'{k2_actual}%', k2_actual <= k2_ceiling],
    ['Activity', 'Flights per active member / month, Jun–Aug', f'>= {k3_target}', round(s18, 2), s18 >= k3_target],
], columns=['KPI', 'Metric', 'Target', 'Actual', 'Met'])
print(smart.to_string(index=False))

# %% [markdown]
# ## 4. Findings

# %%
# Flights per active member by month, 2018: promotion vs standard members
a18 = act[act.Year == 2018]
fl = a18.groupby(['Month', 'promo'])['Total Flights'].mean().unstack().round(2)
fl.columns = ['standard', 'promo']
print(fl)
post = a18[a18.Month.between(9, 12)]
ratio_post = per_member(post[post.promo]) / per_member(post[~post.promo])
print(f'Sep-Dec flights ratio promo/standard: x{ratio_post:.1f}')

# %%
# Weight of the campaign in 2018 enrollments and net growth
j18 = hist[hist['Enrollment Year'].eq(2018)]
camp_active_dec = int((promo_mask & hist['can_idx'].isna()).sum())
base_end_2018 = int(hist['can_idx'].isna().sum())
net_growth_2018 = len(j18) - int(hist['Cancellation Year'].eq(2018).sum())
print(f'campaign share of 2018 joiners: {k1_actual/len(j18):.0%}')
print(f'campaign share of net growth 2018: {camp_active_dec/net_growth_2018:.0%}  (net growth={net_growth_2018})')
print(f'campaign share of active base end-2018: {camp_active_dec/base_end_2018:.1%}  (base={base_end_2018})')

# %%
# Promotion members after the bonus ended (flights Sep–Dec 2018)
p = hist[promo_mask][['Loyalty Number', 'can_idx']]
sd = fx[(fx.Year == 2018) & fx.Month.between(9, 12)].groupby('Loyalty Number')['Total Flights'].sum()
p = p.assign(sd=p['Loyalty Number'].map(sd).fillna(0))
p['group'] = np.select([p.sd == 0, p.sd < 5], ['Stopped (0 flights)', 'Low (1-4)'], 'Continued (5+)')
beh = p.groupby('group').agg(members=('sd', 'size'), cancelled=('can_idx', lambda s: s.notna().sum()))
beh['share_pct'] = (beh.members / len(p) * 100).round(1)
beh['churn_pct'] = (beh.cancelled / beh.members * 100).round(1)
print(beh)

# %%
# Segmentation for marketing - adoption index = segment's share of promo joiners / its share of all members (1 = average)
def bracket(s):
    return pd.cut(s, [0, 50000, 75000, 100000, np.inf], right=True,
                  labels=['Under 50K', '50K–75K', '75K–100K', '100K+'])
hist['sal_band'] = bracket(hist['Salary'])
hist['region'] = hist['Province'].where(hist['Province'].isin(['British Columbia', 'Ontario', 'Quebec']), 'Other provinces')
def adoption(col):
    t = hist.dropna(subset=[col]).groupby(col, observed=True).agg(members=('promo', 'size'), promo=('promo', 'sum'))
    t['index'] = ((t.promo / hist['promo'].sum()) / (t.members / len(hist))).round(2)
    return t
sal_adopt, reg_adopt = adoption('sal_band'), adoption('region')
print(sal_adopt); print(reg_adopt)
for c in ['Gender', 'Marital Status', 'Loyalty Card', 'Education']:
    print(c, adoption(c)['index'].to_dict())

# %% [markdown]
# ## 5. 2019 forecast (no campaign) and a campaign scenario
# Seasonal factor per month (2016–2017) × yearly level on a linear trend (2016–2018, excluding campaign months).
# Note: this is a reconstruction of the forecast code. The dashboard shows the original run
# (~703 for Feb–Apr 2019, +43% uplift, ~1,007 with a campaign); this version gives ~699, +45%, ~1,017.
# The small gap comes from a minor methodological detail; the conclusion is the same.

# %%
e = monthly['enrollments'].unstack(0)            # rows=month, cols=year
season = (e[[2016, 2017]] / e[[2016, 2017]].mean()).mean(axis=1)
non_camp = [m for m in range(1, 13) if m not in (2, 3, 4)]
level = {y: (e.loc[non_camp, y] / season[non_camp]).mean() for y in [2016, 2017, 2018]}
b, a = np.polyfit(list(level), list(level.values()), 1)
lvl = lambda y: a + b * y
f19 = (season * lvl(2019)).round()
f18 = season * lvl(2018)
fa19 = f19.loc[[2, 3, 4]].sum()
uplift = fa(2018) / f18.loc[[2, 3, 4]].sum() - 1
fa_with = fa19 * (1 + uplift)
h1_without = f19.loc[1:6].sum()
h1_with = h1_without - fa19 + fa_with
print(f'Feb-Apr 2019 w/o campaign ~{fa19:.0f}; campaign uplift 2018 = {uplift:+.0%}; with campaign ~{fa_with:.0f}')
print(f'Jan-Jun 2019: without ~{h1_without:.0f}, with ~{h1_with:.0f}, extra ~{h1_with-h1_without:.0f}; 2019 target (+25%) = {fa19*1.25:.0f}')

# %% [markdown]
# ## 6. Charts for the README

# %%
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BLUE, ORANGE, GRAY = '#2a78d6', '#eb6834', '#b4b8c0'
INK, MUTED, SURFACE = '#0b0b0b', '#52514e', '#fcfcfb'
plt.rcParams.update({'font.size': 11, 'axes.edgecolor': '#c9ccd1', 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.spines.top': False,
                     'axes.spines.right': False, 'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE,
                     'axes.grid': True, 'grid.color': '#ecedeb', 'axes.axisbelow': True})
IMG = ROOT / 'images'
IMG.mkdir(exist_ok=True)
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def title(ax, t, sub):
    ax.set_title(t, loc='left', fontsize=13, color=INK, fontweight='bold', pad=22)
    ax.text(0, 1.02, sub, transform=ax.transAxes, color=MUTED, fontsize=10)

# 1) Enrollments by month: 2018 vs 2016-2017 average
fig, ax = plt.subplots(figsize=(9, 4.2))
x = np.arange(1, 13)
avg = e[[2016, 2017]].mean(axis=1)
ax.axvspan(1.5, 4.5, color='#eef4fc', zorder=0)
ax.text(3, 20, 'Campaign months', ha='center', va='bottom', color=MUTED, fontsize=9)
ax.plot(x, avg, color=GRAY, lw=2, marker='o', ms=5, label='2016–2017 average')
ax.plot(x, e[2018], color=BLUE, lw=2, marker='o', ms=5, label='2018')
ax.set_xticks(x, MONTHS); ax.set_ylim(0, 380); ax.set_ylabel('New members')
ax.legend(frameon=False, loc='lower right')
title(ax, 'Enrollments jumped during the campaign', 'New loyalty members per month')
fig.tight_layout(); fig.savefig(IMG / '01_enrollments.png', dpi=160); plt.close(fig)

# 2) Cumulative churn curve
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.plot(curve.index, curve.standard_pct, color=GRAY, lw=2, marker='o', ms=5, label='Standard joiners, Feb–Apr 2017')
ax.plot(curve.index, curve.promo_pct, color=BLUE, lw=2, marker='o', ms=5, label='Campaign joiners, Feb–Apr 2018')
ax.set_xticks(range(0, 11)); ax.set_xlabel('Months since joining'); ax.set_ylabel('% cancelled (cumulative)')
ax.set_ylim(0, 14)
ax.text(10, 9.8, f'Month 10: {k2_actual}%\nvs ceiling {k2_ceiling}%', ha='right', va='top', color=INK, fontsize=10)
ax.legend(frameon=False, loc='upper left')
title(ax, 'Campaign members were just as loyal', 'Cumulative cancellation rate by months since joining')
fig.tight_layout(); fig.savefig(IMG / '02_churn_curve.png', dpi=160); plt.close(fig)

# 3) Flights per active member, 2018
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.axvspan(8.5, 12.5, color='#eef4fc', zorder=0)
ax.text(10.5, 9.6, f'After the bonus ended:\ncampaign members fly x{ratio_post:.1f}', ha='center', va='top', color=INK, fontsize=9)
ax.plot(x, fl['standard'], color=GRAY, lw=2, marker='o', ms=5, label='Standard members')
ax.plot(x[1:], fl['promo'].iloc[1:], color=BLUE, lw=2, marker='o', ms=5, label='Campaign members')
ax.set_xticks(x, MONTHS); ax.set_ylim(0, 10); ax.set_ylabel('Flights per active member')
ax.legend(frameon=False, loc='upper left')
title(ax, 'Campaign members kept flying after the summer', 'Average flights per active member per month, 2018')
fig.tight_layout(); fig.savefig(IMG / '03_flights_per_member.png', dpi=160); plt.close(fig)

# 4) Adoption index by salary band and region
seg = pd.concat([sal_adopt['index'].rename(lambda s: f'Salary {s}'), reg_adopt['index'].sort_values(ascending=False)])
fig, ax = plt.subplots(figsize=(9, 4.4))
ypos = np.arange(len(seg))[::-1]
ax.barh(ypos, seg.values, color=[BLUE if v > 1.05 else GRAY for v in seg.values], height=0.6)
ax.axvline(1, color='#8a909a', lw=1, ls='--')
ax.text(1.03, -0.75, 'average = 1', color=MUTED, fontsize=9)
for yy, v in zip(ypos, seg.values):
    ax.text(max(v, 1) + 0.04, yy, f'{v:.2f}', va='center', color=INK, fontsize=9)
ax.set_yticks(ypos, seg.index); ax.set_xlim(0, 3.5); ax.grid(axis='y', visible=False)
ax.set_xlabel("Adoption index (segment's share of campaign joiners ÷ share of all members)")
title(ax, 'Price-sensitive customers responded 3x more', 'Who joined through the campaign')
fig.tight_layout(); fig.savefig(IMG / '04_adoption_index.png', dpi=160); plt.close(fig)
print('charts saved to', IMG)
