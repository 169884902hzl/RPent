# SOURCE550 当前最佳配置 smoke20 CPU 准备包

CPU 准备通过：20 个唯一 episode，原版 10＋开发 10，身份、顺序、分片和预算与 job4103 完全相同。16 个显式计划文件已同步并逐文件核对 SHA；未提交 GPU、未写共享 COORDINATION、未修改 runtime。完整 launcher CPU 预检由主代理执行，物理结果尚未产生。

本运行用于开发质量检查，包含多项当前最佳配置更新，不是相对 job4103 的单因素对照，也不授予冻结资格。evaluation_only=true、training_allowed=false、qualification_authorized=false。

## 固定身份和产物

| 项目 | 路径或身份 | SHA-256 |
| --- | --- | --- |
| 源码快照 | `/public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006`；commit `0538169f4a2f355b429cdeb80848b10fac7bcace` | archive `11b8dce9eba8925fcc816ef87a442682bbaa70d0775ba50e9acb13a44f70671b` |
| manifest | `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime550_smoke20_20261006/preparation/manifest.json` | `8e66366f67ac7953c20935f2a8ff3aec2424f3c2636c68282af1c08911ad9d50` |
| CPU 报告 | 同目录 `cpu_preparation_report.json` | `d90db5146e3abce9131c10bcd1a157fc04701c14841b1d92ee69a1f38051994a` |
| 配置计划 | `/public/home/sunyihan/rpent_libero_eval/coordination/runtime550_smoke_preparation_20261006.json` | `2e3e6669e04b0d456033e1040514235de3ce80413db8744cfa8c78e2fd25c334` |
| CPU 构建器 | 同目录 `runtime550_smoke_preparation_20261006.py` | `6df8d793bf548b5852398f99b1ced7d056ff3883dcb78ea1036756b1f6e848b4` |
| 4103 manifest | `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime544_smoke20_20261006/preparation/manifest.json` | `3d06ce546475e1fbc4f06e3f3882d1e46e3e09aeb14cb6bcd3f94421d83bb690` |
| baseline | `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/placement442_model_regressions_20261004/preparation/A3-N/new41.json` | `5dc265748c3b7efa64c1d30ee137909f1e1f45a49aa818e2f4304ec1caeb4743` |
| v5@750 checkpoint | `/public/home/sunyihan/rd_instruction_20260923/v5r_20261001/v5_main_job3088/candidate_step750/pytorch_model.bin` | `b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb` |
| launcher | SOURCE550 下 `scripts/run_v5_runtime536_smoke20.sbatch` | `c38e7805b3bdd4a96cd1e3c5682e464e566f416290894dfae8a7101993956e0a` |

CPU 报告还记录了 serializer/runtime/recovery/action-effect/subtask/batch 的逐文件源码 SHA、服务依赖目录、checkpoint 注册身份和 4103 的既有资产校验证据。此准备阶段只 stat 原资产，不打开 BDDL/init payload，不读取 PRO 内容、102 条人工文本或 sealed_test_v4。checkpoint 只确认存在；实际加载身份由 launcher `/health` 核对。

## 配置

保持预算 `100 decisions / 80 chunks / 10000 episode steps / 3072 tokens`，保留未涉及的 baseline 参数。

明确设置 `strict_place_v6=true`，`strict_place_v1` 至 `strict_place_v5=false`；`fixture_in_contact_v1=true`、`target_cache_v1=true`。完整逐分片 diff 保存在 CPU 报告和各计划文件中。

下列 `prepare_v5_fixture540_handle_selection.py` 的 GEOMETRY_FLAGS 全部为 true：

```text
fixture_handle_geometry_v3
fixture_drawer_clouds_v2
fixture_endpoint_geometry_v3
microwave_door_cloud_v6
door_point_recall_v7
door_plane_consensus_v1
fixture_part_visibility_v2
fixture_part_prompt_v1
selected_fixture_target_v1
articulate_verification_v2
articulate_view_retreat_v1
microwave_recall_geometry_v3
microwave_instance_geometry_v4
stove_rgbd_verification_v1
appliance_support_crop_v5
instruction_queries_v1
wrist_recall_v1
```

`instruction_queries_v1` 和 `wrist_recall_v1` 在 manifest 中显式 pin 为 true。`observation_pose_v1` 仅用于第三法 fixture probe，没有加入 full-harness budget。

## 完整 launcher CPU 预检

本子任务已完成 CPU 输入/资源检查及 `bash -n`，没有执行下面会读取资产内容的完整预检。主代理已开始同入口的 8 片检查，当前输出登记在 `PREP/launcher_cpu_preflight/`；该组产物由主代理持有，不在本包中覆盖或更新。

以下为每片的完整调用，执行时从 `/tmp` 启动，避免本地 checkout 遮蔽 SOURCE550：

```bash
cd /tmp
for SMOKE550_PART in 0 1 2 3 4 5 6 7; do
  SLURM_ARRAY_TASK_ID="$SMOKE550_PART" \
  PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006 \
  LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config \
  LIBEROPRO_DATASET_PATH=/public/home/sunyihan/liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602 \
  /public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006/scripts/preflight_v5_runtime536_smoke.py \
    --root /public/home/sunyihan/rpent_libero_eval \
    --source /public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006 \
    --preparation /public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime550_smoke20_20261006/preparation \
    --output "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime550_smoke20_20261006/preparation/launcher_preflight/part${SMOKE550_PART}/preflight.json"
done
```

## 提交命令和输出

8 片、每片 1GPU；主代理提交前按 GPU 预约表和实时空卡数设置 `SMOKE550_CONCURRENCY`，最大 8，不绑定节点、不添加依赖。主代理先写预回执，再提交，并立即登记实际作业号和完整命令。下面只是建议调用，尚未执行：

```bash
SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006 \
SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime550_smoke20_20261006/preparation \
sbatch --parsable --array="0-7%${SMOKE550_CONCURRENCY:?set to live idle GPUs, at most eight}" \
  /public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006/scripts/run_v5_runtime536_smoke20.sbatch
```

launcher 沿用固定的 `runtime536` 输出名称，源码和输入均已显式指向 SOURCE550；实际结果将写入：

```text
/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7/{original,development}
```

无需外部模型 endpoint。launcher 动态启动本地 v5r System One，`v5_batch_eval.py` 动态启动共享本地 SAM3/π0.5。服务 `/health` 必须核对上表 checkpoint revision、`candidate_step750/pytorch_model.bin` 及 3072 context；失败不能算模型成绩。
