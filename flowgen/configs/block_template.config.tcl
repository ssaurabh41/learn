# Block config template for flowgen.py
# Copy it to common_files/block.config.tcl and edit the values.
#
# Single value:
# set NAME "value"
#
# List, one item per line:
# set NAME {
#   "item1"
#   "item2"
# }
#
# "" or {} means not used. $VARIABLES work inside values and lists.
# Relative paths are relative to this file's directory (common_files/).


# Optional helper variables for your own paths. flowgen does not need or
# read them; use them in values, lists and .f files as $NAME.
# Example:
# set PROJ_ROOT "/proj/chip"
# set USER_RTL_DIR "/proj/chip/block/rtl"

# Top-level design (module) name. Required.
set TOP_DESIGN "block"

# Flows to generate. Default: rtl2syn (RTL vs synthesized netlist).
set FLOWS {
  "rtl2syn"
}


# RTL

# RTL language: "sverilog" (default), "verilog" or "vhdl".
set RTL_FORMAT "sverilog"

# Directories searched, in order, for RTL files given without a full path,
# in RTL_FILES and inside .f file lists. RTL_INCDIRS are searched next.
set RTL_SEARCH_DIRS {
  "/proj/chip/block/rtl"
}

# RTL files or .f file lists. Required.
# A .f file has one file per line; // and # start comments; $NAME uses
# config variables, then environment variables.
# Example with files instead of a file list:
# set RTL_FILES {
#   "block_pkg.sv"
#   "block.sv"
# }
set RTL_FILES {
  "source.f"
}

# Include directories for `include files. Also searched for RTL file names
# after RTL_SEARCH_DIRS. Not for vhdl.
# Example:
# set RTL_INCDIRS {
#   "/proj/chip/block/rtl/include"
# }
set RTL_INCDIRS {}

# Verilog macros, as NAME or NAME=VALUE. Not for vhdl.
# Example:
# set RTL_DEFINES {
#   "SYNTHESIS"
#   "DATA_WIDTH=32"
# }
set RTL_DEFINES {}


# NETLISTS

# Directories searched, in order, for netlist files given without a full
# path, in SYN_FILES and inside .f file lists.
set SYN_SEARCH_DIRS {
  "/proj/chip/block/syn/outputs"
}

# Synthesized netlist files or .f file lists. Required for rtl2syn.
set SYN_FILES {
  "block.syn.v"
}

# Place-and-route netlist files or .f file lists. Not used by rtl2syn.
# Example:
# set APR_FILES {
#   "/proj/chip/block/apr/outputs/block.apr.v"
# }
set APR_FILES {}


# GUIDANCE AND CONSTRAINTS

# SVF guidance file from synthesis. Recommended for Formality.
set SVF_FILE "/proj/chip/block/syn/outputs/block.svf"

# Timing constraint files. Not used by Formality.
# Example:
# set SDC_FILES {
#   "/proj/chip/block/constraints/block.sdc"
# }
set SDC_FILES {}

# Power intent files. Not used by flowgen yet.
# Example:
# set UPF_FILES {
#   "/proj/chip/block/upf/block.upf"
# }
set UPF_FILES {}


# LIBRARIES

# Library file format: "db" (default, read_db) or "lib" (.lib or .lib.gz, read_lib).
set LIB_FORMAT "db"

# Library files: standard cells, memories, hard IPs. Required.
# Only these exact files are read.
set LIB_FILES {
  "/pdk/stdcell/db/stdcell_tt_0p80v_25c.db"
}

# Verilog models for hard IPs or cells without a library model.
# Read into both reference and implementation. Items can be .f lists.
# Example:
# set SIM_FILES {
#   "/ip/pll/verilog/pll_top.v"
# }
set SIM_FILES {}

# Modules to black box. Nothing is black boxed unless listed here.
# Example:
# set BLACKBOX_MODULES {
#   "pll_top"
# }
set BLACKBOX_MODULES {}


# TOOL SETTINGS
# Keyed by tool name. Formality is "formality".

# Command that starts the tool. Default: fm_shell
# Example:
# set TOOL_CMD(formality) "/tools/synopsys/fm/bin/fm_shell"

# Tool variables, written as set_app_var. Add one line per variable.
# synopsys_auto_setup is "true" unless set here.
# Example:
# set TOOL_SETTINGS(formality,hdlin_unresolved_modules) "black_box"

# Your own Tcl files, sourced at: setup, pre_match, pre_verify, post_verify.
# Example:
# set TOOL_HOOKS(formality,pre_match) "/proj/chip/block/fm/constants.tcl"


# RUN ENVIRONMENT
# Written into the run_<flow>.csh scripts.

# Shell setup files to source, in order.
set ENV_SOURCE {
  "/tools/synopsys/setup.cshrc"
}

# Environment variables to set, one line each.
set ENV_SETENV(SNPSLMD_LICENSE_FILE) "27020@lic-server1"
