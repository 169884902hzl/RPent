# Codex3 — 2026-10-17T13:59:11.182472+00:00

Latest source `2b229e304df138bdbe069781ce71af602bc1b2c3` is pushed to user-fork/harness-v5. Source snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_2b229e3_20261017`; archive SHA256 `0c349ccf0dc79bb4187e2de7d1b2a30f64957b0b9864d6af4d62eb4edf3011e9`.

## Resource change applied

The 10/17 resource instruction supersedes the dual-node paragraph in DIRECTION_20261016. All pending Codex3 bounded jobs were restricted with ReqNodeList=node02. Array7912 throttle was reduced to3; previously running jobs were not cancelled. New source launcher has nodelist=node02 and nice500. Current main7925 is oracle-only, array%3; startup7923_0 completed with real physical controls. Earlier startup7917_140 completed both K1/K4;7919_1 completed K1. Latest squeue capture: Codex3 runs7925_0/1/6 on node02 (3 total), zero node01 jobs; Codex2 uses7920 on the fourth card. Screenshot and raw parsed capture: reports/resource_node02_cap3_20261017.png and .json. No c5/c6/rf job or historical held job was modified or released. Future GPU work remains node02-only and aggregate <=3; no HUST use.

## Changes and checks

- 13a5c3c: an occluded contacted handle may refine its EEF-predicted public surface by the existing bounded registration. A saved microwave request's full route passes CPU screen after a4.646mm measured correction; the15mm/0.1rad limits and current-pixel continuity remain unchanged. Physical fixture tasks are still pending in7925; startup is not task success.
- d5f4c0e: a verified held identity lost by SAM can update pose/visibility/capture step from >=40 current temporal RGB-D points. Stale SAM pixels/pose alone cannot do so. Saved bowl7912 step6:4231 current surface points, centre z1.02996→0.949965m, capture5→6; oracle changes to release. CPU replay only.
- 2b229e3: an established public ID is not renamed by a higher score from another category query; initial same-capture de-duplication remains. Previously a bowl ID became plate and a different bowl was rebound. Private oracle peer exclusions now persist rather than being overwritten after temporary occlusion. Physical verification remains7925 seed0.
- CPU tests:80 adapter/payload tests for held-depth change;161 runtime tests and65 adapter tests for identity change. One existing pytest unknown-timeout-option warning. Bounded files pass scoped Ruff; historical v5_runtime/test_v5_runtime have69 existing diagnostics combined, no new diagnostics by HEAD-vs-working comparison. git diff check passes.

## Closed source9fa8831 development results

7912 is complete,10 physical arms, all use zero pi05 calls. These are5 representative states, not20/category eligibility and not confirmation.

| Category/state | K1 | K4 | K1 decisions/steps | K4 decisions/steps |
|---|---:|---:|---:|---:|
| bowl seed1 |1|1|9/421|6/380|
| bowl seed6 |1|1|7/251|6/255|
| box seed0 |0|0|18/1270|19/689|
| container seed0 |1|0|15/1437|10/580|
| cup seed0 |0|0|17/1712|12/670|

Bowl has4/4 arms but only2 independent states. Container K4, box and cup failures remain. Container/cup post-carry candidate screens report payload collision; point ownership is being checked from current public RGB-D rather than removing margins. No freeze or training admission.

## Diagnostic retry records

7918 failed because /tmp script existed only on the login node.7924 used a shared path but multiprocessing spawn reexecuted top-level setup and failed with FileExistsError (then ConnectionResetError). Shared script now has a main guard; CPU runpy import confirms no simulator launch at import. Both failed logs and partial directories preserved. Corrected retry7929 waits behind oracle array7925, per new priority; no physical box-truth result yet.

## Outstanding

Per-category20-episode upper bounds remain incomplete. Opening/closing drawer, microwave, stove and plate push still need successful package routes. Codex2 real bounded-choice service identity and latency remain a separate dependency (7920 is theirs); synthetic latency is not counted as model measurement. Confirmation identities and derivatives remain permanently excluded from training. DevelopmentHistory n0/null is retained until eligible development logs are registered. No training/PRO input/hardware/final evaluation performed.

## Interface/source hashes

- `SKILL_PACKAGE_SPEC.md`: `2364e3268855f870bd1d4b10aff337c7c1ade974b89af79298b0b653a5360880`
- `rpent/skill_package/schema.json`: `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`
- `robots/libero/bounded_skills.py`: `181effc02d2b447cc72b92b616b02e0162be6cf155d593ec70e0bf8d6eb31122`
- `robots/libero/bounded_oracle.py`: `1d2c118027702842054b646869f2c8012dbb60ebdbf93e4e8858bdcc5c8336b6`
- `robots/libero/v5_runtime.py`: `e4dabd5ebc742593a8fb3abe479363ac29bd78fe2eb363b20f559232f9195f46`
