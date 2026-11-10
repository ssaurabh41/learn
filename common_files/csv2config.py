#!/usr/bin/env python3
"""csv2config - turn a block config CSV into a block config Tcl file.

Usage:
    csv2config.py [--force] [-o OUTPUT] CSV

Arguments:
    CSV       The block config spreadsheet, named <block_name>.config.csv.
              Start from block_template.config.csv and edit it in
              LibreOffice (keep it as CSV when saving).
    -o        Output file. Default: the CSV name with .csv replaced by
              .tcl, next to the CSV (block.config.csv -> block.config.tcl).
    --force   Overwrite the output file if it already exists.
    -h        Show this help and exit.

Example:
    csv2config.py block.config.csv
    flowgen.py configs/block.config.tcl

CSV columns: Setting, Value, Required, Description, Example.
  - One value per row. For a list, add more rows with the same Setting
    (or an empty Setting cell); they are collected in order.
  - A Setting starting with # is a heading.
  - Empty Value means not used. Empty TOOL_*/ENV_SETENV entries are left out.
  - Description becomes a comment above the setting. Required and Example
    are for the reader only.
  - Settings flowgen does not know are written as your own helper
    variables, so you can use them as $NAME in other values.

Python 3.6+, standard library only.
"""

import argparse
import csv
import os
import re
import sys
import textwrap

# Settings that are lists in the config (one CSV row per item).
LIST_SETTINGS = (
    "FLOWS", "RTL_SEARCH_DIRS", "RTL_FILES", "RTL_INCDIRS", "RTL_DEFINES",
    "SYN_SEARCH_DIRS", "SYN_FILES", "APR_FILES", "SDC_FILES", "UPF_FILES",
    "LIB_FILES", "SIM_FILES", "BLACKBOX_MODULES", "ENV_SOURCE",
)
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\([^()\s]+\))?$")
COLUMNS = ("setting", "value", "required", "description", "example")


class CsvError(Exception):
    pass


def tcl_quote(text):
    """Text in double quotes for Tcl. $NAME stays live (variables expand);
    characters Tcl would treat specially otherwise are escaped."""
    for ch in ("\\", '"', "[", "]"):
        text = text.replace(ch, "\\" + ch)
    return '"%s"' % text


def read_rows(path):
    """Rows as dicts with the COLUMNS keys, plus the CSV line number."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except (IOError, OSError) as exc:
        raise CsvError("cannot read %s: %s" % (path, exc))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvError("%s is not UTF-8/ASCII text; save it as CSV with UTF-8" % path)
    lines = text.splitlines(True)
    if not lines:
        raise CsvError("%s is empty" % path)
    # LibreOffice may save with ; or tab instead of , depending on settings.
    header = lines[0]
    delimiter = max((",", ";", "\t"), key=header.count)
    reader = csv.reader(lines, delimiter=delimiter)
    head = [h.strip().lower() for h in next(reader)]
    if head[:2] != ["setting", "value"]:
        raise CsvError("%s: first row must be the header Setting, Value, ... (got %s)"
                       % (path, ", ".join(head)))
    rows = []
    for lineno, cells in enumerate(reader, 2):
        cells = [c.strip() for c in cells] + [""] * len(COLUMNS)
        row = dict(zip(COLUMNS, cells))
        row["line"] = lineno
        rows.append(row)
    return rows


def collect(rows):
    """Group rows into ordered entries: ('heading', title) or
    ('setting', name, [values], description)."""
    entries, by_name, current = [], {}, None
    errors = []
    for row in rows:
        name, value = row["setting"], row["value"]
        if not any(row[c] for c in COLUMNS):
            continue
        if name.startswith("#"):
            entries.append(("heading", name.lstrip("#").strip()))
            current = None
            continue
        if not name:
            if not value:
                continue
            if current is None:
                errors.append("line %d: value %r has no Setting above it" % (row["line"], value))
                continue
            name = current
        if not NAME_RE.match(name):
            errors.append("line %d: %r is not a valid setting name" % (row["line"], name))
            continue
        if name in by_name:
            entry = by_name[name]
            if name not in LIST_SETTINGS:
                errors.append("line %d: %s is a single value but appears again "
                              "(first on line %d)" % (row["line"], name, entry[4]))
                continue
        else:
            entry = ["setting", name, [], row["description"], row["line"]]
            by_name[name] = entry
            entries.append(entry)
        if value:
            entry[2].append(value)
        current = name
    if errors:
        raise CsvError("\n".join(errors))
    return entries


def render(entries, csv_name):
    blocks, heading = [], None        # heading is written only if a setting follows
    for entry in entries:
        if entry[0] == "heading":
            heading = entry[1]
            continue
        _, name, values, description, _ = entry
        if "(" in name and not values:
            continue                      # empty TOOL_*/ENV_SETENV rows are left out
        lines = []
        if heading is not None:
            lines += ["", "# " + heading]
            heading = None
        lines.append("")
        for para in description.splitlines():
            lines += ["# " + l for l in textwrap.wrap(para, 74)]
        if name in LIST_SETTINGS:
            if values:
                lines.append("set %s {" % name)
                lines += ["  " + tcl_quote(v) for v in values]
                lines.append("}")
            else:
                lines.append("set %s {}" % name)
        else:
            lines.append("set %s %s" % (name, tcl_quote(values[0] if values else "")))
        blocks += lines
    header = "# From %s. Edit the CSV and rerun csv2config.py." % csv_name
    return "\n".join([header] + blocks) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", metavar="CSV", help="block config CSV, <block_name>.config.csv")
    parser.add_argument("-o", "--output", help="output .config.tcl file")
    parser.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = parser.parse_args(argv)

    if not args.csv.endswith(".config.csv"):
        print("csv2config: WARNING: config CSVs are named <block_name>.config.csv: %s" % args.csv)
    output = args.output or (args.csv[:-len(".csv")] + ".tcl" if args.csv.endswith(".csv")
                             else args.csv + ".tcl")
    if os.path.exists(output) and not args.force:
        sys.exit("csv2config: ERROR: %s already exists. Use --force to overwrite it." % output)

    try:
        entries = collect(read_rows(args.csv))
    except CsvError as exc:
        sys.exit("\n".join("csv2config: ERROR: " + l for l in str(exc).splitlines()))
    text = render(entries, os.path.basename(args.csv))
    if any(ord(c) > 127 for c in text):
        print("csv2config: WARNING: non-ASCII characters in the CSV were copied to %s" % output)

    with open(output, "w") as fh:
        fh.write(text)
    print("csv2config: wrote %s" % output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
