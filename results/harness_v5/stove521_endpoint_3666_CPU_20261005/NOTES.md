# 3666 原版灶台测量：真实动作与端点审计

3666 四分片均 COMPLETED，显式 manifest 覆盖原版 Goal task7 init0–9，10 回合、20 固定 on/off 宏动作。60 个测量时刻与标签同 source_step，120 个视角、240 次 SAM 查询；515 个 manifest/producer/测量引用文件 SHA 全一致，无执行异常，0 训练行，不是冻结或确认批。

| 固定宏动作 | 真值端点（退臂前/后） | 名义动作 | 实际动作 |
| --- | --- | --- | --- |
| on | turnon 10/10；turnoff 0/10 | 160 块 × 5 = 800 | 每局 212–229，合计 2,184 |
| off | turnon 10/10；turnoff 0/10 | 160 块 × 5 = 800 | 每局 160，合计 1,600 |

根因已追到 `V5EnvFacade.chunk_step`：原版 Goal7 的成功是 turnon；每块第一步原始 term=true 后，服务端截掉余下 4 动作。客户端 `V5SkillEnvClient.complete_skill()` 只隐藏客户端 terminated 属性，未改变服务端截块。因而 off 160 块只有 160 实际动作，不能视为完成了 800 动作后仍无能关闭。所有原始失败与 3666 结果保留。

退臂恢复未改变 on/off 真值。公开线圈测量从开启状态下 agentview 17/20、wrist 5/20 可见，提升到两视角均 20/20；所有 off 后退臂观测都仍红，现有保守验证器在两视角各 10/10 明确判 off=false，不存在把 unknown 当 off 完成的放行。

240 查询产出 14 实例。掩码叠图逐个核对：6 是 wrist 真实灶台控制圆盘（6/10 off-after 视角）；3 是酒瓶；5 是柜子抽屉把手。14 实例云和掩码均已核 SHA。真实圆盘整体云 PCA 伸长比只有 1.05–1.10，圆盘全云轴不能当操纵杆方向；其与测量 shell 的 xy 最近距离最大 4.8 cm。该批没有一个真实 off 端点，也没有 off 的几何对照，不能据此宣称控制方向足以验证 off。

`sam_queries_montage.png` 是所有 14 个实例的公共 RGB+mask 叠图；`instance_visual_audit.json` 记录人工图像类别，仅用于诊断。`endpoint_pairs.json` 保留逐 seed、phase、pre/post 的私有真值和 qpos，未进入公共状态或控制。

已修独立诊断服务器 `robots/libero/v5_stove_probe_env.py`，仅限原版 Goal7 init0–9，on/off 各独立、固定 160×5 的 scope。scope 内保留每步原生终止标志，但完成全部五动作；外部 truncation 仍立即停；scope 外沿用正常 V5 native-stop。共享 `V5EnvFacade` 和评测终止规则未修改。每宏写 scope 的请求/实际动作、原生成功步数与 truncation；控制不使用私有谓词、qpos 或坐标。

同 10 原版初态的修复后开发协议：`results/harness_v5/stove523_fullchunks_original_20261005/preparation/stove_control_fullchunks.json`。4 分片 `%8`，每片 1 GPU/8 CPU，无绑定/依赖，0 训练行，非确认。27 个 focused CPU tests 通过，包括原版 goal 已成功时完整 5 动作、正常 scope 外仍只跑到原生终止、truncation 即停、固定动作预算与 on/off 出错后 scope 分离。bash syntax 通过。新 GPU 测量尚由父代理提交。

审计命令：

```bash
PYTHONPATH=. .venv/bin/python scripts/audit_v5_stove521_3666.py \
  --manifest results/harness_v5/stove521_endpoint_original_20261005/preparation/stove_control.json \
  --job-root results/harness_v5/stove521_endpoint_original_20261005/probe_job3666 \
  --output results/harness_v5/stove521_endpoint_3666_CPU_20261005/audit_v2
```

远端审计目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove521_endpoint_3666_CPU_20261005/audit_v2`。本地 `audit/` 下 report/actions 已更新为该版；其余 5 个 JSON 为同一次完整引用审计，内容未改。

| 产物 | SHA256 |
| --- | --- |
| report.json | 57504d42e152fb1e4f7c5c7e8465e250951e6a601a901b40c7fc155fb7b0b84c |
| actions.json | 497c7bd9b3905c258c6e56229928a15352b88dde6d9b6bdb1763b74fbef91c1b |
| instance_visual_audit.json | ab745f8599d8c7ee0a664e90121976960fc85d0a0294ad72745817d0634ed291 |
| sam_queries_montage.png | ef37fede70b1d5051444199a3ea6c81b207bad62b279dc9cafe82c2da56b26f7 |
| stove523 manifest | 14e3dbde9930393a0961ec3a6c181859f800a78b725947dbc9a8fe7061445812 |
| independent diagnostic server | 81b0c17833be393fb1bcbfe23ac3595332f05a76e616b7c6d71845778401b4bd |
| updated stove521 probe | 1ef3326c7437a3b39220b40518146703e941257a87fcea1f95d387341e12255e |
| stove523 launcher | 1857f49d6ae22e63b2916f95cbd92cc6c960649e00fae530494096d1b09aa04d |

下一批先核实际控制数与原生 latch，再看真实 off 的几何可答性。不把暗线圈或原版 on 成功当 off。
