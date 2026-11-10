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
    block_template.config.tcl   template listing every setting
docs/                      unrelated older docs (excluded from pack)
```

On the workstation, after unpacking, flowgen/configs/ also holds one
symlink per file in the local common_files/:
`flowgen/configs/<name> -> ../../common_files/<name>`

## pack.py / unpack.py

- `python3 pack.py [-o BUNDLE] [ROOT]`, default output bundle.txt.
- Packs only git-tracked files (so `git add` new files BEFORE packing).
  Excludes docs/ and common_files/ (EXCLUDE_DIRS).
- Bundle format 3 (`#@@PACK 3`), pure ASCII. Each file has a header
  `#@@FILE <path> mode=<octal> enc=<text|b64> lines=<n> eol=<0|1> md5=<hex>`,
  its lines, then `#@@END <path>`. Pure-ASCII text files are stored as
  readable lines; anything else as base64. This survives charset
  conversion and CRLF line endings (a non-ASCII bundle was once corrupted
  in transit: byte 0xbf at offset 114).
- `python3 unpack.py BUNDLE [-d DIR] [--force] [--list]`
  - Validates the whole bundle (MD5 per file) before writing anything.
  - If flowgen/ already exists: error without --force. With --force it
    removes flowgen/ only, then recreates it. Nothing outside flowgen/ is
    removed; common_files/ is never touched. Top-level files (pack.py,
    unpack.py) are simply overwritten.
  - Then creates flowgen/configs/ links to each file in DIR/common_files/
    (skips dotfiles, subdirectories, and names already present such as
    the template). Warns if common_files/ is missing.
  - Only `--force` (double dash) is accepted.
- Regenerate the bundle after every change and commit it.

## flowgen.py

Usage:
```
runflowgen.sh [--force] CONFIG
flowgen.py [--force] CONFIG
```
- CONFIG: block config, typically block.config.tcl (any name works),
  usually given as configs/block.config.tcl.
- --force: missing or unreadable input files (e.g. a missing .f list)
  and empty required file lists (RTL_FILES, SYN_FILES, LIB_FILES)
  become warnings and the run directory is generated anyway; the ignored
  problems are listed in the generated script header. Other config
  errors (missing settings, bad values, Tcl errors) still stop it.

Output (in the current directory; overwritten if it already exists):
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
  Exit codes: 0 PASS, 1 FAIL, 2 did not finish.
- Generated scripts are kept simple: one-line header, no generation date
  or "generated by" comments, no placeholder comments, 2-space indent.

How it works:
- The config is sourced in a real Tcl interpreter (tkinter.Tcl()) with
  the working directory set to the config's real directory. Only global
  variables created by the config are read; arrays become dicts.
- Config path is resolved with realpath, so relative paths are relative
  to common_files/ even through a flowgen/configs/ link.
- `$VARIABLES` inside braced list items are expanded by flowgen
  (Tcl `subst -nocommands -nobackslashes`).
- All values are validated; all errors are reported together; nothing is
  written unless everything renders. Unknown names with known prefixes
  (DESIGN, TOP_, RTL_, SYN_, LIB_, TOOL_, ENV_, ...) produce a typo
  warning. Missing files are warnings.
- .f file lists are expanded by flowgen: one path per line, // and #
  comments, $VAR from the environment, relative to the .f file. Supports
  nested -f/-F, -v, +incdir+, +define+. -y and other options are ignored
  with a warning.
- Relative file names in RTL_FILES/SYN_FILES and their .f lists (and .f
  files themselves) are looked up in RTL_SEARCH_DIRS/SYN_SEARCH_DIRS in
  order, then next to the config or .f file. First match wins (warning if
  found in several). Duplicate files are read once.

## Config style (block.config.tcl)

- Short human-readable comments. "Example:" blocks only where the
  setting starts empty or commented out; examples aligned flush with "#"
  (`# set NAME {` / `#   "item"` / `# }`). No decorative separators,
  no bloat.
- Single values in double quotes: `set TOP_DESIGN "block"`.
- Lists in braces, one double-quoted item per line, 2-space indent:
  ```
  set ENV_SOURCE {
    "/tools/setup.cshrc"
  }
  ```
- Helper variable PROJ_ROOT (not read by flowgen) for paths.
- Design name in examples: "block".

Settings:

| Setting | Required | Meaning |
|---|---|---|
| TOP_DESIGN | yes | top module |
| FLOWS | | flows to generate, default rtl2syn |
| RTL_FORMAT | | sverilog (default), verilog, vhdl |
| RTL_SEARCH_DIRS | | dirs searched (in order) for RTL file names |
| RTL_FILES | yes | RTL files or .f lists |
| RTL_INCDIRS, RTL_DEFINES | | include dirs, macros (not for vhdl) |
| SYN_SEARCH_DIRS | | dirs searched (in order) for netlist file names |
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

1. set_app_var for TOOL_SETTINGS(formality,*) (+ synopsys_auto_setup), hook setup
2. set_svf (if SVF_FILE)
3. read_db or read_lib, one per LIB_FILES entry
4. Reference: read_sverilog/read_verilog/read_vhdl -r {files} [-vcs {+incdir+.. +define+..}];
   SIM_FILES with read_verilog -r
5. Implementation: read_verilog -i -netlist {SYN files}; SIM_FILES with read_verilog -i
6. set_black_box r:/WORK/<m> and i:/WORK/<m> for BLACKBOX_MODULES
7. set_top r:/WORK/$TOP_DESIGN, set_top i:/WORK/$TOP_DESIGN, hook pre_match
8. match, report_unmatched_points > reports/..., hook pre_verify
9. verify; on failure report_failing_points, report_aborted_points,
   analyze_points -failing into reports/; hook post_verify
10. save_session -replace, write <flow>.status (PASS/FAIL), exit

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
- Should pack.py warn about untracked files (they are silently skipped)?
- Next flow after rtl2syn (e.g. syn2apr netlist vs netlist, ECO), UPF
  support (load_upf), constants for DFT ports (set_constant).
- docs/ files contain non-ASCII characters; left untouched (excluded from pack).

## Git

- Branch: claude/chat-session-8t1llt on github.com/ssaurabh41/learn.
- Commit after each change, regenerate bundle.txt, push.
