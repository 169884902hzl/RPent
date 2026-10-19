# 当前把手证据与门身份冲突

1. 10:05 的五项问题已有答案与证据，见 [前缀与 profile 报告](progress_prefix_judge9_and_door_identity_20261018.md)。历史缺上下文的 59 个 unknown 仍不支持补标。
2. 真盒子 4db4ea4 原版批已完成 20/20，Wilson 95% 区间 83.9%–100%；这只是二十回合上限检查，不是类别资格判定。
3. 门身份有新公开证据：同一旧回合 12 个捕获时刻内，现有把手后方平面规则的 20 次真门比较通过、12 次错误面板比较未通过。比较不是独立回合，不能解释为泛化准确率。
4. 唯一当前把手支持修复的两局完整复验 9611 为 0/2；关门无可达候选，开门终态为感知失败。466 项 CPU 回归不能代替物理成功证据。
5. 10/19 00:42 PDT 固定 ec89f74 原版批 r16 为 97/122，登记 220；98 局未完成、零 execution_error。Codex3 继续失败诊断及队列监控，Codex1 核验，Codex2 仅用匹配上下文标注。

## 为什么不能靠跨视角像素支持选门

同帧 RGB 叠图确认，腕部被 SAM 叫作门的点云位于固定控制面板，主视角被拒的点云却覆盖真正门框和把手。两者都能在另一视角找到真实深度对应，因此“有跨视角对应”不能证明门身份。f75b516d 只修了无固定参考面时跳过既有主平面拟合的问题。

新对照只用保存的公开点云。已有 `measured_handle_backing_face` 检查平面在把手后方、法向间距 5–60 mm、宽高与切向覆盖；没有改变这些门槛。capture19 中真门距把手约 32 mm，固定面板约 132 mm。完整回合内有同帧把手证据的 12 个时刻，逐次 32 项比较和现有 helper 的判断一致，分别为通过 20 / 未通过 12；原始诊断不读取私有物体位置，不执行仿真、RPC 或 GPU。

- 子集：`reports/microwave9600_handle_panel_CPU_20261019.json`
- 全部保存时刻：`reports/microwave9600_handle_panel_all_CPU_20261019.json`
- 对照脚本：`scripts/microwave9600_handle_panel_all_CPU_20261019.py --all`

## 实现与边界

`v5_microwave_identity.resolve_door_views_from_current_handle` 复用原有后方平面规则。运行时仅在两视角的门云不能合成同一平面时调用：重新测当前独立把手，核对 cloud 的 perception 来源、捕获步和 SHA，仅在一个视角得到支持时保留它；没有支持或两个冲突视角都得到支持时仍为 unknown。被排除视角的错误门历史会清除。

这不是用目标筛候选，也不把有把手的平面当作开合完成。`stop_admitted=False`；原来的多帧、独立参考面与终点验证不变。新证据写入几何诊断 `current_handle_association`；公开 schema / legal / 私有 judge 仍为 3 / 2 / 13。

源码 commit 为 `ede83b18c1f38b70399eff250c57aa49ec6afe93`。快照将部署到 `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_current_handle_20261019_ede83b18`，归档 SHA256 `8ed798877a134bd8292dc68e578ca99fd7079a79039f454f922669a6641d84f7`。CPU 收据为 `reports/handle_panel_support_cpu_20261019.json`，466 passed / 1 warning，218.16 秒；唯一 warning 仍为已有 pytest-timeout 插件缺失。原始日志保留 pytest 的空白行，未为通过空白检查而清洗；源码和 JSON 的 diff check 通过。针对性测试最初的四个运行时 fixture 缺相机 metadata，补齐 fixture 后 8 项通过；未放宽生产测量判据。

## 新旧物理结果分别保留

| 来源 | 状态 | 结果 | 决策 / tick / 秒 |
| --- | --- | --- | --- |
| d137822 / 9539_120 | 关微波炉 init0 | 原生失败，perception | 17 / 947 / 2014.701 |
| d137822 / 9539_140 | 开微波炉 init0 | 原生失败，perception | 27 / 1432 / 2794.311 |
| f4400223 / 9605_120 | 关微波炉 init0 | 原生失败，planning_unreachable | 33 / 2192 / 3988.124 |
| f4400223 / 9605_140 | 开微波炉 init0 | 原生失败，perception | 19 / 1434 / 1825.794 |
| f75b516d / 9608_120 | 关微波炉 init0 | 原生失败，planning_unreachable | 7 / 331 / 343.660 |
| f75b516d / 9608_140 | 开微波炉 init0 | 启动前被 ede83b18 替换取消 | 无物理结果 |
| ede83b18 / 9611_120 | 关微波炉 init0 | 原生失败，planning_unreachable | 7 / 331 / 344.984 |
| ede83b18 / 9611_140 | 开微波炉 init0 | 原生失败，perception | 22 / 1501 / 2284.402 |

9539 完整汇总为 `reports/microwave9539_closed_20261019.json`。这些是不同不可变源码的开发复验，不能合并成同一源的成功率，也不是单项消融。确认状态永久训练排除继续有效；不训练、不读 PRO、不使用真机。

9611 关门初始测得门表面，但 16 个接触姿态全部被闭合扫掠碰撞拒绝；机器人移动之后，同一表面的 16 个接触姿态均没有数值 IK 解。公开记录足以说明未获得可执行接触，不能据此断言所有姿态物理不可达。开门回合至少五次冲突视角消歧成功选出主相机，但随后仍无可执行接触，且父实体身份多次变化。下一步分别诊断接触姿态覆盖与身份连续性，不能靠放宽碰撞/IK 或把门平面当作端点完成。

逐回合、技能次数、tick、墙钟独占分解及 Wilson 区间保存在 `reports/microwave9611_closed_20261019.json`、`reports/microwave9605_closed_20261019.json` 和 `reports/microwave9608_partial_closed_20261019.json`。取消证据见 `reports/panel_consensus_pending_replaced_20261019.json`。仅同 launcher 启动证明 9607/9610 不另计完整回合。

## 原版批次与杯子失败

固定 ec89f74 的 r16 分类为：碗 16/16、罐 12/14、容器 14/14、杯 7/14、抽屉关 14/15、抽屉开 12/15、微波炉关 0/1、开 0/1、盘 0/2、灶台关 11/15、开 11/15。失败完整保留，未完成状态不作失败或成功。真实盒子另外登记在 4db4ea4 批中，不能合并成 ec89f74 的分母。

`cup_current_mask_CPU_20261019.json` 与两张叠图记录了 init1、init11 当前公开掩码。我实际看过图片：白黄杯的分割覆盖杯体和把手，未见把相邻红杯或桌面混入；这两局当前只有主相机测量，没有腕部匹配视角。候选拒绝原因主要是没有测到成对对夹面，尚不称为真实不可达。该诊断没有仿真步、GPU 或 RPC。
