# Block configuration template for flowgen.py
#
# This file lists every setting flowgen understands. Copy it to your golden
# configs directory and fill it in, for example:
#     common_files/block.config.tcl
#
# How to write values
#   Single value : set NAME "value"
#   List         : set NAME {
#                      "first item"
#                      "second item"
#                  }
#   Empty        : set NAME ""   or   set NAME {}   means "not used"
#
# You can use your own helper variables (like BLOCK_ROOT below) and
# environment variables ($env(HOME)) inside values and list items.
# Relative paths are relative to the directory this file really lives in
# (common_files/), even when it is used through a flowgen/configs/ link.
#
# Generate the run directory with:
#     flowgen.py configs/block.config.tcl


# Helper variable, not read by flowgen. Use it to shorten the paths below.
# Example: set BLOCK_ROOT "/proj/chip/block"
set BLOCK_ROOT "/proj/chip/block"


# DESIGN

# Name of the top-level design (the top module). Required.
# Example: set TOP_DESIGN "block"
set TOP_DESIGN "block"


# FLOWS TO GENERATE

# Which flows to generate. Default is rtl2syn (RTL against synthesized netlist).
# Example: set FLOWS {
#              "rtl2syn"
#          }
set FLOWS {
    "rtl2syn"
}


# RTL (reference design)

# Language of the RTL: "sverilog" (default), "verilog" or "vhdl".
# Example: set RTL_FORMAT "sverilog"
set RTL_FORMAT "sverilog"

# RTL source files. Required. Each item is either a source file or a
# file list ending in .f (one file path per line, // or # for comments;
# relative paths inside a .f file are relative to the .f file).
# Example (files):     set RTL_FILES {
#                          "$BLOCK_ROOT/rtl/block_pkg.sv"
#                          "$BLOCK_ROOT/rtl/block.sv"
#                      }
# Example (file list): set RTL_FILES {
#                          "$BLOCK_ROOT/rtl/source.f"
#                      }
set RTL_FILES {
    "$BLOCK_ROOT/rtl/source.f"
}

# Include directories for `include files. Optional. Not for vhdl.
# Example: set RTL_INCDIRS {
#              "$BLOCK_ROOT/rtl/include"
#          }
set RTL_INCDIRS {}

# Verilog macros to define, as NAME or NAME=VALUE. Optional. Not for vhdl.
# Example: set RTL_DEFINES {
#              "SYNTHESIS"
#              "DATA_WIDTH=32"
#          }
set RTL_DEFINES {}


# NETLISTS

# Synthesized netlist files (or .f file lists). Required for rtl2syn.
# Example: set SYN_FILES {
#              "$BLOCK_ROOT/syn/outputs/block.syn.v"
#          }
set SYN_FILES {
    "$BLOCK_ROOT/syn/outputs/block.syn.v"
}

# Place-and-route (APR) netlist files (or .f file lists). Optional.
# Not used by rtl2syn; kept for netlist-to-APR checks and other flows.
# Example: set APR_FILES {
#              "$BLOCK_ROOT/apr/outputs/block.apr.v"
#          }
set APR_FILES {}


# SYNTHESIS GUIDANCE AND CONSTRAINTS

# SVF guidance file written by synthesis. Optional, but recommended for
# Formality: it makes matching faster and more reliable.
# Example: set SVF_FILE "$BLOCK_ROOT/syn/outputs/block.svf"
set SVF_FILE "$BLOCK_ROOT/syn/outputs/block.svf"

# Timing constraint (SDC) files. Optional. Not used by Formality; kept for
# synthesis, timing and other flows.
# Example: set SDC_FILES {
#              "$BLOCK_ROOT/constraints/block.sdc"
#          }
set SDC_FILES {}

# Power intent (UPF) files. Optional. Not used by flowgen yet.
# Example: set UPF_FILES {
#              "$BLOCK_ROOT/upf/block.upf"
#          }
set UPF_FILES {}


# LIBRARIES AND SIMULATION MODELS

# Format of the files in LIB_FILES: "db" (default) or "lib".
# "db"  reads compiled .db files (read_db).
# "lib" reads Liberty .lib or .lib.gz files (read_lib).
# Example: set LIB_FORMAT "db"
set LIB_FORMAT "db"

# Technology library files: standard cells, memories, hard IPs. Required.
# Give full file names; only these files are read.
# Example: set LIB_FILES {
#              "/pdk/stdcell/db/stdcell_tt_0p80v_25c.db"
#              "/ip/sram/db/sram_1rw_tt_0p80v_25c.db"
#          }
set LIB_FILES {
    "/pdk/stdcell/db/stdcell_tt_0p80v_25c.db"
}

# Verilog simulation models (.v) for hard IPs, memories or cells that have
# no library model. Optional. Read into both reference and implementation.
# Items can also be .f file lists.
# Example: set SIM_FILES {
#              "/ip/pll/verilog/pll_top.v"
#          }
set SIM_FILES {}

# Modules to treat as black boxes (only their ports are compared).
# Optional. Nothing is black boxed unless it is listed here.
# Example: set BLACKBOX_MODULES {
#              "pll_top"
#              "sram_1rw"
#          }
set BLACKBOX_MODULES {}


# TOOL SETTINGS
#
# Settings for one tool are keyed by the tool name. Today flowgen
# generates Formality only, so the tool name is "formality". New tools will
# use their own name, for example "dc" or "primetime".

# Command that starts the tool. Optional. Default for Formality: fm_shell
# Example: set TOOL_CMD(formality) "/tools/synopsys/fm/V-2023.12/bin/fm_shell"
# set TOOL_CMD(formality) "fm_shell"

# Tool variables, written into the tool script as set_app_var. Add any
# Formality variable you need here, one line each. Optional.
# synopsys_auto_setup is "true" unless you set it here.
# Example: set TOOL_SETTINGS(formality,hdlin_unresolved_modules) "black_box"
# Example: set TOOL_SETTINGS(formality,verification_timeout_limit) "4:0:0"
# set TOOL_SETTINGS(formality,synopsys_auto_setup) "true"

# Your own Tcl files, sourced at fixed points in the Formality script.
# Optional. Hook points:
#   setup        after the tool variables, before anything is read
#   pre_match    designs read and top set (set_constant, set_user_match, ...)
#   pre_verify   after matching
#   post_verify  after verification (extra reports)
# Example: set TOOL_HOOKS(formality,pre_match) "$BLOCK_ROOT/fm/constants.tcl"


# RUN ENVIRONMENT
#
# Written into the run_<flow>.csh scripts before the tool starts.

# Shell setup files to source, in order. Optional.
# Example: set ENV_SOURCE {
#              "/tools/synopsys/setup.cshrc"
#          }
set ENV_SOURCE {
    "/tools/synopsys/setup.cshrc"
}

# Environment variables to set, one line each. Optional.
# Example: set ENV_SETENV(SNPSLMD_LICENSE_FILE) "27020@lic-server1"
set ENV_SETENV(SNPSLMD_LICENSE_FILE) "27020@lic-server1"
