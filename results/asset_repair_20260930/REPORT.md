# LIBERO-PRO official asset installation repair — 2026-09-30

The authoritative HF copy is installed and verified. D2 remains the original
8 suites × tasks 0–4 × init40; no replacement is needed. A1-N awaits Codex1's
independent asset verification, as requested. This is an installation result,
not a closed-loop model score or a harness-v5 freeze.

## Source, paths and execution

- Dataset: `zhouxueyang/LIBERO-Pro`, fixed revision
  `c86fc3b8293185a6f373677018ff3e37f8391602`, endpoint `https://hf-mirror.com`.
- Persistent download:
  `/public/home/sunyihan/liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602/`.
- Interpreter: `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`, Python3.10.
- Installed BDDL/init root:
  `/public/home/sunyihan/rpent_libero_eval/.venv/lib/python3.10/site-packages/liberopro/liberopro/`.
- Evidence root: `/public/home/sunyihan/rpent_libero_eval/results/asset_repair_20260930/`.
- Actual commands: [COMMANDS.sh](COMMANDS.sh). Utility:
  `scripts/repair_liberopro_assets.py`, SHA256
  `9c491d45f0265c56f1439f463159d33bc8fe815a13d88c1673a2b871a3dcfaf9`.
- Login-node download/backup/sync/validation; no GPU allocation. The saved
  pre-sync queue has no LIBERO jobs; node02 also had no surviving v5 runner.
  Codex2's2671/2651 and CPU generation were untouched.
- Initial four-worker download hit HTTP429; one-worker resume first hit the
  same API window, then completed. Original downloaded files and failed-resume
  log are preserved. No asset was synchronized before download and backup.

## Full backup and comparison

The complete current installation contained1619 files. All were archived
before writes, and every archived file hash was verified against the original.
Backup: `installed_before.tar.gz`, SHA256
`c28e6b6e0a2ffed8aeeb7e6cfdbe07ed292ea162498d07902455035d417cf967`;
binary stays in persistent remote storage.

The HF snapshot contains670 files under the two requested roots:350 match
existing files,40 differ,280 are new. The1229 installed-only files are retained.
All670 synchronized files match their pinned HF hashes.

| Changed group | Files |
| --- | ---: |
| BDDL Spatial Task | 2 |
| BDDL Long Task | 1 |
| BDDL Long Object | 7 |
| Init Spatial Task | 10 |
| Init Long Task | 10 |
| Init Long Object | 10 |

[differences.json](differences.json) lists every different path, its status,
before/HF bytes and SHA256, including all HF-only and installed-only files.
[hf_files.json](hf_files.json) is the complete downloaded file inventory;
[installed_before.json](installed_before.json) and
[installed_after.json](installed_after.json) preserve full installation hashes.

## Official benchmark verification

Both staged HF validation and a fresh-process installed validation pass using
the official `get_benchmark`, `get_task` and `get_task_init_states` methods.
All16 perturbation suites have10 tasks; all160 tasks have50 trials. Thus the
8 final suites'80 tasks all meet>=10, and all original40 D2 tasks have init40.
Every benchmark language matches its own BDDL language. Full task-level trials,
language, paths and hashes: [validation_after.json](validation_after.json),
with readable output in [validation_after.log](validation_after.log).

| Task | Before trials | HF / installed trials |
| --- | ---: | ---: |
| Spatial Task/task3 | 0 | 50 |
| Spatial Task/task7 | 0 | 50 |
| Long Task/task2 | 0 | 50 |
| Long Object/task4 (outside final8) | 0 | 50 |

**The repeated Spatial Task/task3/task7 wording remains in HF**:
`Pick the akita black bowl on the top of the cabinet and place it on the plate`.
Each matches its own authoritative BDDL. This repair does not claim that the
upstream duplication is corrected. No language, goal, task or init is invented.
Codex1 should retain this observation when registering the source identity.

## Historical Main15 scope

The40 BDDL/init files for Spatial Swap/Object Swap task0–9 all match between
the pre-repair installation and HF. No file used by those task names appears
in the40 changed-file list. Main15v1/v2 scores are unchanged and excluded from
v5. Earlier Main15 runs did not pin per-run asset hashes; today's matching
pre-install snapshot does not establish retrospective per-run byte identity.
This limitation is annotated in `LIBERO_PRO_RESULTS.md`.

## Pinned audit identities

| Artifact | SHA256 |
| --- | --- |
| hf_files.json | `27174f4b37c1e36309119ae2ceb5c0c52f3366b162f1580c4b0826aeb355c664` |
| differences.json | `a1e553d6652652fb12f8be3c6a3d2db249e9580f9f16ad72c07f10fb15dce15c` |
| installed_after.json | `4fb9158690c53028797a70984333862af8fe1020e95e373a0327336d824ddc54` |
| validation_after.json | `2d08d343cf755479e35a79c436f59c2e7cc1f5bff8fd3d7dd5b07c333fd3bf59` |
| original D2 manifest (unchanged) | `7d8a64e7b4297d96005806a72a82f2951662e43321bda4aa370c2b793ad50ac3` |
