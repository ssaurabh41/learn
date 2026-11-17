# Session handoff: flowgen (EDA flow generator)

Paste this file into a new Claude Code session (or keep it in the repo root)
to continue the work with the same context and decisions.

## Who I am and how to work with me

- I develop IC design flows (VLSI digital, Synopsys EDA tools).
- Ask, don't assume. If something is unclear, ask before writing code.
  When running unattended, pick the most reasonable interpretation,
  proceed, and record the assumption.
- Simplest solution for simple problems; better design for harder ones.
  No over-engineering.
- Don't touch unrelated code; point out bad code or design smells so we
  can handle them separately.
- Flag uncertainty explicitly. Small, low-risk experiments are welcome.
- Suggest better or longer-lasting approaches when you see them.

## Environment constraints (my workstation)

- Python 3.6.5, standard library only (no third-party packages).
  Python must have tkinter (used to read the Tcl config).
- Shell: tcsh. Tool/license setup needs `source <cshrc>` and `setenv`.
- Synopsys Formality (fm_shell). Launching is always manual.
- I cannot git clone. I move the repo as one text file (bundle.txt) and
  recreate it with unpack.py.
- All files must be pure ASCII. No unicode characters.
- Indentation in Tcl, config and csh files: 2 spaces. Python stays at
  4 spaces (not yet confirmed whether Python should also be 2).

## Goal

A flow generator: Python as the base, Tcl as the EDA tool scripting
language. It reads a block config (Tcl) and creates a run directory with
generated tool scripts and run scripts. Start with Synopsys Formality,
default comparison RTL vs synthesized netlist (rtl2syn). Other tools and
flows (e.g. netlist vs APR, DC, PrimeTime) come later.

## Repository layout

```
bundle.txt                 all packed files (copy this to the workstation)
pack.py                    packs git-tracked files into bundle.txt
unpack.py                  recreates files from bundle.txt
session.md                 this file
common_files/              golden block configs (LOCAL ONLY, never packed;
                           repo copy holds only a README)
flowgen/
  flowgen.py               the generator
  runflowgen.sh            tcsh wrapper: runs flowgen.py with python3
  README.md
  configs/
    block_template.config.tcl     reference listing every setting
    new_block.config.tcl          short block config written by --new
                                  (@BLOCK@ is replaced by the block name)
    project_template.config.tcl   copied to common_files/project.config.tcl
                                  by the first --new
docs/                      unrelated older docs (excluded from pack)
```

On the workstation the configs live only in common_files/, next to
flowgen/: project.config.tcl (shared settings) and <block>.config.tcl.
flowgen reads them from there. There are no config links any more
(decided 2026-11-13: one place, one name, no unpack --force to register
a config).

## pack.py / unpack.py

- `python3 pack.py [-o BUNDLE] [ROOT]`, default output bundle.txt.
- Packs only git-tracked files (so `git add` new files BEFORE packing).
  Excludes docs/ and common_files/ (EXCLUDE_DIRS). File modes come from
  the git index (so packing on Windows keeps 755). Untracked and
  uncommitted files are listed as warnings. Errors (bundle not touched):
  git fails inside a repo, ROOT is not a directory, nothing to pack, a
  file name with characters outside letters, digits and ._+-
- Bundle format 3 (`#@@PACK 3`), pure ASCII. Each file has a header
  `#@@FILE <path> mode=<octal> enc=<text|b64> lines=<n> eol=<0|1> md5=<hex>`,
  its lines, then `#@@END <path>`. Pure-ASCII text files are stored as
  readable lines; anything else as base64. This survives charset
  conversion and CRLF line endings (a non-ASCII bundle was once corrupted
  in transit: byte 0xbf at offset 114).
- `python3 unpack.py BUNDLE [-d DIR] [--force] [--list]`
  - Validates the whole bundle (MD5 per file) before writing anything.
  - If flowgen/ already exists: error without --force. With --force it
    removes flowgen/ only, then recreates it. If flowgen/ holds user
    files (not in the bundle, not a config link), it is renamed to
    flowgen.old_<date>_<time> instead of removed. Nothing outside
    flowgen/ is removed; common_files/ is never touched. Top-level files
    (pack.py, unpack.py) are simply overwritten.
  - Bundle paths are checked against an allow-list (letters, digits,
    ._+-); ./, ../, absolute paths, common_files/ and .git/ are rejected,
    as are duplicate entries and an empty bundle.
  - Prints the next commands (runflowgen.sh --new <block>, then
    runflowgen.sh <block>). It no longer creates config links.
  - Only `--force` (double dash) is accepted.
