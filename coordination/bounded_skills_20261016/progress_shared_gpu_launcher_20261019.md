单卡并发选 N=8：17.0394 → 77.8066 局/GPU小时，实测 4.5663 倍；独立重复为 79.1028、4.6423 倍，N12 均未继续提升。
三例历史→新串行基线差异为0；24局N4/N8与新N1的选择、仿真步数、最终结果完全一致，选定N8完整重放通过。
原版220局由164个旧记录和10446的56局组成；最新r3快照完成200/220、成功131、失败69、进程错误0，余20局仍运行/排队。
D2已通过真实调用；另发现私有计量缺模型归档环境变量。修复启动器已通过14项CPU测试和22/22条CPU隔离证据检查，10476等待同启动器物理检查。
原版ec89f74、D2 75ce7d53的技能/规划源码不变，无训练；Codex3继续等待作业、修启动故障，10476通过后补提D240局，旧诊断保留。

## 吞吐与一致性

| N | 完整局数 | 局/GPU小时 | SAM p50/p95 秒 | GPU均值 | 显存峰 MiB | CPU峰 核 | RSS求和峰 GB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 24 | 17.039449 | 0.513306 / 0.558074 | 6.0817% | 9766 | 1.0590 | 8.985 |
| 4 | 24 | 59.542044 | 0.599385 / 1.615592 | 14.1769% | 12495 | 4.1894 | 20.142 |
| 8 | 24 | 77.806600 | 2.041456 / 4.044072 | 20.2201% | 16316 | 7.9986 | 35.939 |
| 12 | 24 | 76.832818 | 3.979679 / 6.233530 | 21.3801% | 20009 | 11.9974 | 51.330 |

- 登记工作集为碗、放入容器、开火各8个官方状态，init0–7；不是全部类别或D2长VLA分支的吞吐估计。每档23成功、1失败，全部计入完整局吞吐，worker_error=0。
- 计时含每局新进程/环境/收尾，不含一次共享服务加载和独立预检。10327服务加载13.03秒。RSS按进程求和，可能重复共享页。GPU同为RTX5880 Ada 48GB。
- 三例按类别预登记。历史→新串行差异0，正式并发验收据此要求精确一致；24局N4/N8与新N1全部一致，选定N8另做完整重放。
- 10327_0 COMPLETED 0:0，登录节点finalizer重数通过。10240_0自然完成的独立重复也选N8：N4/N8/N12为58.8199/79.1028/75.0006局/GPU小时，所有档无进程错误，一致性通过。重复状态不增加独立分母。
- [最终吞吐摘要](reports/shared_study_final_20261019.json)、[全部24局配对](reports/shared_all24_N4_N8_consistency_20261019.json)。远端：`results/bounded_skills/shared_throughput_20261019/job10327_0/{study_summary,offline_study_summary}.json`，逐次记录在`measurements/N*/`及`consistency/N8/`。

## 启动与资源

每GPU作业一个SAM3，D2另共享一个π0.5；每局fresh exec、独立EGL/环境/RNG/IK。局内候选保持串行。保存逐次SAM延迟、每局日志、assignment、worker summary，每2秒采样资源。worker错误非零退出，其余回合继续。

仅node02、nice500，每GPU作业20CPU/140G，四作业80CPU/560G。Codex2无GPU作业时借第四卡；有排队则收紧后继并发，不取消运行任务。c5/c6/rf和held未改动。登录节点资源控制每60秒、账目日志每10分钟；当前唯一控制器收据`reports/monitor_shared_archive_repair_20261019.json`，PID1209049，优先启动10476。

