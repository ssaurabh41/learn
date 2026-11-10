#!/bin/tcsh -f
# Regression test for flowgen, using the template config and the example
# design in this directory. Usage: examples/run_regression.csh
#
# Checks:
#   1. csv2config turns block_template.config.csv into exactly the shipped
#      block_template.config.tcl
#   2. flowgen runs on the template config with no warnings or errors
#   3. the run directory has every expected file, and the run script parses
# Output goes to examples/regression_out/ (removed at the start of each run).

set here = "`dirname $0`"
set root = "`cd $here/.. && pwd`"
if ( "$root" == "" || ! -d "$root/flowgen" ) then
  echo "regression: cannot find the repo root from $0"
  exit 2
endif
set out = "$root/examples/regression_out"
if ( -d "$out" ) rm -rf "$out"
mkdir -p "$out"
set fail = 0

# 1. CSV template -> config template
python3 "$root/common_files/csv2config.py" "$root/common_files/block_template.config.csv" \
  -o "$out/block_template.config.tcl" > "$out/csv2config.log"
if ( $status != 0 ) then
  echo "FAIL csv2config (see $out/csv2config.log)"
  set fail = 1
else
  cmp -s "$out/block_template.config.tcl" "$root/common_files/block_template.config.tcl"
  if ( $status != 0 ) then
    echo "FAIL block_template.config.tcl is out of date; regenerate it from the CSV:"
    echo "     common_files/csv2config.py --force common_files/block_template.config.csv"
    set fail = 1
  else
    echo "PASS csv2config"
  endif
endif

# 2. flowgen on the template config
cd "$out"
python3 "$root/flowgen/flowgen.py" "$root/common_files/block_template.config.tcl" >& flowgen.log
if ( $status != 0 ) then
  echo "FAIL flowgen exited with an error (see $out/flowgen.log)"
  set fail = 1
else
  grep -q -e "WARNING" -e "ERROR" flowgen.log
  if ( $status == 0 ) then
    echo "FAIL flowgen printed warnings (see $out/flowgen.log)"
    set fail = 1
  else
    echo "PASS flowgen"
  endif
endif

# 3. Run directory contents
set rundir = "`ls -d $out/*_block_formality |& head -1`"
set dirfail = 0
foreach f ( run_rtl2syn.csh rtl2syn/rtl2syn.tcl rtl2syn/logs rtl2syn/reports block_template.config.tcl )
  if ( ! -e "$rundir/$f" ) then
    echo "FAIL missing $f in the run directory"
    set dirfail = 1
  endif
end
if ( -e "$rundir/run_rtl2syn.csh" ) then
  tcsh -n "$rundir/run_rtl2syn.csh"
  if ( $status != 0 ) then
    echo "FAIL run_rtl2syn.csh does not parse"
    set dirfail = 1
  endif
endif
if ( $dirfail == 0 ) then
  echo "PASS run directory"
else
  set fail = 1
endif

if ( $fail != 0 ) then
  echo "regression: FAILED"
  exit 1
endif
echo "regression: PASSED"
exit 0
