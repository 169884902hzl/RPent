六例交还已完成：6/6停稳、6/6后继请求；π真抓住的三例均由bounded续接到原生成功（15068167）。
停止规则12条对照已闭合；第三个碗种子延长到220步仍失败，保留pick默认值，不推广为全部子任务的最优阈值。
三处source_binding_missing已归因为公开同类误检歧义；通用观察恢复有CPU证据，物理消歧尚未证明。
另修原版s15的提示绑定程序错误：3968bdb4已推送，320项CPU通过，同状态首π物理请求通过，三原seed完整分叉在跑。
原版其余分支继续；新40局D2同状态/种子/预算重登记，启动2/2通过，10686_0已有实际π推理，不报未闭合的混合整局分数、不训练。

## 3968bdb4最新开发修复与调度

公开提示只使用anchors广告的可见/缓存实体。s15腕扫后e2可见，e67失测且不在公开anchors；旧formatter仍用e67否决唯一公开微波炉。新代码保留选中e2和公开几何，生成`close the microwave`。候选不可消歧时省略；选中后失测给出`unmeasured/perception/subtask_binding_unmeasured`回执、0控制步、失败计数+1。schema仍`bounded-skills/4`；行为变化已写COORDINATION通知Codex1/2，追加SHA84bae7fad660989fb9d033fbde596552a181389f1b6ad8017723de555487632d。

- 新快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_public_vla_binding_20261020_3968bdb4`；commit `3968bdb4f5f88c63be1a60fc34d955ff169af5b3`，归档SHA `bf0212555ae870ecd3c59aa910c9b17083a55ef69eaf9589b21d839cf334f0db`。
- 同状态s15启动：10684.1 COMPLETED0:0，236.40秒，1/1首π物理请求，worker错误0。三seed完整分叉用同分配、同启动器继续（工具session22167），尚无闭合结果。证据`public_binding_startup_3968bdb4_20261020.json`。
- 6例旧分叉的提示CPU前后6/6字节一致，无物理/SAM/π调用；这只证明提示文本兼容，不冒充新源码完整动作重放。证据`vla_six_public_prompt_sets_CPU_20261020.json`。
- 原版10682为620ff0da源，原始s15程序错误保留，新源单独补跑；其余运行不中断。39状态中间统计r1：开9/9、关4/6、推盘13/14；杯pick已执行6/6，另6条预备拒绝无π；杯on1/1。未完成不计失败，不混成整局得分。
- D2新登记40状态完全相同：manifest SHA`ecd48f215024e800d9d9c3a736bb5c8eeb0867b3de86276dadf7d4273b77f28c`，5项CPU预检通过，startup10681.0已COMPLETED0:0，2/2实际首π物理请求（543.40秒）。旧D2源15068167的10681_0已停止，停止前37条π分支和1个worker闭合、程序错误0，其余partial保留unknown。新10686_0已经R，并且7个回合的实际π预测ledger已产生；唯一新派发器3896745每分钟sacct/squeue，余3批等原版释放卡后接续。原派发器3680760已停止。

以下六例及停止规则的已闭合物理证据属于15068167或各节明确标注的旧源，不能与3968bdb4新批合并。

## 源码与入口

- 执行修复源：`1506816747489926709bc7fc49a0e730fd5da354`，已普通推送 `user-fork/harness-v5`。
- 5880 快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_subtask_binding_20261020_15068167`。
- 归档 SHA256：`1bff3a649f05bebf1808cfd25db474072bf5e5b21ec5c976161e1eafd19f7945`。
- 六例入口：`scripts.probe_bounded_hybrid_repair:evaluate_case`；D2 完整分叉入口：`scripts.probe_bounded_hybrid_d2:evaluate_case`。
- 解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。schema/contract 仍为 `bounded-skills/4`，模型状态格式未因本次私有绑定记忆修复改变。
- 下表已闭合的物理结果属于 15068167，旧c023结果另见独立报告。原版 10670 使用 f9096f79，独立保留。历史派发器代码cb103385，PID3568107/3524921及其继任3680760均已停止；当前调度以上方新源状态为准。

