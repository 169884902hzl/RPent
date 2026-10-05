# Codex3: register public-stop and thin-rim physical comparisons

Read the latest user95% grasp criterion and live3491/3503 evidence. Accepted
unchanged3cm support clearance, continuous0.5s holding,100 first attempts per
class/condition,95% overall success,90% minimum class success,95% visual/truth
agreement and separate false-positive/negative reporting. No objection or
standard change. This is original-task diagnosis only, not training data.

Optional `grasp_thin_aperture_v1` tests a2mm nonempty aperture instead of5mm.
Six empty closure controls settle below1.193mm; the true lifted thin bowl
measured4.9mm. Visual3cm rise remains required. Defaults are unchanged. All
related held-aperture checks use the same boundary. **Codex1/Codex2 notice:**
this switch changes verifier semantics; it is not frozen/admitted, and training
receipts must be rerendered if it is later adopted. No new state lines/fields.

Four conditions: current direct visual-stop80; overhead short visual-stop160;
overhead short RPent public descent/ascent-stop160; initial-pose/full-instruction
RPent public-stop160. Every public-stop result still goes through the visual
verifier; simulator truth never controls the contact policy or stop. Budget
variants and identical clamped approach heights do not count as different
methods. First launch is24 cases, one per class/condition, an instrument smoke.
Registered full cohort2400 cases is prepared, not yet submitted/executed.
One-task moka/frypan classes repeat50 reset states twice; uniqueness and
nominal Wilson interpretation remain disclosed.

Independent source:
`/public/home/sunyihan/rpent_libero_eval/source_v5_grasp458_stop_20261005/`,
commit `4571752`, archive SHA256
`2e9fe18a4603569a85967b8eb8bb8b707b674f2838ab33438a2a1b85dd7829c5`.
Preparation:
`results/harness_v5/grasp458_stop_aperture_20261005/preparation/`.
Smoke SHA256 `643c3e90f8bcdc8b983c006a5635c35e58897410fb9f0ef56d7b2a3d9cbfc21b`;
full SHA256 `9da8be3adcf57b655d2842cdb0802af4af6880590a0fab6d0e8752b2bd2c6b65`.
150 focused binding/verifier/runtime/truth/state tests passed. Also fixed the
offline failure classifier to read `failure_reason`, retaining raw receipts.

Pre-submit reservation1GPU/8CPU/90GB/2h/nice1000/no node bindings,
afterok3491. Planned command:
`sbatch --parsable --dependency=afterok:3491 runtime_launchers/run_v5_grasp458_stop_aperture.sbatch`.
Output `results/harness_v5/grasp458_stop_aperture_20261005/smoke_job<newid>/`.
Allocated ID will be appended immediately. Keep old3436 at throttle1 while
the new probe uses the second GPU. Hold only pending resource helper3493,
retarget that same helper to afterany:newprobe and release it; do not duplicate
the helper or modify any trial source/record. Thus total owned GPUs stays<=2,
then3436 concurrency automatically returns to2 after this probe. No A3/A4
qualification rerun or behavior freeze before the user's gates pass.
