# Act Reactions Dashboard

A full-stack dashboard for exploring public reactions to legislation: a Python backend, a SQLite database built from your CSV files, and a plain HTML/CSS/JavaScript frontend. No build step and no Python packages to install (standard library only, Python 3.8+).

## Run it

```bash
python3 backend/server.py            # http://127.0.0.1:8000
python3 backend/server.py --port 9000 --host 0.0.0.0
```

The database is already built in `database/act_reactions.db`. If it is missing, the server builds it from `data/` on start. The frontend loads Chart.js from a CDN, so the browser needs internet access.

## Structure

```
backend/
  server.py        REST API + static file server (http.server, sqlite3)
  import_csv.py    Builds the SQLite database from data/*.csv
data/              Source CSV/JSON files (edit or replace these, then rebuild)
database/
  act_reactions.db SQLite database (generated)
frontend/
  index.html
  css/styles.css
  js/
    api.js         Backend client
    loader.js      Fetches data, then loads the scripts below in order
    state.js       Shared state, data helpers, navigation
    components.js  Data table and chart helpers
    core.js        Filters, router, act drawer, add/edit/delete
    common.js      Shared view helpers
    overview.js  acts.js  analysis.js  models.js  simulator.js  database.js   One file per page
    app.js         Starts the app
```

## Database

| Table / view | Source |
|---|---|
| `act_summary` | `data/act_level_summary.csv` |
| `act_split` | `data/act_split_and_targets.csv` |
| `model_regression`, `model_classification` | `data/model_comparison_*.csv` |
| `test_predictions` | `data/test_predictions.csv` |
| `neighbors` | `data/neighbors_top5.csv` (five most similar acts, from the title embeddings) |
| `run_info` | `data/run_info.json` |
| `acts` | Working table joining `act_summary` and `act_split`. Add, edit and delete in the dashboard write here |
| `scenarios` | Saved in the Policy simulator |
| `v_jurisdiction_summary`, `v_domain_summary` | Views over `acts` |

Browse all of them in the dashboard under **Data > Database**, or query directly: `sqlite3 database/act_reactions.db`.

To use new data, replace the files in `data/` (same column names) and run `python3 backend/import_csv.py`, or use **Reset data** on the Acts page, which rebuilds the database from the CSV files.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/bootstrap` | Acts, model results, predictions, run info, scenarios and table list |
| GET / POST | `/api/acts` | List or create an act |
| PUT / DELETE | `/api/acts/<id>` | Update or delete an act |
| GET / POST | `/api/scenarios` | List or save simulator scenarios |
| DELETE | `/api/scenarios/<id>` | Delete a scenario |
| GET | `/api/tables` | Tables and views with row counts and columns |
| GET | `/api/tables/<name>?limit=&offset=&q=` | Rows of a table or view |
| GET | `/api/tables/<name>/export.csv` | Download a table as CSV |
| POST | `/api/reset` | Rebuild the database from `data/` |

## Notes

- The Policy simulator estimates reception from jurisdiction, policy area and kind of law, plus title similarity to existing acts. It runs in the browser using the acts loaded from the database.
- `neighbors_top5.csv` was computed from the multilingual MiniLM title embeddings in `act_embeddings_package.zip`.
