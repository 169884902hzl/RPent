# 技能层开合/放置确认批实际提交（2026-10-05）

先写入提交前回执，再提交两个无依赖、无节点绑定数组。已有 3670/3684/3685 未修改。

| 组 | Job | 实际命令 | 输出目录 |
|---|---:|---|---|
| articulate | 3687 | `SKILL535_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_skill535_articulate_place_20261005 SKILL535_ARTICULATE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill535_articulate_place_confirmation_20261005/preparation/fixtures.json SKILL535_ARTICULATE_MANIFEST_SHA=ffb890d894609f3046e88832a33189053a50bb66c6ca333aca6c4c6d98585645 SKILL535_PROBE_SHA=15778e26c767bba2c70fd7cf766caef42410061e79b87211a6de5478c45186b6 sbatch --parsable scripts/run_v5_skill535_articulate_confirmation.sbatch` | `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill535_articulate_confirmation_20261005/job3687/part0..7` |
| place | 3686 | `SKILL535_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_skill535_articulate_place_20261005 SKILL535_PLACE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill535_articulate_place_confirmation_20261005/preparation/place.json SKILL535_PLACE_MANIFEST_SHA=d9c39247883a38e8587364e0bd9c9d73a87f720f866bea7e70c767077c53dc35 SKILL535_PROBE_SHA=15778e26c767bba2c70fd7cf766caef42410061e79b87211a6de5478c45186b6 sbatch --parsable scripts/run_v5_skill535_place_confirmation.sbatch` | `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill535_place_confirmation_20261005/job3686/part0..7` |

两个数组均 `array=0-7%8`、1 GPU/片、无依赖、无 ReqNodeList/ExcNodeList。确认批不入训、不授权资格。清单 SHA：fixtures `ffb890d894609f3046e88832a33189053a50bb66c6ca333aca6c4c6d98585645`，place `d9c39247883a38e8587364e0bd9c9d73a87f720f866bea7e70c767077c53dc35`；probe `15778e26c767bba2c70fd7cf766caef42410061e79b87211a6de5478c45186b6`；生成器 `1666548a9437b7a5b145bcc658c2c7be92306d9c39b4ee858e455893ffb85099db44`。

远端源码快照关键 SHA：`harness_v5_eval.py` `462ca6acf6dd494232d42fa89839bb99fe32aa66c94143f336bb8f845d6914d4`；`robots/libero/v5_runtime.py` `6233b59871771c348f113cf1411d0a2931430da3e0704ca43ea3bb69015e1d4a`；`v5_state.py` `f3c1790bb3ba92e6376b2f5591fff81a53f09831468f250618d3802e93d01e68`；`v5_action_effect.py` `d287adde7f317f994e05a0aa256d3df4c22e808a3366ce27188a3a880d84f0ef`；`v5_recovery.py` `5cac3bc47639cfac3b13931c94ca9bee269a123a7f0c639556f054a57c00ace1`。
