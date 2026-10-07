# 4499 首局布局恢复与启动核对

已完成：4499_0（COMPLETED，0:0，3m25s）。本子任务未提交任何 GPU 作业，未修改 COORDINATION、582r2 源码或旧产物。

## 实际结果

- `moka_layout_580100` 完整摩卡壶转移：原版目标 false → true；官方物理成功；公共严格放置验证 true。
- 35 个完整块，175 requested controls = 175 executed controls；无外部截断、无原生成功截块、无基础设施错误。
- 公共双帧 verdict `[true,true]`；6 个中性稳定控制步，物理间隔 0.3 秒。停止条件为公共 `placement_endpoint_verified`。
- 运行请求 1103 token、19 候选；实体行均为 `src=perception`，未发现私有目标符号、`oracle.status` 或 `sim_truth`。
- 模型调用前恢复的 rawstate 与注册落定状态完全相同；恢复误差、准备/恢复几何最大差额均为 0。sensor/controller reset 已由 worker 实际调用完成。
- 落定/恢复 SHA：`4c4f34e4dd33df2ae682e624d0bc240acc8e778cbd76791c9704af8712c6efa1`；提案 SHA：`5124916a9030431ffa49c6f6aecf508734ca7992c73e274f1a8c4b2e0749776c`。
- 融合开启；来源计数 agentview=46、wrist=1。开启融合不意味着每条测量都成功融合两个视角；终点两帧来源为 agentview。
- 回合墙钟 155.58 秒。仍沿用 582r2 的 320 块上限，未改变预算。

## 产物与身份

- 原始回合：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/startup_preflight/4499/probe/episodes.jsonl`
  - SHA：`844ff2cf19a4a16b58d4033f11a74af1fffcd5ac77161e46a899c35138447bd0`
- 实际请求：同目录 `moka_layout_580100/choices.jsonl`
  - SHA：`9d5820cb499d57db6021e8d95e37541e4267889b65556fe39413d8c4c265d560`
- 启动 contract：同目录 `contract.json`
  - SHA：`4b957eeff612e730e0e3b582259482b0bb982a70ed6daf85eccac070b9d7611d`
- 完整核对：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka4499_layout_startup_CPU_20261008/report.json`
  - SHA：`bad3318b27a3cc5d22a9b8d6dbc6fa812a2879a3daa56e9b3f02c9a08363f221`
- 审计脚本：同目录 `audit_startup.py`
  - SHA：`bf00206416c5782cf1d9cf8b6710b75be5631a859dfa32d518ae17eb82e2ee0d`
- 原 runtime：`/public/home/sunyihan/rpent_libero_eval/source_v5_placement582_r2_20261008`
  - tar SHA：`a176b90245d281e0edbe7637e01be47be98f7115331a25a2a55606d2ac9cf630`
- 24 态 manifest SHA：`58d59c72890b2511e2c933ded040bf0cb850c9f7735b7668381db0c249986c93`
- launcher SHA：`6596e8779bd45472c7d806e5256f5152849c89cc3eeb544eccc2fb57f2681c50`

## 审计命令

```bash
python3 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka4499_layout_startup_CPU_20261008/audit_startup.py \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/preparation_r2/moka_layout24.json \
  --manifest-sha256 58d59c72890b2511e2c933ded040bf0cb850c9f7735b7668381db0c249986c93 \
  --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/startup_preflight/4499/probe/episodes.jsonl \
  --contract /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/startup_preflight/4499/probe/contract.json \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka4499_layout_startup_CPU_20261008/report.json
```

已执行，exit 0，19 项完整性核对通过。不提交或重复执行任何物理回合。

## 解释限制与续接

- `choices.selected=grasp(e98,direct)` 是沿用原单技能 runner 的诊断占位。实际执行由转移 adapter 覆写成 `vla_subtask`，原始回执与完整 prompt 都记录了这点。不得当作模型选择，也不得作为单次抓取确认数据。
- `true_sustained_grasp=null`，本局只能报告完整转移成功。首局不证明整体/分类抓取门槛或 ≥100 次确认门槛。
- 24 个布局由已用官方基底生成，非未用官方初态，不主张 IID。额外 76 未包含、未提交。
- Runtime ledger 直接记录提案 SHA 与落定/恢复几何；提案 XYZ 可由原版基底几何加登记变换重建，不能声称已直接保存完整提案几何。
- 原 CPU `prep_gap` 记录和同预算落定审计均保留，未修改判定。
- 若父代理安排剩余 23 个状态，须排除 `moka_layout_580100`，并使用上述首局 contract。父代理负责 COORDINATION、提交与 push。
