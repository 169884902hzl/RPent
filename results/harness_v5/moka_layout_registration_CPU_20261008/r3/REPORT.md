# Moka layout registration and CPU materializer

Actual state availability: explicit original90 pool200, after known selection/confirmation/reservation45, original Moka-On-compatible0. task18 has25, task20 has5, task21 has15 remaining. The stated76 cohort was not found. Only task19 original goal has Moka On stove; all its official states are already excluded. Other original tasks cannot be relabeled as that complete subtask.

Registered24 rules: original task19 bases seed0–23 are used only as generation bases (base_used=true). Cartesian grid x=-1.5/-0.5/+0.5/+1.5cm, y=-1.5/0/+1.5cm, yaw=-10/+10deg; only moka_pot_1 may transform. Furniture, BDDL goal, original instruction, target, other objects, initial robot qpos remain fixed. No result filtering or replacement. Original40 training init10–39 hashes (1200 identities) are explicitly excluded from future generated-state overlap checks.

Remote packet /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_registration_CPU_20261008/r3/

- manifest SHA 7cfd263126c0ba2db1d7e9b04ba57a4719d2cd83ae7da1593b36c7b1592adcf6
- rules24 SHA be85d6019c49ca2d19acb2c583ac592c9f7960e6cbc1533a7722c7bcaac6210b
- materializer SHA 243aa94bf8d9f34b9bf12f1639bc2dcb613a494dae3327d042f913387003666c
- CPU launcher SHA b246a2fe3b7fce9f7c0d80c36441dcfd584dc18e61a6a199e538e1e32b926fec
- reset adapter SHA 2e9514d87389b166850f5e68c3b53af6920b63cc439d478b757d5f847d00f3b3

Same-byte CPU_preflight_v2 exited0 with imports,24 generation base hashes, original asset hashes. No environment/physics in preflight. Materializer uses no renderer, GPU, SAM or model; fixed50 neutral/open controls per layout,1200 total. Requested resources4CPU/16GB/30min, estimate5–15min unmeasured. The parent owns submission. No job was submitted by this helper.

Each layout output will retain rawstate/fileSHA, base/source, exact restoration error, stabilization delta, geometry, and gaps. Collision or unintended displacement/hash overlap retains the declared record and does not choose a new transform. A prepared layout is not a skill confirmation result. Rawstate hashes contain time/velocity, so uniqueness does not establish different geometry or IID sampling; geometry must be checked from retained state evidence before claiming independent scenes.

Original goals:

- task18: put the frying pan on the stove; [["on", "chefmate_8_frypan_1", "flat_stove_1_cook_region"]]; BDDL SHA f54f8550e4058af1ed72aa0a0a41a4ae8d8d5cacbf453085130b0a279c7f8d55
- task19: put the moka pot on the stove; [["on", "moka_pot_1", "flat_stove_1_cook_region"]]; BDDL SHA d94a21d1fb32f76c08050242581c692486ae12956ae2de3dd96dd4d7d656fcd6
- task20: turn on the stove; [["turnon", "flat_stove_1"]]; BDDL SHA b081c85eec6ba5ede60bcb773e33cef284bd7befc96d4bbeeff48764d6fe16d6
- task21: turn on the stove and put the frying pan on it; [["turnon", "flat_stove_1"], ["on", "chefmate_8_frypan_1", "flat_stove_1_cook_region"]]; BDDL SHA f478f7d636e36ff4f6a689a43e01d9b9310429a7e3c5e7c397cbea766e81c125
