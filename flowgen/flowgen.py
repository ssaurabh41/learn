#!/usr/bin/env python3
"""flowgen - generate EDA run directories from a Tcl block config.

Usage:
    flowgen.py [--force] CONFIG
    flowgen.py -h

Arguments:
    CONFIG    The block config file to read, typically block.config.tcl
              (any name works). Usually given through the configs link
              directory, e.g. configs/block.config.tcl.
    --force   Generate the run directory even if input files are missing
              or a .f file list cannot be read. Those errors become
              warnings. Use it to try out the flow before all design files
              exist. Other config errors (missing settings, bad values,
              Tcl errors) still stop generation.
    -h        Show this help and exit.

Examples:
    flowgen.py configs/block.config.tcl
    flowgen.py --force configs/block.config.tcl

Output:
    ./<yyyy_mm_dd_hh_mm_ss>_<TOP_DESIGN>_formality/ in the current directory,
    with one run script per flow (run_<flow>.csh) and one sub-directory per
    flow holding the generated Formality Tcl script. Nothing is launched;
    run the scripts manually. An existing directory of the same name is
    overwritten.

Config:
    Plain Tcl, evaluated by a real Tcl interpreter (tkinter). Values are
    written in double quotes, lists in braces with one double-quoted item
    per line; $VARIABLES inside list items are expanded by flowgen.
    Relative paths are relative to the config file's real directory.
    See configs/block_template.config.tcl for every supported setting.

Requires Python 3.6+ built with tkinter. Standard library only.
"""

import argparse
import datetime
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

# Every variable flowgen understands. Unknown names with one of the
# prefixes below produce a warning (catches typos); any other name is
# treated as a user helper variable.
KNOWN_VARS = (
    "TOP_DESIGN", "FLOWS",
    "RTL_FORMAT", "RTL_FILES", "RTL_INCDIRS", "RTL_DEFINES",
    "SYN_FILES", "APR_FILES", "SVF_FILE", "SDC_FILES", "UPF_FILES",
    "LIB_FORMAT", "LIB_FILES", "SIM_FILES", "BLACKBOX_MODULES",
    "TOOL_CMD", "TOOL_SETTINGS", "TOOL_HOOKS",
    "ENV_SOURCE", "ENV_SETENV",
)
CHECKED_PREFIXES = ("DESIGN", "TOP_", "FLOW", "RTL_", "SYN_", "APR_", "SVF_", "SDC_", "UPF_",
                    "LIB_", "SIM_", "BLACKBOX", "TOOL_", "ENV_")

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(Exception):
    pass


# Reading the Tcl config

def load_tcl_config(path):
    """Source the config in a fresh Tcl interpreter.

    Returns ({name: str or {key: str}}, interpreter) for the global
    variables the config created (arrays become dicts).
    """
    tcl = tkinter.Tcl()
    before = set(tcl.splitlist(tcl.eval("info globals")))

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
        else:
            values[name] = tcl.eval("set ::%s" % name)
    return values, tcl


class FileSet(object):
    """Files collected from a file-list variable (with .f files expanded)."""

    def __init__(self):
        self.files = []
        self.incdirs = []
        self.defines = []