- Regenerate the bundle after every change and commit it.

## flowgen.py

Usage:
```
runflowgen.sh --new BLOCK
runflowgen.sh [--force] BLOCK
```
- --new BLOCK: writes common_files/BLOCK.config.tcl from
  configs/new_block.config.tcl and, if missing,
  common_files/project.config.tcl from configs/project_template.config.tcl,
  then prints what to edit and the generate command. Never overwrites.
- BLOCK: reads common_files/BLOCK.config.tcl (common_files/ is found
  next to the flowgen/ directory of the running flowgen.py). A path to
  a config file is also accepted. With an unknown block the error lists
  the blocks that have a config.
- After generating, flowgen prints the run script to launch and where
  the result and log will be. The project config is copied into the run
  directory next to the block config.
- Missing or unreadable input files (RTL, netlist, library, SVF, hook,
  cshrc, .f list) are errors. With --force they become warnings and the
  run directory is generated anyway; the ignored problems are listed in
  the headers of the generated scripts. Other config errors (missing
  settings, bad values, Tcl errors) still stop it. Files of settings no
  flow reads yet (APR_FILES, SDC_FILES, UPF_FILES) are not checked.

Output (in the current directory; never overwritten, a same-second rerun
gets a _2, _3 suffix):
```
<yyyy_mm_dd_hh_mm_ss>_<TOP_DESIGN>_formality/
  block.config.tcl      copy of the config used (original file name)
  run_rtl2syn.csh       tcsh: source ENV_SOURCE, setenv ENV_SETENV, run tool
  rtl2syn/              the tool runs here
    rtl2syn.tcl         generated Formality script
    logs/               empty; log goes to logs/rtl2syn.log
    reports/            empty; reports go here
```
- run_rtl2syn.csh runs `<TOOL_CMD> -f rtl2syn.tcl < /dev/null |& tee
  logs/rtl2syn.log` from rtl2syn/, then reads rtl2syn/rtl2syn.status.
  Exit codes: 0 PASS, 1 FAIL, 2 did not finish. The run script removes
  the old status file before starting the tool and exits 2 if an
  ENV_SOURCE file cannot be read.
- Generated scripts are kept simple: one-line header, no generation date
  or "generated by" comments, no placeholder comments, 2-space indent.

How it works:
- The config is sourced in a real Tcl interpreter (tkinter.Tcl()) with
  the working directory set to the config's real directory. Only global
  variables created by the config are read; arrays become dicts.
- Config path is resolved with realpath, so relative paths are relative
  to the config's real directory (common_files/).
- `$VARIABLES` inside braced list items are expanded by flowgen
  (Tcl `subst -nocommands -nobackslashes`).
- All values are validated; all errors are reported together; nothing is
  written unless everything renders. Unknown names close to a known
  setting (difflib, e.g. BLACK_BOX_MODULES, top_design) produce a typo
  warning. A tool key other than "formality" is an error.
- .f file lists are expanded by flowgen: one path per line, // and #
  comments (line start or after a space), $VAR from the config variables,
  then the environment (unset is an error), relative to the .f file. Supports nested -f/-F,
  -v, +incdir+, +define+. Duplicates are dropped. -y and other options
  are ignored with a warning.
- File name lookup (RTL_FILES, SYN_FILES, names inside .f files): next to
  the config or the .f file first, then *_SEARCH_DIRS in order, then (RTL
  only) RTL_INCDIRS and +incdir+ dirs. All .f files are read before any
  lookup. First match wins (warning if several); not found anywhere is a
  file error listing the dirs searched.
- ENV_SETENV entries are written in config order with double quotes
  ($VAR expanded by csh at run time). ENV_SOURCE items may carry
  arguments after the file name.

## Config style (block.config.tcl)

- Human-readable comments, each setting with an "Example:" block.
  No decorative separator characters.
- Single values in double quotes: `set TOP_DESIGN "block"`.
- Lists in braces, one double-quoted item per line, 2-space indent:
  ```
  set ENV_SOURCE {
    "/tools/setup.cshrc"
  }
  ```
- Helper variables PROJ_ROOT and BLOCK (not read by flowgen) for paths:
  $PROJ_ROOT/$BLOCK/rtl/source.f, .../syn/outputs/$TOP_DESIGN.syn.v.
- A block config starts with `source project.config.tcl` (explicit, plain
  Tcl; works because the config is sourced with its own directory as the
  working directory). Project settings: PROJ_ROOT, LIB_FORMAT, LIB_FILES,
  ENV_SOURCE, ENV_SETENV, TOOL_CMD, TOOL_SETTINGS. A block config can set
  any of them again.
