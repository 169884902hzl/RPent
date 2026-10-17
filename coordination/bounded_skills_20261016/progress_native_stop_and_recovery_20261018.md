# Original-scene bounded skills: recovery and native-stop accounting

All results are original-scene development simulation, with the private oracle selecting existing public options and pi0.5 disabled. No model task score, confirmation admission, training or real-robot result is claimed. Permanent confirmation exclusions remain effective.

|Source/job|Category and initial state|Native task result|Decisions|Control steps|Wall time|
|---|---|---:|---:|---:|---:|
|a8238d0 /8053_200|stove_on,libero_goal task7 init0|1/1|3|680|202.393s|
|627c861 /8056_181|stove_off,libero_90 task39 init1|1/1|9|1,001|434.420s|

The95% Wilson interval for either one-trial cohort is20.7–100.0%;neither establishes a category-level success rate. Old7812732/8040_200 stove_on and2ceec13/8046_181 stove_off failures on these respective initial states remain in the ledger. The stove_on repair changes public measured approach/posture ranking. The stove_off recovery explicitly selects open-gripper,then a screened4cm withdrawal,then a fresh measured approach and reclosure. It does not bypass collision/IK screening or raise force/budget/tolerance. These runs do not isolate each contributing change.

The older2ceec13 stove_off array is a distinct cohort. Its completed rows and denominator are updated in `reports/oracle_closed_progress_20261018.json`;a live partial count is never merged into the new source's1/1. Startup runs do not enter task denominators. The long plate8036_160 run also remains a separate,older source;its missing complete private snapshots prohibit claiming an exact physics replay from that record.

## Native-stop receipt correction

8053 reached public native task success before finishing its nominal wrist waypoint. Its historical receipt says failure/native_stop even though the episode succeeded. Source923cfae changes the single-action receipt to success/native_success when the environment reports native success;truncation alone does not qualify. Source6ddc6a1 stops blended and ordinary chunks at native termination and emits no receipts for unexecuted suffixes. Original raw receipts are retained. This is an execution/accounting correction,not a rescore of historical records.

Latest runtime snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_6ddc6a1_20261017`;archive SHA256 `d30bf5c6548a524957d7287934e507e04376d63694ad1d69306c19de01a994b4`.

Manifest: `/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/preparation/original20_manifest_6ddc6a1_calibrated.json`. Entrypoint `scripts.probe_bounded_feasibility:episode`;interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`. CPU manifest/state preflight passed before startup8058_0 was submitted. Actual control evidence is required before releasing this snapshot's continuation array.

Current source CPU validation:169 passed in53.27s for test_bounded_skills,test_bounded_payload,test_bounded_trajectory,test_skill_package_schema. One existing unknown pytest timeout-option warning remains. Prior627c861 focused140-test evidence and the newest169-test invocation overlap and must not be summed.

Canonical spec `SKILL_PACKAGE_SPEC.md` SHA256 `955922e4c05a6f1d309a9846902033ce58b810745088a067ead5d62093eb068e`;schema `rpent/skill_package/schema.json` SHA256 `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`. Candidate/message fields are unchanged by the native-stop correction. Shared FailureMemory627c861 retains anchored no-effect contact failures across unrelated entity drift;Codex2 was notified to sync the canonical helper/spec.

Resources follow the10/17 override:node02 only,aggregate Codex3 running GPU jobs at most3,all new submissions nice500. Protected c5/c6/rf and old held jobs are untouched;no running development job is cancelled. Queue evidence is in `reports/resource_latest_node02_cap3_20261018.{json,png}`. No actual model-service endpoint/latency is available in this thread;request-generation time is harness geometry cost,not decision-model compute. DevelopmentHistory remainsn=0/null until eligible development-only records are established.
