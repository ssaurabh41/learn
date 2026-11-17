#!/usr/bin/env python3
"""flowgen - generate EDA run directories from a Tcl block config.

Usage:
    runflowgen.sh --new BLOCK          (csh wrapper in this directory)
    runflowgen.sh [--force] BLOCK
    flowgen.py --new BLOCK
    flowgen.py [--force] BLOCK
    flowgen.py -h

Arguments:
    --new BLOCK
              Start a new block: create common_files/BLOCK.config.tcl (and
              common_files/project.config.tcl, the settings shared by all
              blocks, if it does not exist yet), then say what to edit.
    BLOCK     The block to generate: reads common_files/BLOCK.config.tcl.
              common_files/ is the directory next to flowgen/. A path to a
              config file is also accepted.
    --force  Generate the run directory even if input files are missing
              or a .f file list cannot be read. Without it those are
              errors; with it they become warnings, listed in the headers
              of the generated scripts. Use it to try out the flow before
              all design files exist. Other config errors (missing
              settings, bad values, Tcl errors) still stop generation.
    -h        Show this help and exit.

Examples:
    flowgen.py --new uart_ctrl
    flowgen.py uart_ctrl
    flowgen.py --force uart_ctrl
    flowgen.py /some/where/uart_ctrl.config.tcl

Output:
    ./<yyyy_mm_dd_hh_mm_ss>_<TOP_DESIGN>_formality/ in the current directory,
    with one run script per flow (run_<flow>.csh) and one sub-directory per
    flow where the tool runs, holding the generated Formality Tcl script
    (<flow>.tcl) and empty logs/ and reports/ directories. Nothing is launched;
    run the scripts manually. An existing directory is never overwritten;
    a second run in the same second gets a _2, _3, ... suffix.

Config:
    Plain Tcl, evaluated by a real Tcl interpreter (tkinter). Values are
    written in double quotes, lists in braces with one double-quoted item
    per line; $VARIABLES inside list items are expanded by flowgen.
    Relative paths are relative to the config file's real directory.
    A block config normally starts with "source project.config.tcl" to
    get the project settings. See configs/block_template.config.tcl for
    every supported setting. A config can also be made from a spreadsheet:
    see csv2config.py -h.

Requires Python 3.6+ built with tkinter. Standard library only.
"""

import argparse
import collections
import datetime
import difflib
import os
import re
import shutil
import stat
import sys

try:
    import tkinter
except ImportError:
    sys.exit("flowgen: ERROR: this Python has no tkinter (needed to read the "
             "Tcl config). Use a Python built with tkinter.")


SUPPORTED_FLOWS = ("rtl2syn",)
RTL_READERS = {"sverilog": "read_sverilog", "verilog": "read_verilog", "vhdl": "read_vhdl"}
LIB_READERS = {"db": "read_db", "lib": "read_lib"}
LIB_EXTENSIONS = {"db": (".db",), "lib": (".lib", ".lib.gz")}
HOOK_POINTS = ("setup", "pre_match", "pre_verify", "post_verify")
FM = "formality"          # tool key in TOOL_SETTINGS / TOOL_CMD / TOOL_HOOKS

# Every variable flowgen understands. A name that is not in this list but
# looks like one of them (e.g. BLACK_BOX_MODULES, top_design) produces a
# typo warning; any other name is treated as a user helper variable.
KNOWN_VARS = (
    "TOP_DESIGN", "FLOWS",
    "RTL_FORMAT", "RTL_SEARCH_DIRS", "RTL_FILES", "RTL_INCDIRS", "RTL_DEFINES",
    "SYN_SEARCH_DIRS", "SYN_FILES", "APR_FILES", "SVF_FILE", "SDC_FILES", "UPF_FILES",
    "LIB_FORMAT", "LIB_FILES", "SIM_FILES", "BLACKBOX_MODULES",
    "TOOL_CMD", "TOOL_SETTINGS", "TOOL_HOOKS",
    "ENV_SOURCE", "ENV_SETENV",
)

# Settings that are lists (one item per line in braces; one row per item
# in the CSV, see csv2config.py). The others are single values or arrays.
LIST_SETTINGS = (
    "FLOWS", "RTL_SEARCH_DIRS", "RTL_FILES", "RTL_INCDIRS", "RTL_DEFINES",
    "SYN_SEARCH_DIRS", "SYN_FILES", "APR_FILES", "SDC_FILES", "UPF_FILES",
    "LIB_FILES", "SIM_FILES", "BLACKBOX_MODULES", "ENV_SOURCE",
)

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\Z")

