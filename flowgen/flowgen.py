#!/usr/bin/env python3
"""flowgen - generate EDA run directories from a Tcl block config.

Usage:
    flowgen.py block.config.tcl

Creates  ./<yyyy_mm_dd_hh_mm_ss>_<DESIGN>_formality/  in the current directory with
one run script per flow (run_<flow>.csh) and one sub-directory per flow
holding the generated Formality Tcl script. Nothing is launched; run the
scripts manually.

The config is plain Tcl, evaluated by a real Tcl interpreter (tkinter), so
variables, lists, arrays, $env(...) and [glob ...] all work. Relative paths
in the config are relative to the config file's own directory.

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
HOOK_POINTS = ("setup", "pre_match", "pre_verify", "post_verify")

# Every variable flowgen understands. Unknown FM_*/ENV_* names produce a
# warning (catches typos); any other name is treated as a user helper var.
KNOWN_VARS = (
    "DESIGN",
    "FM_FLOWS", "FM_SHELL", "FM_RTL_FORMAT", "FM_RTL_FILES", "FM_RTL_VCS_OPTS",
    "FM_SYN_NETLIST", "FM_SVF", "FM_LIBS", "FM_AUTO_SETUP", "FM_APP_VAR", "FM_HOOK",
    "ENV_SOURCE", "ENV_SETENV",
)

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(Exception):
    pass


# --------------------------------------------------------------------------
# Reading the Tcl config
# --------------------------------------------------------------------------

def load_tcl_config(path):
    """Source the config in a fresh Tcl interpreter.

    Returns {name: str} for scalars and {name: {key: str}} for arrays,
    covering only the global variables the config created.
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


class Config(object):
    """Typed, validated view of block.config.tcl. Collects all problems."""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.dir = os.path.dirname(self.path)
        self.errors = []
        self.warnings = []
        self._raw, self._tcl = load_tcl_config(self.path)

        for name in sorted(self._raw):
            if name.startswith(("FM_", "ENV_")) and name not in KNOWN_VARS:
                self.warnings.append("unknown variable '%s' ignored (typo?)" % name)

        self.design = self.scalar("DESIGN", required=True)
        self.flows = self.tcl_list("FM_FLOWS", default=["rtl2syn"])
        for flow in self.flows:
            if flow not in SUPPORTED_FLOWS:
                self.errors.append("FM_FLOWS: unknown flow '%s' (supported: %s)"
                                   % (flow, ", ".join(SUPPORTED_FLOWS)))
        self.fm_shell = self.scalar("FM_SHELL", default="fm_shell")

        self.rtl_format = self.scalar("FM_RTL_FORMAT", default="sverilog")
        if self.rtl_format not in RTL_READERS:
            self.errors.append("FM_RTL_FORMAT: '%s' is not one of %s"
                               % (self.rtl_format, ", ".join(sorted(RTL_READERS))))
        self.rtl_files = self.paths("FM_RTL_FILES", required=True)
        self.rtl_vcs_opts = self.scalar("FM_RTL_VCS_OPTS", default="")
        if self.rtl_vcs_opts and self.rtl_format == "vhdl":
            self.errors.append("FM_RTL_VCS_OPTS only applies to verilog/sverilog")

        self.syn_netlist = self.paths("FM_SYN_NETLIST", required=True)
        self.libs = self.paths("FM_LIBS", required=True)
        svf = self.paths("FM_SVF")
        self.svf = svf[0] if svf else ""
        if len(svf) > 1:
            self.errors.append("FM_SVF: give one SVF file, got %d" % len(svf))
        self.auto_setup = self.boolean("FM_AUTO_SETUP", default=True)

        self.app_vars = self.array("FM_APP_VAR")
        for key in self.app_vars:
            if not IDENT_RE.match(key):
                self.errors.append("FM_APP_VAR(%s): not a valid app var name" % key)

        self.hooks = {}
        for key, value in sorted(self.array("FM_HOOK").items()):
            if key not in HOOK_POINTS:
                self.errors.append("FM_HOOK(%s): unknown hook point (valid: %s)"
                                   % (key, ", ".join(HOOK_POINTS)))
            else:
                self.hooks[key] = self.resolve("FM_HOOK(%s)" % key, value)

        self.env_source = self.paths("ENV_SOURCE")
        self.env_setenv = self.array("ENV_SETENV")
        for key in self.env_setenv:
            if not IDENT_RE.match(key):
                self.errors.append("ENV_SETENV(%s): not a valid environment variable name" % key)

    # -- typed getters ------------------------------------------------------

    def _get(self, name, kind):
        value = self._raw.get(name)
        if value is None:
            return None
        is_array = isinstance(value, dict)
        if is_array != (kind == "array"):
            self.errors.append("%s must be %s" % (name, "an array" if kind == "array"
                                                  else "a plain variable, not an array"))
            return None
        return value

    def scalar(self, name, default=None, required=False):
        value = self._get(name, "scalar")
        if value is None or value == "":
            if required:
                self.errors.append("%s is required" % name)
            return default
        return value

    def tcl_list(self, name, default=None, required=False):
        value = self._get(name, "scalar")
        items = list(self._tcl.splitlist(value)) if value else []
        if not items:
            if required:
                self.errors.append("%s is required (a Tcl list)" % name)
            return list(default or [])
        return items

    def array(self, name):
        return self._get(name, "array") or {}

    def boolean(self, name, default):
        value = self._get(name, "scalar")
        if value is None or value == "":
            return default
        try:
            return bool(self._tcl.getboolean(value))
        except tkinter.TclError:
            self.errors.append("%s: '%s' is not a boolean (use 1/0)" % (name, value))
            return default

    def resolve(self, label, path):
        """Absolute path (relative to config dir); warn if missing."""
        full = os.path.normpath(os.path.join(self.dir, os.path.expanduser(path)))
        if not os.path.exists(full):
            self.warnings.append("%s: file not found: %s" % (label, full))
        return full

    def paths(self, name, required=False):
        return [self.resolve(name, p) for p in self.tcl_list(name, required=required)]