class Config(object):
    """Typed, validated view of the block config. Collects all problems."""

    def __init__(self, path, force=False):
        self.force = force
        self.forced = []      # file errors downgraded to warnings by --force
        self.path = os.path.realpath(path)   # follow flowgen/configs links to common_files
        self.dir = os.path.dirname(self.path)
        self.errors = []
        self.warnings = []
        self._raw, self._tcl = load_tcl_config(self.path)

        for name in sorted(self._raw):
            if name.startswith(CHECKED_PREFIXES) and name not in KNOWN_VARS:
                self.warnings.append("unknown variable '%s' ignored (typo?)" % name)

        self.top = self.scalar("TOP_DESIGN", required=True)
        self.flows = self.tcl_list("FLOWS", default=["rtl2syn"])
        for flow in self.flows:
            if flow not in SUPPORTED_FLOWS:
                self.errors.append("FLOWS: unknown flow '%s' (supported: %s)"
                                   % (flow, ", ".join(SUPPORTED_FLOWS)))

        # Design data
        self.rtl_format = self.choice("RTL_FORMAT", RTL_READERS, default="sverilog")
        self.rtl = self.fileset("RTL_FILES", required=True)
        self.rtl.incdirs += self.paths("RTL_INCDIRS")
        self.rtl.defines += self.tcl_list("RTL_DEFINES")
        if self.rtl_format == "vhdl" and (self.rtl.incdirs or self.rtl.defines):
            self.errors.append("RTL_INCDIRS / RTL_DEFINES (or +incdir+/+define+ in a .f "
                               "file) only apply to verilog/sverilog")
        needs_syn = "rtl2syn" in self.flows
        self.syn = self.fileset("SYN_FILES", required=needs_syn, netlist=True)
        self.apr = self.fileset("APR_FILES", netlist=True)        # for future flows
        self.svf = self.single_path("SVF_FILE")
        self.sdc = self.paths("SDC_FILES")                        # not used by Formality
        self.upf = self.paths("UPF_FILES")                        # not used yet

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

        # Run environment
        self.env_source = self.paths("ENV_SOURCE")
        self.env_setenv = self.array("ENV_SETENV")
        for key in self.env_setenv:
            if not IDENT_RE.match(key):
                self.errors.append("ENV_SETENV(%s): not a valid environment variable name" % key)

    def file_error(self, msg):
        """An error caused by a missing or unreadable input file."""
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
        for item in (self._tcl.splitlist(value) if value else ()):
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
            result.setdefault(tool.strip(), {})[sub.strip()] = value
        return result

    def resolve(self, label, path, base=None):
        """Absolute path (relative to base, default the config dir); warn if missing."""
        full = os.path.normpath(os.path.join(base or self.dir, os.path.expanduser(path)))
        if not os.path.exists(full):
            self.warnings.append("%s: file not found: %s" % (label, full))
        return full

    def paths(self, name, required=False):
        return [self.resolve(name, p) for p in self.tcl_list(name, required=required)]

    def single_path(self, name):
        items = self.paths(name)
        if len(items) > 1:
            self.errors.append("%s: give one file, got %d" % (name, len(items)))
        return items[0] if items else ""

    def fileset(self, name, required=False, netlist=False):
        """Files from a list variable; entries ending in .f are file lists."""
        result = FileSet()
        items = self.paths(name, required=required)
        for item in items:
            if item.endswith(".f"):
                self.read_filelist(name, item, result, [])
            else:
                result.files.append(item)
        if netlist and (result.incdirs or result.defines):
            self.warnings.append("%s: +incdir+/+define+ in a .f file ignored for netlists" % name)
            result.incdirs, result.defines = [], []
        if required and items and not result.files:
            self.file_error("%s: the .f file lists contain no files" % name)
        return result

    def read_filelist(self, name, path, result, stack):
        """Expand a .f file: one path per line, // or # comments, $VAR expanded.

        Also understands -f/-F <file> (nested lists), -v <file>,
        +incdir+<dir>[+<dir>...] and +define+<MACRO>[=<value>][+...].
        Relative paths are relative to the .f file's directory.
        """
        label = "%s (%s)" % (name, os.path.basename(path))
        if path in stack:
            self.errors.append("%s: file list includes itself" % label)
            return
        try:
            with open(path) as fh:
                lines = fh.readlines()
        except (IOError, OSError) as exc:
            self.file_error("%s: cannot read file list: %s" % (label, exc))
            return
        base = os.path.dirname(path)
        for lineno, line in enumerate(lines, 1):
            line = line.split("//", 1)[0].strip()
            if not line or line.startswith("#"):
                continue
            tokens = [os.path.expandvars(t) for t in line.split()]
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                where = "%s line %d" % (label, lineno)
                if tok in ("-f", "-F", "-v", "-y"):
                    if i + 1 >= len(tokens):
                        self.errors.append("%s: %s needs a file name" % (where, tok))
                        break
                    if tok == "-y":
                        self.warnings.append("%s: -y library directories are not supported, "
                                             "ignored: %s" % (where, tokens[i + 1]))
                    else:
                        arg = self.resolve(where, tokens[i + 1], base)
                        if tok == "-v":
                            result.files.append(arg)
                        else:
                            self.read_filelist(name, arg, result, stack + [path])
                    i += 2
                    continue
                if tok.startswith("+incdir+"):
                    result.incdirs += [self.resolve(where, d, base)
                                       for d in tok[len("+incdir+"):].split("+") if d]
                elif tok.startswith("+define+"):
                    result.defines += [d for d in tok[len("+define+"):].split("+") if d]
                elif tok.startswith(("-", "+")):
                    self.warnings.append("%s: option %s not supported, ignored" % (where, tok))
                else:
                    result.files.append(self.resolve(where, tok, base))
                i += 1


# Quoting helpers

_TCL_BARE = re.compile(r"^[A-Za-z0-9_./:+=@%,~-]+$")
_TCL_SPECIAL = re.compile(r'([\\{}\[\]$";# \t])')