# Where things live: <root>/flowgen/flowgen.py, <root>/common_files/<block>.config.tcl
TOOL_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_DIR = os.path.join(os.path.dirname(TOOL_DIR), "common_files")
CONFIG_SUFFIX = ".config.tcl"
PROJECT_CONFIG = "project" + CONFIG_SUFFIX
NEW_BLOCK_TEMPLATE = os.path.join(TOOL_DIR, "configs", "new_block" + CONFIG_SUFFIX)
PROJECT_TEMPLATE = os.path.join(TOOL_DIR, "configs", "project_template" + CONFIG_SUFFIX)
WRAPPER = os.path.join(TOOL_DIR, "runflowgen.sh")     # shown in "what to type next" messages


class ConfigError(Exception):
    pass


# Reading the Tcl config

def load_tcl_config(path):
    """Source the config in a fresh Tcl interpreter.

    Returns ({name: str or {key: str}}, interpreter) for the global
    variables the config created (arrays become dicts; ENV_SETENV keeps
    the order in which the config set its entries).
    """
    tcl = tkinter.Tcl()
    before = set(tcl.splitlist(tcl.eval("info globals")))
    # Remember the order in which ENV_SETENV(...) entries are set.
    tcl.eval("namespace eval ::flowgen {variable env_order {}}")
    tcl.eval("trace add variable ::ENV_SETENV write "
             "{apply {{name key op} {lappend ::flowgen::env_order $key}}}")

    old_cwd = os.getcwd()
    os.chdir(os.path.dirname(path))      # relative paths/globs resolve here
    try:
        tcl.call("source", path)
    except tkinter.TclError as exc:
        detail = tcl.eval("set ::errorInfo")
        raise ConfigError("Tcl error while reading %s: %s\n%s" % (path, exc, detail))
    finally:
        os.chdir(old_cwd)

    values = {}
    for name in sorted(set(tcl.splitlist(tcl.eval("info globals"))) - before):
        if not IDENT_RE.match(name):
            continue  # flowgen variables are always plain identifiers
        if tcl.eval("array exists ::%s" % name) == "1":
            flat = tcl.splitlist(tcl.eval("array get ::%s" % name))
            values[name] = dict(zip(flat[0::2], flat[1::2]))
        elif tcl.eval("info exists ::%s" % name) == "1":
            values[name] = tcl.eval("set ::%s" % name)
    env = values.get("ENV_SETENV")
    if isinstance(env, dict):
        ordered = collections.OrderedDict()
        for key in tcl.splitlist(tcl.eval("set ::flowgen::env_order")):
            if key in env and key not in ordered:
                ordered[key] = env[key]
        for key in sorted(env):
            ordered.setdefault(key, env[key])
        values["ENV_SETENV"] = ordered
    return values, tcl


class FileSet(object):
    """Files collected from a file-list variable (with .f files expanded)."""

    def __init__(self):
        self.files = []
        self.incdirs = []
        self.defines = []


def add_unique(items, new):
    """Append the new items, skipping ones already present (order kept)."""
    for item in new:
        if item not in items:
            items.append(item)


