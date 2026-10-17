# Sparse measured-instance boundary development

Source `cee33e8` is pushed on `user-fork/harness-v5`. Sparse tangent-supported holes are completed only inside the clean current RGB-D mask extent. Original 4 mm collision clearance, robot filtering and object/obstacle separation remain active. Model request and schema are unchanged.

The saved original object task0/init0, capture5 was reconstructed through the production instance pipeline using original SAM masks, both RGB-D views, proprioception and static hand/arm geometry. The old reconstruction exactly reproduces the saved170,671 obstacle/4,434 target counts. The new reconstruction has170,668/4,437. The strong `s0_a0_side_1_orient_at_pregrasp` candidate passes the actual smooth route and closure after two isolated edge pixels regain target membership; it previously failed closure. The executed lower-quality `s7_a0_oblique_-1` remains feasible. This is CPU geometry evidence, not a physical success.

Public crops were inspected. Yellow additions follow the soup-can outline;20 main-view and34 wrist-view additions below1mm lie around its lower rim. This visual review does not provide a private mask label or establish zero background contamination. Extent and local surface checks remain necessary.

Tests before commit:163 passed in72.72s,one existing pytest timeout-config warning. Scoped Ruff(ignoreCPY001) and diff check pass. Full details are in `reports/sparse_instance_cee33e8_delivery_20261018.json`.

Same immutable source/launcher startup8110_20 completed280 physical controls. Full box init0 is8111_20;remaining19 states8112 wait after it. Bowl11a73af init2 is8108_2,with8109 remaining19;contact1fde995 is8103. Three serial channels remain onnode02,Nice500,aggregateGPU<=3;node01/protected/held jobs unchanged. All states are original-scene development only;no training,PRO input,confirmation reuse or rescoring.
