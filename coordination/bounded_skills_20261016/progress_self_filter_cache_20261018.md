Codex1 / Codex2：已推送harness-v5运行源码b6cf6d0e8cb3b1a5dcd1f6e9d698aafaad170556。它在da28708基础上只复用同一capture、同一不可变场景点云和完全相同输入像素的机械臂过滤结果；换capture、换几何、像素变化都重新计算。每次返回副本，调用方无法改坏缓存。没有删减测量、碰撞点、IK检查或回执条件。

性能证据来自保存的公开双视角RGB-D；恢复后的完整场景点云与原记录逐点相等。两种原版状态、两个视角、各四次调用，共16对新旧输出SHA全部一致。单次耗时如下：

| 状态/视角 | 原实现中位秒（4次） | 新实现首次秒 | 新实现命中中位秒（3次） |
| --- | --- | --- | --- |
| 碗/主视角 | 1.055 | 1.092 | 0.031 |
| 碗/腕部 | 1.023 | 1.025 | 0.030 |
| 开抽屉/主视角 | 1.055 | 1.095 | 0.029 |
| 开抽屉/腕部 | 1.055 | 1.038 | 0.031 |

这是CPU函数测量，不是整局墙钟改善或新的物理成功率。入口scripts/profile_saved_self_filter_CPU_20261018.py；原始时间与SHA：reports/self_filter_repetition_CPU_20261018.json、self_filter_cache_candidate_CPU_20261018.json；配对核对：self_filter_cache_paired_CPU_20261018.json。保存的choices摘要SHA仅覆盖首行，NPZ摘要覆盖完整文件；报告明确标注。私有任务真值没有参与这个计算。

最终源码8个相关CPU测试文件253 passed，148.636秒，测试期间源码SHA稳定。运行模块SHA256为041f63d05d6753eb30e6a272e705ac23700495c8fe511da55ad1689af017130b；回执reports/self_filter_cache_final_CPU_20261018.{json,log}。diff检查通过（原始pytest日志自带空白原样保留），Ruff相对HEAD无新增发现，原有6项未扩成无关格式修改。

快照/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_self_filter_20261018_b6cf6d0；archive SHA256 cc0a7bdc5578aa97a0c325d4a43aa4e30128cd41ef724f49b7a8edc78042bffe。schema bounded-skills/3及SHA256 7082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3保持不变。原220状态和绝对路径CPU预检通过；manifest SHA256 0040274982f0afd4e5f3e9858bef4e1050e4364bc6766be6e419df4ff4f61270。入口scripts.probe_bounded_feasibility:episode；解释器/public/home/sunyihan/rpent_libero_eval/.venv/bin/python，不resolve symlink。

同快照同launcher启动检查8860_24已提交，等待当前node02任务自然释放卡；尚未取得该源码的物理结果。通过真实物理请求后才放行碗/开抽屉两状态的新旧chunk时间配对。只替换自己的CPU监控，原running均保留；监控会继续覆盖8846、8858和8860，容量检查每分钟，sacct每10分钟。Codex2有GPU工作即降替补并发，不取消running。其余普通pending跟随当前优先队列；不动历史held、node01、c5/c6/rf。

da28708已有新物理进展：关抽屉新臂成功17决策/635步/2230.617秒，旧臂仍在跑；开抽屉新旧均成功，分别7/10决策、594/582步、1067.315/965.582秒，新规则墙钟+10.5%如实保留。它减少了决策次数，却没有在这个状态缩短整局时间，不能宣称总体加速。新代码仍需实测。所有失败与旧源码数据保留，尚未完成每类20局上限，不作冻结或确认结论。
