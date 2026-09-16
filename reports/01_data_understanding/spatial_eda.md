# Spatial distribution report

- Bounding box used: lat [-17.6, -17.2], lon [-66.4, -65.8]
- Total queries: 1,927,675
- Inside bbox: 1,924,161 (99.82%)
- Outside bbox: 3,514 (0.18%)
- Zero coordinates (origin or dest): 3

## Decision

- Queries inside the bbox exceed the 95% pre-specified threshold -> proceed with the bbox as the spatial scope.
- Zero coordinates are excluded from spatial analysis but retained in the dataset until Data Preparation.

## Top origin/dest municipio pairs among out-of-bbox queries

shape: (10, 3)
┌──────────────────┬──────────────────┬─────┐
│ origin_municipio ┆ dest_municipio   ┆ n   │
│ ---              ┆ ---              ┆ --- │
│ str              ┆ str              ┆ u32 │
╞══════════════════╪══════════════════╪═════╡
│ Cochabamba       ┆ Tarata           ┆ 652 │
│ Cochabamba       ┆ Capinota         ┆ 259 │
│ externo          ┆ Cochabamba       ┆ 227 │
│ Tarata           ┆ Cochabamba       ┆ 194 │
│ Cochabamba       ┆ Vinto            ┆ 172 │
│ Cochabamba       ┆ Arani            ┆ 151 │
│ Vinto            ┆ Cochabamba       ┆ 134 │
│ Cochabamba       ┆ Villa de Anzaldo ┆ 76  │
│ Capinota         ┆ Cochabamba       ┆ 71  │
│ Villa Tunari     ┆ Cochabamba       ┆ 70  │
└──────────────────┴──────────────────┴─────┘