class Config(object):
    """Typed, validated view of the block config. Collects all problems."""

    def __init__(self, path, force=False):
        self.force = force
        self.forced = []      # file errors downgraded to warnings by --force
        self.path = os.path.realpath(path)   # follow links
        self.dir = os.path.dirname(self.path)
        self.errors = []
        self.warnings = []
        self._raw, self._tcl = load_tcl_config(self.path)

        self.file_problems = 0    # missing or unreadable input files seen

        for name in sorted(self._raw):
            if name in KNOWN_VARS:
                continue
            close = difflib.get_close_matches(name.upper(), KNOWN_VARS, n=1, cutoff=0.75)
            if close:
                self.warnings.append("unknown variable '%s' ignored (did you mean %s?)"
                                     % (name, close[0]))

        self.top = self.scalar("TOP_DESIGN", required=True)
        if self.top and not IDENT_RE.match(self.top):
            self.errors.append("TOP_DESIGN: \"%s\" is not a module name (letters, digits "
                               "and _ only)" % self.top)
        self.flows = []
        add_unique(self.flows, self.tcl_list("FLOWS", default=["rtl2syn"]))
        for flow in self.flows:
            if flow not in SUPPORTED_FLOWS:
                self.errors.append("FLOWS: unknown flow '%s' (supported: %s)"
                                   % (flow, ", ".join(SUPPORTED_FLOWS)))

        # Design data
        self.rtl_format = self.choice("RTL_FORMAT", RTL_READERS, default="sverilog")
        self.rtl = self.fileset("RTL_FILES", "RTL_SEARCH_DIRS", required=True,
                                incdirs=self.paths("RTL_INCDIRS"))
        add_unique(self.rtl.defines, self.tcl_list("RTL_DEFINES"))
        for item in self.rtl.incdirs + self.rtl.defines:
            if re.search(r"\s", item):
                self.errors.append("RTL_INCDIRS / RTL_DEFINES: spaces are not supported "
                                   "in include directories and defines: \"%s\"" % item)
        if self.rtl_format == "vhdl" and (self.rtl.incdirs or self.rtl.defines):
            self.errors.append("RTL_INCDIRS / RTL_DEFINES (or +incdir+/+define+ in a .f "
                               "file) only apply to verilog/sverilog")
        needs_syn = "rtl2syn" in self.flows
        self.syn = self.fileset("SYN_FILES", "SYN_SEARCH_DIRS", required=needs_syn, netlist=True)
        # APR_FILES, SDC_FILES and UPF_FILES are not read by any flow yet,
        # so their files are not checked.
        self.apr = self.tcl_list("APR_FILES")
        svf = self.scalar("SVF_FILE")
        self.svf = self.resolve("SVF_FILE", svf) if svf else ""
        self.sdc = self.tcl_list("SDC_FILES")
        self.upf = self.tcl_list("UPF_FILES")
        if self.upf:
            self.warnings.append("UPF_FILES is set but not used yet: the generated "
                                 "Formality script does not load UPF")

        # Libraries and simulation models
        self.lib_format = self.choice("LIB_FORMAT", LIB_READERS, default="db")
        self.libs = self.paths("LIB_FILES", required=True)
        if self.lib_format in LIB_EXTENSIONS:
            for lib in self.libs:
                if not lib.endswith(LIB_EXTENSIONS[self.lib_format]):
                    self.warnings.append("LIB_FILES: %s does not look like a %s file "
                                         "(LIB_FORMAT is \"%s\")"
                                         % (lib, self.lib_format, self.lib_format))
        self.sim = self.fileset("SIM_FILES", netlist=True)
        self.blackboxes = self.tcl_list("BLACKBOX_MODULES")

        # Tool settings: TOOL_CMD(<tool>), TOOL_SETTINGS(<tool>,<name>), TOOL_HOOKS(<tool>,<point>)
        self.tool_cmd = self.array("TOOL_CMD")
        for tool, cmd in self.tool_cmd.items():
            if tool != FM:
                self.errors.append("TOOL_CMD(%s): unknown tool \"%s\" (supported: %s)"
                                   % (tool, tool, FM))
            elif re.search(r"[\r\n]", cmd):
                self.errors.append("TOOL_CMD(%s): must be one line" % tool)
        self.tool_settings = self.keyed_array("TOOL_SETTINGS")
        self.tool_hooks = {}
        for tool, points in self.keyed_array("TOOL_HOOKS").items():
            for point, file_name in points.items():
                if tool == FM and point not in HOOK_POINTS:
                    self.errors.append("TOOL_HOOKS(%s,%s): unknown hook point (valid: %s)"
                                       % (tool, point, ", ".join(HOOK_POINTS)))
                else:
                    self.tool_hooks.setdefault(tool, {})[point] = self.resolve(
                        "TOOL_HOOKS(%s,%s)" % (tool, point), file_name)
        for name in self.tool_settings.get(FM, {}):
            if not IDENT_RE.match(name):
                self.errors.append("TOOL_SETTINGS(%s,%s): not a valid app var name" % (FM, name))

        # Run environment. An ENV_SOURCE item is a file, optionally
        # followed by arguments: "/tools/setup.cshrc -v 2023.12".
        self.env_source = []
        for item in self.tcl_list("ENV_SOURCE"):
            words = item.split()
            self.env_source.append([self.resolve("ENV_SOURCE", words[0])] + words[1:])
        self.env_setenv = self.array("ENV_SETENV")
        for key in self.env_setenv:
            if not IDENT_RE.match(key):
                self.errors.append("ENV_SETENV(%s): not a valid environment variable name" % key)
        try:
            env_lines(self)          # reports values csh cannot quote
        except ConfigError as exc:
            self.errors.append(str(exc))

    def file_error(self, msg):
        """An error caused by a missing or unreadable input file."""
        self.file_problems += 1
        if self.force:
            self.forced.append(msg)
            self.warnings.append("%s (ignored: --force)" % msg)
        else:
            self.errors.append(msg)

    # Typed getters

    def _get(self, name, kind):
        value = self._raw.get(name)
        if value is None:
            return None
        is_array = isinstance(value, dict)
        if is_array != (kind == "array"):
            self.errors.append("%s must be %s" % (name, "an array, e.g. set %s(key) \"value\"" % name
                                                  if kind == "array"
                                                  else "a plain variable, not an array"))
            return None
        return value

    def scalar(self, name, default=None, required=False):
        value = self._get(name, "scalar")
        if value is None or value.strip() == "":
            if required:
                self.errors.append("%s is required" % name)
            return default
        return value.strip()

    def choice(self, name, options, default):
        value = self.scalar(name, default=default)
        if value not in options:
            self.errors.append("%s: \"%s\" is not one of %s"
                               % (name, value, ", ".join(sorted(options))))
        return value

    def tcl_list(self, name, default=None, required=False):
        """List items, with $variables expanded (braces do not expand them in Tcl)."""
        value = self._get(name, "scalar")
        items = []
        try:
            raw_items = self._tcl.splitlist(value) if value else ()
        except tkinter.TclError as exc:
            self.errors.append("%s: not a valid list (%s). Check the quotes and braces."
                               % (name, exc))
            return list(default or [])
        for item in raw_items:
            try:
                item = str(self._tcl.call("subst", "-nocommands", "-nobackslashes", item))
            except tkinter.TclError as exc:
                self.errors.append("%s: %s" % (name, exc))
                continue
            if item.strip():
                items.append(item.strip())
        if not items:
            if required:
                self.errors.append("%s is required (a list in braces)" % name)
            return list(default or [])
        return items

    def array(self, name):
        return self._get(name, "array") or {}

    def keyed_array(self, name):
        """NAME(<tool>,<key>) -> {tool: {key: value}}."""
        result = {}
        for key, value in self.array(name).items():
            tool, sep, sub = key.partition(",")
            if not sep or not tool or not sub:
                self.errors.append("%s(%s): key must be <tool>,<name>, e.g. %s(%s,...)"
                                   % (name, key, name, FM))
                continue
            if tool.strip() != FM:
                self.errors.append("%s(%s): unknown tool \"%s\" (supported: %s)"
                                   % (name, key, tool.strip(), FM))
                continue
            result.setdefault(tool.strip(), {})[sub.strip()] = value
        return result

    def resolve(self, label, path, base=None):
        """Absolute path (relative to base, default the config dir).

        A missing file is an error, or a warning with --force.
        """
        full = os.path.normpath(os.path.join(base or self.dir, os.path.expanduser(path)))
        if not os.path.exists(full):
            self.file_error("%s: file not found: %s" % (label, full))
        return full

    def paths(self, name, required=False):
        return [self.resolve(name, p) for p in self.tcl_list(name, required=required)]

    def search_dirs(self, name):
        """Directories of a *_SEARCH_DIRS setting (missing ones are file errors)."""
        dirs = []
        for d in self.paths(name):
            if os.path.exists(d) and not os.path.isdir(d):
                self.errors.append("%s: not a directory: %s" % (name, d))
            else:
                add_unique(dirs, [d])
        return dirs

    def find(self, label, path, search, base=None):
        """Locate a file. A full path is used as given. A relative one is
        tried next to base (the .f file, or the config), then in the search
        dirs in order; the first match wins. Not found anywhere is an error,
        or a warning with --force."""
        path = os.path.expanduser(path)
        base = base or self.dir
        if os.path.isabs(path):
            return self.resolve(label, path)
        dirs = []
        add_unique(dirs, [base] + list(search))
        found = []
        add_unique(found, [os.path.normpath(os.path.join(d, path)) for d in dirs
                           if os.path.exists(os.path.join(d, path))])
        if len(found) > 1:
            self.warnings.append("%s: %s found in several places, using %s"
                                 % (label, path, found[0]))
        if found:
            return found[0]
        self.file_error("%s: file not found: %s (searched: %s)" % (label, path, ", ".join(dirs)))
        return os.path.normpath(os.path.join(base, path))

    def expand(self, text):
        """$NAME / ${NAME} in a .f file: config variables first, then
        environment variables. Unknown names are left in place."""
        def value(m):
            name = m.group(1) or m.group(2)
            config_value = self._raw.get(name)
            if isinstance(config_value, str):
                return config_value
            return os.environ.get(name, m.group(0))
        return re.sub(r"\$\{(\w+)\}|\$(\w+)", value, text)

    def fileset(self, name, search_var=None, required=False, netlist=False, incdirs=()):
        """Files from a list variable; entries ending in .f are file lists.

        A file name without a full path is looked up next to the config (or
        next to its .f file), then in the search_var dirs, then in the
        include dirs (incdirs plus +incdir+ from the .f files).
        """
        result = FileSet()
        add_unique(result.incdirs, list(incdirs))
        search = self.search_dirs(search_var) if search_var else []
        problems = self.file_problems
        items = self.tcl_list(name, required=required)
        # Read every .f file first, so +incdir+ dirs from anywhere in them
        # are known before any file name is looked up.
        refs = []                        # (label for messages, file name, base dir)
        for item in items:
            if item.endswith(".f"):
                self.read_filelist(name, self.find(name, item, search), result, refs,
                                   [], search)
            else:
                refs.append((name, item, None))
        if netlist and (result.incdirs or result.defines):
            self.warnings.append("%s: +incdir+/+define+ in a .f file ignored for netlists" % name)
            result.incdirs, result.defines = [], []
        lookup = list(search)
        add_unique(lookup, result.incdirs)
        for label, ref, base in refs:
            add_unique(result.files, [self.find(label, ref, lookup, base)])
        if required and items and not result.files and self.file_problems == problems:
            self.errors.append("%s: the .f file lists contain no files" % name)
        return result

    def read_filelist(self, name, path, result, refs, stack, search):
        """Read a .f file: one name per line, // or # comments.

        A comment starts with // or # at the start of a line or after a
        space. $VAR and ${VAR} are config variables, then environment
        variables. Also understands -f/-F <file> (nested lists), -v <file>,
        +incdir+<dir>[+<dir>...] and +define+<MACRO>[=<value>][+...].
        File names go to refs and are looked up later (see fileset);
        +incdir+ dirs and nested .f files are relative to this .f file.
        """
        label = "%s (%s)" % (name, os.path.basename(path))
        real = os.path.realpath(path)
        if real in stack:
            self.errors.append("%s: file list includes itself" % label)
            return
        if not os.path.exists(path):
            return                       # already reported by find()
        try:
            with open(path, encoding="ascii", errors="replace") as fh:
                lines = fh.readlines()
        except (IOError, OSError) as exc:
            self.file_error("%s: cannot read file list: %s" % (label, exc))
            return
        base = os.path.dirname(path)
        for lineno, line in enumerate(lines, 1):
            line = FILELIST_COMMENT_RE.split(line, 1)[0].strip()
            if not line:
                continue
            where = "%s line %d" % (label, lineno)
            tokens = []
            for tok in line.split():
                tok = self.expand(tok)
                if "$" in tok:
                    self.errors.append("%s: variable not set in the config or the "
                                       "environment: %s" % (where, tok))
                else:
                    tokens.append(tok)
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok in ("-f", "-F", "-v", "-y"):
                    if i + 1 >= len(tokens):
                        self.errors.append("%s: %s needs a file name" % (where, tok))
                        break
                    if tok == "-y":
                        self.warnings.append("%s: -y library directories are not supported, "
                                             "ignored: %s" % (where, tokens[i + 1]))
                    elif tok == "-v":
                        refs.append((where, tokens[i + 1], base))
                    else:
                        self.read_filelist(name, self.find(where, tokens[i + 1], search, base),
                                           result, refs, stack + [real], search)
                    i += 2
                    continue
                if tok.startswith("+incdir+"):
                    add_unique(result.incdirs, [self.resolve(where, d, base)
                                                for d in tok[len("+incdir+"):].split("+") if d])
                elif tok.startswith("+define+"):
                    add_unique(result.defines,
                               [d for d in tok[len("+define+"):].split("+") if d])
                elif tok.startswith(("-", "+")):
                    self.warnings.append("%s: option %s not supported, ignored" % (where, tok))
                else:
                    refs.append((where, tok, base))
                i += 1


