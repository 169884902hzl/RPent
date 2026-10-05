# Codex3 skill503：资源生效与平底锅完整探索两组

已核实3616、3619、3620 ArrayTaskThrottle=6，两条仅资源等待的依赖已移除，ReqNodeList/ExcNodeList均空。3619_3在接触前因LIBERO90 env_meta诊断标志未传到客户端失败；原日志与ledger保留，零调用启动失败不是模型成绩。正在修strict meta参数传递，不修改已有源码快照或确认配方。当前7个技能分片运行，剩余资源由Slurm调度。

3616_0/1各100条完整探索记录、200/200 choices SHA核对通过，真值全部已知，执行/基础设施错误0。不是确认批，不授冻结资格；每组50个唯一原版状态各reset两次，Wilson按名义100试次，需披露场景内相关性。

|条件|真值首次抓取|Wilson95%|验证一致率|误报/真失败|漏判/真成功|
|---|---:|---|---:|---:|---:|
|original_pan_name160|83/100|74.45–89.11%|100%|0/17|0/83|
|original_pan_handle160|65/100|55.25–73.64%|98%|0/35|2/65|

把手组16次测量前置拒绝，仍保留在完整100分母；其余84次执行contact。centre组100次执行contact。把手组1次public budget stop；centre为0。centre的17次真失败中7次有手指支撑但下沿抬离不足，10次最终无目标抬升/手指支撑。把手组16次前置拒绝、18次最终未抬起/持住、1次下沿抬离不足。不能把public early_success当真值成功。

产物：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp503_pan_closed200_CPU_20261005/report/summary.json`，SHA `0bddf08aed7d8fdd167bf00f13996fd67b2a051eaa54f2710af70d37ad03d385`；同目录trials SHA `26184611eb425b5b72bd99adf221747593c487ce5e12b5ce374304affd84ccb0`。原始两片SHA为`140437dd52fe89bb2f255ff850583c066168c1a051964beb3db92b69c4158895`和`713081f9b85f73506b97660b8f8db681f0ca2151cf6a29ce0fc962a9e055bd22`。

实际CPU命令（远端repo根，exit0）：

```bash
.venv/bin/python runtime_launchers/diagnose_v5_grasp503_closed.py --ledger results/harness_v5/grasp490_pan_retry1_20261005/full_job3616/part0/episodes.jsonl --ledger results/harness_v5/grasp490_pan_retry1_20261005/full_job3616/part1/episodes.jsonl --prefix-rows 100 --expected-per-arm 100 --output results/harness_v5/grasp503_pan_closed200_CPU_20261005
```

脚本只扩展固定前缀工具允许读满已闭合探索arm；不改标签、原ledger或运行中作业。平底锅尚未达到确认门槛，继续原版完整子任务句与更大预算对照；统一技能候选默认融合，新冻结标准190/200不变。
