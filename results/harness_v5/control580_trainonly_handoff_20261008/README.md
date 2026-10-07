# control580 r4 train-only 时序验证器 CPU 交接

已真实跑通首个完整物理源的公开特征编码、标签后置连接、固定 epoch CPU 拟合和实际 runtime infer 概率对齐。没有修改旧 trainer、runtime、规划器或停止规则。

源码 commit：`2528b3590d9dfaf3acce22fa6e2c32244d2fe5d2`

不可变六文件源码快照：
`/public/home/sunyihan/rpent_libero_eval/source_v5_control580_trainonly_20261008`

解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`

入口：`scripts.prepare_v5_temporal_control_trainonly_20261008.prepare`、`scripts.train_v5_temporal_control_trainonly_20261008.train`。

复用 `v5_temporal_verifier` 的 before + 最近3帧双视角 RGB-D、本体特征、`world_xy_grid_v1` 和 `baseline_relative_v1`。拟合使用既有 MLP32、AdamW(lr=.001, weight_decay=.03)，固定 300 epoch、seed577；不做早停、不读独立 validation、不拟合或准入停止阈值。

## 源与严格配对

registry 明确登记三条 train 原状态：seed0 = 4505/part0；seed1/2 = 4511/part1、part2。所有读取均来自 registry、manifest、已记录 frame/ledger 的显式路径，不枚举 artifacts。val3/4 只登记排除名字，未打开其状态或轨迹。

registry：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_trainonly_CPU_20261008/preparation/train_registry.json`

SHA：`4df8dccc3077447409e44714880af637219fcf170754b94d240db803eb867a02`

公共图像和 world 点云按保存的 SHA 核对，机器人观测来自执行块的公开 proprioception；fixture bounds 只来自 before_off 的 perception shell。全部公共特征算完后，才读取私有 off 端点标签。标签连接按 raw_state_sha256 + off phase + chunk_index +累计controls，逐行保存公开源和私有源的 path、SHA、行号。关节角不进入特征、公共行、运行时控制或停止。私有评分故障/公开源不足保持 unknown，未完成状态保持 pending。

精确配对文件：
`.../dataset_first_completed/paired_samples.jsonl`

SHA：`c469ec60165a2b9b255b5cef7effa8c353c32d39e3d4f4df8641fc577939af20`

## 已运行的单状态开发结果

首批 320 行 = 正类47 / 负类271 / unknown2。unknown 为第1/2块尚不足3个当前帧，未误记为负类。source 4511 的两个状态仍 pending，未读取半成品或以零填充训练标签。

dataset manifest：`.../dataset_first_completed/dataset_manifest.json`

SHA：`b7f336ef04360776659aa2507ec313bd6b977e23f3192ff1edb5d409a7f76e49`

模型：`.../fit_first_completed/temporal_mlp32.npz`

SHA：`c31877ba9789c0dfe1cf43c2c6fc1cec39a84573f20a7ef750d74a9fd2d8e235`

318 个可用训练帧，固定0.5分类点的 TP46 / FP0 / FN1 / TN271，训练内 AUROC1.0，Brier0.002474；actual runtime infer 的概率误差最大 2.70e-7，默认 stop=false。只有1个状态，按 train 状态留一评估为 unknown，独立 validation 资格 pending。训练内准确率不能作为 ≥95% 一致率的准入证据。

样本均为 contact_postchunk。没有声称机械臂已撤离或无遮挡；现行 control pose / directed angle 仍缺测。最终物理停止效果与独立确认仍未验证。

## 剩余两状态完成后

使用同一 registry 重新编码到新的输出目录（不覆盖首批）。生产器只接收已完成、2400 controls 的完整物理源；缺少源会在 pending_cases 中明确标注。固定 epoch 最终拟合只使用已测得正/负类；某个按状态留一折的剩余训练数据不足两类时，该折保留 unknown。

```bash
cd /tmp
export PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_control580_trainonly_20261008
export CUDA_VISIBLE_DEVICES=-1 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -m scripts.prepare_v5_temporal_control_trainonly_20261008 \
  --registry /public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_trainonly_CPU_20261008/preparation/train_registry.json \
  --registry-sha256 4df8dccc3077447409e44714880af637219fcf170754b94d240db803eb867a02 \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_trainonly_CPU_20261008/dataset_all_train_states
```

读取新 dataset_manifest.json 的 SHA 后，调用相同快照中的 `train_v5_temporal_control_trainonly_20261008`，传 `--dataset-manifest`、`--dataset-manifest-sha256`、`--source-commit 2528b3590d9dfaf3acce22fa6e2c32244d2fe5d2`，写到新的 fit 目录。脚本自动生成按 train 原状态留一的开发指标；这些结果仍不使用 val3/4，也不替代独立确认。encoder/source/files 的 SHA 任一变化即拒绝读取。

10 个相关隔离回归全部通过。单类或缺测数据不创建分类器；公共向量计算完成前不打开私有标签；未知行不计负类。CPU 拟合没有启动 GPU 服务。
