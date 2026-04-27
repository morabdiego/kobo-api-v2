# py-kobotoolbox

[![PyPI version](https://img.shields.io/pypi/v/kobo-api-v2.svg)](https://pypi.org/project/kobo-api-v2/)
[![Python](https://img.shields.io/pypi/pyversions/kobo-api-v2.svg)](https://pypi.org/project/kobo-api-v2/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, synchronous Python client for the [KoboToolbox API v2](https://kf.kobotoolbox.org/api/v2/docs/).

## Installation

```bash
pip install kobo-api-v2
```

Requires Python ≥ 3.10.

## Quick start

```python
from kobo import KoboClient

client = KoboClient(api_token="<your_api_token>")

# List available surveys
surveys = client.get_surveys()

# Download the first survey as Excel in one call
saved = client.get_excel(surveys[0]["uid"])
print(saved)  # → /absolute/path/to/data_survey.xlsx
```

Your API token is under **Account Settings → Security → API key** in your KoboToolbox account.

---

## API reference

### `KoboClient(api_token, base_url=...)`

```python
# Public server (default)
client = KoboClient(api_token="...")

# Self-hosted instance
client = KoboClient(api_token="...", base_url="https://kobo.myserver.org")
```

---

### Surveys

```python
# List surveys (returns list[dict] with uid, name, deployment_status, …)
surveys = client.get_surveys()
surveys = client.get_surveys(search="census", limit=50, offset=0)

# Full metadata for a single survey
survey = client.get_survey(uid)

# XLSForm content (survey, choices, settings sections)
content = client.get_survey_content(uid)
for row in content["survey"]:
    print(row["type"], row.get("$autoname"))
```

#### `get_surveys` parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` | `100` | Results per page (API max: 300) |
| `offset` | `0` | Pagination offset |
| `search` | `None` | Free-text filter |

---

### `get_excel` — one-call export

Download survey data as an Excel file with a single method call:

```python
# Minimal — saves to data_survey.xlsx in the current directory
saved = client.get_excel(uid)

# Custom output path
saved = client.get_excel(uid, path="outputs/survey.xlsx")

# Reuse an already-triggered export task
saved = client.get_excel(uid, export_uid="eNHpF8SxT9oP2752mj8UJQ")
```

When `export_uid` is omitted the method:
1. Creates (or reuses) a saved export setting named `"python-client"`
2. Triggers a new XLS export using XLSForm internal field names (`lang="_xml"`)
3. Polls until the server finishes generating the file (every 3 s, 120 s timeout)
4. Downloads the file and returns its absolute `Path`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `asset_uid` | — | Survey UID |
| `export_uid` | `None` | UID of an already-triggered export; triggers a new one if omitted |
| `path` | `"data_survey.xlsx"` | Local destination path |
| `poll_interval` | `3.0` | Seconds between status checks |
| `timeout` | `120.0` | Max seconds to wait before raising `ExportTimeoutError` |

---

### Export settings (reusable configurations)

Export settings are named configurations saved in KoboToolbox that can be reused across multiple exports.

```python
# Create a new setting (raises KoboError if the name already exists)
setting_uid = client.create_export_setting(uid, name="my_config")

# Create or reuse — recommended for recurring scripts
setting_uid, created = client.get_or_create_export_setting(uid, name="my_config")

# List all saved settings for a survey
settings = client.list_export_settings(uid)
```

All settings default to the values below and can be overridden with `**overrides`:

| Field | Default | Description |
|-------|---------|-------------|
| `type` | `"xls"` | Format: `"xls"`, `"csv"`, `"geojson"` |
| `lang` | `"_xml"` | `"_xml"` = XLSForm internal names; or a language label, e.g. `"English"` |
| `fields_from_all_versions` | `True` | Include fields from older form versions |
| `group_sep` | `"/"` | Column name separator for groups |
| `hierarchy_in_labels` | `False` | Prepend group hierarchy to labels |
| `multiple_select` | `"summary"` | `"summary"`, `"both"`, or `"details"` |
| `flatten` | `False` | Flatten group structure |
| `xls_types_as_text` | `False` | Export all values as strings |
| `include_media_url` | `False` | Include attachment download URLs |

```python
setting_uid = client.create_export_setting(
    uid,
    name="csv_english",
    type="csv",
    lang="English",
)
```

---

### Async exports (manual control)

For full control over the export lifecycle:

```python
# 1. Trigger an export task
export_uid = client.trigger_export(uid, type="xls", lang="_xml")

# Filter by date
export_uid = client.trigger_export(
    uid,
    query={"$and": [{"_submission_time": {"$gte": "2024-01-01"}}]},
)

# Specific submissions or fields
export_uid = client.trigger_export(uid, submission_ids=[101, 102])
export_uid = client.trigger_export(uid, fields=["name", "age"])

# 2. Wait and get the download URL
result = client.wait_for_export(uid, export_uid)
print(result["result"])  # direct download URL

# 3. Or wait and download in one step
saved = client.download_export(uid, export_uid, dest_path="data/survey.xlsx")
```

| Method | Returns |
|--------|---------|
| `trigger_export(uid, ...)` | `export_uid: str` |
| `wait_for_export(uid, export_uid)` | `dict` with `result` (download URL) |
| `download_export(uid, export_uid, path)` | `Path` of the saved file |

---

## Error handling

| Exception | Raised when |
|-----------|-------------|
| `KoboError` | The API returns an HTTP error (4xx / 5xx) |
| `ExportTimeoutError` | Export did not complete within `timeout` seconds |

```python
from kobo.client import KoboError, ExportTimeoutError

try:
    saved = client.get_excel(uid, path="out.xlsx")
except ExportTimeoutError:
    print("Export took too long")
except KoboError as e:
    print(f"API error: {e}")
```

---

## License

MIT — see [LICENSE](LICENSE).
