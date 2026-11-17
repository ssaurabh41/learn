# common_files

Golden block configs (`<block>.config.tcl`). On your own machine this
directory is the source of truth: it is never packed into `bundle.txt`, and
`unpack.py` never touches it. flowgen reads the configs from here:
`runflowgen.sh <block>` reads `<block>.config.tcl`.

Start a new block with `flowgen/runflowgen.sh --new <block>`, or fill in
a spreadsheet: copy `flowgen/configs/block_template.config.csv` here as
`<block>.config.csv`, edit it, and run
`flowgen/csv2config.py <block>.config.csv`. The first
time it also creates `project.config.tcl`, the settings shared by all
blocks. Every setting is explained in
`flowgen/configs/block_template.config.tcl`.
