# Microwave observation-pose development result

Job4500 completed `0:0` in 7m09; episode wall clock 422.66s. Same visited original LIBERO-90 task33/init0, eight contact blocks, immutable source584 plus the explicitly indexed observation-pose overlays. This is a development case, not qualification or a confirmation trial.

All nine observation moves reached their measured waypoints according to actual EEF sensors. Both independent public planes were measured in all 18 fresh verification frames; all nine pairs were usable and all 18 frames had measured `occluded=false`. All contributing planes came from agentview. Wrist contribution remained zero: successful translation does not establish that the wrist sees either plane.

In the wrist records, the fixed-frame SAM query returned zero instances in all 18 frames. The door query returned zero instances in 13 frames. Five frames had door instances but lacked an independent fixed patch, so the existing filter rejected them rather than assigning an angle from unsupported evidence.

The door was already open before contact and remained at private diagnostic joint angle −1.501553261371256. All eight post-action pairs reported an open endpoint, but none observed the requested opening direction. This run therefore establishes capture availability, not successful opening. The legacy per-action receipt says `verified`; the unchanged door and `no_effect` must be reported alongside it.

The ledger records 80 requested/executed π0.5 controls, including setup. Original raw ledger, manifest and relevant immutable code identities are pinned in `manifest.json`. `records.json.gz` retains the collected public records and post-execution private labels; `diagnosis.json` gives per-pair actual waypoint errors and per-camera availability. Private labels did not select motion or stops.

Next comparison disables the active block callback for the same source584, task33/init0 and 40-block close case from job4497. The new opt-in callback probes public RGB-D without controls until a provisional endpoint triggers withdrawal and two fresh stable verification frames.
