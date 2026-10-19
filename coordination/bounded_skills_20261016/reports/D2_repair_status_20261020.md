六分支均停稳交还、均生成后继请求；两个碗分支续接 carry_to→release 后原生成功。
停止对照12/12闭合；两种子55/57步成功，另一个延长220步仍失败，逐步v3无成功窗口。保留现有pick停止默认，未证明对所有子任务最优。
三处绑定是公开同类误检造成歧义，CPU通用腕扫恢复3/3；物理消歧尚未验证。
原版四类真实startup4/4通过；71状态×(π三分支+自身一分支)作业10653已提交，结果待物理运行。
仍未完成：三处后继碰撞拦截、原版分叉结果；继续由Codex3诊断。无训练、D2不入训练，确认池永久排除。

六个旧10477拒绝均发生在制动轨迹的几何检查，0步执行；每条具体检查及拒绝姿态在同名JSON。通用交还改用零六轴OSC增量、保持夹爪命令、原OSC阻尼，连续4帧线速≤5mm/s且角速≤0.02rad/s，最多30步。后继移动仍正常扫掠和IK，不以停稳代替路径证明。

|种子|π控制步|私有抓取终点|停稳步|后继物理结果|
|---:|---:|---|---:|---|
|13401000|55|True|9|103步，carry_to:success(endpoint)；release:success(native_success)|
|13402000|57|True|10|102步，carry_to:success(endpoint)；release:success(native_success)|
|14401000|45|False|12|0步，observe:failure(measured_sweep_collision)|
|16401000|73|True|11|0步，observe:failure(measured_sweep_collision)|
|17401000|120|False|7|23步，observe:no_effect(no_measured_scene_change)|
|17402000|110|False|11|0步，observe:failure(measured_sweep_collision)|

旧快照缺Observable采样相位，不能重建10477的历史π输入；重放采用同一canonical恢复及原种子，不能声称和10477完整π输入相同。当前748源下，全场/目标局部监测六例的实际π输入和动作字节6/6一致，证明范围仅限这六个pick分支。

|种子|3块/5mm/120步|关闭无进展/120步|关闭无进展/220步|
|---:|---|---|---|
|13401000|55步/True|55步/True|55步/True|
|13402000|57步/True|57步/True|57步/True|
|14401000|45步/False|120步/False|220步/False|

14401000三种设置逐步物理重放与记录状态误差为0、v3未知0，均没有持续夹持成功窗口，不是成功后掉落。末端靠近目标初始公开位置约16–17cm仍不能单凭距离证明夹住。预算对照用830源，后续接触前静态场景修复用748源；按源分别保留。

OpenPI官方LIBERO评测：每5控制步重新规划，初始等待10步；spatial/object/goal/10/90预算分别220/280/300/520/400。官方没有我们的3块/5mm规则。[源码](https://github.com/Physical-Intelligence/openpi/blob/main/examples/libero/main.py)。

|绑定缺失|公开归因|修复证据|
|---|---|---|
|object_task_t3|BBQ误作ketchup，与正确ketchup同时存在|通用观察恢复CPU通过；物理未验证|
|object_task_t4|奶油奶酪误作milk，与正确milk同时存在|同上|
|goal_swap_t4|盘子误作bowl，与正确bowl同时存在|同上|

一条旧17401000分支（45控制步）耗时2241.86秒：

|部分|秒|
|---|---:|
|preparation_and_planning|0.04|
|pi05_inference|1.78|
|sam_rpc|2077.21|
|private_metrology|2.81|
|handoff|0.13|
|other_rgbd_geometry_control_io|159.87|

SAM RPC占92.7%，含服务排队/传输。准备/规划0.04秒只计fork内预备动作，初始候选规划在fork前，后继规划另计，不能把它解释为全部规划开销。

164后继扫掠的6个公开阻塞点位于主视角(433–443,261–263)的夹爪附近，距最近手指视觉凸包3.0–4.9mm、距预测持物面7.3–15.1mm；端点缓存未保存后继该视角的当前语义目标，不能据此断言新帧也无分割。暂只能归为自体边缘/持物归属待判，未扩大滤波或碰撞容差。

物理执行源7484079b91021a7eebbcd48756c4eb3a047d1563；保存原版子任务入口59f7daf807f0022e3645dc83b2b5c6a158915cb5；准备脚本ae578bb3修正仅持有目标源才属于place阶段。新manifest SHA256：9a66314ef33e8a079d4dca44252ab23a935bc49b1db553b90595e6355d5b3908。

本轮CPU：13项诊断/汇总测试通过；Ruff聚焦脚本通过。首次测试命令误写文件名未运行，已改为test_original_hybrid_fork_summary.py后通过。真实startup第一次因未设LIBERO_TYPE=standard退出1，未产生物理请求；修启动helper后4/4通过。正式提交器先遇Slurm数组显示ID与Raw ID差异，未提交作业；改用JobIDRaw核验后正式提交10653。
