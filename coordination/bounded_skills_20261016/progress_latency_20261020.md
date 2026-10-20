CPU 保存状态对照：碗候选后果 10.05→2.38 s、杯 15.76→2.88 s、微波炉 6.44→2.19 s；不含实时感知、初始接触拟合或整局执行。
248 个候选中，端点筛查放行而完整路线拒绝 14 个，反向 1 个；完整路线仍在选中后执行，尚无整局结果一致性结论。
213 条 π 轨迹的按块抽查审计完成：检查数 30,377→6,160；29 条存在未保存的块尾，不能推算新结果。
固定 32 状态 N1 两版预检通过，10698 排在 10687、10689 自然结束后；91307c12 已借自有 allocation 执行 4 步/222 tick，排除出 N1 计时。
运行中的 10686–10689 是 3968bdb4 的 D2/N8 精度批。它们不是固定集 N1，不与新源合分母；无训练。

|保存输入|候选数|完整路线后果 s|端点后果 s|便宜放行/完整拒绝|便宜拒绝/完整放行|
|---|---:|---:|---:|---:|---:|
|碗 9248_0|77|10.047|2.384|1|0|
|杯 9544_124|107|15.762|2.875|7|0|
|微波炉 9611_120|64|6.437|2.190|6|1|

按技能：`move_to` 132 项中两方向差异 12/132、1/132；`descend` 8 项中为 2/8、0/8；其余无该标志差异。`carry_to/lower` 的 26 项在这批初态中为条件后果，没有测量完整路线，不能把它们算作正确分类。14 个放行项保留 `collision=null`、`path_min_clearance_m=null`，没有声称路径安全。微波炉 `52b05fd5c514f7ae` 的反向差异是终点数值 IK 未找到解；独立实测关节种子的排查未解决它。阈值未放宽。

逐候选原件：`reports/lazy_saved_three_CPU_20261020/summary.json`；三态 CPU 原件由 `compare_lazy_saved_CPU_20261020.py` 产生，源码 a1db4772。公开输入、既有接触计划相同，0 物理步、0 RPC；不代表全请求加速或物理成败。完整请求与 oracle 的时间将由 N1 另报。

π 抽查的 213 条均来自闭合原版开发分支：158 条原生终止保持逐控制步检查、14 条视觉停止位于块尾、29 条视觉停止位于块内且没有保存余下控制、12 条未执行 π。原始逐次结果不改判。保存的稠密视觉证据有状态，抽帧不能替代新频率下的重新测量；没有生成新真值标签。原件 `reports/block_cadence_213_CPU_20261020_r2.json`。历史 213 分支检测累计 294168.72 s、π 推理 1188.40 s，含 N8 竞争，不能作 N1 延迟或按比例预测提速。

初版速度源 172a8600 保留于 `/public/home/sunyihan/rpent_libero_eval/source_bounded_speed_172a8600_20261020`，归档 SHA256 `773078db0e1983fec5c402331857ce00d7cadebde4bdfa5ae9ad0c260a76a32d`。早期启动器 `launcher_fixed_latency_20261020_f7eba4cf/`、Git d7e119f2、SHA256 `f7eba4cf2118b20cd359b1d5f00c938baaf163c2345a6b96f2ddb88f1314fdcc` 也保留。

当前优化源为 `/public/home/sunyihan/rpent_libero_eval/source_bounded_speed_91307c12_20261020`，完整 commit `91307c125c2badfad7f2460d1fa2184fd7ff73a8`，归档 SHA256 `2440a1e584becc6d9cdd7a69b0749bd633570426e8b2b0d6fbe6fda96a0bbc0b`。启动器就在该快照内的 `coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py`，SHA256 `28fe77751aa1435eb4200ecf0ff2cddea109ebe3cccbb65864c3d32b3d511d25`。它额外记录真实开局物理状态哈希。已推送 `user-fork/harness-v5`。