- Optional settings are empty in the templates; examples are comments.
- Design name in examples: "block".

Settings:

| Setting | Required | Meaning |
|---|---|---|
| TOP_DESIGN | yes | top module |
| FLOWS | | flows to generate, default rtl2syn |
| RTL_FORMAT | | sverilog (default), verilog, vhdl |
| RTL_SEARCH_DIRS | | dirs searched for RTL file names |
| RTL_FILES | yes | RTL files or .f lists |
| RTL_INCDIRS, RTL_DEFINES | | include dirs, macros (not for vhdl) |
| SYN_SEARCH_DIRS | | dirs searched for netlist file names |
| SYN_FILES | yes for rtl2syn | synthesized netlist files or .f lists |
| APR_FILES | | APR netlist (future flows) |
| SVF_FILE | | synthesis guidance |
| SDC_FILES | | constraints (not used by Formality) |
| UPF_FILES | | power intent (not used yet) |
| LIB_FORMAT | | db (default, read_db) or lib (read_lib, .lib/.lib.gz) |
| LIB_FILES | yes | exact library files; nothing else is read |
| SIM_FILES | | Verilog models for hard IPs/cells, read into both sides |
| BLACKBOX_MODULES | | explicit black boxes (never automatic) |
| TOOL_CMD(tool) | | tool command, default fm_shell |
| TOOL_SETTINGS(tool,name) | | tool variables; for formality -> set_app_var |
| TOOL_HOOKS(tool,point) | | Tcl files sourced at setup, pre_match, pre_verify, post_verify |
| ENV_SOURCE | | cshrc files sourced by the run script |
| ENV_SETENV(NAME) | | environment variables set by the run script |

Tool key today is "formality". synopsys_auto_setup defaults to true unless
set in TOOL_SETTINGS(formality,synopsys_auto_setup).

## Generated Formality script (rtl2syn) order

1. set_app_var synopsys_auto_setup first, then TOOL_SETTINGS(formality,*), hook setup
2. set_svf (if SVF_FILE)
3. read_db or read_lib, one per LIB_FILES entry
4. Reference: read_sverilog/read_verilog/read_vhdl -r {files} [-vcs {+incdir+.. +define+..}];
   SIM_FILES with read_verilog -r
5. Implementation: read_verilog -i -netlist {SYN files}; SIM_FILES with read_verilog -i
6. set_black_box r:/WORK/<m> and i:/WORK/<m> for BLACKBOX_MODULES
7. set_top r:/WORK/$TOP_DESIGN, set_top i:/WORK/$TOP_DESIGN, hook pre_match
8. match, report_unmatched_points > reports/..., hook pre_verify
9. verify; write <flow>.status (PASS/FAIL) at once; on failure
   report_failing_points, report_aborted_points, analyze_points -failing
   into reports/; hook post_verify
10. save_session -replace, exit

## Not verified against Formality documentation (check `man` in fm_shell)

The Synopsys manuals are behind SolvNet; these are best-knowledge forms:
1. read_lib accepting .lib.gz directly.
2. read_sverilog -r ... -vcs "+incdir+... +define+..." syntax.
3. set_black_box r:/WORK/<module> before set_top (form and position).
4. Reading SIM_FILES with plain read_verilog -r / -i.
5. `if {[verify]}` relying on verify returning 1 on success.
6. save_session -replace and analyze_points -failing.

## Verification done in the cloud session (no Formality available)

- Python 3.6 compatibility checked with vermin; Python 3.12 + tkinter used to run.
- Generated Tcl executed end to end in tclsh with stub Formality commands.
- Generated csh checked with `tcsh -n`.
- pack/unpack round trips: identical files, CRLF conversion, corruption
  detection, --force behaviour, config links.
- ASCII check: `grep -lP '[^\x00-\x7F]' <files>`.

## Open questions / possible next steps

- Should Python files also use 2-space indentation?
- Not verified in tcsh (none on the dev machine): the new run script
  lines (if ( ! -r file ), if ( ! -d dir ), setenv with double quotes).
- Audit items left open: read_lib may not exist in fm_shell; aborted or
  inconclusive verify is reported as FAIL; no version number or
  provenance in run directories; bundle has no end marker (a bundle cut
  between two files unpacks without error).
- Next flow after rtl2syn (e.g. syn2apr netlist vs netlist, ECO), UPF
  support (load_upf), constants for DFT ports (set_constant).
- docs/ files contain non-ASCII characters; left untouched (excluded from pack).

## Git

- Branch: main on github.com/ssaurabh41/learn (work goes directly to main).
- Commit after each change, regenerate bundle.txt, push.
