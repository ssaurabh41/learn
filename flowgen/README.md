# flowgen

Generates EDA run directories from one Tcl block config. Python 3.6+ (with tkinter), standard library only.

The first supported tool is Synopsys Formality, with the `rtl2syn` flow: RTL reference vs. synthesized netlist.

## Usage

```
runflowgen.sh configs/block.config.tcl
```

`runflowgen.sh` is a csh (tcsh) wrapper that runs `flowgen.py` with `python3`, passing all arguments through. Add `--force` to generate even when input files are missing or a required file list is empty.

This creates the following in the current directory. If the directory already exists, it is overwritten.

```
<yyyy_mm_dd_hh_mm_ss>_<TOP_DESIGN>_formality/
  block.config.tcl      copy of the config used
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

The log goes to `rtl2syn/logs/rtl2syn.log`, the reports to `rtl2syn/reports/`, and the result (PASS or FAIL) to `rtl2syn/rtl2syn.status`. The run script exits with 0 for PASS, 1 for FAIL, and 2 if the flow did not finish.

## Config

The config is plain Tcl. Start from `configs/block_template.config.tcl`, which explains every setting with examples. The usual name is `block.config.tcl`, but any name works.

- Single values go in double quotes: `set TOP_DESIGN "block"`.
- Lists go in braces, one double-quoted item per line. flowgen expands `$VARIABLES` inside list items.
- Relative paths are resolved from the config file's real directory (`common_files/`, even when run through a `flowgen/configs/` link).
- File lists (`RTL_FILES`, `SYN_FILES`, `APR_FILES`, `SIM_FILES`) accept `.f` files. A `.f` file holds one path per line, with `//` or `#` comments. It may also contain `-f`, `-v`, `+incdir+` and `+define+`.
- File names without a full path in `RTL_FILES`, `SYN_FILES` and their `.f` lists are looked up in `RTL_SEARCH_DIRS` / `SYN_SEARCH_DIRS`, in order, then (for RTL) in `RTL_INCDIRS` and `+incdir+` dirs, then next to the config (or the `.f` file).
- `$NAME` inside a `.f` file uses config variables (e.g. your own `USER_RTL_DIR`), then environment variables.
- Helper variables such as `PROJ_ROOT` are optional; flowgen never needs them. A name found in several directories uses the first one, with a warning. A file listed twice is read once.
- Misspelled setting names and missing files produce warnings. Errors are all reported together, and nothing is generated if there are any.

Block configs live in the top-level `common_files/` directory. `unpack.py` creates `flowgen/configs/` with a link to each file in `common_files/`; re-run it with `--force` after adding a config. `common_files/` holds your golden configs on your own machine: it is never packed into `bundle.txt`, and `unpack.py` never touches it.

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
| `ENV_SOURCE` | | cshrc files sourced by the run script |
| `ENV_SETENV(NAME)` | | environment variables set by the run script |
