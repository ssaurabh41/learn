# common_files

Local files of your own. It is never packed into `bundle.txt`, and
`unpack.py` never touches it, so it is a safe place to keep a copy of
your configs.

flowgen no longer reads configs from here. Block configs live in
`flowgen/configs/`: `flowgen/runflowgen.sh --new <block>` creates
`flowgen/configs/<block>.config.tcl` (and, the first time,
`flowgen/configs/project.config.tcl`), and `runflowgen.sh <block>` reads
it from there. Every setting is explained in
`flowgen/configs/block_template.config.tcl`.
