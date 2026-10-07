# Microwave block callback without routine contact interruption

The default remains off. With `microwave_readonly_probe_v1=true`, the fixed baseline captures two public frames with the actual 0.3s neutral-hold interval before contact, without release, withdrawal or observation repositioning. Missing baseline evidence stays missing.

After each contact block, the callback only captures current RGB-D and robot sensors. It sends no release, move or hold controls. A unique, independent measured frame/door plane pair reaching the existing 30° open / 15° close angle threshold is only a provisional candidate. It triggers the existing withdrawal and two fresh frames with the real 0.3s interval; only the complete unchanged temporal validator can authorize stopping. An occluded provisional view may trigger confirmation but cannot authorize a stop. Unknown measurements do not trigger withdrawal or stopping. Private joint labels do not affect candidates or commands.

`e8c7fab` contains the opt-in behavior. `9306a46` prepares an immutable copy of the explicitly indexed source584 files. The copied runtime gains only its two constructor/assignment flag lines; it does not absorb the unrelated live runtime. The capture overlay also contains the earlier observation-pose implementation, whose switch stays off for this comparison. All verifier thresholds, state, 40-block budget and post-skill behavior match job4497.

Offline capture/temporal tests: 69 passed. Same snapshot/launcher remote CPU preflight: exit0, 29 explicit inputs, one state hash. This proves import/configuration and input integrity; physical startup and effectiveness are still pending. The parent agent owns GPU submission.

Exact source, manifest, hashes, launcher and fresh output are recorded in `handoff.json`; the overlay bytes are in `overlay_packet.json`. These are visited-original development comparisons, excluded from training and qualification.
