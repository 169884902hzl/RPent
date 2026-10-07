# 580 r2：异常退出边界与 SAM 查询量修复

已修两个有证据的错误路径：

1. parent `probe_public_red_recovery.main()` 在共享 SAM/VLA
   `daemon.start()/wait_for_ready()` 后才创建 case/row；提前失败没有 episode。
   collector 现在在外层保存 `startup_error`、异常、阶段、已确认控制数、
   `physical_execution_started=false`、`model_or_skill_success=null`，返回非零。
2. r1 `run_phases()` 捕获 off 错误后只写 `execution_error`，最终仍固定
   写 recorded。若第160块已计数、其后的 public capture 失败，parent 的
   `chunks=160/actions=800` 检查可能通过。r2 立即传播该错误，保留
   `partial_collection.json` 和已有 ledger；不再写 completed。

没有新增技能资格门。合法但失败的任务端点仍保留私有 false 标签；不会
凭 on/off 真值筛选或停止动作。退出0只要求这次已授权的固定采集确实
执行并完整写账，不代表技能达到门槛，也不代表 control ROI 可测。

## 失败判据

- import/manifest/asset/source/preflight 或共享服务启动失败：非零；没有
  已确认 contact trace 时为 startup_error，模型/技能成绩为空。
- VLA 或 recovery 抛异常、固定控制数不足、public capture/写盘失败、
  private scoring 失败：非零；已有 contact trace 时为 collection_error。
- parent 空返回0、没有 episode/真实计数/完整160条 public ledger，或
  三帧 source_step 不递增：collector 非零并保存 boundary。
- 保存的 parent episode 必须无 infrastructure failure，off 不得为
  execution_error；须有 on prefix、off160×5、当前进程的 trace 计数与
  完整 ledger。成功结果保存在 `collector_boundary.json`。
- 已存在的输出目录被拒绝时，错误写在旁边的新 sidecar，不覆盖旧记录。

## 实际 CPU 证据

真实 `.venv` prepare-only **3/3 通过**，每份核对1个 raw-state SHA 与
23个源码文件，未启动仿真或 GPU 服务。

外部子进程测试 **2/2 通过**，使用真实 parent 入口：

| 注入情形 | 实际退出码 | 保存状态 | 已确认 controls | 物理启动 | 成绩 |
|---|---:|---|---:|---|---|
| ProcessDaemon.start 在启动进程前抛错 | 1 | startup_error | 0 | false | null |
| parent 不写数据而空返回0 | 1 | startup_error | 0 | false | null |

两者都保存1行 episode、完整 stderr 和边界记录。外部 driver 实際命令：

```bash
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r2/cpu_boundary_tests/startup_fault/driver.py
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r2/cpu_boundary_tests/empty_zero_exit/driver.py
```

证据：同包 `cpu_boundary_tests/external_boundary_summary.json`，SHA
`54703ae9f875eed8525781decb682dc32aa66e1e0ce6b1cd4dcb7dae1e04e672`。

末块采集失败回归通过：CPU fake executor 已报告160块/800 controls，
第160块 public capture 故意抛 OSError；public ledger 只有159行，错误
向上抛出，partial 的 off 状态是 execution_error，没有 recorded。
固定正常流程也通过：172次 capture 调用、3次 control 几何提取、
36 hold controls、两次 release/retreat、800 off controls。
这些 fake executor 数字只证明控制流，不算实际物理成绩。

## 查询量与公开证据

control/feature SAM 从每状态2,100请求降为 **36请求**：仅 before_off、
after_release、after_retreat 三个时刻，各2相机×6查询。此数不包含继承的
scene refresh 查询。三帧序列首帧复用对应 stage 的已捕获几何和文件，
不再对同一帧重复6查询。逐 off chunk 仅保存新 RGB-D/world/标定文件
引用和 SHA、本体及命令；不复制大数组、不请求 SAM。缓存几何明确写
`is_current=false/current_control_binding=null`，不冒充当前可见 control。
新 raw frames 可在 CPU 离线重新测量；没有公开接触传感器，不填私有值。

## r2 产物与提交入口

准确 manifest：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r2/capture_manifest.json`

manifest SHA：`1ed09b14fa58d6309b4aef79fa59090eeb6d49eb29c5e27b3693e7840552fc2f`

collector SHA：`e583ad659d4f9addfd7200d24aba80e9519e0339cea004cc1f10ceb70f33431f`

launcher SHA：`7888230bccc05af057c5dc3f6642b7bb947ac8a918f71654b681e58e989753e9`

producer SHA：`89408903add134b35ab5ff5b99e5bb72a07d3563afb3e95c61fa7da48906cd00`

producer 现已复制到包内的 `prepare_control_packet_source.py` 并固定 SHA，
后续主仓库 preparer 改动不会使这个 r2 包的源码引用漂移。
源码、运行解释器、SAM/VLA 的本机动态 HTTP 服务方式与 r1相同。
`commands.json` 保存完整环境与实际 preflight 命令。

```bash
sbatch --array=0-0%1 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r2/run_capture.sbatch
```

新输出：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_original_r2_20261007/probe_jobJOBID/part0`。

子代理没有提交 GPU。父代理报告旧4458已经取消并保留日志，r1源码可由
commit `6ffacf3` 恢复；旧 packet 未覆盖。r2仅训练分区seed0–2，验证
seed3–4不回流，已登记确认重叠0；registry完整性仍pending。物理请求、
当前 control 几何召回、清遮挡效果和端点回弹仍待单状态 smoke。
