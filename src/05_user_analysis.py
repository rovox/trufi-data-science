"""Task 5 — userID behavior analysis.

The single most decisive analysis for the project: determines whether
userID is installation-level (individual target viable) or
session/ephemeral-level (must pivot to cell-level analysis).
"""

from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl

REPORTS = Path("reports/01_data_understanding")
REPORTS.mkdir(exist_ok=True)

df = pl.read_parquet("data/interim/queries.parquet")

per_user = df.group_by("userID").agg([
    pl.len().alias("n_queries"),
    pl.col("ts").min().alias("first_seen"),
    pl.col("ts").max().alias("last_seen"),
    (pl.col("ts").max() - pl.col("ts").min()).dt.total_days().alias("lifespan_days"),
    pl.col("ts").dt.year().n_unique().alias("n_years"),
    pl.col("ts").dt.month().n_unique().alias("n_months"),
])

n_users = len(per_user)
n_queries = per_user["n_queries"].sum()

print(f"Unique users: {n_users:,}")
print(f"Total queries: {n_queries:,}")

print("\n=== Query distribution per user ===")
desc = per_user["n_queries"].describe()
print(desc)

print("\n=== Users with at least N queries ===")
at_least = {}
for k in [1, 2, 5, 10, 50, 100]:
    n = (per_user["n_queries"] >= k).sum()
    at_least[k] = n
    print(f"  >= {k:>3}: {n:>8,} ({n/n_users*100:5.2f}%)")

top1_cut = per_user["n_queries"].quantile(0.99)
top1_queries = per_user.filter(pl.col("n_queries") >= top1_cut)["n_queries"].sum()
print(f"\nTop 1% users (>= {top1_cut:.0f} queries) concentrate: {top1_queries/n_queries*100:.1f}% of queries")

multi_year = per_user.filter(pl.col("n_years") > 1).height
print(f"Users appearing in >1 year: {multi_year:,} ({multi_year/n_users*100:.1f}%)")

print("\n=== Lifespan (days between first and last query) ===")
lifespan_desc = per_user["lifespan_days"].describe()
print(lifespan_desc)

median_lifespan = per_user["lifespan_days"].median()
median_queries = per_user["n_queries"].median()

# Active users per month
monthly = (
    df.sort("ts")
    .group_by_dynamic("ts", every="1mo")
    .agg(pl.col("userID").n_unique().alias("active_users"))
)
print("\n=== Active users per month ===")
print(monthly)

# Bot detection: impossible jumps (<2 min apart, >~11km latitude change)
df_sorted = df.sort(["userID", "ts"])
df_sorted = df_sorted.with_columns([
    pl.col("ts").diff().over("userID").dt.total_seconds().alias("dt_sec"),
    (pl.col("lat_orig").diff().over("userID")).abs().alias("dlat"),
])
suspicious = df_sorted.filter(
    (pl.col("dt_sec") < 120) & (pl.col("dlat") > 0.1)
)
n_suspicious = suspicious.height
print(f"\nSuspicious jumps (<2 min, >~11 km): {n_suspicious:,}")

# Figures
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
axes[0, 0].hist(per_user["n_queries"].to_numpy(), bins=100, log=True)
axes[0, 0].set_title("Queries per user (log scale)")
axes[0, 1].hist(per_user["lifespan_days"].to_numpy(), bins=100)
axes[0, 1].set_title("User lifespan (days)")
axes[1, 0].plot(monthly["ts"], monthly["active_users"])
axes[1, 0].set_title("Active users per month")
axes[1, 1].hist(per_user["n_months"].to_numpy(), bins=50)
axes[1, 1].set_title("Months active per user")
plt.tight_layout()
plt.savefig(REPORTS / "fig_user_analysis.png", dpi=150)
print(f"\nWrote {REPORTS / 'fig_user_analysis.png'}")

# Decision matrix evaluation
pct_ge2 = at_least[2] / n_users * 100
verdict_lines = []
if median_queries <= 1:
    verdict_lines.append("Median queries/user = 1 -> session-level ID signal: individual target may be unviable.")
else:
    verdict_lines.append(f"Median queries/user = {median_queries:.0f} -> repeated use detected: installation-level ID signal.")

if pct_ge2 < 30:
    verdict_lines.append(f"Only {pct_ge2:.1f}% of users have >=2 queries (<30% threshold) -> pivot to cell-level analysis per pre-specified rule.")
else:
    verdict_lines.append(f"{pct_ge2:.1f}% of users have >=2 queries (>=30% threshold) -> individual-level target remains viable.")

if median_lifespan is not None and median_lifespan < 1:
    verdict_lines.append(f"Median lifespan = {median_lifespan:.2f} days (<1 day threshold) -> userID likely session-level, individual target unviable per pre-specified rule.")
else:
    verdict_lines.append(f"Median lifespan = {median_lifespan:.1f} days -> userID persists beyond a single session.")

pct_multi_year = multi_year / n_users * 100
if pct_multi_year > 50:
    verdict_lines.append(f"{pct_multi_year:.1f}% of users appear in >1 year -> ID is stable over time, historical features are meaningful.")
else:
    verdict_lines.append(f"{pct_multi_year:.1f}% of users appear in >1 year -> limited long-term stability of the ID.")

if n_suspicious > 0:
    verdict_lines.append(f"{n_suspicious:,} suspicious impossible jumps detected -> filter these before modeling (possible bots/scrapers/shared devices).")
else:
    verdict_lines.append("No suspicious impossible jumps detected.")

print("\n=== Decision matrix evaluation ===")
for line in verdict_lines:
    print(f"- {line}")

report = f"""# userID behavior analysis

- Unique users: {n_users:,}
- Total queries: {n_queries:,}
- Median queries per user: {median_queries:.1f}
- % users with >=2 queries: {pct_ge2:.2f}%
- % users with >=10 queries: {at_least[10]/n_users*100:.2f}%
- Top 1% users concentrate: {top1_queries/n_queries*100:.1f}% of queries
- Users appearing in >1 year: {multi_year:,} ({pct_multi_year:.1f}%)
- Median lifespan (days between first/last query): {median_lifespan:.1f}
- Suspicious impossible jumps: {n_suspicious:,}

## Decision matrix evaluation

""" + "\n".join(f"- {line}" for line in verdict_lines) + """

## Query distribution
```
""" + str(desc) + """
```

## Lifespan distribution
```
""" + str(lifespan_desc) + """
```
"""
(REPORTS / "user_analysis.md").write_text(report)
print(f"\nWrote {REPORTS / 'user_analysis.md'}")
