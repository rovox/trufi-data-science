# userID behavior analysis

- Unique users: 130,549
- Total queries: 1,927,675
- Median queries per user: 5.0
- % users with >=2 queries: 77.88%
- % users with >=10 queries: 32.90%
- Top 1% users concentrate: 15.9% of queries
- Users appearing in >1 year: 33,039 (25.3%)
- Median lifespan (days between first/last query): 9.0
- Suspicious impossible jumps: 2,156

## Decision matrix evaluation

- Median queries/user = 5 -> repeated use detected: installation-level ID signal.
- 77.9% of users have >=2 queries (>=30% threshold) -> individual-level target remains viable.
- Median lifespan = 9.0 days -> userID persists beyond a single session.
- 25.3% of users appear in >1 year -> limited long-term stability of the ID.
- 2,156 suspicious impossible jumps detected -> filter these before modeling (possible bots/scrapers/shared devices).

## Query distribution
```
shape: (9, 2)
┌────────────┬───────────┐
│ statistic  ┆ value     │
│ ---        ┆ ---       │
│ str        ┆ f64       │
╞════════════╪═══════════╡
│ count      ┆ 130549.0  │
│ null_count ┆ 0.0       │
│ mean       ┆ 14.765912 │
│ std        ┆ 31.878518 │
│ min        ┆ 1.0       │
│ 25%        ┆ 2.0       │
│ 50%        ┆ 5.0       │
│ 75%        ┆ 14.0      │
│ max        ┆ 1298.0    │
└────────────┴───────────┘
```

## Lifespan distribution
```
shape: (9, 2)
┌────────────┬────────────┐
│ statistic  ┆ value      │
│ ---        ┆ ---        │
│ str        ┆ f64        │
╞════════════╪════════════╡
│ count      ┆ 130549.0   │
│ null_count ┆ 0.0        │
│ mean       ┆ 89.398793  │
│ std        ┆ 141.574426 │
│ min        ┆ 0.0        │
│ 25%        ┆ 0.0        │
│ 50%        ┆ 9.0        │
│ 75%        ┆ 129.0      │
│ max        ┆ 627.0      │
└────────────┴────────────┘
```
