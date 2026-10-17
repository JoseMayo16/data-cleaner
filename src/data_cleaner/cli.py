"""Command line entry point.

data-cleaner profile contacts.xlsx
data-cleaner clean contacts.xlsx -o clean.xlsx [--report report.json] [--country CO]
                   [--date-order auto|DMY|MDY] [--decimal auto|,|.]
                   [--duplicates remove|flag|keep] [--kind "Tel 2=phone" ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cleaner import Options, clean, profile, to_xlsx
from .detect import KINDS
from .rules import COUNTRIES
from .table import TableError, read_any, write_csv


def _kinds(pairs: list[str]) -> dict[str, str]:
    out = {}
    for pair in pairs:
        name, _, kind = pair.rpartition("=")
        if not name or kind not in KINDS:
            raise SystemExit(f"--kind expects COLUMN=KIND with KIND in {', '.join(KINDS)}")
        out[name] = kind
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="data-cleaner")
    sub = parser.add_subparsers(dest="command", required=True)

    prof = sub.add_parser("profile", help="show what each column looks like")
    prof.add_argument("file", type=Path)
    prof.add_argument("--sheet")

    run = sub.add_parser("clean", help="clean a file")
    run.add_argument("file", type=Path)
    run.add_argument("-o", "--output", type=Path, required=True, help=".csv or .xlsx")
    run.add_argument("--sheet")
    run.add_argument("--report", type=Path, help="full audit trail as JSON")
    run.add_argument("--country", default="CO", choices=sorted(COUNTRIES))
    run.add_argument("--date-order", default="auto", choices=["auto", "DMY", "MDY"])
    run.add_argument("--decimal", default="auto", choices=["auto", ",", "."])
    run.add_argument("--duplicates", default="remove", choices=["remove", "flag", "keep"])
    run.add_argument("--kind", action="append", default=[], metavar="COLUMN=KIND")
    run.add_argument(
        "--allow-repeats",
        action="store_true",
        help="rows may share an email or phone (orders, transactions)",
    )
    args = parser.parse_args(argv)

    try:
        table = read_any(args.file.read_bytes(), args.file.name, args.sheet)
    except (TableError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "profile":
        print(f"{len(table.rows)} rows, {len(table.columns)} columns\n")
        for col in profile(table):
            examples = " | ".join(col.examples)
            print(f"{col.name[:24]:24} {col.kind:9} {col.filled:6} filled  {examples[:70]}")
        return 0

    options = Options(
        country=args.country,
        date_order=args.date_order,
        decimal=args.decimal,
        duplicates=args.duplicates,
        kinds=_kinds(args.kind),
        flag_shared_contacts=not args.allow_repeats,
    )
    cleaned, report = clean(table, options)
    if args.output.suffix.lower() == ".xlsx":
        args.output.write_bytes(to_xlsx(cleaned, report))
    else:
        args.output.write_bytes(write_csv(cleaned))
    if args.report:
        args.report.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(f"{report.rows_in} rows in, {report.rows_out} rows out", file=sys.stderr)
    print(
        f"{len(report.changes)} cells changed, {len(report.issues)} issues, "
        f"{len(report.duplicates)} duplicate rows",
        file=sys.stderr,
    )
    for rule, count in report.rule_counts.items():
        print(f"  {rule:20} {count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