# Quoting helpers

FILELIST_COMMENT_RE = re.compile(r"(?:^|\s)(?://|#)")

_TCL_BARE = re.compile(r"^[A-Za-z0-9_./:+=@%,~-]+\Z")
_TCL_SPECIAL = re.compile(r'([\\{}\[\]$";# \t])')


def tcl_word(text):
    """Quote text as one Tcl word (also valid as a Tcl list element)."""
    if _TCL_BARE.match(text):
        return text
    if text and not re.search(r"[{}\\\r\n]", text):
        return "{%s}" % text
    text = _TCL_SPECIAL.sub(r"\\\1", text)
    return text.replace("\n", "\\n").replace("\r", "\\r") or "{}"


def tcl_list_block(items, indent="  "):
    """A braced, one-item-per-line Tcl list."""
    if not items:
        return "{}"
    return "{\n%s\n}" % "\n".join(indent + tcl_word(i) for i in items)


def csh_word(label, text):
    """Single-quote a value for csh; reject what csh cannot quote safely."""
    if re.search(r"['!\r\n]", text):
        raise ConfigError("%s: value may not contain ' or ! or newlines for csh: %r"
                          % (label, text))
    return "'%s'" % text


def csh_env_value(label, text):
    """Double-quote a setenv value for csh, so $VAR is expanded at run time."""
    if re.search(r'["`!\r\n]', text):
        raise ConfigError("%s: value may not contain \" or ` or ! or newlines for csh: %r"
                          % (label, text))
    return '"%s"' % text


