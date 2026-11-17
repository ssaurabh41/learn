# Block config for @BLOCK@.
#
# Check the lines below, then generate the run directory with:
#   runflowgen.sh @BLOCK@
#
# Only the settings a first run needs are here. Every other setting
# (include dirs, defines, black boxes, tool settings, hooks, ...) is
# explained in flowgen/configs/block_template.config.tcl; copy the ones
# you need into this file.


# Project settings shared by all blocks: PROJ_ROOT, libraries, tool setup.
# Anything set there can be changed for this block below this line.
source project.config.tcl

# Name of the block's directory under $PROJ_ROOT.
set BLOCK "@BLOCK@"

# Name of the top module. Change it if it is not the block name.
set TOP_DESIGN "@BLOCK@"

# RTL source files, or .f file lists.
set RTL_FILES {
  "$PROJ_ROOT/$BLOCK/rtl/source.f"
}

# Synthesized netlist.
set SYN_FILES {
  "$PROJ_ROOT/$BLOCK/syn/outputs/$TOP_DESIGN.syn.v"
}

# SVF guidance file written by synthesis. Use "" if there is none.
set SVF_FILE "$PROJ_ROOT/$BLOCK/syn/outputs/$TOP_DESIGN.svf"
