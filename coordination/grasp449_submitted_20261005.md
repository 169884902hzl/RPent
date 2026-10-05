# Codex3: grasp comparison submitted

Source commit `6571414` pushed on `harness-v5`. Pre-submission reservation and
accepted terms were written to remote COORDINATION and pushed first.

- 3434_0/1: RUNNING on node01, 48-case startup probe. Actual command:
  `sbatch --parsable --dependency=afterany:3428 scripts/run_v5_grasp449_smoke.sbatch`.
- 3436: full original-task comparison, 2,400 planned first attempts, 24 shards
  with concurrency two. Actual command:
  `sbatch --parsable --dependency=afterok:3434 scripts/run_v5_grasp449_full.sbatch`.
- Working source directory:
  `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp449_20261005`.
- Outputs:
  `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp449_original_paired_20261005/smoke_job3434/`
  and `full_job3436/` under the same root.
- Probe script SHA256:
  `96fb5f82a96f8615c05fee52ad6b776845de16c54601c64150da75008747bc71`.
- Smoke launcher SHA256:
  `2d2abe15f93dcab403a7b4487987e9ff7f943a8c0a71138466622a23be982da1`.
- Full launcher SHA256:
  `ecc37b34050e036a88d4de40dcd6697dd981e76fd2147451a633ce762102c05e`.
- Verifier SHA256:
  `753b8604c0955eeb1e5e4fa21e0c1747fdc390509a9bdac54f2dad5058e36e6f`.
- Candidate/serializer SHA256:
  `eead76264f8a8543e3f7e8ff8ead457208dbf6b4015445442f1f0dabbf855fb6`.

3428_0/1 both COMPLETED 0:0 (36:05 and 35:15). All 72 registered prefixes are
preserved. This establishes executable diagnostic coverage, not model scores
or causality by itself. The original expert, development, and failed 3423
records are unchanged. Behavior freeze remains blocked pending grasp selection
and repaired A3/A4 closed-loop validation.
