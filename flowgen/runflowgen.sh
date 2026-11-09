#!/bin/tcsh -f
# Run flowgen.py with python3 (3.6+ with tkinter).
# Usage: runflowgen.sh [--force] CONFIG
# Example: runflowgen.sh configs/block.config.tcl

set here = "`dirname $0`"
python3 "$here/flowgen.py" $argv:q
exit $status
