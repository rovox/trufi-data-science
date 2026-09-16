# Data quality report — Trufi App Cochabamba

## Null report

| column | nulls | pct |
|---|---|---|
| year_week_number | 1,765,898 | 91.608% |
| time_of_day | 1,765,898 | 91.608% |
| date | 0 | 0.0% |
| lat_orig | 0 | 0.0% |
| lon_orig | 0 | 0.0% |
| lat_dest | 0 | 0.0% |
| lon_dest | 0 | 0.0% |
| userID | 0 | 0.0% |
| distancia | 0 | 0.0% |
| origin_municipio | 0 | 0.0% |
| dest_municipio | 0 | 0.0% |
| hour | 0 | 0.0% |
| day_of_week | 0 | 0.0% |
| day_of_month | 0 | 0.0% |
| weekend | 0 | 0.0% |
| source_file | 0 | 0.0% |
| source_batch | 0 | 0.0% |
| ts | 0 | 0.0% |
| year | 0 | 0.0% |
| week | 0 | 0.0% |

## Duplicate report

| check | count | pct | decision |
|---|---|---|---|
| Exact duplicates (all columns) | 104 | 0.005% | drop |
| Duplicates on OD + ts | 104 | 0.005% | keep (pin repeat) |
| Duplicates on userID + ts | 137 | 0.007% | keep (will be sessionized) |

Null `userID`: 0. Empty-string `userID`: 0.
