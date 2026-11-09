# flowgen

Generates EDA run directories from one Tcl block config. Python 3.6+ (with tkinter), standard library only.

The first supported tool is Synopsys Formality, with the `rtl2syn` flow: RTL reference vs. synthesized netlist.

## Usage

```
flowgen.py configs/my_block.config.tcl
```

This creates the following in the current directory. If the directory already exists, it is overwritten.

```
<yyyy_mm_dd_hh_mm_ss>_<DESIGN>_formality/
    block.config.tcl      copy of the config used
    run_rtl2syn.csh       run script (tcsh): sets up the env, runs fm_shell
    rtl2syn/
        rtl2syn.tcl       generated Formality script
```

Nothing is launched. To run a flow:

```
cd <yyyy_mm_dd_hh_mm_ss>_<DESIGN>_formality
./run_rtl2syn.csh
```

The log goes to `rtl2syn/rtl2syn.log`, the reports to `rtl2syn/reports/`, and the result (PASS or FAIL) to `rtl2syn/rtl2syn.status`. The run script exits with 0 for PASS, 1 for FAIL, and 2 if the flow did not finish.

## Config

The config is plain Tcl and is evaluated by a real Tcl interpreter. See `block_template.config.tcl` for every supported variable, and copy from it to start a new block config.

Block configs live in the top-level `common_files/` directory. `unpack.py` creates `flowgen/configs/` with a link to each file in `common_files/`; re-run it with `--force` after adding a config. `common_files/` holds your golden configs on your own machine: it is never packed into `bundle.txt`, and `unpack.py` never touches it.

Relative paths are resolved from the config file's real directory (`common_files/`, even when run through a `flowgen/configs/` link). Misspelled `FM_*` or `ENV_*` variables produce a warning, and missing input files produce warnings. Config errors are all reported together, and nothing is generated if there are any.

| Variable | Required | Meaning |
|---|---|---|
| `DESIGN` | yes | top module |
| `FM_RTL_FILES` | yes | RTL file list |
| `FM_SYN_NETLIST` | yes | synthesized netlist(s) |
| `FM_LIBS` | yes | `.db` technology libraries |
| `FM_FLOWS` | | flows to generate (default `rtl2syn`) |
| `FM_RTL_FORMAT` | | `sverilog` (default), `verilog`, `vhdl` |
| `FM_RTL_VCS_OPTS` | | options for `read_*verilog -vcs` |
| `FM_SVF` | | SVF guidance file |
| `FM_AUTO_SETUP` | | `synopsys_auto_setup` (default 1) |
| `FM_APP_VAR(name)` | | extra `set_app_var` |
| `FM_HOOK(point)` | | Tcl file to source at `setup`, `pre_match`, `pre_verify`, `post_verify` |
| `FM_SHELL` | | Formality command (default `fm_shell`) |
| `ENV_SOURCE` | | cshrc files sourced by the run script |
| `ENV_SETENV(NAME)` | | environment variables set by the run script |
