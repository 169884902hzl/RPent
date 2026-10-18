# 10/18：可见锚点的接近恢复与复测

1. 10:05 五项已交付：函数级耗时和可并行/缓存结论、碗 init2 同命令双臂成功、CPU 任意前缀标注接口、候选顺序无语义、最近三条详细回执。
2. 杯子失败局三个保存状态已恢复合法的非接触接近选项；这是 CPU 几何与标签证据，还不是物理恢复成功。
3. 源码 eee8434 已推送，255 项相关 CPU 测试通过；私有 judge10，公共 schema v3 / legality v2 未变。
4. 微波炉关门 9473_120 仍失败：16 次决策、772 步，与旧轨迹物理步数相同。基座预测修复不能解释为门操作修复。
5. Codex3 继续同快照启动检查 9474_61，之后复测杯子和微波炉；Codex2 按匹配版本使用 CPU 标签，Codex1 核对源码 SHA。未训练、未冻结。

## 本轮改动及其边界

`MeasuredSkillAdapter._route` 在接触拟合失败但锚点仍可见时，允许 `move_to` 到测量边界外 12 cm，保留当前腕姿。路线继续通过完整夹爪扫掠和 IK 筛选。不填补接触宽度，不生成接触计划，也不提供无依据的 align/descend/lift。候选不按任务目标筛选。

私有 selector 先保留“丢失当前接触时开手”的恢复优先级。没有接触计划时，可选一个未尝试过的、实际端点变化超过 2 cm 的可行接近动作；随后先等测量，不在同一个 chunk 连走多个观察位置。已持有其他物体时不释放它。

快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_anchor_recovery_20261018_eee8434`。

- archive SHA256：`c33b9e70f4edd74720c4199196ef4feb2b9c3a29cff87726d6ed489c08bdc43f`
- bounded_skills.py SHA256：`ba6e87feaa48e90b81a96cfe42a43502b5191697175a41ad5dc8b7715f297a67`
- bounded_oracle.py SHA256：`2028080c01b5162cf13f089ca8a84217678ecb5132278f2af8bf40d5c116c185`
- schema SHA256：`df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`
- 运行入口：`scripts.probe_bounded_feasibility:episode`；解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

私有规则版本是 `libero-private-task-progress-rules/10`。8966ce8 / judge9 的在线离线零差异证据仍单独保留，不能当作 judge10 的物理或标签结果。离线标注输出会写入自己的 judge；使用者必须固定匹配的源码版本。

## 杯子保存状态的逐次对照

原失败是 `job9248_14`。三个时刻均能把剩余源绑定到 e98、目标绑定到 e73；e98 可见但没有对夹接触计划。旧 selector 最后只扫描，之后无选项。

| 原决策位置 | 原选择 | 新增 e98 接近中可行数 | 新选择 | 候选数前→后 | CPU 秒 |
| --- | --- | ---: | --- | --- | ---: |
| 3 | wrist_scan | 11/12 | move_to e98 / above / direct | 62→98 | 40.099 |
| 6 | wrist_scan | 11/12 | move_to e98 / above / direct | 77→101 | 38.065 |
| 9 | 无公开选项 | 11/12 | move_to e98 / above / direct | 75→99 | 38.987 |

原请求的候选原样保留，再为所有可见、无接触拟合的锚点计算新增路线。没有只替任务源生成选项。每个新增目录中，在线选择与 CPU 标注的 legal/acceptable/selected 均无差异。

这是同一保存 RGB-D/本体状态上的扩展目录诊断，不是重新采集的运行时请求。未执行仿真、分割或 RPC。完整后果未再次压缩，JSON 字节 44209→67263、50330→65774、48996→64439，不作为实际模型 token 数。物理启动和完整复测另计。

证据：`reports/cup9248_14_anchor_recovery_CPU_20261018.json`；脚本：`scripts/replay_unfitted_anchor_CPU_20261018.py`；预检与源码：`reports/chunk_v3_anchor_recovery_20261018_preparation.json`。

255 项 CPU 测试的精确命令、源码文件 SHA 与压缩原始日志见 `reports/unfitted_anchor_cpu_validation_20261018.json`。新辅助脚本 Ruff 通过；五个既有核心/测试文件与 HEAD 的 Ruff 诊断计数逐个比较，新增问题为 0，没有清理无关问题。

## 微波炉关门：复测没有改善

| 运行 | 源码 | 原生成功 | 决策 | 仿真步 | 墙钟秒 | 终止原因 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 9248_6 | ec89f74 | false | 16 | 772 | 1388.822 | no_public_option / perception |
| 9473_120 | 8966ce8 | false | 16 | 772 | 1387.742 | no_public_option / perception |

9473 的仿真步分配为 move_to 468、descend 38、set_gripper 30、nudge 98、observe 138。Slurm COMPLETED 只表示程序正常退出。原始物理结果保存在 `reports/microwave9473_120_physical_20261018.jsonl`。

该完整回合的互斥主线程分桶：分割 322.188 秒、实体测量 279.389、规划后果 370.820、请求包装 106.593、oracle 3.196、仿真步进/渲染 19.079、私有离线上下文捕获 88.888、产物 I/O 69.489。其余深度/捕获/执行收尾见原始结果。完整回合中存在重复 refresh，不能将这些累计数解释成一次感知。

函数级前十五项、哪些可缓存及为何尚不能直接逐候选多进程，见 `progress_prefix_judge9_and_door_identity_20261018.md` 与 `reports/profile_saved9024_120_CPU_20261018.json`。固定控制面板的跨视角跟踪没有被接入门验证器。

## 队列与后续执行

9474_61 是新快照、同 launcher 的真实启动检查。必须记录实际物理请求后，才放行 61/120/140 的完整开发复测。提交使用 node02 / nice500。普通排队不当作基础设施故障。

唯一队列控制器已从 fixed-base 复测切换到 anchor-recovery 复测；旧控制器已退出，不同时运行两个调度器。Codex2 无 GPU 作业时可借第四卡；有作业排队后恢复至多三卡，不取消正在运行的任务。9248 的其余原版上限与 9472 真盒子仍保留独立源码和登记状态。确认池永久排除训练，不训练任何模型。