def env_lines(cfg):
    """csh lines that set up the environment: ENV_SOURCE, then ENV_SETENV."""
    lines = []
    for words in cfg.env_source:
        path = csh_word("ENV_SOURCE", words[0])
        args = "".join(" " + csh_word("ENV_SOURCE", w) for w in words[1:])
        lines += [
            "if ( ! -r %s ) then" % path,
            "  echo %s" % csh_word("ENV_SOURCE", "ERROR: cannot read " + words[0]),
            "  exit 2",
            "endif",
            "source %s%s" % (path, args),
        ]
    for name, value in cfg.env_setenv.items():
        lines.append("setenv %s %s" % (name, csh_env_value("ENV_SETENV(%s)" % name, value)))
    return lines


# Formality script generation

def section(title):
    return ["", "# " + title]


def hook_lines(cfg, point):
    """'source <file>' for TOOL_HOOKS(formality,<point>), or nothing."""
    hook = cfg.tool_hooks.get(FM, {}).get(point)
    if not hook:
        return []
    return ["", "# Hook: %s" % point, "source %s" % tcl_word(hook)]


def vcs_option(fileset):
    """-vcs option carrying include dirs and defines, or ''."""
    opts = ["+incdir+" + d for d in fileset.incdirs] + ["+define+" + d for d in fileset.defines]
    return " -vcs %s" % tcl_word(" ".join(opts)) if opts else ""


