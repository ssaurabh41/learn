#!/bin/tcsh -f
# Run flowgen.py with python3 (3.6+ with tkinter).
# Usage: runflowgen.sh --new BLOCK  or  runflowgen.sh [--force] BLOCK
# Example: runflowgen.sh --new uart_ctrl ; runflowgen.sh uart_ctrl

set here = "`dirname $0`"
python3 "$here/flowgen.py" $argv:q
exit $status
