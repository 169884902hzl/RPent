多回合共享 SAM3 启动器已实现，7 项 CPU 测试通过；原版和 D2 两个固定源码入口的真实 CPU 预检均为 exit 0。
吞吐试验 10240_0 已在 04:28:52 PDT 启动，4/4 局产生首次物理请求、启动错误 0，正在跑 N1 完整基线；吞吐提升、选定 N 和整局一致性尚不能下结论。
原版技能/规划保持 ec89f74，D2 保持 75ce7d53；新代码只涉及启动、计时、资源调度和产物登记。
通过吞吐及一致性核对后，才将剩余原版和 D2 批次转到共享启动器；已运行作业自然结束，held 作业保持原样。

## 已实现

- 每 GPU 作业一个原有 SAM3 服务，各回合用独立 Python 解释器、环境、EGL 上下文、RNG 和 IK 状态；每回合内部的候选计算保持串行。
- 原样转发 SAM3 RPC，逐次保存请求延迟、错误、PID；每 2 秒采样进程树 CPU/RSS 和所分配 GPU 的利用率及显存。RSS 为进程求和，可能重复计入共享页，报告明确标注。
- 保存每局完整日志、assignment、worker summary；startup 未产生物理请求或 worker 出错均非零退出，其他独立回合继续并保留记录。
- 原版/D2 混合数组按分片选择固定 source、manifest、环境；共享模型服务从同一固定源码启动，局内执行接口不变。D2 使用已有逐次 sampling_seed 及服务端 RNG fork；该路径尚待真实并发验证。
- 每作业 20 CPU、140G、1 GPU；最多四作业为 80 CPU、560G。仅 node02、Nice500。监控按 Codex2 GPU 队列将后继并发限至 3 或 4，绝不取消已运行任务或 release held 作业。

## 已登记的实测

- 原版工作集：碗转移、放入容器、开火三个类别，官方 init0–7，共 24 局；按类别和 seed 登记，没有按成功筛选。
- 同一启动器先并行启动四局，须各自产生第一次物理请求，之后测 N=1、4、8、12；若吞吐仍提高至少 10%，继续 16、20。若到 20 仍增长，须继续测或报告明确的 CPU 饱和证据，不能凭配置上限宣称平台。
- 在三局完整串行基线已完成且与历史结果零差异后，登记第二个测量作业 10327。它从同一 24 局工作集依次测 N4/N8/N12，另作真实启动和选定 N 的整局一致性；N1 完整吞吐统计复用仍在自然运行的 10240，两个测量在不同的分配 GPU 上并行，不改工作集。原作业的后续重复档保留为独立记录，不合并成新的独立状态。
- 同一工作集测每小时完整回合数、SAM3 延迟 p50/p95、GPU 利用率和显存、CPU 和内存峰值；完整失败回合也计入吞吐。
- 先将前三个历史回合与新串行回放比较，再在选定并发负载下与并行回放比较。保存实际 chunk 选择序列、成功状态、仿真步；并行的各项差异不得大于串行自身基线。若超出，先追查，不切正式批次。
- 吞吐数字只代表这三个类别的登记工作集，不代表全部 220 局类别。

## 当前证据与路径

- GPU 试验冻结启动器：`/public/home/sunyihan/rpent_libero_eval/launcher_shared_20261019_ad3599a8b0e1/`；SHA256 `ad3599a8b0e1e1940b3f37c217b57c4eb254a0c0a0169ad5001130bc4224fc78`。
- 登记：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/shared_throughput_20261019/preparation/throughput_study_r1.json`；SHA256 `70cabe22543b2b70753f0f918162e405b1064bccffa9393a8bf92c6e82e0e7e9`。
- 单元测试：`.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_shared_gpu_launcher.py`，7 passed；现有 pytest 的 unknown `timeout` 警告不影响退出码。新增检查验证跨作业串行基线的读取，以及基线为零时拒绝并行选择差异。
- 两个固定源码的批次入口预检日志：同 preparation 目录的 `batch_interface_cpu_r1_0.log`、`batch_interface_cpu_r1_1.log`，分别 exit 0。
- GPU 作业及结果根：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/shared_throughput_20261019/job10240_0/`；物理启动和完整成绩必须以该目录实际产物为准。
- 首次物理请求证据：`reports/shared_job10240_real_startup_20261019.json`。启动段 SAM3 延迟 p50/p95=1.044/2.102 秒，GPU 峰值 12464 MiB、CPU 峰值 4.002 核、进程树 RSS 峰值 18207346688 字节；这些是启动段指标，不作为完整回合吞吐。
- `reports/shared_startup_first_chunk_comparison_20261019.json`：前三类首次 chunk 选择序列与历史记录完全一致，3/3；整局一致性仍待基线和选定并发档完成。
- `reports/shared_serial_three_baseline_20261019.json`：三局完整串行回放与历史的选择、成功状态、仿真步数差异均为零；并行验收据此要求这三项精确一致。
- 并发档作业 10327 的冻结启动器：`/public/home/sunyihan/rpent_libero_eval/launcher_shared_20261019_c133c49d192c/`，SHA256 `c133c49d192c31812f98638cf08bb7fa5e6baaa0043d34515c1177bc3ce55f04`；登记 `throughput_study_parallel_r2.json`，SHA256 `4a50b40d87b6f7fe2ce5148ebcbf027649ff2d1eb669256caf4d9561cd95a60d`。同源 CPU 预检 exit 0。
- 当前监控收据：`coordination/bounded_skills_20261016/reports/monitor_restart_shared_priority_20261019.json`；每 10 分钟核对 sacct，并给共享启动器下一可用时隙。
- 切换前原版登记 220 局，已有 140 局完整物理记录，执行异常 0；完整成绩以 `reports/original20_support_pre_shared_launcher_20261019.json` 为准。旧失败保留。
- `prepare_shared_remaining_20261019.py` 只有在 study summary 的一致性和实测吞吐同时通过后才登记正式替换计划；不重复已完成或仍自然运行的原版局，D2 保留全部 40 局分母。

本文件为进行中回执，尚未报告 GPU 加速或串并行等价通过。
