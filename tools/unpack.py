#!/usr/bin/env python3
"""unpack - recreate files from a bundle made by pack.py.

Usage:
    unpack.py BUNDLE [-d DIR] [--list]

Files are written under DIR (default: current directory), overwriting any
existing files with the same path. Every file is checked against its MD5
before anything is written; a damaged bundle writes nothing.

Python 3.6+, standard library only.
"""

import argparse
import hashlib
import os
import re
import sys

HEADER_RE = re.compile(r"^#@@FILE (\S+) mode=([0-7]{3}) lines=(\d+) eol=([01]) md5=([0-9a-f]{32})$")


class BundleError(Exception):
    pass


def parse(bundle_path):
    """Return [(path, mode, text)] after validating the whole bundle."""
    with open(bundle_path, encoding="utf-8") as fh:
        lines = [l.rstrip("\r\n") for l in fh]
    if not lines or lines[0] != "#@@PACK 1":
        raise BundleError("not a pack bundle (missing '#@@PACK 1' first line)")

    files, i = [], 1
    while i < len(lines):
        if lines[i] == "":
            i += 1                      # tolerate blank lines between files
            continue
        m = HEADER_RE.match(lines[i])
        if not m:
            raise BundleError("line %d: expected #@@FILE header, got: %r" % (i + 1, lines[i][:80]))
        path, mode, count, eol, md5 = m.groups()
        count = int(count)
        if path.startswith("/") or ".." in path.split("/"):
            raise BundleError("line %d: unsafe path: %s" % (i + 1, path))

        body = lines[i + 1:i + 1 + count]
        end = i + 1 + count
        if len(body) != count or end >= len(lines) or lines[end] != "#@@END " + path:
            raise BundleError("%s: truncated or damaged (missing #@@END)" % path)

        text = "\n".join(body) + ("\n" if eol == "1" and count else "")
        if hashlib.md5(text.encode("utf-8")).hexdigest() != md5:
            raise BundleError("%s: MD5 mismatch (content was changed in transit)" % path)
        files.append((path, int(mode, 8), text))
        i = end + 1
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recreate files from a pack.py bundle.")
    parser.add_argument("bundle", help="bundle file made by pack.py")
    parser.add_argument("-d", "--dir", default=".", help="output directory (default: .)")
    parser.add_argument("--list", action="store_true", help="only list the files")
    args = parser.parse_args(argv)

    try:
        files = parse(args.bundle)
    except (OSError, UnicodeDecodeError, BundleError) as exc:
        sys.exit("unpack: ERROR: %s" % exc)

    for path, mode, text in files:
        if args.list:
            print("%03o %s" % (mode, path))
            continue
        dest = os.path.join(args.dir, *path.split("/"))
        if os.path.dirname(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.chmod(dest, mode)

    if not args.list:
        print("unpack: %d files -> %s" % (len(files), os.path.abspath(args.dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
