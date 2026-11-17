#!/usr/bin/env python3
"""unpack - recreate files from a bundle made by pack.py.

Usage:
    unpack.py BUNDLE [-d DIR] [--force] [--list]

Files are written under DIR (default: current directory). Your block
configs live in DIR/common_files/, next to flowgen/; flowgen reads them
from there, so unpack never has to be run again for a new config.

If a top-level directory from the bundle (flowgen/) already exists in DIR,
unpack stops with an error and changes nothing. With --force that directory
is removed first and recreated from the bundle, so no stale files are left
behind. If it holds files of your own (anything that is not in the bundle,
e.g. run directories), it is not deleted but renamed to flowgen.old_<date>_<time>. Nothing else in DIR is removed:
common_files/ is never in a bundle and is never touched. Top-level files
(pack.py, unpack.py) are overwritten.

Every file is checked against its MD5 before anything is written; a damaged
bundle writes nothing.

Python 3.6+, standard library only.
"""

import argparse
import base64
import binascii
import datetime
import hashlib
import os
import re
import shutil
import sys

CONFIG_SRC = "common_files"          # local golden configs (never in a bundle)

PROTECTED_TOPS = (CONFIG_SRC, ".git")  # a bundle may never write here
PATH_RE = re.compile(r"^[A-Za-z0-9._+-]+(/[A-Za-z0-9._+-]+)*\Z")

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

    files, seen, i = [], set(), 1
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
        if path in seen:
            raise BundleError("line %d: file is in the bundle twice: %s" % (i + 1, path))
        seen.add(path)

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
    if not files:
        raise BundleError("the bundle contains no files")
    for path in seen:
        parent = path.rpartition("/")[0]
        while parent:
            if parent in seen:
                raise BundleError("%s is both a file and a directory in the bundle" % parent)
            parent = parent.rpartition("/")[0]
    return files


def check_path(path, i):
    parts = path.split("/")
    if (not PATH_RE.match(path) or "." in parts or ".." in parts
            or parts[0] in PROTECTED_TOPS):
        raise BundleError("line %d: unsafe path: %s" % (i + 1, path))


def own_files(top_dir, bundle_paths, top):
    """Files under top_dir that are the user's: not in the bundle, not links, not caches.

    Links are skipped because older versions of unpack created config
    links in flowgen/configs/.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(top_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = top + "/" + os.path.relpath(full, top_dir).replace(os.sep, "/")
            if not os.path.islink(full) and rel not in bundle_paths and not name.endswith(".pyc"):
                found.append(rel)
    return sorted(found)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recreate files from a pack.py bundle.")
    parser.add_argument("bundle", help="bundle file made by pack.py")
    parser.add_argument("-d", "--dir", default=".", help="output directory (default: .)")
    parser.add_argument("--force", action="store_true",
                        help="replace the existing flowgen/ (top-level directories in the "
                             "bundle); it is kept as flowgen.old_<date>_<time> if it holds "
                             "files of your own. Nothing else is removed")
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
    for path, _, _ in files:
        if "/" not in path and os.path.isdir(os.path.join(args.dir, path)):
            sys.exit("unpack: ERROR: %s is a directory in %s but a file in the bundle"
                     % (path, os.path.abspath(args.dir)))

    bundle_paths = set(p for p, _, _ in files)
    try:
        for top in existing:
            target = os.path.join(args.dir, top)
            if os.path.isdir(target) and not os.path.islink(target):
                mine = own_files(target, bundle_paths, top)
                if mine:
                    backup = "%s.old_%s" % (target, datetime.datetime.now().strftime(
                        "%Y%m%d_%H%M%S"))
                    os.rename(target, backup)
                    print("unpack: existing %s holds %d file(s) of your own (%s%s); kept as %s"
                          % (target, len(mine), ", ".join(mine[:3]),
                             ", ..." if len(mine) > 3 else "", backup))
                else:
                    print("unpack: removing existing %s" % target)
                    shutil.rmtree(target)
            else:
                print("unpack: removing existing %s" % target)
                os.remove(target)

        for path, mode, data in files:
            dest = os.path.join(args.dir, *path.split("/"))
            if os.path.dirname(dest):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(data)
            os.chmod(dest, mode)
    except OSError as exc:
        sys.exit("unpack: ERROR: %s\nunpack: stopped part way; fix the problem and "
                 "run unpack again with --force." % exc)

    out_dir = os.path.abspath(args.dir)
    print("unpack: %d files -> %s" % (len(files), out_dir))
    wrapper = os.path.join(out_dir, "flowgen", "runflowgen.sh")
    if os.path.isfile(wrapper):
        print("unpack: next, start a block:  %s --new <block>" % wrapper)
        print("unpack:   then generate it:   %s <block>" % wrapper)
    return 0


if __name__ == "__main__":
    sys.exit(main())
