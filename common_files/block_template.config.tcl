# From block_template.config.csv. Edit the CSV and rerun csv2config.py.

# YOUR OWN VARIABLES

# Example helper variable. Leave empty if not used.
set USER_RTL_DIR ""

# DESIGN

# Top-level design (module) name.
set TOP_DESIGN "block"

# Flows to generate, one row each. Default: rtl2syn (RTL vs synthesized
# netlist).
set FLOWS {
  "rtl2syn"
}

# RTL

# RTL language: sverilog (default), verilog or vhdl.
set RTL_FORMAT "sverilog"

# Directories searched, in order, for RTL file names given without a full
# path (in RTL_FILES and inside .f files). One row per directory.
set RTL_SEARCH_DIRS {
  "../examples/rtl"
}

# RTL files or .f file lists, one row each. A .f file has one file per line;
# // and # start comments; $NAME uses config variables, then environment
# variables.
set RTL_FILES {
  "source.f"
}

# Include directories for `include files, one row each. Also searched for
# RTL file names after RTL_SEARCH_DIRS. Not for vhdl.
set RTL_INCDIRS {
  "../examples/rtl/include"
}

# Verilog macros, NAME or NAME=VALUE, one row each. Not for vhdl.
set RTL_DEFINES {}

# NETLISTS

# Directories searched, in order, for netlist file names given without a
# full path. One row per directory.
set SYN_SEARCH_DIRS {
  "../examples/syn"
}

# Synthesized netlist files or .f file lists, one row each.
set SYN_FILES {
  "block.syn.v"
}

# Place-and-route netlist files or .f file lists. Not used by rtl2syn.
set APR_FILES {}

# GUIDANCE AND CONSTRAINTS

# SVF guidance file from synthesis. Recommended for Formality.
set SVF_FILE "../examples/syn/block.svf"

# Timing constraint files, one row each. Not used by Formality.
set SDC_FILES {}

# Power intent files, one row each. Not used by flowgen yet.
set UPF_FILES {}

# LIBRARIES

# Library file format: db (default, read_db) or lib (.lib or .lib.gz,
# read_lib).
set LIB_FORMAT "db"

# Library files (standard cells, memories, hard IPs), one row each. Only
# these exact files are read.
set LIB_FILES {
  "../examples/lib/stdcell_tt.db"
}

# Verilog models for hard IPs or cells without a library model, one row
# each. Read into both reference and implementation. Can be .f lists.
set SIM_FILES {}

# Modules to black box, one row each. Nothing is black boxed unless listed
# here.
set BLACKBOX_MODULES {}

# RUN ENVIRONMENT

# Shell setup files to source, in order, one row each.
set ENV_SOURCE {
  "../examples/env/setup.cshrc"
}

# Environment variable to set: ENV_SETENV(<NAME>). One row per variable.
set ENV_SETENV(SNPSLMD_LICENSE_FILE) "27020@lic-server1"
