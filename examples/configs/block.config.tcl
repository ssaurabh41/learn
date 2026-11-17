# Block config for the example design (see examples/README.md).
# It also uses the search directories: file names without a full path.

source project.config.tcl

set BLOCK "block"
set TOP_DESIGN "block"

set RTL_SEARCH_DIRS {
  "$PROJ_ROOT/$BLOCK/rtl"
}
set RTL_FILES {
  "source.f"
}
set RTL_INCDIRS {
  "$PROJ_ROOT/$BLOCK/rtl/include"
}

set SYN_SEARCH_DIRS {
  "$PROJ_ROOT/$BLOCK/syn/outputs"
}
set SYN_FILES {
  "$TOP_DESIGN.syn.v"
}

set SVF_FILE "$PROJ_ROOT/$BLOCK/syn/outputs/$TOP_DESIGN.svf"
