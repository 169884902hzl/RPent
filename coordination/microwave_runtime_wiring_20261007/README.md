# 微波炉公开时序采集与块间停止接线

CPU实现已完成；尚未运行GPU物理smoke，不是技能资格结果。原4340的4/10、
公开10/10缺测记录保留。本开发方案只复用其中访问过的原版90任务33/init0，
不生成训练行，不把该状态算独立确认。

入口：`robots/libero/v5_microwave_capture.py::MicrowaveEndpointCapture`。
`start()`采动作前两帧，`observe(chunks)`采当前块后的两帧；后者可直接作为
`V5Executor.vla_act(..., public_stop=callback)`。`make_microwave_public_stop`
返回回调和同一可变ledger，运行时在`last_verification_measurements.microwave_temporal`
保存ledger。`articulate`与开/关门的`vla_subtask`均已接入。

开关默认关闭：

- `--microwave-temporal-capture-v1`：启用采集，任何endpoint都不会中止接触策略。
- `--microwave-temporal-stop-v1`：隐含采集；只有稳定公开endpoint=true时阻止下一VLA块。
- `--microwave-temporal-capture-every-v1 1`：默认每块检查，可显式改频率。

使用现有`MeasuredScene.measure_fixture_endpoint(..., temporal_capture=True)`做SAM独立
固定框/活动门绑定。仅这个参数开启时额外保存掩码及测量源元数据，旧调用的字段不变。
两相机当前点云在world/metre坐标融合；每视角唯一绑定，法向差>10°或法向距离>1.5cm
则缺测。保存每个云、mask、RGB、world map的显式路径/SHA，记录当前step与相机贡献。
固定面的几何fallback只使用公开RGB-D的实际点集，并保存它与活动门mask的实测重叠。
公开高分辨率相机校准另以1024px保存，避免把旧256px的K误标成高分辨率校准。
校准来源是现有`env.get_camera_meta`公开接口；底层仍是RPent的当前仿真相机标定，
没有新增对象真值测量。

每阶段采两次新快照，之间实际执行6个中性保持控制（按0.05s/control开发配置，0.3s），
并记录controls与配置dt。远端已核对RLinf将cfg.init_params传给原版LIBERO；现有
env构造未覆盖control_freq，当前安装的LIBERO bddl_base_domain.py:63默认20Hz，
robosuite base.py:207设control_timestep=1/control_freq。此为当前源码配置证据，
尚未从物理smoke的实例RPC读取频率；smoke仍须核对。若实际配置不一致应按真实
频率调整控制数，不能声称满足0.3s仿真稳定间隔。如果原生中止/预算使实际间隔不足，保留缺测；不能拿SAM等待的
墙钟代替物理稳定时间。时间戳取真实capture完成时间，step严格递增。

撤臂先用本体感知与已测量fixture bbox算实际间距；有夹持接触时先松夹，再向上清出
该测量bbox。不把目标位置或servo返回值当作已经撤离。实际EEF距bbox>=12cm，且
当前robot SAM mask对固定面和活动门的遮挡都<=2%时，才标为撤臂/无遮挡。robot mask
没测到不等于无遮挡。撤离不可达、绑定位姿歧义、旧帧、相机冲突、遮挡等均为
unmeasured，不允许stop。此撤臂/hold会改变π0.5中途姿态和技能时序，必须在开发
物理记录里检查，当前不宣称保持技能成功率。

沿用时序几何原型的开发角阈值（开>=30°、关<=15°）及参考/稳定判据；这些参数还没
取得物理确认资格。代码没有新增审批/qualification门。默认off，开发可显式开启并
保留失败后修复；确认/最终规则由既有协议管理。公共稳定端点停止后不再额外进行
原单帧articulate_view_retreat，避免重复撤离把门再次拖离终点。

## 原版一局真实启动smoke

`prepare_smoke.py`只读取指定manifest；默认max_chunks=8，用于启动/测量检查，
不是成功率对照。先capture-only，再显式stop开发配置。两份本机CPU计划
`smoke_capture1.json` / `smoke_stop1.json`已经生成；远端应使用同一脚本从远端
显式manifest重新生成，使parent_manifest也是远端可追溯路径。

```bash
python "$SOURCE/coordination/microwave_runtime_wiring_20261007/prepare_smoke.py" \
  --source-manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json \
  --source-identity-file "$SOURCE_IDENTITY_FILE" --output "$SMOKE_PLAN"
LIBERO_TYPE=standard python "$SOURCE/scripts/probe_v5_microwave_public571.py" \
  --manifest "$SMOKE_PLAN" --output "$SMOKE_OUT" --shard-index 0 --shards 1
```

须使用新不可变快照与已有同一个launcher的实际环境/Python/资产配置，先CPU校验
所有路径及hash，再真实启动一局至第一次物理请求。没有实际请求之前不放行数组。
这里不提交作业，不改queue或共享服务。stop版生成加`--enable-stop`，保留上一尝试。
原runner根据constructor签名读取condition overrides，已支持上述新参数，无需改runner。
应使用同目录`run_smoke.sbatch`，而不是旧571launcher（它硬编码旧commit与10case）。
该launcher要求绝对路径，检查实际调用依赖含typed_choice_eval与两个新增modules，
跑现有manifest hash预检。可以先`MICROWAVE_CPU_ONLY=1 bash .../run_smoke.sbatch`；
正式真实一局后再次检查runner退出、startup_error与requested_controls>0，写入
`physical_startup_contract.json`。缺任何依赖/真实请求时退出非0。使用了原571 public
parent adapter，维持唯一当前公开实体绑定，不让general oracle依私有symbol绑定。

smoke应检查：两阶段>=2帧、mask独立性、每视角贡献、实际6controls保持、撤臂真实
结果、robot mask缺测比例、门法向变化，以及stop后是否又执行下一块。记录中的
`private_after`与逐块joint真值仍只作后验标签，不给公开stop callback。

窄测试：

```bash
python -m pytest tests/unit_tests/robots/libero/test_v5_microwave_capture.py \
  tests/unit_tests/robots/libero/test_v5_microwave_door_temporal.py \
  tests/unit_tests/robots/libero/test_v5_drawer_public_stop.py \
  tests/unit_tests/robots/libero/test_v5_microwave_identity.py \
  tests/unit_tests/robots/libero/test_v5_temporal_endpoint_stop.py -q
```

80项通过（新增capture19项）。覆盖实际撤臂与命令不同、松夹失败、独立点集/双视角冲突、遮挡缺测、
真正稳定间隔被中断、默认off、capture-only不stop、块间到端点立即停，以及私有
诊断不能改变公开几何判定。尚无新的物理准确率；小量物理接线检查预计2–4小时，
SAM绑定/撤臂若缺测需要按日志继续修，而非调阈值补endpoint。
