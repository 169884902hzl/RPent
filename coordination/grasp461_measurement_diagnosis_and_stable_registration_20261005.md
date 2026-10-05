# Codex3: saved visual diagnosis and next independent grasp probe

Accepted the user's03:10 grasp standard: physical truth for sustained lifted
grasp, overall>=95%, every class>=90%, at least100 first trials/class/condition,
class Wilson95%CI and runtime-verifier agreement>=95% with both error directions.
No thresholds were lowered. Private truth never controls runtime actions.

3550_0/_1 are running without node binding;3554 waits for the full array.
3550 fixed source115ba66 is unchanged. The current two shards cover bottle
only, not the full six-class result. Formal qualification remains unfinished.

CPU diagnosis consumed exactly90 saved original-task first trials from
3491/3520/3545, verifying every choices.jsonl hash against its ledger. No new
physics, no GPU, no training rows. Report:
`results/harness_v5/grasp461_saved_measurements_CPU_20261005/report_v2.json`,
SHA256 `7abb18f551a835a998e2fe69b391bdbb60dd04cf2eebcdfd2c1a1ef0e5508c67`.
Original report.json remains retained;v2 only gives the2mm post-frame
hypothesis an accurate label rather than implying a receipt-time discrepancy.

| Saved/retrospective verifier | TP | TN | FP | FN | Agreement |
|---|---:|---:|---:|---:|---:|
| Recorded runtime receipt |54|30|3|3|93.33%|
| Post-frame centre rise,2mm aperture |55|30|3|2|94.44%|
| Post-frame lower rise,2mm aperture |55|31|2|2|95.56%|

Recorded false-positive rate3/33=9.09%;false-negative rate3/57=5.26%.
Three false positives:two later drops/loss of support and one rotated frypan
whose centre rises5.03cm but measured lower surface rises2.73cm and true
minimum clearance is1.71cm. Three false negatives:two visually missed moka
pots and one true thin bowl grip below the old5mm aperture cutoff.
Across33 physical failures:28 no final lift/hold,2 lost sustained support,
2 finger contact without sufficient clearance,1 clearance without support.
The single post-frame lower-bound comparison is retrospective and still
misses later drops;95.56% is not a physical qualification claim.

Independent probe implemented in
`scripts/probe_v5_grasp449_20261005.py::rpent_pick_then_stable_measure`:
public RPent stop ->5cm trial lift ->two fresh visual lower-bound measurements
separated by10 close/hold steps at registered20Hz;one wrist-view query when
main-view measurement is absent. No private contact/pose or BDDL is consumed
by the helper. Missing/old visual frames stay negative. Default runtime,
renderer, active3550 source and existing receipts remain unchanged.
24 relevant binding/measurement/truth tests passed. Physical execution is
pending. If adopted into runtime later, receipt changes must be delivered
to Codex1/2 for training rerender;nothing is frozen or admitted here.

Pre-submit registration:12-case smoke,2 approach families x6 classes, original
init0. Full1200-case registry prepared but not submitted. Neither added trial
lift/verification, alias nor larger budget counts as another genuinely
distinct physical approach method. Five formal failed methods are not yet
complete;no user stop threshold is claimed. Diagnostic init0-49 are excluded
from training, including10-39;no PRO/Jev/human/sealed-test inputs.

Source snapshot `source_v5_grasp462_stable_measure_20261005`,commit7e3bf5d;
archive SHA256 `0e0ff17697da07f439c7bc048d7b3c1a66b3dbe78765b6f50e67d5599bb82851`.
Smoke manifest SHA256
`258d6aaf71cefb96bbe6abaae7f8904e5e3ab312b4ee3fc61d15c44f735eca49`;
full prepared manifest SHA256
`768b1e0c80d7d9711aa73fc7e5ccd5754b00a20f9cee47f7fba9dc2060d18eae`.
Planned command after this receipt is pushed and appended to shared COORD:
`sbatch --parsable --dependency=afterany:3550 runtime_launchers/run_v5_grasp462_stable_measure.sbatch`.
Assigned ID is not yet available and will be recorded immediately. Output
`results/harness_v5/grasp462_stable_measure_20261005/smoke_job<ID>/`;
1GPU/8CPU/90GB,nice1000,no node binding. Wait for the entire existing array
to preserve the two-GPU limit;do not cancel/resubmit3550 or3554.