schema `bounded-skills/5`：SHA256 `916708e0f401acb39495aa3fbb17b985e4bae7647a3285151411bb666e83d54f`；contract SHA256 `3596aed13b7ef44c957cfe71a59d3a5f227d10e6347e74aeba35e26c24c7785a`。新增 `screen_scope=endpoint_ik_coarse_geometry`；明确该字段仅描述终点，完整后果留给选中序列。Codex2 需要同步训练/推理对 null 和新 scope 的解释，不能把这些选项当成完整路径已通过。`legal_after` 仍共享公开前提，没有加入目标筛选。

N1 baseline manifest：`results/bounded_skills/latency_fixed32_20261020/preparation/manifest_r3.json`，SHA256 `d52f8561bb2e4e0b59bf9b52ce0d68e08b9e22a6052c7d9585b395b84bfab402`，源 6a2d6bb8。当前优化 manifest：同目录 `manifest_speed_91307c12.json`，SHA256 `2cdabc957c4c1858c0faf5884c1432151ee5fb95cb2d1194aed584096d5609b3`。32 个初态/种子身份一致；优化臂开启 lazy、`registration_query_workers=4`，两个 VLA 试点设 `controls_per_check=null`。单卡单回合独立进程，候选不并行。10698 申请 node02、1 GPU、8 CPU、96 GB、nice=500。旧 10696 仅在确认 PENDING 后取消，未产生正式 N1 回合；旧 manifest/快照/取消记录保留，不修改保护作业或旧 held 作业。

验证：a1db 的 screen/skill 267 项通过。补齐 schema 消费者后，在项目 `.venv` 上 chunk、offline labels、schema、legal、hybrid repair、CPU capture 共 93 项通过；新增块检测及 hybrid repair 26 项通过，测试存在重叠，不合并成独立总数。最初系统 Python 的两项 IK 测试缺 mujoco，项目环境已实际重跑通过。所有退出和原失败记录保留。

新源真实启动原件：`reports/latency_20261020/startup_speed_on_owned10687_r1.json`。先后执行 move_to 128、descend 47、set_gripper 15、lift 32 tick，4 个回执均 success，进程退出 0。借用 10687 的既有 SAM/π 服务，没有新 GPU allocation；与 N8 重叠的 105.536 s 不作为 N1 延迟或前后提速结论。当前 10698 仍会在自身 allocation 内完成两版启动检查后再运行全部回合。

同状态函数级 profile 选择、4 个回执与步数均一致：`reports/lazy_real_startup_profile_20261020.json`。`contact_axis_registration` 3 调用累计 18.783 s、实例像素重建 20 调用累计 18.769 s；时间存在嵌套，不相加。完整前 15 函数和调用数在原件。实例像素重建还包含自身表面过滤、目标/场景像素分离和体素处理，SAM 本身不再是这一次启动的主要开销。

静止表面查询的保存公开输入对照（master CPU，非 N1）：

|状态|单线程 s|4 线程 s|再次单线程 s|全字段字节一致|
|---|---:|---:|---:|---|
|碗 9248_0|7.834|3.495|7.734|是|
|杯 9544_124|12.546|5.702|12.343|是|
|微波炉 9611_120|5.640|3.177|5.640|是|

原件 `reports/registration_workers_CPU_20261020.json`，含完整平移、区间、残差和 verdict。只并行 cKDTree 查询，均值归约、样本、门槛、执行力度和预算均不变。91307c12 接入显式线程配置，payload/chunk/CPU capture 83 项通过。最新真实启动 `startup_91307c12_on_owned10687_r1` 仍为相同 4 步/222 tick，真实初态 SHA256 `fad8679cdf304380dd4d8756ac909b68c7eeb292d43958ba95267cdeadb5b37f`。该重叠启动只分到 1 核，循环 104.742 s，尚未测到整循环提速；正式 8 核 N1 结果仍待产出。

按块检测的第一个共享 allocation 试点 `pilot_block_on_owned10688_r1` 实际运行 24 块、120 控制、25 次检测；分支物理标签 false，原因 block_budget。交还完成，后续自身 observe 请求正常生成并执行。检测 71.969 s、π 推理 2.788 s、控制 1.370 s，仍未达到检测时间不超过 π 时间的目标。它仅匹配旧的 legacy 物理哈希，旧快照缺完整 observation phase，且首个动作不一致；不是严格同源/同初态的前后因果对照，也不是 N1，不能将结果变化归因于检测频率。

