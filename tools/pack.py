#!/usr/bin/env python3
"""pack - concatenate a repo's files into one plain-text bundle.

Usage:
    pack.py [-o BUNDLE] [ROOT]

ROOT defaults to the git repo containing the current directory (or the
current directory if not in git). In a git repo only tracked files are
packed; otherwise every file under ROOT except .git/ is packed.

The bundle is plain text, so it survives copy/paste and CRLF line endings.
Recreate the files with unpack.py (which is itself inside the bundle).

Bundle format:
    #@@PACK 1
    #@@FILE <path> mode=<octal> lines=<n> eol=<0|1> md5=<hex>
    <n lines of file content>
    #@@END <path>

Python 3.6+, standard library only.
"""

import argparse
import hashlib
import os
import subprocess
import sys


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
    return sorted(f for f in files if os.path.isfile(os.path.join(root, f)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pack repo files into one text bundle.")
    parser.add_argument("root", nargs="?", help="directory to pack (default: git repo root)")
    parser.add_argument("-o", "--output", help="bundle file (default: bundle.txt)")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root or repo_root())
    output = os.path.abspath(args.output or "bundle.txt")

    chunks = ["#@@PACK 1\n"]
    packed, non_ascii, skipped = 0, [], []
    for rel in list_files(root):
        path = os.path.join(root, rel)
        if os.path.abspath(path) == output:
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append(rel)          # binary file: not supported
            continue
        if "\0" in text:
            skipped.append(rel)
            continue
        if text.startswith("#@@PACK"):
            continue                     # never pack a bundle inside a bundle
        if any(ord(c) > 127 for c in text):
            non_ascii.append(rel)

        text = text.replace("\r\n", "\n")
        eol = 1 if text.endswith("\n") or not text else 0
        lines = text.split("\n")
        if eol:
            lines = lines[:-1]           # drop the empty piece after the last newline
        mode = os.stat(path).st_mode & 0o777
        md5 = hashlib.md5(text.encode("utf-8")).hexdigest()

        chunks.append("#@@FILE %s mode=%03o lines=%d eol=%d md5=%s\n"
                      % (rel, mode, len(lines), eol, md5))
        chunks.extend(line + "\n" for line in lines)
        chunks.append("#@@END %s\n" % rel)
        packed += 1

    with open(output, "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(chunks)

    for rel in skipped:
        print("pack: WARNING: skipped binary file: %s" % rel)
    for rel in non_ascii:
        print("pack: WARNING: non-ASCII characters in: %s" % rel)
    print("pack: %d files from %s -> %s" % (packed, root, output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
