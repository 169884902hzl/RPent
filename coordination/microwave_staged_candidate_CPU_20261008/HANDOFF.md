# 微波炉跨真实动作块候选门控：开发交接

修复 job4516 第36块只有一帧近终点测量就撤离的问题。`microwave_staged_candidate_v1` 默认关闭，只在新比较配置中开启。非终点或当前平面缺测会清空候选序列；只有连续候选跨真实接触 controls ≥0.3s，固定框满足原10°/10mm稳定条件、门满足原3°/10mm稳定条件时才撤离。撤离后仍须原两帧完整验证器通过才允许stop；没有新增真值控制或放宽阈值。

- 代码：`faf15d1`；CPU包/复算：`1703fe1`。
- 91项聚焦CPU测试通过。用 `.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_v5_microwave_capture.py tests/unit_tests/robots/libero/test_v5_microwave_door_temporal.py tests/unit_tests/robots/libero/test_v5_microwave_wrist_roi.py`。
- `recompute4516.json`：block36，180个实际controls，公开angle14.896°，只有一候选；新门控返回 `waiting_more_public_candidates`，withdraw/stop均false。block36之后的原记录已受旧withdraw干预，不能作为新物理轨迹的预测。
- 4516的失败与完整轨迹保留于 `coordination/microwave4516_wrist_roi_close_CPU_20261008/`。

## GPU5880包

- SOURCE `/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_staged_candidate_20261008`
- identity `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_staged_candidate_CPU_20261008/r1/source_identity.json`，SHA `d60edd2ae9c32b5df07277b6186d4b2fd4dd6cb6fa2b868b405bdc918fe5b6eb`
- PLAN `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_staged_candidate_CPU_20261008/r1/close_staged_candidate40.json`，SHA `d1fa1324891f2aa61345ceb0976874f1d8c7017a743866d59f3e7ace0ea64a5f`
- OUTPUT `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_staged_candidate_original_20261008/close40`
- launcher `SOURCE/coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch`，SHA `8cba334fa65b15d906b8c5cda055c5599804602d127131fd7e33c0935ad0d2bf`
- 解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`

643文件来自4516显式642文件索引加新prep；只有capture、runtime两行开关和prep改变，没有叠live runtime或moving-target改动。同launcher CPU预检exit0，snapshot实际import及开关constructor通过；未由子代理提交GPU作业。本状态是已用原版LIBERO90 task33/init0的开发复查，不是确认批，不进训练。原有40块×5 controls预算、ROI、只读采样和验证阈值保持一致。未收集政策输入张量/噪声哈希；新run首动作若不同，不能作单项因果推断。

父代理登记GPU后，用上述路径export `MICROWAVE_SOURCE`、`MICROWAVE_PLAN`、`MICROWAVE_PLAN_SHA`、`MICROWAVE_OUTPUT`，`MICROWAVE_CPU_ONLY=0`，提交同launcher单局。只在真实物理请求已产生后放后续批；startup/infrastructure错误必须非零退出。