## 六例同状态、同采样种子重放（15068167）

|种子|π控制步|v3 持续夹持|停稳步|第一个后继chunk|
|---:|---:|---|---:|---|
|13401000|55|True|9|carry_to:success(endpoint, 99步)；release:success(native_success, 4步)|
|13402000|57|True|10|carry_to:success(endpoint, 98步)；release:success(native_success, 4步)|
|14401000|45|False|12|observe:failure(measured_sweep_collision, 0步)|
|16401000|73|True|11|carry_to:success(endpoint, 189步)；observe:success(fresh_public_views, 23步)|
|17401000|120|False|7|observe:no_effect(no_measured_scene_change, 23步)|
|17402000|110|False|11|set_gripper:success(measured_gripper_change, 15步)|

六个旧 10477 拒绝都发生在制动轨迹的扫掠检查，尚未执行制动。逐条拒绝位置、部件碰撞计数及姿态保存在同名 JSON 的 `six_handoffs`，不以总数代替逐条证据。

|原采样种子|原拒绝检查|距当前末端的拒绝点|测得接近状态|
|---:|---|---:|---|
|13401000|measured_sweep_collision|23.71 mm|开度78.27 mm；点数palm:7|
|13402000|measured_sweep_collision|3.59 mm|开度79.80 mm；点数leftfinger:4, rightfinger:5|
|14401000|measured_sweep_collision|0.78 mm|开度74.08 mm；点数rightfinger:5, rightfinger_pad:2|
|16401000|measured_sweep_collision|3.01 mm|开度20.81 mm；点数leftfinger:2, leftfinger_pad:2, rightfinger:1, rightfinger_pad:3|
|17401000|measured_payload_collision|3.55 mm|开度36.92 mm；点数payload碰撞|
|17402000|measured_sweep_collision|2.86 mm|开度36.77 mm；点数palm:31|

五条是夹爪扫掠碰撞，一条是持物包络碰撞；都把接触后的短暂制动当作新的自由空间路线来筛查。修复将接触停稳与后继位移规划分开：停稳不主动平移末端，后继位移仍走完整筛查。

通用交还使用零六轴 OSC 增量、保留夹爪命令和原 OSC 阻尼；连续 4 帧线速≤5 mm/s、角速≤0.02 rad/s，最多 30 步。后继运动仍做整路碰撞与 IK 检查。

旧快照缺少 Observable 采样相位，不能声称重建了 10477 的历史 π 输入。当前比较采用同一 canonical 恢复、原采样种子；15068167 对 7484079b 的完整 π 输入与动作 6/6 一致，且调用数相同。证据：`binding_handoff_inputs_CPU_20261020_closed.json`。

奶油奶酪续接又跑了最多 4 个 bounded 决策：4 次腕扫、92 仿真步、无 π 推理，未放置成功。请求里篮子 carry_to 的碰撞与 IK 均通过；保存端点显示私有源绑定为空。根因是诊断入口直接调用 bind，却没保存已有选择器会保存的身份与同类 peer；oracle 下一次纳入公开缓存后重新陷入歧义。15068167 只补回这项已有身份记忆；新物理复核先完成189步carry_to＋23步observe，再43步lower＋5步release，2次决策共260仿真步，环境原生成功。最初就有两项可见同类时仍保持歧义，不私选实例，不读取仿真坐标。

## 停止规则实测

|采样种子|3块/5mm、120步预算|关闭无进展、120步|关闭无进展、220步|
|---:|---|---|---|
|13401000|55步成功|55步成功|55步成功|
|13402000|57步成功|57步成功|57步成功|
|14401000|45步失败|120步失败|220步失败|

12 条包括六例基线和三个原失败种子的六条扩展。三个设置共享已修正的提示坐标系和夹爪标定；t2的两个原失败种子在这一接口下均成功，不能把成功归因于延长预算或放宽无进展停止。14401000 三条按精确动作 CPU 物理重放，状态误差0、v3 unknown0，全轨迹没有持续夹持成功窗口。45步终点最近另一只碗；延长到120/220步后最近目标本身，但仍约18.7/18.4cm、没有任何双指接触。不是成功后掉落。

