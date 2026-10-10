# 3D IP Kit — Plan

**Kit:** soft D2D controller and hard D2D PHY, released together
**Shipped flow:** customer integration checks · **Tools:** multi-vendor · **Version control:** SOS
**Languages:** Python 3.6+ (standard library only) for tooling and verif · Tcl inside EDA tools · tcsh for sourced environment setup only
**CI/CD:** manual trigger · auto-publish to internal · GA needs approval · `ip3d` CLI now, thin Airflow DAG later

---

## 1. Release tiers

| Tier | Source | Gate | Who uses it |
|---|---|---|---|
| **dev** | workarea | smoke | IP team |
| **internal** | SOS tag | full QC | integration, test chip, AEs |
| **ga** | promoted from internal, never rebuilt | QC + scrub + approver | customers |

Early-access drops are GA releases with `maturity: alpha|beta` in the MANIFEST.

---

## 2. Dev tree (SOS project)

```
ip3d/
  ip/ctrl/   rtl sdc upf syn lec doc            soft
  ip/phy/    lef gds lib netlist bump model doc  hard
  ip/ref/    ctrl+phy test integration           internal
  verif/     shipped customer flow (see 4)
  tools/     CI/CD + release tooling (see 5)     internal
  env/       tcsh setup files to source          internal
```

## 3. Customer kit

```
ip3d_<ver>/
  README  RELEASE_NOTES  LICENSE  MANIFEST.json
  ctrl/  phy/  verif/
```

MANIFEST.json holds the SOS tag, tool versions, tooling revision, command line, user, host, timestamp, approver (GA) and a sha256 for every file.

---

## 4. Shipped verification flow (customer)

```
verif/bin/ip3d_check -cfg my.json [-check X] [-bundle]
verif/checks/<check>/check.py             logic + pass criteria (vendor-neutral)
verif/checks/<check>/vendor/{cdns,snps,siem}/*.tcl   tool call only
```

| Check | Proves |
|---|---|
| kit_integrity | kit complete and unmodified (no EDA tool needed) |
| pin_bump | customer pins and bumps line up with the IP bump map |
| constraints | customer SDC covers what the IP requires |
| upf | customer UPF matches the IP power intent |
| lec | customer wrapper is equivalent to the reference |

- A check passes only if: exit code is 0, the log scan is clean, and every expected output exists.
- An unsupported vendor is an explicit failure, never a silent skip.
- `-bundle` packs logs, the MANIFEST verification result and environment info into one tarball for AE support.

---

## 5. CI/CD tooling (`tools/`)

```
tools/
  bin/ip3d                      CLI entry: ip3d <stage> [args]
  lib/ip3d/
    stage.py                    stage contract (below)
    spec.py manifest.py logscan.py lsf.py lock.py
    stages/  build  qc  publish  promote  diff
    qc/      one module per QC item, run in the order listed in kit_spec
  spec/kit_spec.json            single source of truth
  spec/errors/<tool>.pat        error patterns per tool
  spec/waivers.json             waivers: pattern, scope, owner, reason, expiry
  spec/approvers.json           who may approve GA
  tests/fixture_ip/  test_*.py  fake IP, no EDA tools needed, runs on Python 3.6
```

**kit_spec.json** lists every deliverable (path, view, tiers, required) and the ordered list of QC items. Build, QC, the GA filter and the MANIFEST all read from it.

**Stage contract.** Every stage takes `-in <dir> -out <dir>` and writes `status.json` (result, checks, logs).

| Exit code | Meaning |
|---|---|
| 0 | pass |
| 1 | check failed |
| 2 | usage or config error |
| 3 | tool, license or infra error |

**QC items, starting set:** completeness, checksums, log scan with waivers, verif/ on ref, scrub (GA only). Future items, such as view consistency, are a new module under `qc/` plus one line in kit_spec.

**Waivers.** An expired waiver fails QC. Every waiver used is listed in `status.json` and the release notes.

---

## 6. Pipeline

```
ip3d ci -tag <T>        build → qc → publish(internal) → diff vs previous
ip3d promote -from <ver> -approver <name>
                        verify → filter(ga) → qc+scrub → publish(ga) → tar+sha256
```

- **Manual trigger only.** One command starts each pipeline.
- **build:** populate a fresh workarea at the tag in a unique run dir, assemble in staging, write the MANIFEST.
- **publish:** take a lock, `mv` atomically (same filesystem as staging), make the tree read-only, clean up on interrupt.
- **diff:** list files added, removed and changed against the previous release; this feeds the release notes.
- **promote:** refuses unless the approver is in `approvers.json`. The approver is recorded in the MANIFEST.
- Heavy jobs go through `lsf.py` with blocking submission, so the job's exit code reaches the stage.
- **Later:** an Airflow DAG with one task per stage, each calling `ip3d <stage>`. No logic in the DAG.

Development pipeline, unchanged: ctrl (lint, synth, LEC) and phy (DRC/LVS, char, LEF) → ref integration → the shipped `verif/` on ref → kit.

---

## Open decisions (defaults in brackets)

- Tag and version naming [`ip3d_<MAJOR.MINOR.PATCH>`]
- Release area paths [TBD]
- First vendor to implement [TBD]
- Encrypted RTL (IEEE 1735)? [no]
- One GA kit or per-customer kits? [one]
- Bump map format [CSV, to be defined]

## To confirm

- Blocking `bsub` mode on your cluster (`man bsub`).
- Whether the `mkdir` lock and atomic `mv` work on the release NFS.
- Vendor commands for the 3D bump checks.
- Python 3.6 really exists on customer hosts.

---

## Next

1. Save this plan as `docs/ip3d_kit_plan.md`, and update "Languages and conventions" in the system prompt to the Python / Tcl / tcsh split.
2. Settle the open decisions.
3. Build in this order: `kit_spec.json` + stage contract + tests fixture, then `kit_integrity`, `build`, `qc`, `publish`, `diff`, `promote`, and finally the vendor checks.