- 原版source：`/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_support_plane_20261018_ec89f74`；生产启动器`launcher_shared_20261019_14b98fc0f5c9/`，SHA256 `14b98fc0f5c9c3454c136d6b1b75120f25223424e494d306e7b9a9a0d4cffa55`。
- 原版准备`results/bounded_skills/shared_remaining_20261019/preparation/r2/`，10439_0真实启动4/4通过，10446索引0/2/4/6，共56局。汇总脚本只按登记batch和assignment取结果，拒绝重复、错配和startup；不计吞吐研究或诊断重放。
- D2 source：`source_bounded_hybrid_progress_20261019_75ce7d53`。该源码在本次吞吐任务前已登记，用于显式披露不覆盖的存储进度规则；没有为PRO临时加规则。
- 最新D2准备`shared_remaining_20261019/preparation/r7_d2_archive/`。启动器`launcher_shared_20261019_8fcc579c17ec/`，SHA256 `8fcc579c17ec180b5803f85b3229d65aa7609f3faaa4b4d64b55d92c298cdae6`。
- 10476_0待真实首次VLA物理步检查；通过后再放行修复后的D2正式40局。10473_0缺归档的旧开发诊断自然运行；仅PENDING的10473_1/2已取消，收据`reports/shared_D2_missing_archive_transition_20261019.json`。旧记录不删除，不按成功挑选重跑。

## 已定位的启动问题

1. 10202：GL模块晚于MuJoCo导入。启动器先导入固定source的env_server。
2. 10439：恢复中的forward改写qacc_warmstart；10461仍失败，因为RLinf用spawn，父进程钩子没有进入环境子进程。启动工厂在子进程内安装同一私有恢复顺序修复；保留完整哈希检查。两状态CPU直接恢复和实际RLinf spawn均哈希精确相等，重复5步控制后继也相同。证据`D2_restore_CPU_corrected_*`、`D2_restore_CPU_spawn_*`。
3. 10467：诊断trial深拷贝首请求，内容与恢复缓存相同但对象身份不同。只在D2调用层对规范化字节完全相同的首请求复用缓存；过期/不同请求仍拒绝，adapter.execute保持原样。证据`D2_restored_request_identity_CPU_20261019.json`。
4. 10468 COMPLETED 0:0，2/2实际VLA调用13/9次、物理90/43步，回执为completion_lost_during_handoff、handoff_braking_screen_rejected；这是接口证据，不是技能成功。旧预检等整技能耗16:47。10472的首次物理步预检COMPLETED 0:0，2/2各一次推理后实际步数+1，耗3:08，success=null，不进最终结果分母。
5. 旧D2私有计量unknown原文为`counterfactual_batch_failed:KeyError('LIBERO_GRASP_DIAGNOSTIC_MODELS')`。旧单局sbatch也未配置此变量。每个新worker设置独立绝对模型归档路径，原私有计量代码自行归档live MuJoCo模型。两状态CPU重建补归档后各11/11隔离证据known；仅证明管道，不把重建标签写回原始记录，不改v3判据。

14项CPU测试通过：`.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_shared_gpu_launcher.py`；覆盖真实子进程隔离/归档环境、错误非零退出、固定源码预检、GL导入顺序、warmstart恢复、请求身份、首步因果凭据、分母去重和登录节点收尾。既有unknown timeout警告保留。私有归档真实CPU检查在`D2_archive_CPU_{0,1}_20261019.json`，scope明确为诊断，未采用为回合标签。

源文件完整性报告`reports/shared_source_integrity_20261019.json`：两固定源码各6个关键技能/规划/分支状态/contract文件均与指定Git commit字节相同。最新启动器修复提交35747dad已普通推送user-fork/harness-v5；没有合并或强推。

所有确认状态永久排除训练。PRO D2全部是隔离开发诊断，不进入训练、手册、memory或VLA历史成功率卡。原版完整结果及分类Wilson区间以逐次记录为准；r3快照在`reports/original220_shared_interim_20261019_r3.json`。

新增真实RLinf spawn CPU端到端验证：`D2_archive_CPU_spawn_0_20261019.json`，子进程内恢复哈希和5步后继一致性通过，`v5_measure_grasp_hold`实际RPC返回11/11隔离证据known。仅用于验证环境传播/归档管道，CPU重建标签不采用为回合结果。GPU启动器仍8fcc579c；仅CPU复现脚本新增此检查路径。
