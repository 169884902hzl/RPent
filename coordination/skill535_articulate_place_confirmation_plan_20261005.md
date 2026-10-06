# Skill535 开合/放置独立确认批计划（CPU 预登记草稿）

本草稿只记录新 manifest 生成器和 launcher 的只读准备；未提交 Slurm，不修改已有 3670/3684/3685，也没有训练行。生成器只读取标准 `libero_90`、原版 40-task catalog、529 access/reservation index，以及显式列出的当前 grasp manifest。公共运行时仍由 `probe_v5_skill501_original.py` 从测量实体生成状态和候选；BDDL 符号、目标谓词和仿真标签只留在私有诊断字段。

## 源码身份

|文件|SHA256|
|---|---|
|`scripts/prepare_v5_skill535_articulate_place_confirmation.py`|`1666548a9437b7a5b145bcc658c2c7be92306d9c39b4ee361ba162422d9b8973`|
|`scripts/run_v5_skill535_articulate_confirmation.sbatch`|`6c4c7a57dc445a7b8c63432182af5b8a99cdecc98cf6c69620e48b7359e3437c`|
|`scripts/run_v5_skill535_place_confirmation.sbatch`|`95faa7118ce240dd1d4d4a84805b14cefebba027f29a9d53612e5037996b0409`|
|probe `scripts/probe_v5_skill501_original.py`|`15778e26c767bba2c70fd7cf766caef42410061e79b87211a6de5478c45186b6`|

## 固定选择

- `drawer_open`: `libero_90` task 6/7/8 init 10--39 + task 11 init 10--19，共 100 个唯一 state。
- `drawer_close`: task 0/22/23 init 10--39 + task 28 init 10--19，共 100 个唯一 state。
- `microwave_open`, `microwave_close`: task 33/35 各 init 0--49，共 100 个唯一 state；两类共享同一组 reset state，但每类每个 state 只做一次 first attempt，且复用 529 明确 reservation，不从结果选样本。
- `stove_turn_on`: task 44 全 0--49，task 20/45 各 0--9、40--49，task 21 0--4、40--44，共 100；避开 529/3685 的 task 20/21 init 10--39。
- `stove_turn_off`: task 39 0--49，task 44 0--29，task 20 0--9、40--49，共 100；task 20/44 用显式 `turn_on` setup 后测关闭。
- `place_on`: task 10 + 25，各 0--49，共 100；`place_in`: task 2 + 24，各 0--49，共 100。

每类都复制为 `current160` 与 `vla_subtask160` 两个 arm，故 fixtures 1200 cases、place 400 cases；每个 type/arm 均 exactly 100。状态 SHA 在同一 type 内唯一，跨 microwave 的两种 mode 复用仅是预注册 reset，不混合 first-attempt 分母。准备阶段硬检查与原版 40 catalog、529 visited/reservation、3684/3685 当前 manifest 的 tuple/state-SHA 重叠；失败直接退出，不能换结果。

## 预生成命令（CPU；提交前在远端执行）

```bash
cd /public/home/sunyihan/rpent_libero_eval
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_skill535_articulate_place_20261005 \
  .venv/bin/python scripts/prepare_v5_skill535_articulate_place_confirmation.py \
  --libero-config-path runtime_config \
  --expected-asset-root .venv/lib/python3.10/site-packages/liberopro/liberopro \
  --base-config results/harness_v5/placement441_original_gate200_20261004/job3414/part0/libero_spatial_t0_s0/config.json \
  --base-config-sha256 3805be2a884256b8ce8e76c5c5d1507ce38bff8fcbeb8394d37cb87af83a547e \
  --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
  --reservation-index results/harness_v5/original90_access529_CPU_20261005/report/pools.json \
  --reservation-index-sha256 d64ea56a262cd5035e2892d2efdadd70257eecf2e072b19ab410d926fcb75ff1 \
  --microwave-reservation results/harness_v5/original90_access529_CPU_20261005/report/microwave_open_close_reserved.json \
  --microwave-reservation-sha256 20c47ff13744e55d2ae9cadb4d405acd1ec53c62df2bdbe87e0f12fe9d1611b4 \
  --access-index results/harness_v5/original90_access529_CPU_20261005/preparation/additional_index.json \
  --access-index-sha256 866cd80e179e0b75ec66ed49efe2cc17fb1aefbc1bc8c50148e25f2aec736261 \
  --original40-catalog results/harness_v5/skill500_original_comparisons_20261005/preparation_v2/original_tasks.json \
  --original40-catalog-sha256 05b67091af18cc15297c12852f49aa52b1401350bfd0b899c5f55d7561437122 \
  --prior-manifest results/harness_v5/grasp535_remaining_confirmation_CPU_20261005/frypan/full.json \
  --prior-manifest results/harness_v5/grasp535_remaining_confirmation_CPU_20261005/moka_pot/full.json \
  --output results/harness_v5/skill535_articulate_place_confirmation_20261005/preparation
```

输出 `preparation/fixtures.json` 与 `preparation/place.json` 的 SHA 由 `registration.json` 产生后再写入提交回执。若 529 index 的某个显式 reservation manifest 或当前 grasp manifest 缺失/哈希变化，命令应失败，不能静默去掉排除项。

## 提交命令模板（不在本草稿执行）

```bash
SKILL535_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_skill535_articulate_place_20261005 \
SKILL535_ARTICULATE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill535_articulate_place_confirmation_20261005/preparation/fixtures.json \
SKILL535_ARTICULATE_MANIFEST_SHA=<registration.json fixtures.sha256> \
SKILL535_PROBE_SHA=15778e26c767bba2c70fd7cf766caef42410061e79b87211a6de5478c45186b6 \
sbatch --parsable scripts/run_v5_skill535_articulate_confirmation.sbatch

SKILL535_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_skill535_articulate_place_20261005 \
SKILL535_PLACE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill535_articulate_place_confirmation_20261005/preparation/place.json \
SKILL535_PLACE_MANIFEST_SHA=<registration.json place.sha256> \
SKILL535_PROBE_SHA=15778e26c767bba2c70fd7cf766caef42410061e79b87211a6de5478c45186b6 \
sbatch --parsable scripts/run_v5_skill535_place_confirmation.sbatch
```

两数组均 `array=0-7%8`、1 GPU/片、无 `ReqNodeList`/`ExcNodeList`、无依赖；输出分别是
`results/harness_v5/skill535_articulate_confirmation_20261005/job<JOB>/part0--7` 和
`results/harness_v5/skill535_place_confirmation_20261005/job<JOB>/part0--7`。

确认汇总需按 type/arm 报告私有物理成功、public `true/false/null`（null=unmeasured）、FP/FN、Wilson 95% CI、首次 place（真实 verified grasp setup 条件）及严格验证器 precision/recall。该 manifest 的 `qualification_authorized=false`，确认批不进训练。
