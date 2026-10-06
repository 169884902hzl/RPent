# Codex3 runtime553 修复后完整冒烟预回执

已读取并接受用户10/06 00:52队列、独立确认标准、显式manifest隔离和无节点绑定；旧确认失败保留，无异议。4186完成20局：原版7/10、开发6/10，205/205测量回执，vla_subtask选择48，连续重复最大2/累计最大5；完整报告SHA 74c71e2a82b00abe0e34083ab6e6ba756c01760a4f9f78e0ac6bcbae79e3751d。融合实体以rgbd_dual_view/1为主。唯一结构故障：GoalSwap t0 init41第5步3130token。

原因是中文环境回执JSON的Unicode转义。f8e5faa改UTF-8，同一完整请求3130→3034token，回执JSON值逐一相等、其他行和候选不变，无截断，3072硬上限不变。20项相关CPU检查通过。这会影响请求字节，正式通知Codex1/Codex2：冻结尚未通过，后续训练必须用最终冻结渲染器；不得把旧字节和新字节混为精确一致。证据源请求SHA 6123508006dd909a5e47766510fa81e48fefb7750e2d048a52ac71ccbd4ba3ac。

新SOURCE553快照f8e5faa，archiveSHA 896327b831c282f6b5c6f74bae47da5c5d08a9faa8bb2dec7d8bd1afb7cffacd。计划20局、8片×1GPU，依赖无、节点绑定无；身份/顺序/预算与4186一致，输出沿runtime536/job<JOB>/part0..7，manifestSHA cbe9aed4af21ae060ff706d8cf5673e63b2dfd6392ee89f1dd2e664e9bf0a4fd。8/8同入口CPU预检从/tmp通过，报告SHA 940a0d369d181cc5017ef66cb7067505aaf8ae37ca462a70bc1e72873f2e74b8。Slurm号在预回执推送后分配并立即追加；目前8卡在运行4149，不打断物理回合。

6cf2b1d的灶台修复也在该源码：RGB变暗不足以证明qpos<0的关闭端点，公共判定保留unknown；它尚未物理资格。5d812cf的平底锅跨视角handle测量只在新开发开关后，当前完整harness没有启用该专项开关，不改变4148原确认。第三法/stove测量专项独立开发。

实际拟执行命令：

```bash
env SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime553_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime553_smoke20_20261006/preparation sbatch --parsable --nice=0 --array=0-7%8 --job-name=libero-runtime553-smoke /public/home/sunyihan/rpent_libero_eval/source_v5_runtime553_20261006/scripts/run_v5_runtime536_smoke20.sbatch
```

未冻结、未开训练和大规模采集。临时4186调度已清理：26/26release成功，0错误，active=false；账本d62ea4e已推送，无回合中断。