# --------------------------------------------------------------------------
# Quoting helpers
# --------------------------------------------------------------------------

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
    return "{\n%s\n}" % "\n".join(indent + tcl_word(i) for i in items)


def csh_word(label, text):
    """Single-quote a value for csh; reject what csh cannot quote safely."""
    if re.search(r"['!\n]", text):
        raise ConfigError("%s: value may not contain ' or ! or newlines for csh: %r"
                          % (label, text))
    return "'%s'" % text


# --------------------------------------------------------------------------
# Formality script generation
# --------------------------------------------------------------------------

def section(title):
    return ["", "# " + ("-- %s " % title).ljust(74, "-")]


def hook_lines(cfg, point):
    if point in cfg.hooks:
        return ["# Hook '%s' (FM_HOOK(%s))" % (point, point),
                "source %s" % tcl_word(cfg.hooks[point])]
    return ["# Hook point '%s': set FM_HOOK(%s) in the config to source a file here."
            % (point, point)]


def gen_fm_rtl2syn(cfg, flow, stamp):
    reader = RTL_READERS[cfg.rtl_format]
    lines = [
        "# " + "=" * 74,
        "# Formality equivalence check: %s (RTL reference vs synthesized netlist)" % flow,
        "#   Block     : %s" % cfg.design,
        "#   Generated : %s by flowgen.py from %s" % (stamp, cfg.path),
        "#   Run       : ../run_%s.csh   (do not edit; regenerate instead)" % flow,
        "# " + "=" * 74,
        "",
        "set FLOW   %s" % tcl_word(flow),
        "set DESIGN %s" % tcl_word(cfg.design),
        "file mkdir reports",
        "file delete -force ${FLOW}.status",
    ]

    lines += section("Setup")
    lines.append("set_app_var synopsys_auto_setup %s" % ("true" if cfg.auto_setup else "false"))
    for name in sorted(cfg.app_vars):
        lines.append("set_app_var %s %s" % (name, tcl_word(cfg.app_vars[name])))
    lines += hook_lines(cfg, "setup")

    lines += section("Synthesis guidance (SVF)")
    if cfg.svf:
        lines.append("set_svf %s" % tcl_word(cfg.svf))
    else:
        lines.append("# No FM_SVF given: running without synthesis guidance.")

    lines += section("Technology libraries (shared by reference and implementation)")
    lines.append("read_db %s" % tcl_list_block(cfg.libs))

    lines += section("Reference: RTL")
    rtl_cmd = "%s -r %s" % (reader, tcl_list_block(cfg.rtl_files))
    if cfg.rtl_vcs_opts:
        rtl_cmd += " -vcs %s" % tcl_word(cfg.rtl_vcs_opts)
    lines += [rtl_cmd, "set_top r:/WORK/$DESIGN"]

    lines += section("Implementation: synthesized netlist")
    lines += ["read_verilog -i -netlist %s" % tcl_list_block(cfg.syn_netlist),
              "set_top i:/WORK/$DESIGN"]

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
    lines = [
        "#!/bin/tcsh -f",
        "# Generated %s by flowgen.py from %s" % (stamp, cfg.path),
        "# Runs Formality flow '%s' for block '%s'. Usage: ./run_%s.csh" % (flow, cfg.design, flow),
        "",
        "set flow = %s" % flow,
        'set here = "`dirname $0`"',
        'cd "$here/$flow"',
        "",
        "# Tool and license environment (ENV_SOURCE / ENV_SETENV)",
    ]
    for path in cfg.env_source:
        lines.append("source %s" % csh_word("ENV_SOURCE", path))
    for name in sorted(cfg.env_setenv):
        lines.append("setenv %s %s" % (name, csh_word("ENV_SETENV(%s)" % name,
                                                       cfg.env_setenv[name])))
    if not (cfg.env_source or cfg.env_setenv):
        lines.append("# (none configured: fm_shell must already be on PATH)")
    lines += [
        "",
        "# stdin from /dev/null: if the script stops on an error, fm_shell exits",
        "# instead of waiting at its prompt.",
        "%s -f ${flow}.tcl < /dev/null |& tee ${flow}.log" % cfg.fm_shell,
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


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def write_file(path, text, executable=False):
    with open(path, "w") as fh:
        fh.write(text)
    if executable:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a Formality run directory from a Tcl block config.")
    parser.add_argument("config", help="block config file, e.g. block.config.tcl")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.config):
        sys.exit("flowgen: ERROR: config file not found: %s" % args.config)

    try:
        cfg = Config(args.config)
    except ConfigError as exc:
        sys.exit("flowgen: ERROR: %s" % exc)

    for msg in cfg.warnings:
        print("flowgen: WARNING: %s" % msg)
    if cfg.errors:
        for msg in cfg.errors:
            print("flowgen: ERROR: %s" % msg)
        sys.exit("flowgen: %d error(s) in %s; nothing generated." % (len(cfg.errors), cfg.path))

    now = datetime.datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    block = re.sub(r"[^A-Za-z0-9_.-]", "_", cfg.design)   # safe as a directory name
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
    shutil.copy2(cfg.path, os.path.join(run_dir, "block.config.tcl"))  # record of inputs

    for flow, (fm_tcl, run_csh) in outputs.items():
        os.makedirs(os.path.join(run_dir, flow))
        write_file(os.path.join(run_dir, flow, flow + ".tcl"), fm_tcl)
        write_file(os.path.join(run_dir, "run_%s.csh" % flow), run_csh, executable=True)

    print("flowgen: generated %s" % run_dir)
    for flow in cfg.flows:
        print("flowgen:   %-10s run with: %s" % (flow, os.path.join(run_dir, "run_%s.csh" % flow)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
