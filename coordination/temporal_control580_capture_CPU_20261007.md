# 580：训练分区 control 证据采集包（CPU 准备）

已生成独立包：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/`。
准确 manifest 文件名为 `capture_manifest.json`，不是 `manifest.json`。
源码入口：`scripts/prepare_v5_temporal_control_capture_20261007.py`。

只复采原版 `libero_goal` task7 的既有 verifier-train seed0–2，共 3 个
raw states；seed3–4 validation 不回流。已登记确认 SHA 重叠为 0，完整确认
登记仍为 false/pending。该包不提供新的独立覆盖或确认资格。

## 已实现与已验证

继承固定 160×5 on 和 160×5 off 诊断，不改变技能停止判据。
关火前明确 release、retreat，再采双视角三帧；每个 off chunk 后采当前
公开 RGB-D、标定、SAM 控制部件/特征及唯一 parent 绑定。关火后松手、
撤臂各采三帧；每两帧间固定 6 个 hold controls。每状态共 175 次公开
采集、36 hold controls，约 2,100 次 SAM 查询，3 状态约 6,300 次。

每块记录公开命令及参数、动作计数、单调时钟起终点、EEF 起终点/位移、
夹爪开度。当前接口没有公开力/接触传感器，该字段明确为 null；不将
私有接触或关节量填入公开证据。当前没有实测 sim timestamp，只记录
source_step、采集时的 monotonic 时间和 nominal control interval。

“请求撤臂”不等于“测得无遮挡”。control ROI 只来自当前 SAM mask 与
深度几何的唯一 parent 关联；没有测到时保留 unmeasured。炉面/炉圈
不冒充开关本体。private on/off/intermediate/qpos 只在独立标签文件；
不影响 ROI、动作或 stop。stop 默认关闭，没有训练模型、调阈值或修改
runtime/toolkit。

真实 `.venv` prepare-only **3/3 通过**，每份核对 1 个原始状态 SHA 和
23 个源码文件，未启动仿真或 GPU 服务。源码与生成 collector 语法通过。
CPU fake executor 固定流程检查通过：160 off chunks、800 controls、
175 captures、36 holds、两次 release/retreat，仅私有 start/end 标注
调用，不读取 private 文件。以上均不算物理结果或 ROI 可用性。

## 源码与入口身份

物理 collector 复用不可变 source：
`/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006`。
完整导入文件在 `capture_manifest.json.source_files` 逐文件固定 SHA。
运行解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

SAM3 和 π0.5 由继承的 `probe_public_red_recovery.main()` 在同一作业内
通过 `ProcessDaemon` 启动，使用 `pick_free_port` 后建立本地 HTTP RPC，
不依赖 node01/node02 的外部服务。SAM module：
`robots.libero.v5_sam3_server`；π0.5 module：
`rpent.robots.components.pi05_vla_server --embodiment libero`。
原版环境/私有标签 module：`stove564_probe_env`，单独本地 HTTP 端口。
launcher 不绑定节点；并发由父代理按实时空卡调整。

manifest SHA256：
`f69eac761ea2fc776a2544c655da00394b84159b94d4057e745c721496f18f28`

collector SHA256：
`dc16bb81792f3c12c5208eaf7c7f16c95cb890bfc97657361b133f5afdef95d6`

launcher SHA256：
`c113ff92e9ac8892d0aff17fba7d3c7a9c432e2a1ae1911a1fa34af83e757df8`

preparer SHA256：
`ac8a329c2c8bf4441b50eb5202e923e7a1973bcedbdc231f7768e51bebe1d339`

handoff SHA256：
`26521918670bcca3d5f1ad748cce1a783ad87bdf99e4c2aeb17ed24ab0167443`

## 实际运行命令

完整 preparation 与已执行 3 条 preflight 命令保存在同包 `commands.json`。
物理命令尚未执行，父代理登记回执后先启动 shard0 到真实请求，保留
失败日志，再安排另两状态；本子代理未提交 GPU。

```bash
export PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off_physical_development_CPU_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_stop_selection_CPU_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config
export PI05_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/pi05
export SAM3_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/sam3/sam3.pt
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /tmp
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/capture_control_sequence.py --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/capture_manifest.json --manifest-sha256 f69eac761ea2fc776a2544c655da00394b84159b94d4057e745c721496f18f28 --shard-index 0 --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_original_20261007/probe_jobJOBID/part0
```

launcher 单状态入口（尚未执行）：

```bash
sbatch --array=0-0%1 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/run_capture.sbatch
```

后续剩余状态使用同 launcher 的 `--array=1-2%2`，不复跑已完成状态。
完整固定 160 块序列仅用于证据采集；不得解释成已准入的运行时 stop。

## 剩余项

物理启动/实际请求、pre-off 恢复是否清遮挡、control ROI 召回、固定块
是否会关火后回弹，均待真实采集；不能从 preflight 推断通过。完整确认
registry 尚未完成，本包限定开发采集，不宣称资格。
