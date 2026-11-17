#!/bin/tcsh -f
# Regression test for flowgen. Usage: examples/run_regression.csh
# Needs python3 (3.6+ with tkinter) and tcsh on PATH.
#
# Each case generates a run directory in examples/regression_out/<case>/
# (removed at the start) and must print no warnings or errors:
#   example   examples/configs/block.config.tcl (uses the search dirs)
#   new_block flowgen/configs/new_block.config.tcl, as --new writes it
#   csv       flowgen/configs/block_template.config.csv through csv2config.py
# The run directory must hold the run script (which must parse), the
# Formality script, logs/, reports/ and copies of both configs.
# Last, the reference template block_template.config.tcl must be valid
# (its paths do not exist here, so it is run with --force).

set here = "`dirname $0`"
set root = "`cd $here/.. && pwd`"
if ( "$root" == "" || ! -f "$root/flowgen/flowgen.py" ) then
  echo "regression: cannot find the repo root from $0"
  exit 2
endif
set flowgen = "$root/flowgen/flowgen.py"
set out = "$root/examples/regression_out"
if ( -d "$out" ) rm -rf "$out"
mkdir -p "$out/configs"
set fail = 0

# Configs for the cases. The copies in regression_out/configs/ get the
# example project config with PROJ_ROOT as a full path.
set q = '"'
sed "s|^set PROJ_ROOT .*|set PROJ_ROOT ${q}$root/examples${q}|" \
  "$root/examples/configs/project.config.tcl" > "$out/configs/project.config.tcl"
sed "s|@BLOCK@|block|g" "$root/flowgen/configs/new_block.config.tcl" \
  > "$out/configs/new_block.config.tcl"
python3 "$root/flowgen/csv2config.py" "$root/flowgen/configs/block_template.config.csv" \
  -o "$out/configs/csv.config.tcl" > "$out/csv2config.log"
if ( $status != 0 ) then
  echo "FAIL csv: csv2config failed (see $out/csv2config.log)"
  set fail = 1
endif

foreach case ( example new_block csv )
  if ( "$case" == "example" ) then
    set config = "$root/examples/configs/block.config.tcl"
  else
    set config = "$out/configs/$case.config.tcl"
    if ( ! -f "$config" ) continue
  endif
  mkdir -p "$out/$case"
  cd "$out/$case"
  python3 "$flowgen" "$config" >& flowgen.log
  if ( $status != 0 ) then
    echo "FAIL ${case}: flowgen failed (see $out/$case/flowgen.log)"
    set fail = 1
    continue
  endif
  grep -q -e "WARNING" -e "ERROR" flowgen.log
  if ( $status == 0 ) then
    echo "FAIL ${case}: flowgen printed warnings (see $out/$case/flowgen.log)"
    set fail = 1
    continue
  endif
  set rundir = "`ls -d $out/$case/*_block_formality`"
  set casefail = 0
  foreach f ( run_rtl2syn.csh rtl2syn/rtl2syn.tcl rtl2syn/logs rtl2syn/reports \
              project.config.tcl `basename $config` )
    if ( ! -e "$rundir/$f" ) then
      echo "FAIL ${case}: missing $f in the run directory"
      set casefail = 1
    endif
  end
  tcsh -n "$rundir/run_rtl2syn.csh"
  if ( $status != 0 ) then
    echo "FAIL ${case}: run_rtl2syn.csh does not parse"
    set casefail = 1
  endif
  if ( $casefail == 0 ) then
    echo "PASS $case"
  else
    set fail = 1
  endif
end

# The reference template must be a valid config.
mkdir -p "$out/template"
cd "$out/template"
python3 "$flowgen" --force "$root/flowgen/configs/block_template.config.tcl" >& flowgen.log
if ( $status != 0 ) then
  echo "FAIL template: block_template.config.tcl is not a valid config (see $out/template/flowgen.log)"
  set fail = 1
else
  echo "PASS template"
endif

if ( $fail != 0 ) then
  echo "regression: FAILED"
  exit 1
endif
echo "regression: PASSED"
exit 0