def tcl_word(text):
    """Quote text as one Tcl word (also valid as a Tcl list element)."""
    if _TCL_BARE.match(text):
        return text
    if text and not re.search(r"[{}\\]", text):
        return "{%s}" % text
    return _TCL_SPECIAL.sub(r"\\\1", text).replace("\n", "\\n") or "{}"


def tcl_list_block(items, indent="    "):
    """A braced, one-item-per-line Tcl list."""
    if not items:
        return "{}"
    return "{\n%s\n}" % "\n".join(indent + tcl_word(i) for i in items)


def csh_word(label, text):
    """Single-quote a value for csh; reject what csh cannot quote safely."""
    if re.search(r"['!\n]", text):
        raise ConfigError("%s: value may not contain ' or ! or newlines for csh: %r"
                          % (label, text))
    return "'%s'" % text


# Formality script generation

def section(title):
    return ["", "# " + title]


def hook_lines(cfg, point):
    hooks = cfg.tool_hooks.get(FM, {})
    if point in hooks:
        return ["# Hook '%s' from TOOL_HOOKS(%s,%s)" % (point, FM, point),
                "source %s" % tcl_word(hooks[point])]
    return ["# Hook point '%s': set TOOL_HOOKS(%s,%s) in the config to source a file here."
            % (point, FM, point)]


def vcs_option(fileset):
    """-vcs option carrying include dirs and defines, or ''."""
    opts = ["+incdir+" + d for d in fileset.incdirs] + ["+define+" + d for d in fileset.defines]
    return " -vcs %s" % tcl_word(" ".join(opts)) if opts else ""


def gen_fm_rtl2syn(cfg, flow, stamp):
    settings = dict(cfg.tool_settings.get(FM, {}))
    settings.setdefault("synopsys_auto_setup", "true")
    lines = [
        "# Formality equivalence check: %s (RTL reference vs synthesized netlist)" % flow,
        "# Block     : %s" % cfg.top,
        "# Generated : %s by flowgen.py from %s" % (stamp, cfg.path),
        "# Run       : ../run_%s.csh   (do not edit; regenerate instead)" % flow,
    ]
    if cfg.forced:
        lines.append("# WARNING   : generated with --force; these input problems were ignored:")
        lines += ["#   " + msg for msg in cfg.forced]
    lines += [
        "",
        "set FLOW       %s" % tcl_word(flow),
        "set TOP_DESIGN %s" % tcl_word(cfg.top),
        "file mkdir reports",
        "file delete -force ${FLOW}.status",
    ]

    lines += section("Setup: app vars from TOOL_SETTINGS(%s,*)" % FM)
    for name in sorted(settings):
        lines.append("set_app_var %s %s" % (name, tcl_word(settings[name])))
    lines += hook_lines(cfg, "setup")

    lines += section("Synthesis guidance (SVF)")
    if cfg.svf:
        lines.append("set_svf %s" % tcl_word(cfg.svf))
    else:
        lines.append("# No SVF_FILE given: running without synthesis guidance.")

    lines += section("Technology libraries, shared by reference and implementation "
                     "(LIB_FORMAT %s)" % cfg.lib_format)
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

    lines += section("Black boxes (BLACKBOX_MODULES)")
    if cfg.blackboxes:
        for module in cfg.blackboxes:
            lines += ["set_black_box r:/WORK/%s" % tcl_word(module),
                      "set_black_box i:/WORK/%s" % tcl_word(module)]
    else:
        lines.append("# None.")

    lines += section("Top-level designs")
    lines += ["set_top r:/WORK/$TOP_DESIGN",
              "set_top i:/WORK/$TOP_DESIGN"]

    lines += [""] + hook_lines(cfg, "pre_match")

    lines += section("Match")
    lines += ["match",
              "report_unmatched_points > reports/${FLOW}.unmatched.rpt"]

    lines += [""] + hook_lines(cfg, "pre_verify")

    lines += section("Verify")
    lines += [
        "set verify_ok [verify]",
        "if {$verify_ok} {",
        "    set result PASS",
        "} else {",
        "    set result FAIL",
        "    report_failing_points > reports/${FLOW}.failing.rpt",
        "    report_aborted_points > reports/${FLOW}.aborted.rpt",
        "    analyze_points -failing > reports/${FLOW}.analyze.rpt",
        "}",
    ]

    lines += [""] + hook_lines(cfg, "post_verify")

    lines += section("Save session and finish")
    lines += [
        "save_session -replace ${FLOW}",
        "set fh [open ${FLOW}.status w]",
        "puts $fh $result",
        "close $fh",
        'puts "flowgen: $FLOW verification result: $result"',
        "exit",
        "",
    ]
    return "\n".join(lines)


