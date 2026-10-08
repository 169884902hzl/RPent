# Stove contact unload development result

The new default-off `stove_contact_unload_v1` runtime switch removes residual
finger contact by opening while lifting for 20 controls, then holding open for
40 controls. It does not infer or declare endpoint success. Code commit
`a0d342b`; 12 focused tests passed. Articulate and vla_subtask use the same
unload method. Existing legal-r2 model/comparator jobs do not enable it.

Evidence uses one previously visited original Goal task7/init2 only. Exactly
900 prefix controls and 180 public checkpoints were replayed. Fixed suffixes
were selected before simulation: release alone did not retain off; release
while lifting/backing/diagonal withdrawal and release before withdrawal did;
closed-gripper lift before release rolled back. This is correlated development
evidence, not a confirmation rate or qualification.

The actual `V5Executor.clear_stove_contact` method was then executed against
real ControlEnv.step on the same prefix. It requested and executed 60 controls,
ended off and stayed off through the final 20 controls. Measured end-effector
displacement was 7.34 cm; gripper opening changed from 2.82 to 7.97 cm. Private
joint labels were logged passively and never selected actions or stopping.
Endpoint verification remains null until public measurements support it.

- Snapshot: `/public/home/sunyihan/rpent_libero_eval/source_v5_stove_unload_runtime_a0_20261008`.
- Source identity: `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove_unload_runtime_CPU_20261008/source_preparation_a0/source_identity.json`.
- Physical manifest: `/public/home/sunyihan/rpent_libero_eval/coordination/stove_hold_dynamics_CPU_20261008/runtime_unload_a0_r1/manifest.json`.
- Manifest SHA256: `318fd558df996f6ae3a2cbe474d0b8542f367010bc0fcbec9814479f5811236b`.
- Public controls SHA256: `ed159b45baf7a01a625c3538b70a6ab083f9d6dc0feddec114f2ac1db7083933`.
- Private labels SHA256: `8263f7fe06b2e6fb155f8c48eae71b7eee2da2ae616ce7efd6b1dcdd4d7613ae`.

No confirmation states, PRO input, training rows or final evaluation were used.
Next validate the public endpoint/withdrawal path on visited original states,
including turn-on; independent confirmation remains pending. All thresholds
are internal acceptance criteria.
