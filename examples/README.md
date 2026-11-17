# examples

A small placeholder design and its configs, used by the regression test.
It follows the usual layout: `$PROJ_ROOT/<block>/rtl/source.f` and
`$PROJ_ROOT/<block>/syn/outputs/<top>.syn.v`, with `PROJ_ROOT` set to this
directory. The files only need to exist for flowgen: they are not a real
library or a real synthesis result, so Formality itself will not pass on
them.

```
configs/project.config.tcl   project settings (library, tool setup)
configs/block.config.tcl     block config; uses the search dirs
block/rtl/                   RTL, source.f, include/
block/syn/outputs/           netlist and SVF
pdk/stdcell_tt.db            placeholder library
env/setup.cshrc              placeholder tool setup
```

Run the regression after every change to flowgen:

```
examples/run_regression.csh
```

It generates run directories under `regression_out/` (next to `examples/`, so
unpacking a new bundle leaves it alone) and checks
that flowgen prints no warnings and that the run directories are complete.
