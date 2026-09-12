import os
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TAB_NAMES = {
    "startups": "Startups",
    "products": "Products",
    "papers": "Research Papers",
    "jobs": "Jobs",
    "news": "News",
    "entity_mapping": "Entity Mapping Log",
}


def _get_client() -> gspread.Client:
    creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_or_create_worksheet(spreadsheet: gspread.Spreadsheet, tab_name: str, num_cols: int):
    try:
        return spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=tab_name, rows=2000, cols=max(num_cols, 5))


def _flatten_record(record: dict) -> dict:
    """
    Flattens a nested pydantic-style dict (e.g. {"source": {"name": ..., "url": ...},
    "content": {...}}) into a single-level dict suitable for a spreadsheet row.
    """
    flat = {}
    for key, value in record.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"{key}.{sub_key}"] = sub_value
        elif isinstance(value, list):
            flat[key] = ", ".join(str(v) for v in value)
        else:
            flat[key] = value
    return flat


def write_records(sheet_key: str, records: list[dict], sheet_id: str | None = None):
    """
    Write a list of entity dicts (from .model_dump() on your pydantic models)
    to the appropriate tab, creating the tab and header row if needed.

    sheet_key: one of "startups", "products", "papers", "jobs", "news", "entity_mapping"
    records: list of plain dicts (call .model_dump() on your pydantic entities first)
    sheet_id: optional override; defaults to GOOGLE_SHEET_ID from .env
    """
    if not records:
        print(f"[sheets] no records to write for '{sheet_key}', skipping")
        return

    sheet_id = sheet_id or os.environ["GOOGLE_SHEET_ID"]
    tab_name = TAB_NAMES[sheet_key]

    client = _get_client()
    spreadsheet = client.open_by_key(sheet_id)

    flat_records = [_flatten_record(r) for r in records]
    headers = list(flat_records[0].keys())

    worksheet = _get_or_create_worksheet(spreadsheet, tab_name, len(headers))

    existing = worksheet.get_all_values()
    if not existing:
        worksheet.append_row(headers)

    rows = [[str(rec.get(h, "")) for h in headers] for rec in flat_records]

    # batch write in chunks to stay well under Sheets API payload limits
    CHUNK = 500
    for i in range(0, len(rows), CHUNK):
        worksheet.append_rows(rows[i : i + CHUNK], value_input_option="RAW")

    print(f"[sheets] wrote {len(rows)} rows to '{tab_name}'")


def write_entity_mapping_log(mappings: list[dict], sheet_id: str | None = None):
    """
    mappings: list of {"raw_name": str, "canonical_name": str} dicts
    """
    write_records("entity_mapping", mappings, sheet_id=sheet_id)