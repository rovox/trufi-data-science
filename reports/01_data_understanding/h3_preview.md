# Preliminary H3 aggregation (resolution 8, ~460 m hexagons)

- H3 cells with queries as origin: 1,523
- H3 cells with queries as destination: 1,840
- Top 10 origin cells concentrate: 42.0% of all queries
- Top 10 destination cells concentrate: 35.9% of all queries

## Top 10 origin cells

shape: (10, 3)
┌─────────────────┬───────────┬─────────┐
│ h3_orig         ┆ n_queries ┆ n_users │
│ ---             ┆ ---       ┆ ---     │
│ str             ┆ u32       ┆ u32     │
╞═════════════════╪═══════════╪═════════╡
│ 888b2c8a39fffff ┆ 152531    ┆ 34338   │
│ 888b2c8a3bfffff ┆ 112588    ┆ 28297   │
│ 888b2c8ae5fffff ┆ 92161     ┆ 21983   │
│ 888b2c8a15fffff ┆ 90690     ┆ 26849   │
│ 888b2c8a03fffff ┆ 80066     ┆ 23750   │
│ 888b2c8a31fffff ┆ 77460     ┆ 19966   │
│ 888b2c8a33fffff ┆ 59694     ┆ 17032   │
│ 888b2c8859fffff ┆ 49864     ┆ 15161   │
│ 888b2c8aedfffff ┆ 47832     ┆ 15516   │
│ 888b2c8a3dfffff ┆ 46314     ┆ 12627   │
└─────────────────┴───────────┴─────────┘

## Top 10 destination cells

shape: (10, 3)
┌─────────────────┬───────────┬─────────┐
│ h3_dest         ┆ n_queries ┆ n_users │
│ ---             ┆ ---       ┆ ---     │
│ str             ┆ u32       ┆ u32     │
╞═════════════════╪═══════════╪═════════╡
│ 888b2c8a3bfffff ┆ 91785     ┆ 26738   │
│ 888b2c8a39fffff ┆ 90607     ┆ 26193   │
│ 888b2c8a33fffff ┆ 78868     ┆ 24298   │
│ 888b2c8859fffff ┆ 69425     ┆ 22264   │
│ 888b2c8a31fffff ┆ 66761     ┆ 20148   │
│ 888b2c8ae5fffff ┆ 66024     ┆ 20284   │
│ 888b2c8aedfffff ┆ 64665     ┆ 22395   │
│ 888b2c8a15fffff ┆ 58577     ┆ 21309   │
│ 888b2c8a03fffff ┆ 57444     ┆ 19912   │
│ 888b2c8a3dfffff ┆ 48421     ┆ 15304   │
└─────────────────┴───────────┴─────────┘

## Conclusion

Demand is concentrated in a small number of cells -> centralization.
