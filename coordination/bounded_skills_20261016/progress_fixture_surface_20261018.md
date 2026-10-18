Codex1 / Codex2：公开接触几何和 chunk 回执修复已推送 harness-v5，源码 739fa4b40160d19bfe760bd3aaaf67947be543df。未训练模型。

源码快照：/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_fixture_surface_20261018_739fa4b；archive SHA256 8df4439001c8ad5bbd90d02055d44d9449020d2d4c6b48de5e852152b3947d0b。入口 scripts.probe_bounded_feasibility:episode；解释器 /public/home/sunyihan/rpent_libero_eval/.venv/bin/python（保留 venv 路径，不 resolve symlink）。220 原版状态的绝对路径/文件 CPU 预检通过；同 launcher startup8845_24已提交，尚未作为完整任务结果。真实启动通过后重跑11类代表状态的新/旧chunk规则配对，oracle关闭π0.5。只用node02，nice=500，不动protected/held/running任务。

修复1（947103e）：相对 nudge/rotate_wrist 继承前缀建立的测量接触锚点；不会误用自由运动/异步路线。修复2（279bd38）：用两指实际凸包闭合扫掠估夹持开度，替代整条斜把手投影。保存的抽屉公开点云：估计67.700→30.461mm，实际40.712mm；仍用原有±15mm容差，无判据放宽。修复3（739fa4b）：chunk执行前保存其引用锚点的当前公开点云，后续将前缀预期位移作用于该点云，再以新RGB-D身份重叠和三轴1cm位移界验证；不以SAM可见表面中心漂移代替实际物体运动。真实旧点云诊断：2cm预期通过（残余界3.742mm），0/4cm错误预期均被拒。

CPU：最终245 passed，源码在140.54s测试期间未变；报告reports/chunk_anchor_surface_CPU_20261018.json；仅CPU接口和保存点云证据，不宣称物理修复完成。

接口：schema仍bounded-skills/3，SHA256 7082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3；SKILL_PACKAGE_SPEC SHA256 2bb0ea99f3ffc7cf65a1f76deecf05cfea7fb0a81a4a26877f1d7f529b36f4fd。参数和公开字段无新增。执行中前缀字段和可接受集合格式保持已交付的/3合同。

墙钟：source334144f/job8831已闭合6对，碗/盒/容器/杯新旧均成功，开/关抽屉新失败旧成功，仍逐局保留。各仅1状态，不能推广为每类20局或资格结果。12臂时间分解见reports/wall_time_8831_closed6_20261018.json/.md。新/旧墙钟：碗451.6/508.1，盒259.7/388.0，容器228.8/279.9，杯1140.2/1237.8秒；抽屉失败臂不是提速证据。感知和规划占主导，仿真/渲染为7–35秒。新规则4个抓放臂的执行中感知分别127.2、103.3、79.3、205.0秒；下一步评估只测回执所需对象，但当前未削减任何感知。b877de8仅复用完全相同点云剔除，CPU局部42→10次、24.061→6.056秒，尚待新物理墙钟。

候选压缩既有CPU证据：同一公开请求56→56个候选，5个不可行紧凑标记；Qwen tokenizer 13181→12558 tokens。无任务目标过滤。单例格式结果，非模型性能结论。π0.5异步/合同测试也在最终245项检查内；本轮上限作业不调用π0.5。

所有确认池排除仍有效。当前是开发诊断，失败记录不覆盖；完成上限后才做两个对照、K1/K4及分叉。
