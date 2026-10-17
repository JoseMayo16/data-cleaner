"""Apply the rules to a whole table and keep a full audit trail.

Every changed cell is recorded (row, column, before, after, rules), every value that could not
be fixed becomes an issue, and duplicates are removed or flagged with the row they repeat.
Row numbers are spreadsheet rows (header = row 1) so they match what the user sees in Excel.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date

from . import rules
from .detect import detect_date_order, detect_decimal, detect_kind
from .table import Table, write_xlsx

MDY_COUNTRIES = {"US"}
COMMA_DECIMAL_COUNTRIES = {"CO", "ES", "AR", "CL", "PE", "EC", "DE"}


@dataclass
class Options:
    country: str = "CO"
    date_order: str = "auto"  # auto | DMY | MDY
    decimal: str = "auto"  # auto | , | .
    duplicates: str = "remove"  # remove | flag | keep
    kinds: dict[str, str] = field(default_factory=dict)  # column -> kind overrides
    fix_names: bool = True
    merge_categories: bool = True
    fix_email_typos: bool = True
    # One row per person (contact lists): flag different rows sharing an email or phone.
    # Turn off for transaction tables, where a customer appears on many orders.
    flag_shared_contacts: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> Options:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Change:
    row: int
    column: str
    before: str
    after: str
    rules: list[str]


@dataclass
class Issue:
    row: int
    column: str
    value: str
    problem: str


@dataclass
class ColumnReport:
    name: str
    kind: str
    filled: int
    unique: int
    changed: int = 0
    issues: int = 0
    detail: str = ""
    examples: list[str] = field(default_factory=list)


@dataclass
class Report:
    rows_in: int
    rows_out: int
    columns: list[ColumnReport]
    changes: list[Change]
    issues: list[Issue]
    duplicates: list[dict]
    rule_counts: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)


def profile(table: Table, options: Options | None = None) -> list[ColumnReport]:
    options = options or Options()
    out = []
    for i, name in enumerate(table.columns):
        values = table.column(i)
        filled = [v for v in values if v.strip() and not rules.is_empty_token(v)]
        kind = options.kinds.get(name) or detect_kind(name, values)
        examples = list(dict.fromkeys(rules.squeeze(v) for v in filled))[:4]
        out.append(ColumnReport(name, kind, len(filled), len(set(filled)), examples=examples))
    return out


def _canonical_variants(values: list[str]) -> dict[str, str]:
    """Map every spelling of a category to its most common spelling."""
    groups: dict[str, Counter] = defaultdict(Counter)
    for v in values:
        if v:
            groups[re.sub(r"[^a-z0-9]", "", rules.plain(v))][v] += 1

    def rank(item):
        # Prefer a properly capitalized spelling with its accents ("Medellín" over
        # "MEDELLIN"), then the most frequent one.
        text, count = item
        return (not text.isupper() and not text.islower(), not text.isascii(), count)

    mapping = {}
    for variants in groups.values():
        best = max(variants.items(), key=rank)[0]
        mapping.update({v: best for v in variants})
    return mapping


def clean(table: Table, options: Options | None = None) -> tuple[Table, Report]:
    options = options or Options()
    columns = profile(table, options)
    default_order = "MDY" if options.country in MDY_COUNTRIES else "DMY"
    default_decimal = "," if options.country in COMMA_DECIMAL_COUNTRIES else "."

    rows = [list(r) for r in table.rows]
    applied: dict[tuple[int, int], list[str]] = defaultdict(list)
    issues: list[Issue] = []
    rule_counts: Counter = Counter()

    for c, col in enumerate(columns):
        values = [r[c] for r in rows]
        if col.kind == "date":
            order = (
                options.date_order
                if options.date_order != "auto"
                else detect_date_order(values, default_order)
            )
            col.detail = "day/month/year" if order == "DMY" else "month/day/year"
        if col.kind == "number":
            decimal = (
                options.decimal
                if options.decimal != "auto"
                else detect_decimal(values, default_decimal)
            )
            col.detail = "decimal comma" if decimal == "," else "decimal point"
        if col.kind == "phone":
            col.detail = f"default country {options.country}"

        for r, row in enumerate(rows):
            original, v, used = row[c], row[c], applied[(r, c)]
            squeezed = rules.squeeze(v)
            if squeezed != v:
                v = squeezed
                used.append("whitespace")
            if v and rules.is_empty_token(v):
                v = ""
                used.append("empty_value")

            problem = None
            if v and col.kind == "email":
                v, email_rules, problem = rules.normalize_email(v, options.fix_email_typos)
                used.extend(email_rules)
            elif v and col.kind == "phone":
                new, problem = rules.normalize_phone(v, options.country)
                if new != v:
                    v = new
                    used.append("phone_format")
            elif v and col.kind == "date":
                iso = rules.parse_date(v, order)
                if iso is None:
                    problem = "unrecognized or impossible date"
                elif iso != v:
                    v = iso
                    used.append("date_format")
            elif v and col.kind == "number":
                number = rules.parse_number(v, decimal)
                if number is None:
                    problem = "not a number"
                elif number != v:
                    v = number
                    used.append("number_format")
            elif v and col.kind == "name" and options.fix_names:
                new = rules.title_name(v)
                if new != v:
                    v = new
                    used.append("name_case")

            row[c] = v
            if problem:
                issues.append(Issue(table.source_rows[r], col.name, original, problem))
                col.issues += 1

        if col.kind == "category" and options.merge_categories:
            mapping = _canonical_variants([row[c] for row in rows])
            for r, row in enumerate(rows):
                if row[c] and mapping.get(row[c], row[c]) != row[c]:
                    row[c] = mapping[row[c]]
                    applied[(r, c)].append("category_variant")

    changes = []
    for (r, c), used in sorted(applied.items()):
        if used and rows[r][c] != table.rows[r][c]:
            changes.append(
                Change(table.source_rows[r], table.columns[c], table.rows[r][c], rows[r][c], used)
            )
            columns[c].changed += 1
            rule_counts.update(used)

    kept_rows, kept_source, duplicates = _deduplicate(rows, table.source_rows, options, issues)
    if options.flag_shared_contacts:
        _flag_shared_contacts(kept_rows, kept_source, columns, issues)
    if duplicates:
        rule_counts["duplicate_row"] = len(duplicates)

    issues.sort(key=lambda i: (i.row, i.column))
    report = Report(
        len(table.rows),
        len(kept_rows),
        columns,
        changes,
        issues,
        duplicates,
        dict(rule_counts.most_common()),
    )
    return Table(list(table.columns), kept_rows, kept_source), report


def _deduplicate(rows, source, options, issues):
    first_seen: dict[tuple, int] = {}
    kept, kept_source, duplicates = [], [], []
    for row, src in zip(rows, source, strict=True):
        key = tuple(rules.plain(v) for v in row)
        if key in first_seen and options.duplicates != "keep":
            duplicates.append({"row": src, "duplicate_of": first_seen[key]})
            if options.duplicates == "flag":
                issues.append(Issue(src, "", "", f"duplicate of row {first_seen[key]}"))
                kept.append(row)
                kept_source.append(src)
            continue
        first_seen.setdefault(key, src)
        kept.append(row)
        kept_source.append(src)
    return kept, kept_source, duplicates


def _flag_shared_contacts(rows, source, columns, issues):
    """Different rows with the same email or phone are probably the same person."""
    for c, col in enumerate(columns):
        if col.kind not in ("email", "phone"):
            continue
        seen: dict[str, int] = {}
        for row, src in zip(rows, source, strict=True):
            value = row[c]
            if not value:
                continue
            if value in seen:
                issues.append(
                    Issue(
                        src,
                        col.name,
                        value,
                        f"same {col.kind} as row {seen[value]}: possible duplicate",
                    )
                )
            else:
                seen[value] = src


def typed_rows(table: Table, columns: list[ColumnReport]) -> list[list]:
    """Numbers as numbers and dates as dates, for Excel output."""
    kinds = [c.kind for c in columns]
    out = []
    for row in table.rows:
        typed = []
        for v, kind in zip(row, kinds, strict=True):
            if v and kind == "number" and rules.parse_number(v) == v:
                typed.append(float(v) if "." in v else int(v))
            elif v and kind == "date" and len(v) == 10 and v[4] == "-":
                typed.append(date.fromisoformat(v))
            else:
                typed.append(v)
        out.append(typed)
    return out


def to_xlsx(table: Table, report: Report) -> bytes:
    return write_xlsx(
        {
            "Cleaned": (table.columns, typed_rows(table, report.columns)),
            "Issues": (
                ["row", "column", "value", "problem"],
                [[i.row, i.column, i.value, i.problem] for i in report.issues],
            ),
            "Changes": (
                ["row", "column", "before", "after", "rules"],
                [[c.row, c.column, c.before, c.after, ", ".join(c.rules)] for c in report.changes],
            ),
        }
    )
