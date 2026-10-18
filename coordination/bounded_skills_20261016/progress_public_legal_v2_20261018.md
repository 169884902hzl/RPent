# Shared public prefix legality /2

Codex1 / Codex2: contract, oracle labels and model decoding must use `contract.legal_after(request, prefix)` from the same source snapshot. `/1` draft is superseded; old records are preserved and require label regeneration before training. No training is started.

Wire shape remains `bounded-skills/3`; legality is `public-request-legal/2`, private judge `/6`. Known frozen collision/IK blockers are excluded; conditional carry/lower use only published held postconditions or the public held state. Opening/release clears holding. No planner, private goal or new observation is called.

CPU: 268 integrated tests passed (one existing pytest timeout-option warning); Codex2 bridge 25 tests and 20 subtests passed. Audit: 26 LIBERO requests /48 positions and 415 MuJoCo requests /775 positions, selected and acceptable outside legal =0, illegal prefixes=0. Mean helper time 0.1815 ms LIBERO, 0.07075 ms MuJoCo. 17 LIBERO denominators change from /1; MuJoCo changes=0. Raw rows unchanged.

Source identities:

- `rpent/skill_package/schema.json`: `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`
- `rpent/skill_package/contract.py`: `7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c`
- `robots/libero/bounded_oracle.py`: `18eecb231f1483e72959b482fd6f2ed254fc82882e64a7712eec3a40e68498d1`
- `SKILL_PACKAGE_SPEC.md`: `a3c95dc309c14c569cafe5acb5a7868d86e3c1a00ee832b2e84fff6800bad558`

Physical 9001 remains pinned to 4335578 and does not validate this new legality version. A fresh snapshot/startup is required for current three-end physical results.

Artifacts: `reports/public_legal_v2_saved_CPU_20261018.json`, `reports/public_legal_v2_integrated_CPU_tests_20261018.log`, `reports/public_legal_v2_Codex2_bridge_CPU_tests_20261018.log`.
