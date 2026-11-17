#!/usr/bin/env python3
"""pack - concatenate a repo's files into one plain-text bundle.

Usage:
    pack.py [-o BUNDLE] [ROOT]

ROOT defaults to the git repo containing the current directory (or the
current directory if not in git). In a git repo only tracked files are
packed, as they are on disk, with the file mode recorded in git; files
that are not committed are listed in a warning. Outside a git repo every
file under ROOT is packed. Paths under EXCLUDE_DIRS are never packed:
docs/, and common_files/ (the golden block configs live only on the
user's machine).

The bundle is pure ASCII, so it survives copy/paste, downloads and CRLF
line endings. Pure-ASCII text files are stored as readable lines; any other
file (non-ASCII text, binary) is stored as base64 and restored byte-exact.
Recreate the files with unpack.py (which is itself inside the bundle).

Bundle format:
    #@@PACK 3
    #@@FILE <path> mode=<octal> enc=<text|b64> lines=<n> eol=<0|1> md5=<hex>
    <n lines: file content (text) or base64 of the raw bytes (b64)>
    #@@END <path>

Python 3.6+, standard library only.
"""

import argparse
import base64
import hashlib
import os
import re
import subprocess
import sys

EXCLUDE_DIRS = ("docs/", "common_files/")   # top-level directories never packed
PATH_RE = re.compile(r"^[A-Za-z0-9._+-]+(/[A-Za-z0-9._+-]+)*\Z")   # what unpack.py accepts


class PackError(Exception):
    pass


def git(root, *args):
    return subprocess.check_output(("git", "-C", root) + args,
                                   stderr=subprocess.DEVNULL).decode("utf-8", "replace")


def repo_root():
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                      stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except (OSError, subprocess.CalledProcessError):
        return os.getcwd()


def in_git_repo(root):
    path = root
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return True
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def list_files(root):
    """Return ({relative path: mode}, [warnings]); paths use '/' separators.

    In a git repo: the tracked files, with the mode recorded in git (so a
    bundle packed on Windows keeps the execute bits).
    """
    modes, warnings = {}, []
    if in_git_repo(root):
        try:
            # Each entry: "<mode> <hash> <stage>\t<path>"
            for entry in git(root, "ls-files", "-s", "-z").split("\0"):
                if entry:
                    info, _, rel = entry.partition("\t")
                    modes[rel] = 0o755 if info.startswith("100755") else 0o644
            # Each entry: "XY <path>"
            for entry in git(root, "status", "--porcelain", "-z").split("\0"):
                rel = entry[3:]
                if not entry or rel.startswith(EXCLUDE_DIRS):
                    continue
                if entry.startswith("??"):
                    warnings.append("not in git, NOT packed: %s" % rel)
                elif os.path.isfile(os.path.join(root, rel)):
                    warnings.append("not committed, packed as it is on disk: %s" % rel)
                else:
                    warnings.append("deleted on disk, NOT packed: %s" % rel)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise PackError("%s is a git repo but git failed (%s); nothing packed" % (root, exc))
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for name in filenames:
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                modes[rel] = 0o755 if os.stat(path).st_mode & 0o100 else 0o644
    modes = dict((f, m) for f, m in modes.items()
                 if os.path.isfile(os.path.join(root, f)) and not f.startswith(EXCLUDE_DIRS))
    return modes, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pack repo files into one text bundle.")
    parser.add_argument("root", nargs="?", help="directory to pack (default: git repo root)")
    parser.add_argument("-o", "--output", help="bundle file (default: bundle.txt)")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root or repo_root())
    output = os.path.abspath(args.output or "bundle.txt")
    if not os.path.isdir(root):
        sys.exit("pack: ERROR: not a directory: %s" % root)
    try:
        modes, warnings = list_files(root)
    except PackError as exc:
        sys.exit("pack: ERROR: %s" % exc)

    chunks = ["#@@PACK 3\n"]
    packed, encoded = 0, []
    for rel in sorted(modes):
        path = os.path.join(root, rel)
        if os.path.abspath(path) == output:
            continue
        if not PATH_RE.match(rel):
            sys.exit("pack: ERROR: file name not supported (use letters, digits and "
                     "._+- only): %s" % rel)
        with open(path, "rb") as fh:
            data = fh.read()
        if data.startswith(b"#@@PACK"):
            continue                     # never pack a bundle inside a bundle
        mode = modes[rel]

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

    if not packed:
        sys.exit("pack: ERROR: no files to pack in %s; %s not written" % (root, output))
    tmp = output + ".tmp"
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.writelines(chunks)
    os.replace(tmp, output)             # an old bundle is only replaced by a complete one

    for msg in warnings:
        print("pack: WARNING: %s" % msg)
    for rel in encoded:
        print("pack: note: not pure ASCII text, stored as base64: %s" % rel)
    print("pack: %d files from %s -> %s" % (packed, root, output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