FLOW_GENERATORS = {"rtl2syn": gen_fm_rtl2syn}


def gen_run_script(cfg, flow, stamp):
    tool_cmd = cfg.tool_cmd.get(FM, "").strip() or "fm_shell"
    lines = [
        "#!/bin/tcsh -f",
        "# Generated %s by flowgen.py from %s" % (stamp, cfg.path),
        "# Runs Formality flow '%s' for block '%s'. Usage: ./run_%s.csh" % (flow, cfg.top, flow),
        "",
        "set flow = %s" % flow,
        'set here = "`dirname $0`"',
        'cd "$here/$flow"',
        "",
        "# Tool and license environment (ENV_SOURCE, ENV_SETENV)",
    ]
    for path in cfg.env_source:
        lines.append("source %s" % csh_word("ENV_SOURCE", path))
    for name in sorted(cfg.env_setenv):
        lines.append("setenv %s %s" % (name, csh_word("ENV_SETENV(%s)" % name,
                                                       cfg.env_setenv[name])))
    if not (cfg.env_source or cfg.env_setenv):
        lines.append("# (none configured: %s must already be on PATH)" % tool_cmd)
    lines += [
        "",
        "# stdin from /dev/null: if the script stops on an error, the tool exits",
        "# instead of waiting at its prompt.",
        "%s -f ${flow}.tcl < /dev/null |& tee ${flow}.log" % tool_cmd,
        "",
        "if ( ! -e ${flow}.status ) then",
        '    echo "flowgen: $flow did not finish. See $flow/${flow}.log"',
        "    exit 2",
        "endif",
        'set result = "`cat ${flow}.status`"',
        'echo "flowgen: $flow result: $result  (log: $flow/${flow}.log, reports: $flow/reports/)"',
        'if ( "$result" != "PASS" ) exit 1',
        "exit 0",
        "",
    ]
    return "\n".join(lines)


# Main

def write_file(path, text, executable=False):
    with open(path, "w") as fh:
        fh.write(text)
    if executable:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", metavar="CONFIG",
                        help="block config file, typically block.config.tcl")
    parser.add_argument("--force", action="store_true",
                        help="generate even if input files are missing or a .f file "
                             "list cannot be read (those errors become warnings)")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.config):
        sys.exit("flowgen: ERROR: config file not found: %s" % args.config)

    try:
        cfg = Config(args.config, force=args.force)
    except ConfigError as exc:
        sys.exit("flowgen: ERROR: %s" % exc)

    for msg in cfg.warnings:
        print("flowgen: WARNING: %s" % msg)
    if cfg.errors:
        for msg in cfg.errors:
            print("flowgen: ERROR: %s" % msg)
        hint = ""
        if not args.force and any("file list" in m for m in cfg.errors):
            hint = " Use --force to generate anyway with missing files."
        sys.exit("flowgen: %d error(s) in %s; nothing generated.%s"
                 % (len(cfg.errors), cfg.path, hint))

    now = datetime.datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    block = re.sub(r"[^A-Za-z0-9_.-]", "_", cfg.top)   # safe as a directory name
    run_dir = os.path.abspath("%s_%s_formality" % (now.strftime("%Y_%m_%d_%H_%M_%S"), block))

    try:
        # Render everything before touching the disk, so a bad value
        # never leaves a half-written run directory.
        outputs = {}
        for flow in cfg.flows:
            outputs[flow] = (FLOW_GENERATORS[flow](cfg, flow, stamp),
                             gen_run_script(cfg, flow, stamp))
    except ConfigError as exc:
        sys.exit("flowgen: ERROR: %s" % exc)

    if os.path.isdir(run_dir):
        print("flowgen: WARNING: %s exists; overwriting" % run_dir)
        shutil.rmtree(run_dir)
    os.makedirs(run_dir)
    # Record of the inputs, under the config's own name
    shutil.copy2(cfg.path, os.path.join(run_dir, os.path.basename(cfg.path)))

    for flow, (fm_tcl, run_csh) in outputs.items():
        os.makedirs(os.path.join(run_dir, flow))
        write_file(os.path.join(run_dir, flow, flow + ".tcl"), fm_tcl)
        write_file(os.path.join(run_dir, "run_%s.csh" % flow), run_csh, executable=True)

    print("flowgen: generated %s" % run_dir)
    if cfg.forced:
        print("flowgen: WARNING: generated with --force; %d input problem(s) ignored "
              "(listed in the script headers)" % len(cfg.forced))
    for flow in cfg.flows:
        print("flowgen:   %-10s run with: %s" % (flow, os.path.join(run_dir, "run_%s.csh" % flow)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
