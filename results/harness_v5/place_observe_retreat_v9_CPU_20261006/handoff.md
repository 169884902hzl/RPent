# place v9 / 原40选择批提交交接

准备完成，尚未提交 GPU 作业；由 root 在 COORDINATION 先登记再提交。40 案例全部原样保留，20 个唯一原始状态，8 片各 5 个注册案例；不筛持物真、不筛公开可绑定、不删失败，不授确认或冻结资格。

修复：`subtask_place_observe_retreat_v9` 默认 off。VLA 放置后同姿态 v7 重测仍缺测时，执行现有真实 retreat（夹爪命令为 0，保留当前 actuator target），再采两帧公共 RGB-D。新 source_step 必须严格递增且 visible；WaypointNotReached、native interruption、重复或缺测继续 null。strict6 的开度、on=.90 / in=.85 footprint、on 1cm support gap 等所有旧门槛保持，不补造 opening、不用 private truth 控制动作。观察诊断只进原始证据，不新增状态文本行。

两组共用 setup 修复：`grasp_category_profiles_v1=true`、`grasp_independent_views_v1=true`、`grasp_thin_aperture_v1=true` 和原公共 calibration。原 setup 仍为 bowl/direct，但 runtime 选择 C：observed episode start → 原版完整指令风格的 pi0_pick160 → paired independent public grasp validator；不携带 PAN profile 或 trial_lift 覆盖。原40 instruction/runtime身份均保留。

VLA 组的额外开关：v9=true、retreat_clearance_v1=true。测得清障路径避免从抽屉接触位直接斜穿家具，current 组保持旧退避。这是联合方法选择批，不声称纯 v9 因果，也不拿其结果替代独立确认。v7/v8 继续保留。

CPU：新回归 13 例，连同 v8/绑定/runtime/支持面/测量 identity 共 252 例通过；compile/diff 通过。真实 /tmp launcher 用 CUDA_VISIBLE_DEVICES="" 跑过 8 片 preflight，全部 returncode=0；核对原始 state SHA、显式依赖文件、校准公共 XML、manifest、完整 5 控制步动作块契约。16 个源码文件 SHA 均与固定 source commit 一致。0 新物理试验，0 训练行。

## 固定运行身份

- source：`/public/home/sunyihan/rpent_libero_eval/source_v5_place_observe_retreat_v9_20261006`
- commit：`8fe6b188bac4d233f4c4d632a38d6dc5f724f583`（不混 root 后续未测 drawer 修改）
- code-only archive：`/public/home/sunyihan/rpent_libero_eval/source_v5_place_observe_retreat_v9_20261006.tar`；SHA `13b608f53827aec3179ecc90f77bb37c8b4b10bf5a070afd74de4b4a37b7afae`；4,812,800 bytes
- manifest：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_observe_retreat_v9_CPU_20261006/preparation/registered/observe_retreat_v9_same40_category_selection.json`；SHA `76f4f8db4c6e3581af275bbe4823a9918193188fa6d8549e6872921fdd04900d`
- launcher：`/tmp/run_v5_place_observe_retreat_v9_same40_category_20261006.sbatch`；SHA `9047d98d4f1ead4a15317d269b22e3f8e45489e24ec184cb9a0947a59e55d424`
- output：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_observe_retreat_v9_CPU_20261006/physical_same40/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}`
- calibration：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/gripper513_original_opening_calibration_20261005/runtime_calibration.json`；SHA `d4d977a5e5c23a23d80983ab34a4958373c6103035c2156ced24038204e4ca1c`
- preflight：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_observe_retreat_v9_CPU_20261006/preparation/registered/launcher_preflight.json`；SHA `10df236da6c6de71fecf3d40d91fcfbee4d3dcfb600a2d7d11a30c2ebf2a9566`

## 计划提交命令

以下为 8 片完整命令；root 实时核空卡并将同时运行上限设为当时空卡数，不绑定节点、不加无关依赖。作业号待实际 sbatch 回传，不预填。

```bash
sbatch --array=0-7%8 --export=ALL,PLACE560_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_place_observe_retreat_v9_20261006,PLACE560_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_observe_retreat_v9_CPU_20261006/preparation/registered/observe_retreat_v9_same40_category_selection.json,PLACE560_MANIFEST_SHA=76f4f8db4c6e3581af275bbe4823a9918193188fa6d8549e6872921fdd04900d,PLACE560_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_observe_retreat_v9_CPU_20261006/physical_same40,PLACE560_SHARDS=8,PLACE560_PREFLIGHT_ONLY=0 /tmp/run_v5_place_observe_retreat_v9_same40_category_20261006.sbatch
```

实际物理 runner：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u -m scripts.probe_v5_skill501_original --manifest "$PLACE560_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --output "$PLACE560_BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"`，cwd 固定 source，PYTHONPATH 固定 source。

报告必须同时保留 40 注册分母、setup 公私混淆、真实执行/新增完成/已有完成、on/in及current/VLA分层、独立公共验证器 null 覆盖、实际退避触发与 fresh两帧、真实 release、执行/基础设施失败。与旧4279逐例保留并列；未锁定 π0.5 RNG，不将跨轮差异视为因果。

尚未修复：6 个 cabinet/drawer 唯一绑定缺口由 root 感知/部件线继续定位，本份保留它们原样尝试；新物理确认 v9 对5个 in/VLA 缺测的覆盖效果；独立100原版新状态确认在选择修复后另外登记，完整保留所有失败。
