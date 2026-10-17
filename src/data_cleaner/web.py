"""Bridge for the browser. The page runs this module inside Pyodide and calls these functions;
data stays in the browser tab. Results cross into JavaScript as JSON strings or bytes.
"""

from __future__ import annotations

import json

from .cleaner import Options, Report, clean, profile, to_xlsx
from .table import Table, read_any, sheet_names, write_csv

PREVIEW_ROWS = 200

_state: dict = {}


def _as_bytes(data) -> bytes:
    """Pyodide hands JavaScript Uint8Arrays over as proxies with .to_bytes()."""
    to_bytes = getattr(data, "to_bytes", None)
    return to_bytes() if to_bytes else bytes(data)


def load(data: bytes, filename: str, sheet: str | None = None) -> str:
    data = _as_bytes(data)
    table = read_any(data, filename, sheet or None)
    _state.clear()
    _state["table"] = table
    sheets = sheet_names(data) if filename.lower().endswith((".xlsx", ".xlsm")) else []
    return json.dumps(
        {
            "rows": len(table.rows),
            "columns": [c.__dict__ for c in profile(table)],
            "sheets": sheets,
            "preview": table.rows[:PREVIEW_ROWS],
            "source_rows": table.source_rows[:PREVIEW_ROWS],
        }
    )


def run(options_json: str) -> str:
    table: Table = _state["table"]
    cleaned, report = clean(table, Options.from_dict(json.loads(options_json)))
    _state["cleaned"], _state["report"] = cleaned, report
    data = report.to_dict()
    data["header"] = cleaned.columns
    data["preview"] = cleaned.rows[:PREVIEW_ROWS]
    data["source_rows"] = cleaned.source_rows[:PREVIEW_ROWS]
    return json.dumps(data, ensure_ascii=False)


def export(kind: str) -> bytes:
    cleaned: Table = _state["cleaned"]
    report: Report = _state["report"]
    if kind == "xlsx":
        return to_xlsx(cleaned, report)
    if kind == "csv":
        return write_csv(cleaned)
    if kind == "report":
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False).encode("utf-8")
    raise ValueError(kind)
