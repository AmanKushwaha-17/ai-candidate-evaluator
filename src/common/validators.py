"""
Shared upload validation — used by Stage 1 (candidate CSV/XLSX upload) and
Stage 2 (test-results CSV/XLSX upload). Lives in src/common because both
stages need it and neither owns it exclusively.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS = ["name", "email"]
OPTIONAL_COLUMNS = [
    "s_no",
    "college",
    "branch",
    "cgpa",
    "best_ai_project",
    "research_work",
    "github",
    "resume",
    "test_la",
    "test_code",
]
ALL_KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

TEST_RESULT_REQUIRED_COLUMNS: list[str] = []
TEST_RESULT_OPTIONAL_COLUMNS = ["s_no", "name", "email", "test_la", "test_code"]


@dataclass
class ValidationResult:
    dataframe: pd.DataFrame
    total_rows: int
    valid_rows: int
    row_errors: dict[int, list[str]] = field(default_factory=dict)
    missing_required_columns: list[str] = field(default_factory=list)
    dropped_unknown_columns: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing_required_columns

    def summary_text(self) -> str:
        parts = [f"{self.valid_rows}/{self.total_rows} candidates usable"]
        if self.row_errors:
            parts.append(f"{len(self.row_errors)} row(s) flagged")
        if self.dropped_unknown_columns:
            parts.append(f"{len(self.dropped_unknown_columns)} unrecognized column(s) ignored")
        return " · ".join(parts)


def _normalize_column_name(col: str) -> str:
    return str(col).strip().lower().replace(" ", "_").replace("-", "_")


def _is_xlsx(file_bytes: bytes) -> bool:
    return file_bytes[:4] == b"PK\x03\x04"


def get_xlsx_sheet_names(file_bytes: bytes) -> list[str]:
    if not _is_xlsx(file_bytes):
        return []
    import openpyxl  # noqa: PLC0415
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    names = wb.sheetnames
    wb.close()
    return names


def _read_file_defensively(file_bytes: bytes, sheet_name: str | int = 0) -> pd.DataFrame:
    if _is_xlsx(file_bytes):
        try:
            return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, engine="openpyxl")
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Could not parse Excel file (sheet={sheet_name!r}): {exc}") from exc

    attempts = [
        {"encoding": "utf-8-sig"},
        {"encoding": "utf-8"},
        {"encoding": "latin-1"},
    ]
    last_error: Exception | None = None
    for kwargs in attempts:
        try:
            return pd.read_csv(io.BytesIO(file_bytes), on_bad_lines="skip", skip_blank_lines=True, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    raise ValueError(f"Could not parse CSV with any known encoding: {last_error}")


def _row_issues(row: pd.Series, required_columns: list[str]) -> list[str]:
    issues = []
    for col in required_columns:
        value = row.get(col)
        if pd.isna(value) or str(value).strip() == "":
            issues.append(f"missing '{col}'")

    cgpa = row.get("cgpa")
    if cgpa is not None and not pd.isna(cgpa) and str(cgpa).strip() != "":
        try:
            float(str(cgpa).strip())
        except ValueError:
            issues.append(f"unparseable cgpa: {cgpa!r}")

    return issues


def validate_and_normalize_csv(
    file_bytes: bytes,
    required_columns: list[str] = REQUIRED_COLUMNS,
    known_columns: list[str] = ALL_KNOWN_COLUMNS,
    sheet_name: str | int = 0,
) -> ValidationResult:
    """Load a candidate or test-result CSV/XLSX and normalize column names defensively."""
    df = _read_file_defensively(file_bytes, sheet_name=sheet_name)

    rename_map = {}
    dropped_unknown = []
    for col in df.columns:
        norm = _normalize_column_name(col)
        if norm in known_columns:
            rename_map[col] = norm
        else:
            dropped_unknown.append(col)
    df = df.rename(columns=rename_map)
    df = df[[c for c in df.columns if c in known_columns]]

    df = df.dropna(how="all").reset_index(drop=True)

    missing_required = [c for c in required_columns if c not in df.columns]
    if missing_required:
        return ValidationResult(
            dataframe=df,
            total_rows=len(df),
            valid_rows=0,
            missing_required_columns=missing_required,
            dropped_unknown_columns=dropped_unknown,
        )

    for col in known_columns:
        if col not in df.columns:
            df[col] = pd.NA

    row_errors: dict[int, list[str]] = {}
    for idx, row in df.iterrows():
        issues = _row_issues(row, required_columns)
        if issues:
            row_errors[idx] = issues

    df["_row_status"] = "ok"
    df["_row_issues"] = ""
    for idx, issues in row_errors.items():
        df.at[idx, "_row_status"] = "flagged"
        df.at[idx, "_row_issues"] = "; ".join(issues)

    valid_rows = len(df) - len(row_errors)

    return ValidationResult(
        dataframe=df,
        total_rows=len(df),
        valid_rows=valid_rows,
        row_errors=row_errors,
        dropped_unknown_columns=dropped_unknown,
    )


def validate_test_results_csv(file_bytes: bytes, sheet_name: str | int = 0) -> ValidationResult:
    return validate_and_normalize_csv(
        file_bytes,
        required_columns=TEST_RESULT_REQUIRED_COLUMNS,
        known_columns=TEST_RESULT_REQUIRED_COLUMNS + TEST_RESULT_OPTIONAL_COLUMNS,
        sheet_name=sheet_name,
    )