两条成功基线又做了完整动作CPU重放：逐步末端误差0、最终仿真状态误差0、v3 unknown窗口0。13401000的首个完整持续夹持窗口为π第54步至交还第9步；13402000为π第56步至交还第9步。若以π阶段开始计，最早完整窗口分别在第64/66个控制步结束。55/57是公开停止步数，私有真值窗口另列，不能混成同一时间。证据`stop_success_first_windows_CPU_20261020.json`，原始逐帧记录及SHA在其中。

默认 pick 保留 `VLABudget(blocks=24, no_progress_blocks=3, controls_per_check=1, minimum_progress_m=0.005)`，配置和 manifest 显式登记；这仅是当前 pick 证据，不宣称所有开合/放置模式已最优。

[OpenPI 官方 LIBERO 评测源码](https://github.com/Physical-Intelligence/openpi/blob/main/examples/libero/main.py)：replan=5，开局等待10步；spatial/object/goal/10/90 最大控制步分别220/280/300/520/400。官方源码没有我们的3块/5mm规则。

额外偏离接口试验使用明确标记的 OSC 故障注入，只验证停稳与交还；不提供策略成功标签，永久排除训练/history/memory/策略成绩。r2 水平注入只达到33.3cm，没有触发60cm偏离阈值，因此不是偏离规则通过证据；r3 立体远离注入在距源60.22cm时触发原60cm阈值，13步停稳交还并生成后继请求（Slurm退出0）；证据 `deviation_guard_injected_closed_20261020.json`。自然策略与人工注入不混合统计。

## 三处身份缺失

|场景|公开感知归因|已验证范围|
|---|---|---|
|object_task_t3|BBQ误标为ketchup，和正确ketchup同时存在|通用腕扫恢复CPU通过；物理消歧未验证|
|object_task_t4|奶油奶酪误标milk，和正确milk同时存在|同上|
|goal_swap_t4|盘子误标bowl，和正确bowl同时存在|同上|

这些初始公开歧义不会被“记住先前唯一解析身份”的修复自动解决，不为 PRO 增加专用规则。

## 一条分支为什么需要几十分钟

旧 17401000 分支执行45个π控制步，墙钟2241.86秒：

|部分|秒|
|---|---:|
|fork 内移到预备位与规划|0.04|
|π推理|1.78|
|SAM RPC（含排队/传输）|2077.21|
|私有计量|2.81|
|交还|0.13|
|其余 RGB-D、几何、控制、I/O|159.87|

SAM 占92.7%。初始候选规划在fork前，未包含在0.04秒中；后继规划另计。当前 SAM 启动入口仅提前丢弃原输出阈值必丢的低分提议；8个原版请求 baseline/fast/baseline 为4.236/1.173/4.077秒，响应字节相同。三条完整 D2 分支的输入、动作、终点、后继请求、选择和回执相同。负载与并发不同，不能将重叠墙钟当作独立整局吞吐因果估计。

## 原版分叉

数组10670：71个登记子任务状态，每状态π三次、bounded自身一次。分类为微波炉开20、关20、推盘20、失败杯子11。启动前四类真实首物理请求4/4通过，所有路径与状态SHA预检通过。

中间结果见 `original_id_repaired_interim_20261020_r5.json`，持续运行中。无推理的预备路线拒绝、未到分叉点、unknown、未闭合都单列，不能写作π已执行失败。Wilson区间仅描述固定诊断样本，三采样共享初始状态，不等于独立任务泛化区间。

原版杯子s9、种子20812000存在公开 measured_success / v3 false：抬高约4.8cm，但0.5秒11帧均无双指接触。保留v3失败，未改判据，不能据少量前缀声称验证精度达标。

π资产已完整核验：7,473,091,464字节权重SHA256 `4d9089c941793f170b625c2ed0ac7a3aa09b6f103e52dbbc82e67301529d6683`，metadata SHA256 `8eba92f1159903755c6f529320913033a142a691bb148f90a96db0b6b91d6528`，均与HF RLinf130-fullshot固定6222623一致。训练配置为LIBERO40+90；没有逐回合训练manifest，不能声称微波炉90一定未见过。

资源仅node02、nice500；通常≤3卡，Codex2无GPU运行/排队时借第4卡，有作业后10分钟内降限流，不取消运行任务。分配最多80核/560GB；不动c5/c6/rf、node01和held。确认池状态永久排除训练。

当前D2 manifest SHA256：`c9551b5df910fc77598ec38b40c8c26a8784433b37df940de5c92f90a0e76656`。2个真实首π物理请求通过，startup10672.4 COMPLETED0:0；派发器已通过同源清单核验与4个CPU启动预检，待实际空出GPU时逐片提交，原版有排队时预留1个D2槽位；旧10477记录保留。

中间逐状态配对表：`original_forks_closed_pairs_20261020_r5.csv`（15个worker闭合）。f909源：94条π接口已闭合，88真执行78成功，6无推理预备拒绝；分母与当前仍未闭合的119条分开。

## 新定位的首次规划开销

D2 spatial_swap_t1启动544.64秒，SAM22请求合计6.40秒。相同源码/同一启动器重复做49Hz只读采样，worker采样时间608.27秒；实际输入与首块π动作的字节均与未采样启动相同。采样会增加开销，不能按621.16/544.64比较性能。

|函数|累计采样秒|命中样本数|
|---|---:|---:|
|request|565.90|27729|
|grasp_geometry|543.80|26646|
|SmoothMotion.prepare|517.08|25337|
|PublicRouteScreen.__call__|427.90|20967|
|_geometry_at|232.61|11398|
|IK check|133.67|6550|
|trajectory.plan|79.22|3882|

累计时间互相包含，不能相加；采样命中数不是函数调用数。完整前15项和输入/动作SHA见 `D2_initial_request_profile_20261020.json`。主要开销是按原串行顺序筛选抓取方案与整条平滑接近路线；现有同帧精确姿态碰撞缓存已经启用。遵照启动方式实验约束，没有为此改变候选数量、顺序、后果数值或并行候选求解。后续可复用项需先验证相同公开保存状态的请求字节与选择不变。

## SAM图像特征缓存与整局重放口径

独立启动入口`sam3_feature_cache_startup_20261020.py`（SHA2372a1c90496123c50e0ceb14395d86fc6496419d82027ffc6d1fce638d94751）只缓存`set_image`后的图像特征，并隔离提示会修改的容器。CPU24项通过。26个预登记原版请求（含point RPC）做关闭/开启/关闭：6.574/2.956/6.498秒，图像编码23/4/23次，全部响应字节相同；本固定请求序列约2.2倍，不当作整局吞吐。

源150三条完整兼容重放（13401000/16401000/17402000）均闭合，π输入和动作字节、调用数、初始与终点哈希、私有成功、公开停止、后继请求字节、后继动作和回执全部相同。私有结果仍True/True/False，没有重选种子。证据`sam_cache_full_branch_compatibility_closed_20261020.json`。后续3968源码D2缓存启动已登记5项CPU预检，正在做同源码真实首物理检查；当前10682/10686不改入口。

汇总层修复：原始`actual_full_replay_success=False`不自动代表实际整局失败。真实例`goal_swap_t0`的四个子任务分支均失败，但`full_replay=[]`，旧脚本把未执行重放算作1次失败。新汇总将无重放/只有已选前缀列为unknown，同时完整保留四个分支失败和原始false；完整重放中实际失败继续记失败。27项相关CPU通过；真实记录CPU复算见`D2_replay_evidence_summary_CPU_20261020.json`。原始记录不改。40局闭合后，还需检查并补齐未实际执行的通用择优整局核对，不能把空列表当作物理结果。