def forced_header(cfg):
    """Comment lines listing the input problems ignored because of --force."""
    if not cfg.forced:
        return []
    return (["# WARNING: generated with --force, these input problems were ignored:"]
            + ["#   " + msg for msg in cfg.forced])


def gen_fm_rtl2syn(cfg, flow):
    """Formality script, <run_dir>/<flow>/<flow>.tcl, run from that directory."""
    settings = dict(cfg.tool_settings.get(FM, {}))
    auto_setup = settings.pop("synopsys_auto_setup", "true")
    lines = ["# Formality %s: RTL vs synthesized netlist for %s" % (flow, cfg.top)]
    lines += forced_header(cfg)
    lines += [
        "",
        "set FLOW %s" % tcl_word(flow),
        "set TOP_DESIGN %s" % tcl_word(cfg.top),
        "file delete -force ${FLOW}.status",
        "file delete -force {*}[glob -nocomplain reports/${FLOW}.*.rpt]",
    ]

    # synopsys_auto_setup first: it changes the defaults of other variables.
    lines += section("Setup")
    lines.append("set_app_var synopsys_auto_setup %s" % tcl_word(auto_setup))
    lines += ["set_app_var %s %s" % (n, tcl_word(settings[n])) for n in sorted(settings)]
    lines += hook_lines(cfg, "setup")

    if cfg.svf:
        lines += section("Synthesis guidance")
        lines.append("set_svf %s" % tcl_word(cfg.svf))

    lines += section("Libraries")
    lines += ["%s %s" % (LIB_READERS[cfg.lib_format], tcl_word(lib)) for lib in cfg.libs]

    lines += section("Reference: RTL")
    lines.append("%s -r %s%s" % (RTL_READERS[cfg.rtl_format], tcl_list_block(cfg.rtl.files),
                                 vcs_option(cfg.rtl)))
    if cfg.sim.files:
        lines.append("read_verilog -r %s" % tcl_list_block(cfg.sim.files))

    lines += section("Implementation: synthesized netlist")
    lines.append("read_verilog -i -netlist %s" % tcl_list_block(cfg.syn.files))
    if cfg.sim.files:
        lines.append("read_verilog -i %s" % tcl_list_block(cfg.sim.files))

    if cfg.blackboxes:
        lines += section("Black boxes")
        for module in cfg.blackboxes:
            lines += ["set_black_box %s" % tcl_word("r:/WORK/" + module),
                      "set_black_box %s" % tcl_word("i:/WORK/" + module)]

    lines += section("Top-level designs")
    lines += ["set_top r:/WORK/$TOP_DESIGN",
              "set_top i:/WORK/$TOP_DESIGN"]
    lines += hook_lines(cfg, "pre_match")

    lines += section("Match")
    lines += ["match",
              "report_unmatched_points > reports/${FLOW}.unmatched.rpt"]
    lines += hook_lines(cfg, "pre_verify")

    # The status file is written right after verify, so a problem in a
    # report or hook below cannot turn a finished run into "did not finish".
    lines += section("Verify")
    lines += [
        "set verify_ok [verify]",
        "if {$verify_ok} {",
        "  set result PASS",
        "} else {",
        "  set result FAIL",
        "}",
        "set fh [open ${FLOW}.status w]",
        "puts $fh $result",
        "close $fh",
        "if {!$verify_ok} {",
        "  report_failing_points > reports/${FLOW}.failing.rpt",
        "  report_aborted_points > reports/${FLOW}.aborted.rpt",
        "  analyze_points -failing > reports/${FLOW}.analyze.rpt",
        "}",
    ]
    lines += hook_lines(cfg, "post_verify")

    lines += section("Finish")
    lines += [
        "save_session -replace ${FLOW}",
        'puts "$FLOW result: $result"',
        "exit",
        "",
    ]
    return "\n".join(lines)


