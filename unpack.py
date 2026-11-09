#!/usr/bin/env python3
"""unpack - recreate files from a bundle made by pack.py.

Usage:
    unpack.py BUNDLE [-d DIR] [--force] [--list]

Files are written under DIR (default: current directory). Then the
directory flowgen/configs/ (which holds block_template.config.tcl from the
bundle) gets one link per file in your local DIR/common_files/ (the golden
block configs):
    flowgen/configs/<name> -> ../../common_files/<name>
Re-run unpack (with --force) to pick up configs added to common_files/ later.

If a top-level directory from the bundle (flowgen/) already exists in DIR,
unpack stops with an error and changes nothing. With --force that directory
is removed first and recreated from the bundle, so no stale files are left
behind. Nothing else in DIR is removed: common_files/ is never in a bundle
and is never touched. Top-level files (pack.py, unpack.py) are overwritten.

Every file is checked against its MD5 before anything is written; a damaged
bundle writes nothing.

Python 3.6+, standard library only.
"""

import argparse
import base64
import binascii
import hashlib
import os
import re
import shutil
import sys

CONFIG_SRC = "common_files"          # local golden configs (never in a bundle)
CONFIG_LINK_DIR = "flowgen/configs"   # created by unpack, one link per config

HEADER_RE = re.compile(r"^#@@FILE (\S+) mode=([0-7]{3}) enc=(text|b64) lines=(\d+) "
                       r"eol=([01]) md5=([0-9a-f]{32})$")


class BundleError(Exception):
    pass


def read_bundle(bundle_path):
    with open(bundle_path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]                   # BOM added by some editors
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise BundleError("bundle has a non-ASCII byte 0x%02x at offset %d: it was changed "
                          "during transfer (character-set conversion). Bundles are pure "
                          "ASCII; copy it again as-is (e.g. download the raw file)."
                          % (raw[exc.start], exc.start))


def parse(bundle_path):
    """Return [(path, mode, bytes)] after validating the whole bundle."""
    lines = read_bundle(bundle_path).splitlines()
    if not lines or lines[0] != "#@@PACK 3":
        raise BundleError("not a pack.py bundle, or made by a different pack.py version "
                          "(first line must be '#@@PACK 3')")

    files, i = [], 1
    while i < len(lines):
        if lines[i].strip() == "":
            i += 1                      # tolerate blank lines between files
            continue
        m = HEADER_RE.match(lines[i].rstrip())
        if not m:
            raise BundleError("line %d: expected #@@FILE header, got: %r" % (i + 1, lines[i][:80]))
        path, mode, enc, count, eol, md5 = m.groups()
        count = int(count)
        check_path(path, i)

        body = lines[i + 1:i + 1 + count]
        end = i + 1 + count
        if len(body) != count or end >= len(lines) or lines[end].rstrip() != "#@@END " + path:
            raise BundleError("%s: truncated or damaged (missing #@@END)" % path)

        if enc == "text":
            data = ("\n".join(body) + ("\n" if eol == "1" and count else "")).encode("ascii")
        else:
            try:
                data = base64.b64decode("".join(l.strip() for l in body), validate=True)
            except (binascii.Error, ValueError):
                raise BundleError("%s: damaged base64 data" % path)
        if hashlib.md5(data).hexdigest() != md5:
            raise BundleError("%s: MD5 mismatch (content was changed in transit)" % path)
        files.append((path, int(mode, 8), data))
        i = end + 1
    return files


def check_path(path, i):
    if path.startswith("/") or ".." in path.split("/"):
        raise BundleError("line %d: unsafe path: %s" % (i + 1, path))


def link_configs(out_dir):
    """Create flowgen/configs/ with a relative link to each golden config."""
    src = os.path.join(out_dir, CONFIG_SRC)
    link_dir = os.path.join(out_dir, *CONFIG_LINK_DIR.split("/"))
    os.makedirs(link_dir, exist_ok=True)
    if not os.path.isdir(src):
        print("unpack: WARNING: %s not found; %s left empty"
              % (os.path.abspath(src), CONFIG_LINK_DIR))
        return
    rel_src = os.path.relpath(src, link_dir)       # ../../common_files
    names = sorted(n for n in os.listdir(src)
                   if not n.startswith(".") and os.path.isfile(os.path.join(src, n)))
    linked = 0
    for name in names:
        dest = os.path.join(link_dir, name)
        if os.path.lexists(dest):        # e.g. block_template.config.tcl from the bundle
            print("unpack: WARNING: %s/%s already exists (from the bundle); not linked"
                  % (CONFIG_LINK_DIR, name))
            continue
        os.symlink(os.path.join(rel_src, name), dest)
        linked += 1
    print("unpack: linked %d config(s) from %s into %s" % (linked, CONFIG_SRC, CONFIG_LINK_DIR))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recreate files from a pack.py bundle.")
    parser.add_argument("bundle", help="bundle file made by pack.py")
    parser.add_argument("-d", "--dir", default=".", help="output directory (default: .)")
    parser.add_argument("--force", action="store_true",
                        help="remove the existing flowgen/ (top-level directories in the "
                             "bundle) before unpacking; nothing else is removed")
    parser.add_argument("--list", action="store_true", help="only list the files")
    args = parser.parse_args(argv)

    try:
        files = parse(args.bundle)
    except (OSError, BundleError) as exc:
        sys.exit("unpack: ERROR: %s" % exc)

    if args.list:
        for path, mode, _ in files:
            print("%03o %s" % (mode, path))
        return 0

    # Top-level directories (flowgen) this bundle owns.
    tops = sorted(set(p.split("/")[0] for p, _, _ in files if "/" in p))
    existing = [t for t in tops if os.path.lexists(os.path.join(args.dir, t))]
    if existing and not args.force:
        sys.exit("unpack: ERROR: already exists in %s: %s\n"
                 "unpack: use --force to remove and recreate them."
                 % (os.path.abspath(args.dir), ", ".join(existing)))
    for top in existing:
        target = os.path.join(args.dir, top)
        print("unpack: removing existing %s" % target)
        if os.path.isdir(target) and not os.path.islink(target):
            shutil.rmtree(target)
        else:
            os.remove(target)

    for path, mode, data in files:
        dest = os.path.join(args.dir, *path.split("/"))
        if os.path.dirname(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(data)
        os.chmod(dest, mode)

    link_configs(args.dir)
    print("unpack: %d files -> %s" % (len(files), os.path.abspath(args.dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
