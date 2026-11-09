#!/usr/bin/env python3
"""pack - concatenate a repo's files into one plain-text bundle.

Usage:
    pack.py [-o BUNDLE] [ROOT]

ROOT defaults to the git repo containing the current directory (or the
current directory if not in git). In a git repo only tracked files are
packed; otherwise every file under ROOT except .git/ is packed. Paths
under EXCLUDE_DIRS (docs/) are never packed.

The bundle is pure ASCII, so it survives copy/paste, downloads and CRLF
line endings. Pure-ASCII text files are stored as readable lines; any other
file (non-ASCII text, binary) is stored as base64 and restored byte-exact.
Recreate the files with unpack.py (which is itself inside the bundle).

Bundle format:
    #@@PACK 2
    #@@FILE <path> mode=<octal> enc=<text|b64> lines=<n> eol=<0|1> md5=<hex>
    <n lines: file content (text) or base64 of the raw bytes (b64)>
    #@@END <path>

Python 3.6+, standard library only.
"""

import argparse
import base64
import hashlib
import os
import subprocess
import sys

EXCLUDE_DIRS = ("docs/",)   # top-level directories never packed


def repo_root():
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                      stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except (OSError, subprocess.CalledProcessError):
        return os.getcwd()


def list_files(root):
    """Sorted relative paths with '/' separators."""
    try:
        out = subprocess.check_output(["git", "-C", root, "ls-files", "-z"],
                                      stderr=subprocess.DEVNULL)
        files = [f for f in out.decode("utf-8").split("\0") if f]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                files.append(rel.replace(os.sep, "/"))
    return sorted(f for f in files
                  if os.path.isfile(os.path.join(root, f)) and not f.startswith(EXCLUDE_DIRS))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pack repo files into one text bundle.")
    parser.add_argument("root", nargs="?", help="directory to pack (default: git repo root)")
    parser.add_argument("-o", "--output", help="bundle file (default: bundle.txt)")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root or repo_root())
    output = os.path.abspath(args.output or "bundle.txt")

    chunks = ["#@@PACK 2\n"]
    packed, encoded = 0, []
    for rel in list_files(root):
        path = os.path.join(root, rel)
        if os.path.abspath(path) == output:
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        if data.startswith(b"#@@PACK"):
            continue                     # never pack a bundle inside a bundle
        mode = os.stat(path).st_mode & 0o777

        norm = data.replace(b"\r\n", b"\n")
        if all(b in b"\t\n" or 32 <= b < 127 for b in norm):
            enc, data = "text", norm
            text = data.decode("ascii")
            eol = 1 if text.endswith("\n") or not text else 0
            lines = text.split("\n")
            if eol:
                lines = lines[:-1]       # drop the empty piece after the last newline
        else:
            enc, eol = "b64", 1
            b64 = base64.b64encode(data).decode("ascii")
            lines = [b64[i:i + 76] for i in range(0, len(b64), 76)]
            encoded.append(rel)
        md5 = hashlib.md5(data).hexdigest()

        chunks.append("#@@FILE %s mode=%03o enc=%s lines=%d eol=%d md5=%s\n"
                      % (rel, mode, enc, len(lines), eol, md5))
        chunks.extend(line + "\n" for line in lines)
        chunks.append("#@@END %s\n" % rel)
        packed += 1

    with open(output, "w", encoding="ascii", newline="\n") as fh:
        fh.writelines(chunks)

    for rel in encoded:
        print("pack: note: not pure ASCII text, stored as base64: %s" % rel)
    print("pack: %d files from %s -> %s" % (packed, root, output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
