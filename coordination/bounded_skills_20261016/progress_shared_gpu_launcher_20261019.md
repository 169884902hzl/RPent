N=8 已选定：同一登记工作集从 17.0394 提升到 77.8066 局/GPU小时，4.5663 倍；N=12 为 76.8328，未继续提升。
历史→新串行三例差异为零；24 局 N4/N8 的选择、仿真步数和结果与新串行完全相同；选定 N8 的完整重放通过。
原版旧启动器完成164/220，剩余56局已通过真实启动检查并提交10446，三个分片正在物理执行。
D2 的10439_1在首次动作前恢复哈希失败；CPU重现定位到forward改写warmstart，修复后两状态哈希及后继控制一致，10461_0等待真实启动。
只改启动和私有诊断恢复兼容层；原版ec89f74、D2 75ce7d53技能/规划源码不变，不训练；下一步由Codex3验证D2物理调用后放行40局。

## 吞吐与一致性

| 并发 N | 完整局数 | 局/GPU小时 | SAM p50/p95 秒 | GPU均值 | 显存峰 MiB | CPU峰 核 | RSS求和峰 GB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 24 | 17.039449 | 0.513306 / 0.558074 | 6.0817% | 9766 | 1.0590 | 8.985 |
| 4 | 24 | 59.542044 | 0.599385 / 1.615592 | 14.1769% | 12495 | 4.1894 | 20.142 |
| 8 | 24 | 77.806600 | 2.041456 / 4.044072 | 20.2201% | 16316 | 7.9986 | 35.939 |
| 12 | 24 | 76.832818 | 3.979679 / 6.233530 | 21.3801% | 20009 | 11.9974 | 51.330 |

- 原版碗、放入容器、开火各8个官方状态，init0–7；不是全部类别的吞吐估计。每档23成功、1失败、worker_error=0，失败也计入完整局吞吐。
- 计时包含每局新进程、环境和收尾，不含共享服务首次加载和独立启动预检。RSS为进程求和，可能重复共享页。GPU为同型号RTX 5880 Ada 48GB。
- 三例按类别预登记，历史→新串行差异0。所有24局N4/N8与新N1的选择序列、仿真步数、成功状态一致；选定N8再次完整重放后，正式三例一致性通过，adoption_ready=true。
- 10327_0 COMPLETED 0:0；登录节点finalizer独立重数通过，没有重跑物理。10240_0的自然运行保留为独立重复研究，不合并到原220分母。
- 本地摘要：[shared_study_final_20261019.json](reports/shared_study_final_20261019.json)。远端根目录：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/shared_throughput_20261019/job10327_0/`，完整结果在`study_summary.json`和`offline_study_summary.json`，逐次记录在各`measurements/N*/`及`consistency/N8/`。

## 启动器与资源

每GPU作业一个SAM3，D2再共享一个π0.5；每局fresh exec、独立EGL/环境/RNG/IK；局内候选仍串行。逐次保存SAM延迟、worker日志和结果，每2秒采样资源。worker错误非零退出，其他独立回合继续。

仅node02、nice500，每GPU作业20CPU/140G；四作业合计80CPU/560G。Codex2无GPU作业时借第四卡，有排队时调低后继并发，不取消运行任务。c5/c6/rf和held不改动。现有登录节点监控每60秒调资源、每10分钟核sacct。

原版生产启动器：`/public/home/sunyihan/rpent_libero_eval/launcher_shared_20261019_14b98fc0f5c9/`，SHA256 `14b98fc0f5c9c3454c136d6b1b75120f25223424e494d306e7b9a9a0d4cffa55`。

- 原版准备`results/bounded_skills/shared_remaining_20261019/preparation/r2/`；10439_0真实启动4/4通过。10446数组索引0,2,4,6，N8，合计56局，保留完整失败。
- D2准备`preparation/r3_d2_restore/`，只包含40个D2回合，原版56局不重复提交。D2启动重试10461_0，等下一可用时隙；正式数组尚未放行。
- 最新D2诊断启动器：`launcher_shared_20261019_40bd0a28a26b/`，SHA256 `40bd0a28a26be7c95bd962f80ceea818ba20ed81a1738f3bfcdcce5ea8d77078`。

## D2启动错误和有证据的修复

- 10202_0：GL环境模块晚于MuJoCo导入，已在启动器先导入固定source的env_server，不修改源码快照。
- 10439_1 FAILED 1:0，2/2在首次动作前抛`RuntimeError: fork did not restore full physics/controller/RNG/counter identity`；没有冒称VLA物理启动成功，原始记录保留。
- 同BDD L和保存物理状态的CPU MuJoCo重现：restore中的forward改写`qacc_warmstart`。状态0差39个标量，状态1差50个标量；D2诊断启动层在观测重建后原样写回保存warmstart。完整哈希检查和所有字段保持原样，不改变动作执行规则。
- 两状态修复后物理/控制器/RNG哈希与保存值精确相同；每个状态重复同一组5步控制，后继哈希也一致。相机关闭、wrapper计数复制的CPU证明不能替代完整GPU分叉检查。
- 证据：[状态0](reports/D2_restore_CPU_corrected_0_20261019.json)、[状态1](reports/D2_restore_CPU_corrected_1_20261019.json)。复现脚本`check_shared_d2_restore_CPU_20261019.py`。
- 当前12项CPU测试通过：`.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_shared_gpu_launcher.py`。包含真实子进程隔离、错误非零退出、固定source预检、GL导入顺序、warmstart恢复、登录节点收尾及正式分母去重；既有unknown timeout warning保留。

所有确认状态永久排除训练。新启动预检和研究重复状态不进入原220或D2结果分母；物理结果以各生产worker完整summary为准。

正式原版汇总脚本：`scripts/summarize_shared_original_20261019.py`（本coordination目录内）。按已登记batch和assignment读取164局旧记录及56局新记录；拒绝重复、startup和错配状态。首个中间快照为172/220已完成、131成功、worker_error=0；尚未完成的48局不记失败。
