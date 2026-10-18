# 10/18：状态索引纠正、9475 关闭结果与把手朝向修复

1. 9498 的 8/19 是碗 init8/19，不是盘子；此前盘子运行状态的回报有误。已按完整 case 与 SHA 找回盘子 160/161，9500_160 是其真实启动检查。
2. 提交器已增加期望任务名核对、逐状态身份回执及启动 case/manifest 核对；错误的旧索引 CPU 检查退出 1，没有提交 GPU 作业。
3. 9475 三局全部结束：杯子修复成功；微波炉关/开仍失败，分别 16/24 决策。失败记录保留，不宣称微波炉已修好。
4. 新源码 31a70c0 恢复同帧局部把手朝向，211 项相关 CPU 测试通过；没有改门身份、终点判据、力、速度、预算或公共 schema。物理效果待验证。
5. Codex3 继续盘子、微波炉及每类上限；Codex1 核对下面的更正与 SHA，Codex2 继续使用匹配上下文的离线前缀接口。未训练、未冻结。

## 状态错位的根因与更正

原 9248 清单按类别轮转；新 preparation 从另一个按类别分块的清单复制。数字索引 8/19 被错误沿用，CPU 文件存在性与启动成功检查没有识别它们代表了不同状态。

| 清单 | 索引 | 实际状态 |
| --- | --- | --- |
| 原 9248 | 8 / 19 | plate_push_libero_goal_t5_s0 / s1 |
| 9498 | 8 / 19 | bowl_transfer_libero_spatial_t0_s8 / s19 |
| 更正后，同一新清单 | 160 / 161 | plate_push_libero_goal_t5_s0 / s1 |

两个正确状态 SHA 分别为 `cea30572c1ece1c5d5a53c64fef51544c3a02dbb6bf6bc06d02d3a03ea719aa7`、`5ce7bdf94e5030da4f2cdaecaf680d5607faec8614ca63773f1b67ef045d78bf`。更正脚本比较完整 case，包括原版 BDDL SHA，不以序号近似配对。9500 使用原 2997335 快照、同一个 launcher；完整数组须等待其真实物理请求和正常退出。

9498_8 已成功，2 决策、302 步、338.611 秒，属于碗 init8；9498_19 已在运行，保留自然结束。它们不进入盘子配对分母。旧盘子失败以及新方案的 CPU 几何检查仍有效，但截至这次纠正没有新盘子的完整物理结果。`progress_inclined_rim_20261018.md` 及相关 COORDINATION 中把 9497/9498 称作盘子物理验证的部分由本更正取代，原文不覆盖。

提交器新增 `--expected-case-names`。错误索引与期望盘子名不一致时，在 sbatch 之前退出；通过后保存每个选中 case。完整数组还核对 startup 的快照、manifest 与物理记录 case。唯一控制器转为 `chunk_v3_inclined_rim_plate_20261018`，传递正确索引和任务名。只终止旧控制器 PID1825717，没有取消运行任务或修改 held/protected 作业。原文与阴性检查 stderr 见 `reports/plate_case_identity_correction_20261018.json`。

## 9475 完整物理结果

两列逐局官方原版状态身份相同；原版原生结束信号是成功依据，π0.5 关闭。这里是选择出的三局失败复测，不用于估计总体成功率。

| 状态 | ec89f74 成功 | eee8434 成功 | 新决策 | 新仿真步 | 新墙钟秒 |
| --- | --- | --- | ---: | ---: | ---: |
| cup_transfer_libero_10_t4_s1 | false | true | 6 | 1174 | 820.128 |
| microwave_close_libero_90_t33_s0 | false | false | 16 | 770 | 1642.575 |
| microwave_open_libero_90_t35_s0 | false | false | 24 | 1566 | 1715.391 |

逐局回执、choices 路径和 SHA：`reports/anchor_recovery9475_closed_20261018.json`。杯子的非接触恢复解决第二个源物体缺接触拟合；微波炉仍缺稳定的可执行部件几何，增加接近尝试没有解决它。

## 微波炉的新增 CPU 证据与补丁

保存的同帧 SAM 门候选在主视角包含真正的门框、把手及其他深度表面，整块云直接拟合平面会失败。现有 4 mm consensus 和 vertical_face 的原残差门槛可分离主视角门框：开门候选的主平面占 62.14%，关门候选占 68.40%。叠图确认主视角的拟合覆盖实际门框；腕部另一个 100% 平面覆盖固定面板，仍不能当门或终点证据。原始数据、每个云 SHA 与叠图引用：`reports/microwave9475_plane_consensus_CPU_20261018.json`。

开门 row14/step19 同时已有独立把手云，但当前门 provenance 只来自腕部固定面板，原逻辑拒绝主视角朝向。现有局部 backing-plane 函数在两个父实例对应的主视角原始门候选上都给出相同朝向 `[-0.4656614,-0.8849630]`，14250 点，p90 残差 2.267 mm。它只测朝向，不证明门身份或操作成功：`reports/microwave9475_handle_backing_CPU_20261018.json`。

新源码 `31a70c0ab5bf698c3552c780f05450343b396a77` 在独立门朝向缺测时，对当前可见父实例、同一相机、同一次捕获的父云与候选云运行已有局部平面 consensus。文件必须与保存的 SHA 一致；冲突朝向继续缺测。未增加 SAM 调用，不把被拒候选升格为门测量，不修改 endpoint 验证器。公共 schema 仍 bounded-skills/3，public legality 仍 /2。

新增 CPU 回归覆盖：错误门身份不能遮蔽独立的当前 backing；当前复合候选可提供朝向；过期、文件改变或其他视角的候选不能提供朝向。相关五文件测试 **211 passed / 2.04秒**，原 timeout 插件配置警告保留；Ruff 新增问题 0。命令、日志和源码 SHA：`reports/handle_backing_cpu_validation_20261018.json`。这是代码与 CPU 验证，完整物理复测尚未给结论。

## 10:05 五项交付仍然有效

函数前十五项、可缓存范围和 IK 共享状态导致的进程并行限制，碗 init2 新旧两臂成功，以及任意前缀 CPU 接口，见 `progress_prefix_judge9_and_door_identity_20261018.md`。judge10 实际请求三个位置零差异见 `progress_judge10_and_plate_20261018.md`。缺保存上下文的历史 26 请求 / 59 unknown 仍不可补标。候选目录顺序无语义；源端保留最近三条详细回执。确认状态永久排除训练。
