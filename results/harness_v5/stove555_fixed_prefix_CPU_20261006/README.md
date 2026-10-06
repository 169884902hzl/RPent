# Stove555: runnable original measurement and fixed-prefix development driver

This packet follows stove552 without changing the runtime or endpoint verifier.
The stove552 packet, SOURCE550 and job4186 remain intact. Nothing in this packet
qualifies `turn_off`, emits a public `off=True`, contributes training rows or
submits a GPU job.

The same runner entry supports CPU preflight and physical execution. The
preflight hashes explicit absolute base/config/catalog/asset paths and pinned
source files, checks the four runtime resources, and optionally checks all ten
official initial-state hashes. It does not start SAM, π0.5 or a simulator. Both
manifests passed this real preflight from `/tmp` on the login node, using the
installed interpreter and original Goal7 assets. Those two reports are included.
`source_cpu_preflight/` is only the explicitly pinned CPU source subset used for
that check; it is not a complete runtime source snapshot and must not launch a
physical run. Root will register a complete immutable SOURCE555.

`stove_control_sampling10.json` performs the existing ten original Goal7
init0–9 measurements: fixed initial/on/off sequence, twenty contact skills,
eighty captures and 160 views. It adds the separately bound current control
features from stove552 and retains all missing/ambiguous measurement reasons.

`stove_nearzero_selection100.json` implements the previously prepare-only
near-zero selection as one hundred cells. Each cell starts a fresh environment
from its registered original init, captures the reset observation, runs a fixed
160-chunk on preparation, and captures the result. It then either returns to the
public reset TCP XYZ and yaw/pitch, or stages using the current measured control
through the existing `stage_fixture_handle`. A missing or failed measured
approach is recorded and the fixed original off subtask still runs. The off
prefix is exactly one of 1/4/16/64/160 chunks, followed by fixed before/after and
release/retreat captures. There are five scheduled captures per cell: 500 captures
and 1,000 camera views if the run has no collection error.

The diagnostic facade is unchanged: each scope has a 160-chunk maximum and each
chunk has five actions. The driver requests the smaller off prefix and closes
the scope explicitly. It records requested chunks, actual receipt chunks, raw
scope counters and executed controls so a planned prefix cannot be mistaken for
one physically completed. The native Goal7 success latch never truncates these
bounded diagnostic chunks; the external action cap remains 10,000 steps.

All on-setup failures stay in the one hundred cells. Only after the complete
cell action/capture schedule does the driver read saved private labels and write
`cell_analysis_labels.json`: setup succeeded/failed, near-zero true-off,
intermediate-dark, other, or unavailable/ambiguous joint label. Private qpos does
not choose an approach, prefix, capture time, public binding or stopping point.
Actual coverage must be reported; lack of twenty distinct observations in a
target bin does not justify extrapolation or qualification. The public geometry
still needs distinct current pivot/tip and shell/front-edge measurements.

The focused CPU suite passed 65 checks. It verifies the complete 100-cell
schedule, preserved failed setups, actual five-action prefix accounting,
absolute-path preflight and existing control/endpoint behavior. `bash -n` also
passed. Physical motion and SAM feature recall have not been tested in this
packet.

Rebuild the explicit manifests from any directory, using the repository as the
module source:

```bash
PYTHONPATH=/home/agilex/cobot_magic/rpent_libero_eval \
  /home/agilex/cobot_magic/rpent_libero_eval/.venv/bin/python \
  /home/agilex/cobot_magic/rpent_libero_eval/results/harness_v5/stove555_fixed_prefix_CPU_20261006/build_cpu_packet.py
```

The owner must first register SOURCE555, manifest SHA, output root and GPU
reservation in COORDINATION. The following commands are prepared, not executed:

```bash
export STOVE552_SOURCE=/public/home/sunyihan/rpent_libero_eval/SOURCE555_REGISTERED_PATH
export STOVE552_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_fixed_prefix_CPU_20261006/stove_control_sampling10.json
export STOVE552_MANIFEST_SHA=50fef3327c6d264d19a911ea5f3bd86807c683dab9bbbf25d4e9042874d83597
export STOVE552_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_measurement10_original_20261006
sbatch --export=ALL "$STOVE552_SOURCE/scripts/run_v5_stove552_measurement.sbatch"

export STOVE552_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_fixed_prefix_CPU_20261006/stove_nearzero_selection100.json
export STOVE552_MANIFEST_SHA=f1bb636b587e5a98bc581e3519c196d1d71e850744575cd95471f900c5eb8f83
export STOVE552_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_nearzero_selection_original_20261006
sbatch --array=0-7%8 --export=ALL "$STOVE552_SOURCE/scripts/run_v5_stove552_measurement.sbatch"
```

The launcher uses `/tmp` as cwd and absolute arguments. Its first command is the
actual probe module with `--preflight-only --check-states`; the second uses the
same source/manifest/expected SHA and records to an independent job/shard output.
The physical run refuses an existing output directory. It has no node binding.
The old stove523 launcher hardcodes the previous manifest and is not used.

For CPU-only verification of a registered complete snapshot:

```bash
cd /tmp
export PYTHONPATH="$STOVE552_SOURCE" LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -m scripts.probe_v5_stove521_endpoint \
  --source "$STOVE552_SOURCE" --manifest "$STOVE552_MANIFEST" \
  --expected-manifest-sha256 "$STOVE552_MANIFEST_SHA" --preflight-only --check-states \
  --preflight-report /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_fixed_prefix_CPU_20261006/registered_SOURCE555_preflight.json
```