FLOW_GENERATORS = {"rtl2syn": gen_fm_rtl2syn}


def gen_run_script(cfg, flow):
    tool_cmd = cfg.tool_cmd.get(FM, "").strip() or "fm_shell"
    lines = [
        "#!/bin/tcsh -f",
        "# Run Formality %s for %s" % (flow, cfg.top),
        "# Exit status: 0 PASS, 1 FAIL, 2 did not finish (setup or tool problem)",
    ]
    lines += forced_header(cfg)
    lines += [
        "",
        "set flow = %s" % flow,
        'set here = "`dirname $0`"',
        'if ( ! -d "$here/$flow" ) then',
        '  echo "ERROR: directory not found: $here/$flow"',
        "  exit 2",
        "endif",
        'cd "$here/$flow"',
        "",
        "# Environment",
    ]
    lines += env_lines(cfg)
    lines += [
        "",
        "# Run the tool. Input from /dev/null so it exits if the script stops early.",
        "# The old result is removed first, so a tool that fails to start is not",
        "# reported with the result of an earlier run.",
        "rm -f ${flow}.status",
        "%s -f ${flow}.tcl < /dev/null |& tee logs/${flow}.log" % tool_cmd,
        "",
        "if ( ! -e ${flow}.status ) then",
        '  echo "$flow did not finish. See $flow/logs/${flow}.log"',
        "  exit 2",
        "endif",
        'set result = "`cat ${flow}.status`"',
        'echo "$flow result: $result (logs: $flow/logs, reports: $flow/reports)"',
        'if ( "$result" != "PASS" ) exit 1',
        "exit 0",
        "",
    ]
    return "\n".join(lines)


# Main

def write_file(path, text, executable=False):
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    if executable:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def block_names():
    """Blocks that have a config in common_files/."""
    if not os.path.isdir(CONFIG_DIR):
        return []
    return sorted(n[:-len(CONFIG_SUFFIX)] for n in os.listdir(CONFIG_DIR)
                  if n.endswith(CONFIG_SUFFIX) and n != PROJECT_CONFIG)


def find_config(name):
    """Config file for a block name (or a path to a config file)."""
    if os.path.isfile(name):
        return name
    path = os.path.join(CONFIG_DIR, name + CONFIG_SUFFIX)
    if os.path.isfile(path):
        return path
    blocks = block_names()
    raise ConfigError("no config for \"%s\": %s not found.\n"
                      "flowgen: blocks with a config: %s\n"
                      "flowgen: to start a new block: %s --new %s"
                      % (name, path, ", ".join(blocks) or "none yet", WRAPPER, name))


