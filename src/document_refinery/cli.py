"""Small operational CLI for local validation and SQL discovery."""

from __future__ import annotations

import argparse
from importlib.resources import files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="document-refinery")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("ddl", help="print the packaged Delta DDL")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "ddl":
        print(files("document_refinery.sql").joinpath("001_foundation.sql").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

