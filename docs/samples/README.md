# Sample CSV files for `/api/import/violations`

Drop any of these into the **Import** page in the UI (or `curl` against the API) to test the
import pipeline. The license numbers in these files match the deterministic seed (the
RNG is keyed by `seed_rng_seed=42`), so after a fresh `docker compose up -d` they all
resolve to real drivers in the DB.

Driver licence numbers follow the modern Kazakhstani format: **9 digits**, e.g.
`339670711`. The seed generates them deterministically from `seed_rng_seed=42`.

A few seeded driver licenses you can also reference manually:
| Driver name        | Licence    |
| ------------------ | ---------- |
| Aigul Nurlanov     | 339670711  |
| Dana Nurlanov      | 642621108  |
| Ruslan Akhmetov    | 790256940  |
| Saltanat Zhumagulova | 777641645|
| Aliya Iskakova     | 530613729  |
| Aliya Nazarbayev   | 941889393  |

## File format

| Column            | Required | Notes                                                  |
| ----------------- | -------- | ------------------------------------------------------ |
| `license_number`  | yes      | must match an existing driver, e.g. `KZ-DR-00001`      |
| `koap_article`    | yes      | one of the 12 articles in `app/koap_catalogue.py`       |
| `occurred_at`     | yes      | ISO date, `YYYY-MM-DD`                                 |
| `fine_kzt`        | no       | integer, KZT; blank → null                             |
| `at_fault`        | no       | `true`/`false`/`1`/`0`/`yes`/`no`/`да`/`нет`; blank → `false` |

Delimiter is auto-detected: comma (`,`) or semicolon (`;`). UTF-8 BOM is accepted
(Excel-RU/KZ exports start with one).

## The six samples

| File                          | Delimiter | Scenario                                                                |
| ----------------------------- | --------- | ----------------------------------------------------------------------- |
| `01_happy_comma.csv`          | `,`       | 5 valid rows, 4 different drivers, 5 different articles. Expect 5/5/0.   |
| `02_happy_semicolon.csv`      | `;`       | Same as above but with `;` (Excel-RU export style). Expect 5/5/0.       |
| `03_mixed_errors.csv`         | `,`       | 2 valid + 3 invalid rows: unknown license, unknown article, bad date. Expect 2/2/3 — the 2 valid rows still commit. |
| `04_recurrence_one_driver.csv`| `,`       | 5× `Art.592 Part 3-1` for one driver → triggers recurrence_multiplier=2.0 and the highest tier. |
| `05_critical_dui.csv`         | `,`       | DUI + DUI-accident + leaving scene + refusal-of-exam on one driver, all `at_fault=true`. Expect risk_tier = "critical", coefficient = 2.2x. |
| `06_excel_ru_with_bom.csv`    | `;`       | UTF-8 BOM, RU `да`/`нет` booleans. Tests that Excel-RU export Just Works. |

## Verification by `curl`

```bash
# Log in as admin
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"info@adam.ua","password":"demo"}' | jq -r .token)

# Upload one of the samples
curl -X POST http://localhost:8001/api/import/violations \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@docs/samples/03_mixed_errors.csv"
```

Expected response shape:

```json
{
  "importedRecords": 2,
  "recomputedDrivers": 2,
  "errors": [
    {"row": 2, "message": "Unknown license: KZ-NONEXISTENT"},
    {"row": 3, "message": "Unknown article: Art.MADE.UP"},
    {"row": 4, "message": "Bad date: not-a-date"}
  ]
}
```

Rows are 1-based (header is row 0). The endpoint commits valid rows even when some rows fail
(partial success).
