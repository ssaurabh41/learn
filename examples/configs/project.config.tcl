# Project config for the example design (see examples/README.md).

# Example project root: the examples/ directory, relative to this file.
set PROJ_ROOT ".."

set LIB_FORMAT "db"
set LIB_FILES {
  "$PROJ_ROOT/pdk/stdcell_tt.db"
}

set ENV_SOURCE {
  "$PROJ_ROOT/env/setup.cshrc"
}
set ENV_SETENV(SNPSLMD_LICENSE_FILE) "27020@lic-server1"
