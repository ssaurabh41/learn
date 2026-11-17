# Project settings shared by all block configs.
#
# Every block config starts with "source project.config.tcl", so what is
# set here applies to all blocks. A block config can set any of these
# again after that line to change it for one block.
#
# EDIT THESE: PROJ_ROOT and LIB_FILES. Everything else is optional.
# Every setting is explained in flowgen/configs/block_template.config.tcl.


# Project root directory. The block configs build their paths from it:
#   $PROJ_ROOT/<block>/rtl/source.f
#   $PROJ_ROOT/<block>/syn/outputs/<top>.syn.v
set PROJ_ROOT "/proj/chip"

# Technology library files: standard cells, memories, hard IPs.
# Give full file names; only these files are read.
# LIB_FORMAT is "db" (.db files) or "lib" (.lib or .lib.gz files).
set LIB_FORMAT "db"
set LIB_FILES {
  "/pdk/stdcell/db/stdcell_tt_0p80v_25c.db"
}

# Shell setup files sourced by the run script before the tool starts.
# Optional.
# Example:
#   set ENV_SOURCE {
#     "/tools/synopsys/setup.cshrc"
#   }
set ENV_SOURCE {}

# Environment variables set by the run script. Optional.
# Examples:
#   set ENV_SETENV(SNPSLMD_LICENSE_FILE) "27020@lic-server1"
#   set ENV_SETENV(PATH) {/tools/synopsys/fm/bin:$PATH}

# Command that starts Formality. Optional. Default: fm_shell
# Example:
#   set TOOL_CMD(formality) "/tools/synopsys/fm/V-2023.12/bin/fm_shell"

# Formality variables for all blocks. Optional.
# Example:
#   set TOOL_SETTINGS(formality,verification_timeout_limit) "4:0:0"
