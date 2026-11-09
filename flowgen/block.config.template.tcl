# =============================================================================
# block.config.template.tcl - TEMPLATE block config for flowgen.py
#
# Lists every variable flowgen understands. Copy what you need into your
# golden config in common_files/ (e.g. common_files/my_block.config.tcl).
#
# Plain Tcl: use set, lists, arrays, $env(...), [glob ...], [file join ...].
# Relative paths are relative to THIS file's directory.
# Only the variables below are used; misspelled FM_*/ENV_* names are warned
# about. Any other variable (e.g. ROOT below) is just a helper for you.
#
# Generate:   flowgen.py configs/my_block.config.tcl
# =============================================================================

# Helper variable (not read by flowgen)
set ROOT /proj/chip/blocks/my_block

# -- Block --------------------------------------------------------------------
# Top module name (required)
set DESIGN my_block

# -- Flows to generate ----------------------------------------------------------
# Default: rtl2syn (RTL reference vs synthesized netlist)
set FM_FLOWS {rtl2syn}

# -- Tool and license environment (written into the run_*.csh scripts) -------
# cshrc files to source, in order
set ENV_SOURCE [list /tools/synopsys/setup.cshrc]
# setenv NAME value
set ENV_SETENV(SNPSLMD_LICENSE_FILE) 27020@lic-server1:27020@lic-server2
# Formality executable (name on PATH or full path). Default: fm_shell
# set FM_SHELL /tools/synopsys/fm/V-2023.12/bin/fm_shell

# -- Reference: RTL (required) -----------------------------------------------
# One of: sverilog (default), verilog, vhdl
set FM_RTL_FORMAT sverilog
set FM_RTL_FILES [list \
    $ROOT/rtl/my_block_pkg.sv \
    $ROOT/rtl/my_block_ctrl.sv \
    $ROOT/rtl/my_block.sv \
]
# Or pick them up with a glob:
# set FM_RTL_FILES [lsort [glob $ROOT/rtl/*.sv]]

# Optional VCS-style options passed to read_sverilog/read_verilog -vcs
# (include dirs, defines, -f filelists). Not used for vhdl.
# set FM_RTL_VCS_OPTS "+incdir+$ROOT/rtl/include +define+SYNTHESIS"

# -- Implementation: synthesized netlist (required) ----------------------------
set FM_SYN_NETLIST [list $ROOT/syn/outputs/my_block.syn.v]

# -- Synthesis guidance (optional, recommended) --------------------------------
set FM_SVF $ROOT/syn/outputs/my_block.svf
# synopsys_auto_setup (default 1). Set 0 to turn it off.
# set FM_AUTO_SETUP 1

# -- Technology libraries (required) ----------------------------------------------
set FM_LIBS [list \
    /pdk/stdcell/db/stdcell_tt_0p80v_25c.db \
]

# -- Extra Formality app vars: set_app_var <name> <value> -------------------------
# set FM_APP_VAR(hdlin_unresolved_modules)  black_box
# set FM_APP_VAR(verification_timeout_limit) 4:0:0

# -- Hooks: your own Tcl files, sourced at fixed points in the flow ------------
#   setup       after app vars, before anything is read
#   pre_match   designs read and set_top done (set_constant, set_black_box, ...)
#   pre_verify  after match (set_user_match, ...)
#   post_verify after verify (extra reports)
# set FM_HOOK(pre_match) $ROOT/fm/constraints.tcl
