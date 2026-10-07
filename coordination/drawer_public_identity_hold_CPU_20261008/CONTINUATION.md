# Drawer v9 immutable 单局 smoke 与可运行验证器数据

源码 commit `40583453969c083e6146b38eced7f93b2d6e5646`。快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_drawer_endpoint_hold_v9_20261008`。archive `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/drawer_endpoint_hold_v9_4058345_20261008.tar.gz`，SHA256 `0cee5fd5c9a57bf14243d16c8a08f8cdb76a2d578aadf1486f669a48436183ec`。

单局 manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_endpoint_hold_v9_CPU_20261008/preparation/same_t23_s20.json`，SHA256 `bba74d6cdd94fbd40567cb93ca2fb23e53b690cdc1dbc7fd5f87ce052c7d1139`。沿旧 4327 同源 manifest 读取已访问原版 LIBERO-90 t23/s20，原状态 bytes/hash、完整任务句、setup、160 完整块、私有只读评分不变。它只做错误面 abstention 与 every-block 公开记录，不是确认批。

actual launcher CPU 前检已运行，exit 0；显式文件、source/archive、producer、原版状态 SHA 全部通过，state_hashes_checked=1，未启动 SAM/π0.5/env/GPU。报告 `.../preparation/actual_launcher_preflight.json`，SHA256 `81ae6b4fde94f95ac17d56f7c1d9e652f5ec56038f269047421d618ab87fcdc5`。

准备后的实际执行命令（**本子代理未提交**；由主代理先写共享回执与 GPU 预约后执行）：

```bash
env DRAWER_V9_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer_endpoint_hold_v9_20261008 \
  DRAWER_V9_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_endpoint_hold_v9_CPU_20261008/preparation/same_t23_s20.json \
  DRAWER_V9_MANIFEST_SHA=bba74d6cdd94fbd40567cb93ca2fb23e53b690cdc1dbc7fd5f87ce052c7d1139 \
  DRAWER_V9_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_endpoint_hold_v9_CPU_20261008/physical_smoke \
  sbatch --parsable --nice=400 /public/home/sunyihan/rpent_libero_eval/source_v5_drawer_endpoint_hold_v9_20261008/coordination/drawer_public_identity_hold_CPU_20261008/run_single_case.sbatch
```

1 GPU、无节点或依赖绑定；提交后输出目录 `.../physical_smoke/job<真实作业号>`。原启动脚本 SHA256 `d8d9f5467d4223efebf1d93288c7d70538701688a925f3948e996d503e954f6a`；drawer v9模块 SHA256 `286ab9ead168cc8da7ef84389ceccc4a03bd59d3e0e6ef18c683ea29445a266d`；快照 runtime SHA256 `9a0f6efa5322c3dee48f1f2d59bcec36c592eadc7dcdc0488baa60b3ba5b7f88`。

## 公开多帧编码完成

使用快照内共享编码器 profile `world_xy_grid_v1` 完成 306×2578 公开特征，全部 finite；保留 80 unknown 行，226 有完整时序。状态组隔离保持 14 train / 6 validation。

| split/mode | false 标签 | true 标签 |
|---|---:|---:|
| train/open | 18 | 31 |
| validation/open | 9 | 12 |
| train/close | 20 | 107 |
| validation/close | 16 | 13 |

报告：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/temporal_encoded_r2/report.json`，SHA256 `67a7adfbce5d42d28388d78b628c80ef65b728a0886376a13b8b7e6a20bfe627`。

可执行数据：同目录 `features.npz`，SHA256 `9b6629dbde2260070132dfa11bfbc40e1d76d4dee93bbe3f0cb4441c7e0cf996`；encoder SHA256 `49f0ed2928628abd3c8123008e164bc62b20ab9e58a7b4baa73536def7333d23`。特征构建先固定公开输入，再按 sample_id 加入隔离私有 endpoint booleans；私有 joint/goal 均不进 x。没有训练验证器模型、没有 runtime 准入、没有新物理成绩。当前 close 验证器未达到95%可靠性，仍须新状态独立确认。

首次编码在 live远端目录因其尚未含 `scripts.prepare_v5_temporal_endpoint_cpu` 导入失败；已经修为完整 immutable 快照相同命令，在 r2 完成。未用临时另一套 encoder，不修改旧失败证据。

CPU 编码实际命令：

```bash
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer_endpoint_hold_v9_20261008 \
  /public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u \
  /public/home/sunyihan/rpent_libero_eval/source_v5_drawer_endpoint_hold_v9_20261008/coordination/drawer_public_identity_hold_CPU_20261008/encode_public_temporal_inputs.py \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/temporal_inputs_r1/manifest.json \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/temporal_encoded_r2
```
