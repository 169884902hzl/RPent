# Expert matching-subtask development probe 4603

This is a development probe of the new `OriginalOraclePolicy` snapshot. It is
not part of the legal-r2 200-episode ledger, confirmation, training, or final
evaluation. The source snapshot was built from commit
`b0371be55d01e6cbce1fd5162784a3abccaf4447` and the same launcher used for the
expert queue. CPU preflight passed before the real startup episode.

Job `4603_0` completed `0:0` on node02. The explicit visited original identity
`libero_object/task8/init0` made a real physical request and completed with
official success in 48.098 s. Fusion was enabled. Its choices were
`grasp(e54,direct)` followed by `place(e54,e114,in)`; the matching
`vla_subtask` candidate was present in the source policy but was not selected in
this episode. Therefore this run validates startup and execution, not macro
selection rate.

The original 200-episode result remains unchanged: 171/200 physical success
under legal-r2. The six program-error retries remain separately marked. This
probe has no admission to that denominator.

Manifest:
`/public/home/sunyihan/rpent_libero_eval/coordination/expert_subtask_probe_20261008/manifest/manifest.json`
SHA256 `65c106b3e46cf9ac0f591fc1a98a7f1cf205c0963c853278de36be73460d5cec`.
Episode ledger:
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/expert/job4603/part0/probe/episodes.jsonl`.
The full startup contract is in the corresponding `startup_preflight/job4595`
directory; no formal follow-up shard was submitted because this probe's purpose
was startup/execution coverage only.