def new_block(block):
    """Create common_files/<block>.config.tcl (and the project config if missing)."""
    if not IDENT_RE.match(block):
        raise ConfigError("--new: \"%s\" is not a block name (letters, digits and _ only)" % block)
    block_path = os.path.join(CONFIG_DIR, block + CONFIG_SUFFIX)
    project_path = os.path.join(CONFIG_DIR, PROJECT_CONFIG)
    if os.path.lexists(block_path):
        raise ConfigError("--new: %s already exists; edit it, or generate with: %s %s"
                          % (block_path, WRAPPER, block))
    try:
        with open(NEW_BLOCK_TEMPLATE, encoding="ascii") as fh:
            text = fh.read().replace("@BLOCK@", block)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        new_project = not os.path.lexists(project_path)
        if new_project:
            shutil.copyfile(PROJECT_TEMPLATE, project_path)
        write_file(block_path, text)
    except (IOError, OSError) as exc:
        raise ConfigError("--new: %s" % exc)

    print("flowgen: created %s" % block_path)
    step = 1
    if new_project:
        print("flowgen: created %s (shared by all blocks)" % project_path)
        print("flowgen: %d. edit %s: PROJ_ROOT, LIB_FILES, tool setup (once per project)"
              % (step, project_path))
        step += 1
    print("flowgen: %d. check %s: TOP_DESIGN and the file paths" % (step, block_path))
    print("flowgen: %d. generate the run directory: %s %s" % (step + 1, WRAPPER, block))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", metavar="BLOCK", nargs="?",
                        help="block name (reads common_files/BLOCK.config.tcl) or a path "
                             "to a config file")
    parser.add_argument("--new", metavar="BLOCK",
                        help="create common_files/BLOCK.config.tcl for a new block")
    parser.add_argument("--force", action="store_true",
                        help="generate even if input files are missing or a .f file "
                             "list cannot be read (those errors become warnings)")
    args = parser.parse_args(argv)

    try:
        if args.new:
            if args.config:
                raise ConfigError("give either --new BLOCK or BLOCK, not both")
            return new_block(args.new)
        if not args.config:
            raise ConfigError("which block? Give a block name (blocks with a config: %s) "
                              "or start one with --new BLOCK"
                              % (", ".join(block_names()) or "none yet"))
        cfg = Config(find_config(args.config), force=args.force)
    except ConfigError as exc:
        sys.exit("flowgen: ERROR: %s" % exc)

    for msg in cfg.warnings:
        print("flowgen: WARNING: %s" % msg)
    if cfg.errors:
        for msg in cfg.errors:
            print("flowgen: ERROR: %s" % msg)
        hint = ""
        if not args.force and cfg.file_problems:
            hint = (" Use --force to generate anyway: the %d missing input file(s) "
                    "become warnings." % cfg.file_problems)
        sys.exit("flowgen: %d error(s) in %s; nothing generated.%s"
                 % (len(cfg.errors), cfg.path, hint))

    now = datetime.datetime.now()
    base_dir = os.path.abspath("%s_%s_formality" % (now.strftime("%Y_%m_%d_%H_%M_%S"), cfg.top))
    run_dir, count = base_dir, 1
    while os.path.lexists(run_dir):      # never overwrite an existing run
        count += 1
        run_dir = "%s_%d" % (base_dir, count)

    try:
        # Render everything before touching the disk, so a bad value
        # never leaves a half-written run directory.
        outputs = {}
        for flow in cfg.flows:
            outputs[flow] = (FLOW_GENERATORS[flow](cfg, flow), gen_run_script(cfg, flow))
            for text in outputs[flow]:
                bad = sorted(set(ch for ch in text if ord(ch) > 126))
                if bad:
                    raise ConfigError("the config has non-ASCII characters (%s); file names "
                                      "and values must be plain ASCII"
                                      % " ".join(ascii(ch) for ch in bad))
    except ConfigError as exc:
        sys.exit("flowgen: ERROR: %s" % exc)

    os.makedirs(run_dir)
    # Record of the inputs, under the config's own name, with the project
    # config it sources
    shutil.copy2(cfg.path, os.path.join(run_dir, os.path.basename(cfg.path)))
    project = os.path.join(cfg.dir, PROJECT_CONFIG)
    if os.path.isfile(project) and project != cfg.path:
        shutil.copy2(project, os.path.join(run_dir, PROJECT_CONFIG))

    for flow, (fm_tcl, run_csh) in outputs.items():
        os.makedirs(os.path.join(run_dir, flow, "logs"))      # filled in by the tool
        os.makedirs(os.path.join(run_dir, flow, "reports"))
        write_file(os.path.join(run_dir, flow, flow + ".tcl"), fm_tcl)
        write_file(os.path.join(run_dir, "run_%s.csh" % flow), run_csh, executable=True)

    print("flowgen: generated %s" % run_dir)
    if cfg.forced:
        print("flowgen: WARNING: generated with --force; %d input problem(s) ignored "
              "(listed in the script headers)" % len(cfg.forced))
    for flow in cfg.flows:
        print("flowgen: next, run %s:  %s" % (flow, os.path.join(run_dir, "run_%s.csh" % flow)))
        print("flowgen:   result (PASS or FAIL) is printed at the end and written to %s"
              % os.path.join(run_dir, flow, flow + ".status"))
        print("flowgen:   log: %s" % os.path.join(run_dir, flow, "logs", flow + ".log"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