D2 中间结果单列：原 3968 源 40 局中，29 个 physical_result、2 个 oracle_rule_uncovered、2 个关系端点程序错误、7 个仍运行；独立整局回放 9/29，Wilson 95% 17.3–49.2%，其余 11 局 unknown，不把 unknown 当失败。原件 `reports/D2_closed_workers_interim_20261020_r2.json`。两条程序错误用仅修关系端点的 6a2d6bb8 登记相同状态/种子补跑，indices 13/24，manifest SHA256 `7f5459f0e88900dcf93eb0917a08c51cdb0f011212d318f09aa8ec3b0ee00f09`；10699 等原四批自然结束，作业内先验证真实 VLA 请求再跑两局。旧错误不覆盖，不混入新速度源分母。

操作失误单列：首次 a1db 快照曾因错误的解包目标把 5058 个归档文件写到未版本化的远端工作根目录；事后逐文件均与归档相同，但没有解包前备份，无法完整恢复或确定哪些此前不同。没有把这说成“已恢复根目录”。活动精度任务和本轮 N1 均引用独立固定快照。原件 `reports/snapshot_extraction_incident_20261020.json`；后续解包保留归档目录前缀并拒绝已存在目标。

仍待完成：N1 实际两版计时和逐局结果；感知跟踪与完整刷新调用数对照；29 条稠密分支的块频率物理复跑；D2 原精度批闭合和两条关系端点程序错误的新源补跑。确认状态永久排除训练，D2 仅评测，不进入历史成功率表或训练。

## 无损保存压缩的 `EnvState.save/load` 对照

在固定原版状态 `profile_speed_on_owned10687_r1` 已保存的 RGB 与 world 点云上，CPU 实测 `EnvState.save/load` 默认压缩与 level 1；共 8 个文件（两相机、两个时刻），解码数组与原输入及彼此逐元素相同。PNG 平均编码 0.366→0.079 s（4.63×），文件平均大 20.0%；NPZ 平均 0.506→0.270 s（1.87×），文件平均大 1.71%。这只是保存操作微基准，尚未证明单局墙钟变快；默认保持不变，正式结果不混入 91307c12 的 N1 批。

原件 `reports/lossless_artifact_envstate_CPU_20261020_r1.json`；基准脚本 `scripts/bench_envstate_compression_CPU_20261020.py`，SHA256 `7a80e30b6b349d1213eb8a4e87f40d9f1c434cf0a879e48ef69e4a6d47077ea1`；源提交 644398402e641b4510110b00baf08539a2cbb48a。远端快照内同脚本执行成功，8/8 round-trip 一致，未用 GPU、未走物理步。

## D2 已结束 worker 的更新

10686 的 10 个 worker 中 9 个是 physical result，`libero_goal_swap_t4_s40` 为 `ValueError: relation references an unmeasured anchor`；10687 当前落盘 9/10 worker，7 个 physical result、1 个同类 relation 错误（`libero_spatial_task_t3_s40`）、1 个 `oracle_rule_uncovered`（`libero_10_swap_t3_s40`）；10688 落盘 8/10（7 physical、1 `oracle_rule_uncovered`：`libero_10_task_t3_s40`）；10689 落盘 9/10，9 个 physical。当前合计 32 physical、2 个关系端点程序错误、2 个 uncovered、4 个尚无 worker 文件。错误栈分别在 `adapter.request(k=4)` 的公开 request contract 校验处抛出；10699 已登记 6a2d6bb8 关系端点修复并等待旧批自然结束后补跑。此处只报已保存 worker 的状态，不把 unfinished/unknown 当成结果。

队列快照：10687、10688、10689 继续在 node02 运行；10698（固定 32 状态 N1）等待 10687/10689 自然完成，10699（两条 D2 修复）等待 10687/10688/10689。未取消或修改运行中的任务。10698 正式两臂尚未开始，因此目前没有该固定批的前后决策时延或整局结论。
