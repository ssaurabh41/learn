#!/usr/bin/env python3
"""csv2config - turn a block config spreadsheet (CSV) into a block config.

Usage:
    csv2config.py [--force] [-o OUTPUT] CSV

Arguments:
    CSV       The block config spreadsheet, <block>.config.csv, normally in
              flowgen/configs/. Start from configs/block_template.config.csv:
                cp flowgen/configs/block_template.config.csv \\
                   flowgen/configs/uart_ctrl.config.csv
              Edit it in LibreOffice (when opening, set the Value column to
              Text) and save it as CSV.
    -o        Output file. Default: the CSV name with .csv replaced by
              .tcl, next to the CSV (uart_ctrl.config.csv ->
              uart_ctrl.config.tcl), which is where runflowgen.sh finds it.
    --force   Overwrite the output file if it already exists.
    -h        Show this help and exit.

Example:
    csv2config.py flowgen/configs/uart_ctrl.config.csv
    runflowgen.sh uart_ctrl

CSV columns: Setting, Value, Required, Description, Example.
  - One value per row. For a list, add more rows with the same Setting
    (or an empty Setting cell); they are collected in order.
  - A Setting starting with # is a heading.
  - An empty Value means "not set here", so the project config's value
    (or flowgen's default) is used. Empty rows are left out of the output.
  - Setting "source" writes "source <file>", e.g. project.config.tcl.
  - Description becomes a comment above the setting. Required and Example
    are for the reader only.
  - Settings flowgen does not know are written as your own helper
    variables (e.g. USER_RTL_DIR), so you can use them as $NAME.

Python 3.6+, standard library only.
"""

import argparse
import csv
import os
import re
import sys
import textwrap

sys.dont_write_bytecode = True        # no __pycache__/ in flowgen/ (unpack.py
                                      # would treat it as a file of yours)
from flowgen import LIST_SETTINGS, CONFIG_DIR, CONFIG_SUFFIX   # flowgen.py, same directory

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\([^()\s]+\))?\Z")
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
    delimiter = max((",", ";", "\t"), key=lines[0].count)
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
    """Group rows into ordered entries: ['heading', title] or
    ['setting', name, values, description, first line]."""
    entries, by_name, current, errors = [], {}, None, []
    for row in rows:
        name, value = row["setting"], row["value"]
        if not any(row[c] for c in COLUMNS):
            continue
        if name.startswith("#"):
            entries.append(["heading", name.lstrip("#").strip()])
            current = None
            continue
        if not name:
            if not value:
                continue
            if current is None:
                errors.append("line %d: value %r has no Setting above it" % (row["line"], value))
                continue
            name = current
        if name != "source" and not NAME_RE.match(name):
            errors.append("line %d: %r is not a valid setting name" % (row["line"], name))
            continue
        if name in by_name and name not in LIST_SETTINGS and name != "source":
            errors.append("line %d: %s is a single value but appears again (first on line %d)"
                          % (row["line"], name, by_name[name][4]))
            continue
        if name in by_name and name != "source":
            entry = by_name[name]
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
    """Config text. Empty settings are left out; a heading is written only
    if a setting follows it."""
    blocks, heading = [], None
    for entry in entries:
        if entry[0] == "heading":
            heading = entry[1]
            continue
        _, name, values, description, _ = entry
        if not values:
            continue
        lines = []
        if heading is not None:
            lines += ["", "# " + heading]
            heading = None
        lines.append("")
        for para in description.splitlines():
            lines += ["# " + l for l in textwrap.wrap(para, 74)]
        if name == "source":
            lines += ["source %s" % tcl_quote(v) for v in values]
        elif name in LIST_SETTINGS:
            lines.append("set %s {" % name)
            lines += ["  " + tcl_quote(v) for v in values]
            lines.append("}")
        else:
            lines.append("set %s %s" % (name, tcl_quote(values[0])))
        blocks += lines
    header = "# From %s. Edit the CSV and rerun csv2config.py." % csv_name
    return "\n".join([header] + blocks) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", metavar="CSV", help="block config CSV, <block>.config.csv")
    parser.add_argument("-o", "--output", help="output .config.tcl file")
    parser.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = parser.parse_args(argv)

    if not args.csv.endswith(".config.csv"):
        print("csv2config: WARNING: block CSVs are named <block>.config.csv: %s" % args.csv)
    output = args.output or (args.csv[:-len(".csv")] + ".tcl" if args.csv.endswith(".csv")
                             else args.csv + ".tcl")
    if os.path.lexists(output) and not args.force:
        sys.exit("csv2config: ERROR: %s already exists. Use --force to overwrite it." % output)

    try:
        entries = collect(read_rows(args.csv))
    except CsvError as exc:
        sys.exit("\n".join("csv2config: ERROR: " + l for l in str(exc).splitlines()))
    text = render(entries, os.path.basename(args.csv))
    bad = sorted(set(ch for ch in text if ord(ch) > 126))
    if bad:
        sys.exit("csv2config: ERROR: the CSV has non-ASCII characters (%s); values must be "
                 "plain ASCII" % " ".join(ascii(ch) for ch in bad))

    with open(output, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    print("csv2config: wrote %s" % output)
    # A block name only works for a config in flowgen/configs/; anywhere
    # else give the path itself.
    name = os.path.basename(output)
    in_configs = (os.path.realpath(os.path.dirname(os.path.abspath(output)))
                  == os.path.realpath(CONFIG_DIR))
    if in_configs and name.endswith(CONFIG_SUFFIX):
        arg = name[:-len(CONFIG_SUFFIX)]
    else:
        arg = shell_word(output)
    print("csv2config: next, generate the run directory: runflowgen.sh %s" % arg)
    return 0


def shell_word(text):
    """text as one csh word: as is if plain, else in single quotes."""
    if re.match(r"^[A-Za-z0-9_./:+-]+\Z", text):
        return text
    return "'" + text.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    sys.exit(main())
