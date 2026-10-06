# Stove off 语义修复与原版控制测量

`measured_stove_rgbd/4-off-endpoint-unmeasured-dev` 保留两帧稳定变暗的 `visual_transition` 测量事实，但在没有独立的控制关断端点证据时返回 `None`、`state=unmeasured`。不把缺失测量算作失败；明确仍红时的负判定和 turn_on 正判定保持不变，所有测量阈值不变。

原版 `FlatStove.turn_off` 要求严格 `qpos < 0`，炉圈显示红色仅要求 `qpos >= 0.5`。因此 `0 <= qpos < 0.5` 可同时满足“视觉变暗”与“官方未关断”。原版源码、行号和三条历史误报的出处保存在 `stove544_endpoint_semantics_CPU_20261006/report.json`；本包不修改历史判定。

## 精确回归

`recorded_public_cases.json.gz` 保存 4128 三条误报的完整原始公共 stove RGB-D packet，以及原 trace 路径/SHA、旧公共判定和私有诊断标签。回归验证器只收到公共 packet，不收到关节值或私有谓词。

| 原版 case | 原私有标签 | 旧 v3 重放 | 新 v4 重放 |
| --- | --- | --- | --- |
| LIBERO-90 task39 seed12 | false | true | unmeasured |
| LIBERO-90 task39 seed16 | false | true | unmeasured |
| LIBERO-90 task39 seed9 | false | true | unmeasured |

`cpu_regression_report.json` 记录逐例结果、旧 SOURCE550 源码身份、新源码 SHA 和 focused 测试命令。49 项 CPU 检查通过，只证明这个验证语义与调用层回归修复，不赋予 turn_off 技能任何物理资格，也不证明 ≥95% 的技能成功率或验证器一致率。

```bash
.venv/bin/python -m pytest -q \
  tests/unit_tests/robots/libero/test_v5_stove_measurement.py \
  tests/unit_tests/robots/libero/test_v5_stove_endpoint_receipt.py \
  tests/unit_tests/robots/libero/test_v5_stove_control_approach.py
```

## 控制方向证据与最小接线

`assess_recorded_control.py` 只按原版 3679 的已登记 manifest、4 个显式 ledger 和其公共观测/标签/点云引用读取。结果为 60 观测、120 视角：114 视角没有控制候选，9 个候选拟合中 4 个离当前测量炉体过远被拒；5 个受支持控制面均来自动作后公共恢复的腕部视角，主视角为 0，双视角唯一控制配对为 0。60 个私有诊断 off 标签全为 false。详见 `control3679_assessment.json` 和 `control3679_rootcauses.json`。

5 个可测切向角在 105.58–118.03°；与私有诊断关节角在这段 on 区间呈线性对应，斜率 1.006、最大残差约 0.07°。其中 4 个样本几乎重复，且没有 true-off 或近零 intermediate-dark 样本。这是方向特征有潜力的开发证据，不能外推为端点测量或运行时角度阈值。SOURCE544 的三条 4128 trace 本身没有专用 `fixture_control` 云。

最小方案是在原版任务上，动作前、动作后和公共 release/retreat 恢复后保存唯一同 parent 的当前控制云，同时测量固定炉体参考和有向 lever 特征或停止端点；记录两视角一致性、重复帧散布和来源。采集 true-off 与 intermediate-dark 的对照，关节真值仅进入私有标签。独立原版确认批证明公共测量能够分开两类后，才将端点 packet 接入 `verify_stove`。缺少这些证据时继续 unmeasured，不以 PCA 符号或视觉变暗代替关断端点。

远端 CPU 复现命令：

```bash
cd /tmp
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006 \
  /public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove551_off_endpoint_CPU_20261006/assess_recorded_control.py
```

未修改 `v5_runtime.py`、已登记快照、训练/评测 manifest 或 COORDINATION，未提交 GPU。SOURCE550 的 job4186 使用旧版本，保留其独立开发结果；新 measurement v4 后续由主代理登记到新的快照。
