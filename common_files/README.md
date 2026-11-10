# common_files

Your golden block configs, named `<block_name>.config.tcl`, plus the tools
to make them. On your machine this directory is the source of truth:
`unpack.py` only writes the shipped files below and never removes or
changes anything else here. Every `*.config.tcl` here is linked into
`flowgen/configs/`.

Shipped files:

- `block_template.config.csv`  spreadsheet template; every setting, documented
- `block_template.config.tcl`  the same template as a config (made from the CSV)
- `csv2config.py`              turns `<block>.config.csv` into `<block>.config.tcl`

New block:

```
cp block_template.config.csv myblock.config.csv
```

Edit `myblock.config.csv` in LibreOffice (when opening, set the Value
column to Text; save as CSV), then:

```
./csv2config.py myblock.config.csv
```

This writes `myblock.config.tcl`. It will not overwrite an existing file
unless you add `--force`.
