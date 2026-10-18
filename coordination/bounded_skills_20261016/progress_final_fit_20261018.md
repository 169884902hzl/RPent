# Final-iterate payload registration

1. Sourcee5bbb18 fixes premature ICP rejection: limits apply to the returned fit after optimization, with the original0.1rad/15mm bounds unchanged.
2. Saved-public CPU checks recover all four blocking pixels in bowlinit16/19:32previously rejected poses and24full nudge routes now pass. Exactly12current pixels are added; none are removed. All12are bowl pixels in a separate CPU diagnostic.
3. Adapter/payload tests pass241cases; the payload rerun including the new numeric regression passes34cases. Those sets overlap. Changed production/test Ruff passes; the wall-summary script retains four existing lint findings.
4. Source87ef92e targeted physical pairs10/14 are closed,4/4arms successful. Init10 remains slower with more simulation steps under the new chunk rule. Microwave9209fails both arms. These are retained development records.
5. Sourcee5bbb18 startup9213_16 completed with168controls, and paired16/19replays run as9214. Original oracle category coverage remains incomplete; no training, confirmation admission or behavior freeze is claimed.

## Supported root cause

For9026_16,row2 the second ICP proposal reaches0.11943rad and is rejected immediately. Continuing the identical numerical fit for its existing30iterations returns0.09570rad, maximum surface displacement12.241mm and median residual0.550mm instead of4.116mm. For9026_19,row5 the second proposal reaches0.10679rad; the returned fit is0.09940rad/12.985mm with median residual0.542mm instead of3.380mm. The algorithm never exposes an intermediate transform as accepted membership. Final excessive rotation/displacement, missing overlap and unimproved fits still return the original prediction.

This fixes an optimizer stopping condition. It changes no collision clearance, depth connection, stationary-scene veto, force, robot limit, success threshold or seed identity. The returned transformation still owns only current measured pixels with the existing association and static-scene tests.

The saved CPU screen comparison reuses the exact recorded guided masks. Init16adds3pixels andinit19adds9pixels, with no removed pixels. Four originally blocking points become members; all16recorded rejected poses and12full nudge routes per state pass. The independent simulator-restoration diagnostic identifies all12additions as `akita_black_bowl_1_g0`, with zero state-restore error and zero controls. Those private identities are diagnostic evidence and never runtime inputs or training rows.

Evidence: `reports/9026_registration_path_CPU_20261018.json`, `reports/9026_16_final_fit_screens_CPU_20261018.json`, `reports/9026_19_final_fit_screens_CPU_20261018.json`, `reports/9026_final_fit_added_pixels_CPU_20261018.json`, `reports/final_fit_CPU_validation_20261018.json`.

Other hypotheses remain explicit. Disabling transparent robot sites changes neither depth nor RGB at these captures: whole-image RGB differences are zero. Existing circular-section fits do not explain allinit17/19points and were not deployed. Private saved-state diagnostics measure relative bowl/finger motion of7.617/8.258mm and0.195/0.177rad; they do not supply a runtime correction. Init17fails before lift and is not fixed by the held-payload registration change.

## Wall-time accounting and current interface

The wall-time summarizer previously asserted `an instrumented category is missing` on the new private-label-capture timer. It now reports that timer separately. All six closed arms9211and9209are summarized with exclusive buckets that sum to their measured wall time; no planning/perception timing is backfilled. See `reports/wall_payload_interval_pair_20261018.md`. Label capture costs12.950–107.839s across these episodes and must not be mistaken for oracle selection, planning or perception.

The requested function profile and CPU arbitrary-prefix interface remain in `progress_1005_offline_labels_20261018.md`. Two actual measured contexts match all7onlineoracle positions and support2nonoracle prefixes. Codex2 has wired the interface; its older26model requests lack the matching measured annotation contexts, so their59unknown positions remain unsupported. No state substitution or oracle-path label substitution is used. Candidate order remains nonsemantic; source detailed history remains the last3receipts.

Public versions are unchanged: bounded-skills/3 and public-request-legal/2. Schema SHA `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`; contract SHA `7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c`.

Sourcee5bbb18 is pushed to harness-v5. Archive SHA `cd2f0d661c0ae61f39a11a843667824c7122daa36ed67a2f2d86b3d9f7eb5900`. Snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_final_fit_20261018_e5bbb18`. Entry: `scripts.probe_bounded_feasibility:episode`; interpreter: `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`. Full task validation remains pending. COORDINATION append receipt: `reports/coord_final_fit_append_20261018.json`.
