# flowgen

Generates EDA run directories from one Tcl block config. Python 3.6+ (with tkinter), standard library only.

The first supported tool is Synopsys Formality, with the `rtl2syn` flow: RTL reference vs. synthesized netlist.

## Quick start

```
python3 unpack.py bundle.txt            once: creates flowgen/
flowgen/runflowgen.sh --new uart_ctrl   creates common_files/uart_ctrl.config.tcl
flowgen/runflowgen.sh uart_ctrl         creates the run directory
<run directory>/run_rtl2syn.csh         runs Formality, prints PASS or FAIL
```

Each command prints what to do next. `uart_ctrl` is your block's name.

1. `--new` creates a short block config, `common_files/uart_ctrl.config.tcl`. The first time it also creates `common_files/project.config.tcl`, the settings shared by all blocks.
2. Edit `project.config.tcl` once per project: `PROJ_ROOT` and `LIB_FILES`, plus the tool setup (`ENV_SOURCE`, `ENV_SETENV`) if you need it.
3. Check the block config: `TOP_DESIGN` and the paths to the RTL file list, the netlist and the SVF. They are built from `$PROJ_ROOT/$BLOCK`, so a block that follows the usual layout needs no change.
4. Generate. If a file is missing, the error list says which setting to fix.

`common_files/` is the directory next to `flowgen/`. It holds your configs on your own machine: it is never packed into `bundle.txt`, and `unpack.py` never touches it. The commands can be run from any directory; the run directory is created in the current directory.

## Usage

```
runflowgen.sh --new BLOCK
runflowgen.sh [--force] BLOCK
```

`runflowgen.sh` is a csh (tcsh) wrapper that runs `flowgen.py` with `python3`, passing all arguments through. `BLOCK` reads `common_files/BLOCK.config.tcl`; a path to a config file also works. A missing input file (RTL, netlist, library, SVF, hook, cshrc) is an error. Add `--force` to generate anyway, for example before all design files exist: the missing files become warnings and are listed at the top of the generated scripts.

This creates the following in the current directory. An existing directory is never overwritten: a second run in the same second gets a `_2` suffix.

```
<yyyy_mm_dd_hh_mm_ss>_<TOP_DESIGN>_formality/
  uart_ctrl.config.tcl  copy of the block config used
  project.config.tcl    copy of the project config used
  run_rtl2syn.csh       run script (tcsh): sets up the env, runs fm_shell
  rtl2syn/              where Formality runs
    rtl2syn.tcl         generated Formality script
    logs/               empty, filled in by the tool
    reports/            empty, filled in by the tool
```

Nothing is launched. To run a flow:

```
cd <yyyy_mm_dd_hh_mm_ss>_<TOP_DESIGN>_formality
./run_rtl2syn.csh
```

The log goes to `rtl2syn/logs/rtl2syn.log`, the reports to `rtl2syn/reports/`, and the result (PASS or FAIL) to `rtl2syn/rtl2syn.status`. The run script exits with 0 for PASS, 1 for FAIL, and 2 if the flow did not finish (a setup file is missing, the tool did not start, or the script stopped early).

## Config

The config is plain Tcl. A block config starts with `source project.config.tcl`, so every setting can go in the project config (all blocks) or in the block config (one block); a block config can set a project setting again to change it. `configs/block_template.config.tcl` is the reference: it explains every setting with examples. Copy the settings you need from it.

- Single values go in double quotes: `set TOP_DESIGN "block"`.
- Lists go in braces, one double-quoted item per line. flowgen expands `$VARIABLES` inside list items.
- Relative paths are resolved from the config file's directory (`common_files/`).
- File lists (`RTL_FILES`, `SYN_FILES`, `APR_FILES`, `SIM_FILES`) accept `.f` files. A `.f` file holds one path per line, with `//` or `#` comments (at the start of a line or after a space). It may also contain `-f`, `-v`, `+incdir+` and `+define+`. `$VAR` in a `.f` file is a config variable (e.g. your own `USER_RTL_DIR`), else an environment variable; it must be set when flowgen runs. A file listed more than once is read once.
- A file name without a full path (in `RTL_FILES`, `SYN_FILES` or a `.f` file) is looked up next to the config or its `.f` file first, then in `RTL_SEARCH_DIRS` / `SYN_SEARCH_DIRS` in order, then (RTL only) in `RTL_INCDIRS` and `+incdir+` dirs. A name found in several places uses the first, with a warning; a name found nowhere is an error that lists the directories searched.
- A name that looks like a misspelled setting (`BLACK_BOX_MODULES`, `top_design`) produces a warning. A tool name other than `formality` in `TOOL_CMD`, `TOOL_SETTINGS` or `TOOL_HOOKS` is an error.
- Errors are all reported together, and nothing is generated if there are any.

Regression: `examples/run_regression.csh` runs flowgen on the example design in `examples/` and on the `--new` template, and checks that nothing is missing and no warning is printed. Run it after unpacking a new bundle.

Updating flowgen: unpack the new bundle with `python3 unpack.py --force bundle.txt`. It replaces `flowgen/` and leaves `common_files/` alone. If `flowgen/` holds files of your own, such as run directories, the old directory is kept as `flowgen.old_<date>_<time>` instead of being deleted.

| Setting | Required | Meaning |
|---|---|---|
| `TOP_DESIGN` | yes | top module |
| `FLOWS` | | flows to generate (default `rtl2syn`) |
| `RTL_FORMAT` | | `sverilog` (default), `verilog`, `vhdl` |
| `RTL_SEARCH_DIRS` | | directories searched for RTL file names |
| `RTL_FILES` | yes | RTL files or `.f` lists |
| `RTL_INCDIRS`, `RTL_DEFINES` | | include dirs, macros |
| `SYN_SEARCH_DIRS` | | directories searched for netlist file names |
| `SYN_FILES` | yes (rtl2syn) | synthesized netlist files or `.f` lists |
| `APR_FILES` | | APR netlist files (for future flows) |
| `SVF_FILE` | | synthesis guidance file |
| `SDC_FILES`, `UPF_FILES` | | constraints, power intent (not used by Formality yet) |
| `LIB_FORMAT` | | `db` (default) or `lib` |
| `LIB_FILES` | yes | technology library files |
| `SIM_FILES` | | Verilog models for hard IPs and cells |
| `BLACKBOX_MODULES` | | modules to black box |
| `TOOL_CMD(<tool>)` | | command that starts the tool (default `fm_shell`) |
| `TOOL_SETTINGS(<tool>,<name>)` | | tool variables (`set_app_var` for Formality) |
| `TOOL_HOOKS(<tool>,<point>)` | | your Tcl files at `setup`, `pre_match`, `pre_verify`, `post_verify` |
| `ENV_SOURCE` | | cshrc files sourced by the run script; arguments may follow the file name |
| `ENV_SETENV(NAME)` | | environment variables set by the run script, in the order of the config; `$VAR` in a value is expanded when the script runs |
