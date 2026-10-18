# 原版 oracle 覆盖与残余杯子诊断

1. `ec89f74` 的原版数组 `9248` 在 10/18 13:44 PDT 已完成 3/220：碗、汤罐、放入容器各 1/1；全部关闭 π0.5。样本不足，不能据此判断类别通过。
2. 杯子 init9 的 CPU 诊断显示局部公开曲面配准不足以恢复完整刚体转动；没有用私有位姿修正运行时，没有扩大碰撞豁免范围。
3. 原 `box_transfer` 实际是汤罐。奶油奶酪盒的 20 个已登记状态保持不变，已在当前源码完成全量 CPU 预检；启动作业 `9253_0` 排在 `9248` 后，尚无新的盒子物理结果。
4. 代码和四对物理证据已推送 `harness-v5`：`5940f66`。`COORDINATION` 的上次追加已逐字节核对；公开 schema/contract 无变动。
5. Codex3 继续监控并处理原版 oracle；Codex2 可使用已交付的 CPU 前缀接口。类别上限与完整 K1/K4 统计仍未完成；两个历史对照已有完整 220 局物理记录，当前 manifest 的匹配复核另见 `progress_existing_controls_and_prefix_20261018.md`。尚未冻结或训练。

## 当前源码原版数组的完整回合

| 类别 | 成功 / 已完成 | Wilson 95% 区间 | 决策 | 仿真步 | 墙钟秒 |
| --- | ---: | --- | ---: | ---: | ---: |
| 碗抓放 | 1/1 | 20.65%–100% | 2 | 291 | 278.258 |
| 汤罐抓放 | 1/1 | 20.65%–100% | 2 | 484 | 210.826 |
| 放入容器 | 1/1 | 20.65%–100% | 2 | 588 | 187.642 |

这是数组完成前缀，不代表独立类别资格或完整成功率。三局没有运行错误，也未撞上原生步数上限。容器局在 release 后原生成功，随后缀截断记为 `native_success`，不计为执行偏差。汇总保留全部完整失败，并分别列出未完成状态与错误记录：`reports/original20_support_roundrobin_20261018_134415.json`。原始回合在远端 `results/bounded_skills/feasibility_20261017/job9248_{0,1,2}/episodes.jsonl`。

## 杯子残余四点

复用已完成的 `9026_69` 原版 init9、row0/row2 保存状态，只在 CPU 恢复，不发送控制。两次恢复误差均为 0。此前独立身份审计已确认，当前路线的四个剩余障碍点都来自杯子。

| 诊断量 | 数值 |
| --- | --- |
| 私有刚体转动幅度，仅诊断 | 0.25402 rad |
| 公开局部表面拟合转动 | 0.02997 rad |
| 私有平移，仅诊断 | [11.122, 2.210, 0.663] mm |
| 公开表面拟合平移 | [9.059, 2.373, 0.668] mm |
| 旧表面经两种变换后，逐点差异中位数 / 最大值 | 11.558 / 21.151 mm |
| 四个障碍点距公开变换后旧表面的最近距离 | 1.656 / 1.224 / 1.067 / 0.999 mm |

局部残差改善不等于完整物体姿态可观测，尤其是被手指遮挡的曲面。该诊断没有证明能从当前公开输入唯一恢复旋转，也不证明这些四点可绕过现有表面连续性要求。运行时没有读入私有位姿；当前仍保留拒绝结果。证据：`reports/cup69_registration_pose_diagnostic_CPU_20261018.json`、`reports/cup69_support_identity_CPU_20261018.json`。下一项是取得新视角或当前深度连续性证据，再决定是否修改表面归属。

## 真实盒子补充

旧作业 `8987` 已取消，不能把其提交回执当作已完成的盒子试验。沿用此前登记的 20 个 `box_grab_place` 状态，原版 init 索引为 0–13、31–36；没有把永久排除的确认状态补回来。新 manifest 仅更新源码与登记来源，逐 case 内容完全相同；所有路径、原版状态及排除规则由现有 CPU preflight 检查通过。

- manifest：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/preparation/original20_manifest_real_box_support_r3_20261018.json`
- SHA256：`684269e4bba33a1097ee690e3ff4ca4697f4216a977bcf69210f6e9f80d3a920`
- CPU 凭证：`reports/real_box_support_r3_preparation_CPU_20261018.json`
- 真实启动提交：`reports/real_box_support_r3_20261018_startup_submission.json`，`9253_0`，`afterany:9248`。

先取得该快照、manifest、launcher 下的实际物理请求和正常退出，再提交其余盒子分片。当前未提交该补充的正式数组。主数组的 220 个状态不变，补充另列。

## 源码与验证边界

运行源码 `ec89f741b4b729b0ac854b7510ec74105a5a13e9`；快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_support_plane_20261018_ec89f74`；源码归档 SHA256 `68aa74bc9188156b3bde2147bd2455d4fa658a9ab1bfea772cffe36486bacf68`。入口 `scripts.probe_bounded_feasibility:episode`，解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

新增三个 CPU 辅助脚本通过 py_compile 和 scoped Ruff；汇总和私有姿态诊断均在实际保存记录上执行；盒子全量现有 preflight 退出 0。它们未改变运行时技能或公开 schema，不重复宣称进行过新的 252 项运行时测试。所有 GPU 提交仅 node02、nice500；已有运行任务自然结束，确认状态永久排除训练。
