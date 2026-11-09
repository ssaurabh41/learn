# common_files

Golden block configs (`<block>.config.tcl`). On your own machine this
directory is the source of truth: it is never packed into `bundle.txt`, and
`unpack.py` never touches it. `unpack.py` links each file here into `flowgen/configs/`.

Start a new config from `flowgen/configs/block_template.config.tcl`.
