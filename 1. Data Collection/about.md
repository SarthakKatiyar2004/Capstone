# India Code Act Scraper

A notebook (`1.1. policy_scrapper.ipynb`) that collects metadata for every Act listed on [indiacode.gov.in](https://indiacode.gov.in) and saves it as a CSV.

## The core idea

The India Code website is a JavaScript app, so fetching the HTML pages returns an empty shell. But the table you see on an act's `/act/{id}/details` page is filled in from a **JSON API** behind the scenes. That same API's list endpoint returns each act's full metadata, so the notebook calls it directly instead of rendering pages in a browser.

The result: roughly 9 requests (at 100 acts per page) instead of 800+ page loads, with no browser automation needed.

## How it works

### 1. Configuration

| Constant | Purpose |
|---|---|
| `BASE_URL` | Site root, used to build act links |
| `COLLECTION_ID` | UUID of the Acts collection on the site |
| `OBJECTS_API` | The `/server/api/discover/search/objects` endpoint that returns acts as JSON |
| `DROP_KEYS` | Bookkeeping metadata fields (accession/availability dates, provenance) that are discarded |
| `LABELS` | Mapping from raw metadata keys to friendly column names |
| `SEP` | Separator (`" | "`) used to join multi-valued fields into one cell |

### 2. Functions

- **`get_json(session, url, params, retries=4)`**: a GET wrapper with retry and exponential backoff (waits 1s, 2s, 4s, 8s). Raises an error if all attempts fail.
- **`fetch_all_items(session, page_size=100, delay=0.5)`**: walks through the paginated search results. It reads `totalPages` from the first response, loops until every page is fetched, and collects each act's `indexableObject`. A 0.5s delay between requests keeps the load on the server light.
- **`flatten_item(io)`**: converts one act into a flat dictionary. It adds identifiers (`uuid`, `act_url`, `details_url`, `handle`) and the title, then goes through the act's `metadata` and joins each field's values with `SEP`. Empty values are skipped, so an act only has keys for fields it actually has.
- **`build_dataframe(items, labels)`**: builds a pandas DataFrame from all the flattened acts. Because pandas takes the union of all keys, fields an act lacks become blank cells. Columns are sorted so identifier columns come first, then the rest from most to least complete. Finally `LABELS` renames the raw keys.
- **`coverage(df)`**: returns, for each column, how many rows are filled and what percentage that is. Useful for deciding which columns matter.
- **`filter_years(df, lo, hi)`**: keeps acts from a year range. It looks for a four-digit year in `dc.date.issued`, then `Enactment Date`, then `Act Year`, using the first one available. This replicates the site's `dateIssued` min/max filter on the client side.

### 3. Running the notebook

1. **Step 1: fetch.** Creates a `requests.Session` with a browser-like `User-Agent` and `Accept: application/json`, then pulls every act. Progress is printed per page.
2. **Step 2: inspect.** Builds the DataFrame and shows the coverage table. Use it to see which raw keys exist (for example `dc.date.act_year`) and add friendly names to `LABELS`, then re-run.
3. **Step 3: filter and save.** Applies the optional year filter (default 2010 to 2026; remove that line to keep everything) and writes `indiacode_acts_details.csv`, encoded as UTF-8 with BOM (`utf-8-sig`) so Excel opens it correctly.

### 4. Optional: browser cross-check

The last cell (commented out) uses Playwright to open one act's details page in headless Chromium and read the rendered table. Use it only if the website shows a field that Step 2 doesn't. It needs:

```bash
pip install playwright
playwright install chromium
```

The table selector is a guess and may need adjusting.

## Output

`indiacode_acts_details.csv` with one row per act:

- **Identifiers:** `uuid`, `act_url`, `details_url`, `handle`
- **Metadata columns:** one per metadata field found, ordered by completeness, with blanks where an act lacks the field
- **Renamed columns:** `Act`, `Act Year`, `Enactment Date` by default, plus any you add to `LABELS`

## Requirements

- Python 3
- `requests`
- `pandas`
- Playwright (only for the optional check)

## Notes and caveats

- The API is undocumented and could change, so if the scraper breaks, check whether the endpoint or `COLLECTION_ID` has changed.
- The notebook uses `display(...)`, which works in Jupyter but not in a plain Python script.
- Keep the delay between requests, and review the site's terms of use before scraping at scale.
