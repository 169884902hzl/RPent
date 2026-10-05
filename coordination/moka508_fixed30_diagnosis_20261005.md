# Codex3 CPU 回执：3620 摩卡壶固定每组前30条诊断（508）

在 2026-10-05 19:58:23–24 UTC（12:58 PT），显式读取 `grasp493_moka_comparison_20261005/full_job3620/part0/part1/part2` 三个 ledger，各固定最前30条完整换行；之后的29/19/30条不进入分析，不动态追读、不按成败筛选。90/90 `choices.jsonl` SHA匹配，真值全部已知。原 manifest SHA256 `df3a390cf94cca1e74d0aad4698b411ad495a5a938d2af0b4921d649aa9cba2c`，90条来自相同原版任务的前30个初始状态。只读探索分析，0物理动作、0模型调用、0训练行；所有原始标签与ledger保留。

|条件|真持续抓取成功|Wilson95%CI|TP/TN/FP/FN|原始视觉一致率|FP/真失败|FN/真成功|contact已执行/前置拒绝|
|---|---|---|---|---|---|---|---|
|reset + selected-only160|21/30 (70%)|52.1–83.3%|17/8/1/4|83.3%|1/9|4/21|30/0|
|overhead + selected-only160|12/30 (40%)|24.6–57.7%|3/18/0/9|70.0%|0/18|9/12|30/0|
|measured handle + selected-only160|3/30 (10%)|3.5–25.6%|2/26/1/1|93.3%|1/27|1/3|16/14|

14次handle前置拒绝全部是 `visible_handle_not_measured`，无contact提示词/块/动作，不当作π0.5执行失败；完整方法分母仍30，不删前置失败。三个方法contact实际调用的提示词均为 `pick up the moka pot`，不再含完整任务的放置语义。探索前缀不能触发确认或冻结；旧方法C的FN13/50与当前reset FN4/21只是描述性的变化，完整提示词、验证器和分母不同，不能宣称配对改进。

## 14个视觉FN的直接证据

- reset的4个FN全部两个验证帧无当前可见测量，最终保存 `perception_cached`；overhead的9个FN中5个双帧缺测、3个单帧缺测、1个在开度门限处未进入验证；handle的1个FN也在开度门限处未进入验证。总计12个缺测、2个开度前置拒绝，不改为物理失败。
- reset `libero_10/t2/s25`：主视角有当前检测，下界上升13.43cm，eef y=-7.311cm；测量包围盒下界y=-2.266cm，+/-4cm门限仍差约1.05cm。公开gripper-volume检查失败后切到腕视角，腕视角缺测把记录变成cached。说明需要审查朝向相关的夹爪体积和独立记录两个视角；不能根据此局后验加宽门限。
- overhead `s14` 的π0.5 final opening=7.936cm、handle `s10`=7.682cm，超过7cm；没有两帧验证。但最终0.5秒私有持续真值为真，最低碰撞净空分别3.017cm、7.335cm。保留原视觉false，不把contact budget stop与物理失败混同。
- 本批14个FN没有“当前可见下界漂移不足3cm”首因。缺测并不证明遮挡，源图像/掩码未在本CPU任务检查；不得把它们全部归为遮挡。旧3565“第一帧可见表面下界不稳”的证据仍保留，不能套用于新批。

## 2个视觉FP

reset `s20` 两帧下界分别升3.662/3.857cm而最低碰撞净空只有2.868cm；FP对应真实最低几何条件不足。handle `s3` 两帧公开通过，但0.5秒私有保持最后0.1秒失去手指支撑；不能据晚于视觉帧的保持记录倒推“试抬造成失持”。本批没有阶段性私有快照，因果定位仍未知。

通用建议仅用于后续独立开发：保存主/腕视角各自当前证据，缺测fallback不覆盖先前当前检测；真正双视角缺测时用测量恢复重新获取，不用cached位置验证lift；检查夹爪朝向下的测量接触体积；继续保留两帧稳定判据。未改runtime、配方、标注或冻结标准。

## 产物身份与实际命令

远端根目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka508_fixed30_diagnosis_20261005/`，同路径相对部分已同步本机。

- `report/summary.json` SHA256 `8e33495c91b480774ef094687b60106465141b76b6ccafd4f23ed750ed3cc4fe`。
- `report/trials.jsonl` SHA256 `f2a4573bc618ddb071b4cbbb70e7714bdd054c0bfc9a34d166cea054ad07755a`。
- `geometry_v2/geometry_summary.json` SHA256 `a96309715cc15488e0a87c369731e137168aab39caa787fe266c391194568776`。
- `geometry_v2/geometry_trials.jsonl` SHA256 `83b07abf225a993c09f3045f291d43206a882c04ad361a1bdd4719bc683e3a9c`。
- 原始固定prefix SHA：part0 `2f1883945b85b4391b58f61179c9a1065058e6cef770147d3fe0cb97caecdea4`；part1 `d641b48db7d8529f2df17b2ebfbad8784b05f5000fd04a6662b5e8967b0daee5`；part2 `f5ae13f9a5a6bfae4f01097d9506e4b96b950ea12f5a61831a0777070dd5fba5`。
- 补充诊断脚本 `scripts/diagnose_v5_moka508_fixed30.py` SHA256 `7760ade03fe8e3993fee50475441cc3af32e93ad0b316bd002f3f0eba840901f`。

实际CPU命令在5880执行，均exit0：

```bash
.venv/bin/python scripts/diagnose_v5_grasp494_prefix.py \
 --ledger results/harness_v5/grasp493_moka_comparison_20261005/full_job3620/part0/episodes.jsonl \
 --ledger results/harness_v5/grasp493_moka_comparison_20261005/full_job3620/part1/episodes.jsonl \
 --ledger results/harness_v5/grasp493_moka_comparison_20261005/full_job3620/part2/episodes.jsonl \
 --prefix-rows 30 --expected-per-arm 100 \
 --output results/harness_v5/moka508_fixed30_diagnosis_20261005
.venv/bin/python scripts/diagnose_v5_moka508_fixed30.py \
 --fixed-summary results/harness_v5/moka508_fixed30_diagnosis_20261005/report/summary.json \
 --previous-summary results/harness_v5/grasp491_moka_CPU_20261005/report_v2/summary.json \
 --output results/harness_v5/moka508_fixed30_diagnosis_20261005/geometry_v2
```

最初的 `geometry/` 草稿保留；v2把“两个view缺测”的用词修成“两个验证frame缺测”，不改变任何统计或数据。主代理统一写共享COORD、推送；子代理未提交Slurm。
