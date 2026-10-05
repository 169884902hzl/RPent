# Codex3：边沿接近物理 smoke 提交前回执

已读取并接受用户 10/05 01:45 与 03:10 的抓取实验要求；已核对 3550_0–5
正式产物、失败分类及当前 COORDINATION。保持总体真值 >=95%、每类 >=90%、
每类至少 100 次首次抓取、验证器一致率 >=95%、双方误判率及 Wilson 95% CI。
预算/alias/验证器调整不凑成五种真正不同方法；失败全保留。不改测试集或标准。

6/18 正式分片已闭合，bottle 三条件 98/95/96，bowl 99/86/84。
碗类 high10 的 30 次真失败均未用满动作块预算，17 次来自原版 Long3。
本轮检验边沿接近假设；不凭单例宣布根因解决。
已有 3550、3554、3565 不取消、不改源码或依赖、不重复提交。

GPU 预约：3550 完成后，3565 的一张卡 + 本 smoke 一张卡，合计最多两张。
新 smoke 申请 1GPU / 8CPU / 90GB / 1h / nice1000，不设节点绑定。
提交前已完成远端独立快照、12 条 smoke 与 1200 条 full 登记；
full 仅准备，不提交。源文件 import、launcher bash -n 已通过，
36 项 binding / verifier / measured geometry 测试通过；真实 smoke 未运行。

源码快照：
`/public/home/sunyihan/rpent_libero_eval/source_v5_grasp473_measured_rim_20261005/`，
commit `e3d9906`，源码 archive SHA256
`85c9051be9b5d04042356453e22e1d181db87e8c6b64ed01b2200f88332d111e`。
入口 `scripts/probe_v5_grasp449_20261005.py::measured_rim_approach`。
原版任务，同场景两个条件：bounds-centre control / measured-rim；
仅对 bowl/mug/ramekin 换 RGB-D 观测边沿 xy。高度仍为顶面 +10cm，
短提示词/alias、160 动作块、public pick stop、单帧 verifier 均相同；
非容器类别位置相同，不能将其噪声差异归因于边沿。私有真值不控制动作。

准备目录：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp473_measured_rim_20261005/preparation/`。
smoke.json SHA256 `a973a75913040c4d7f011aa07dc02ae156a4afb9244cd10896969c02a5067c03`；
full.json SHA256 `379969d190e04d8ae3e5350045b486f9fdea03843357002f577983a77fdb727c`。
launcher SHA256 `a9ecd8658a1cb70c352e2836b07ba7c2eb84c5701b95e3da96a8aaa35af23c1b`。

回执推送并 append 共享 COORD 后执行：
`sbatch --parsable --dependency=afterany:3550 runtime_launchers/run_v5_grasp473_rim_smoke.sbatch`。
作业号未分配，提交后立即追加；输出
`results/harness_v5/grasp473_measured_rim_20261005/smoke_job<assigned_job_id>/`。

无异议。限制：12 次只是工具/假设 smoke，不满足 100/class 资格；
五种正式方法失败阈值尚未达到。当前不跑 A3/A4、不冻结、不准入训练。
本轮原版诊断 init0–49 不入训练；不读 PRO/human/sealed/Jev 作训练输入。
如后续采纳任何新回执语义，先交 Codex1/2 重渲染，不改既有产物。
