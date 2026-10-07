# 放置子任务公开终点停止

CPU实现与87项相关回归通过，未提交/运行GPU；不是物理资格结果。
入口 `robots/libero/v5_placement_endpoint_stop.py::make_placement_public_stop`，返回
用于 `vla_act(public_stop=...)` 的callback与逐块ledger。仅有物体、目标的
`vla_subtask`启用，其他技能/开合不受此开关影响。运行时与CLI的
`placement_endpoint_stop_v1` / `--placement-endpoint-stop-v1` 默认关闭。

每个VLA块完成后先读取同一动作的真实夹爪开度。开度<0.07m时不感知、
不添加任何保持控制，不强制松夹。开度达到要求后，使用当前agentview主视角
保留双视角融合，按选中的公开物体ID重新测量；间隔6个实际中性保持控制后
再测量一帧。不移臂、不retreat、不调用release，不使用私有完成状态作为stop。
目标使用接触前公开测量的静止缓存；抽屉、门等活动部件不能走这个缓存终点。

两帧实体必须可见、ID相同，source_step分别等于各自真实capture_step，且
`动作前baseline_step < 第一帧 < 第二帧`。旧缓存、缺测、未来目标、来源不是
perception等均不能停止。两个时刻的真实开度与EEF位置分别调用现有
`strict_place_verified_v6`；两个返回都必须为true。没有改变support、footprint、
稳定性、松夹、撤离或on/in阈值。EEF已经撤离由strict6衡量，probe不额外移臂
创造这个前提。悬空、目标外、未撤离、再次夹合或运动未稳定返回false；未知
support/interior返回null。目标的缓存坐标仍来自RGB-D，没有仿真物体坐标。

6个实际保持控制按当前20Hz配置为0.3s；当前远端源码证据是RLinf将init_params
传给LIBERO，env_server未覆盖control_freq，LIBERO默认20，robosuite以
1/control_freq设定control_timestep。ledger保存actual_hold_controls、configured
dt与capture墙钟间隔，不能用SAM等待时间冒充足够的仿真稳定时间。若预算/原生
中止使保持少于6controls，stop保持false/null。该原生状态只用来避免在中止后
追加保持，不用它证明放置完成；没有读取oracle.status或私有native latch。

通过时 `stop_reason=placement_endpoint_verified`，立即不再下发下一VLA块。
`execute_subtask`使用该公开ledger写verified回执并直接返回，避免后续重新接触
或另走松夹/撤离。ledger保存在`last_verification_measurements.placement_endpoint_stop`，
包含两帧测量、真实robot sensors、目标缓存来源、相机贡献和实际稳定控制数。
未通过的每次尝试保留。

## 下一不可变快照上的物理smoke

不修改581或其他正在运行的source包。用含本改动的新commit完整git archive，
逐文件SHA的source_snapshot须包含新module、runtime、harness、strict verifier、
Moka公开绑定wrapper、实际producer及finalizer依赖。继续使用已有修复后的
Moka同snapshot/同launcher真实启动检查，不沿用旧source identity。

已访问的10个原版Moka开发状态可再次用于开发，不能拿来算独立确认。保持其
原版完整指令、320块预算、原始重置状态和公开stove唯一绑定，先用明确指定的
一局真实运行，再放余量。只在新manifest的condition overrides里加本目录
`overrides.json`两项；不要改目标、阈值或用私有status控制完成。

若通过harness CLI调用，在既有完整配置上追加：

```bash
--placement-endpoint-stop-v1 --dual-view-fusion-v1
```

Moka wrapper经现有harness caller接收该flag，无需修改wrapper/launcher源码。
正式放行前，同source/launcher一局应产requested_controls>0并且startup_error
退出非0。启动日志与旧尝试均保留。

物理检查逐局报告：首次公开strict6端点的块号；停止块号；被停止后是否还有
VLA请求；VLA controls与新增hold controls分列；终点之后私有放置谓词是否
仍为true；公共positive/false/null及后验真值混淆矩阵。与同一visited状态的r5
开发记录配对，诊断之前达到后又退回是否消失。若公开观测一直缺失，本开关
不会自行release或改阈值，按当前图像/SAM绑定继续修。没有新资格门或审批流程。

窄测试：

```bash
python -m pytest tests/unit_tests/robots/libero/test_v5_placement_endpoint_stop.py \
  tests/unit_tests/robots/libero/test_v5_subtask_release_reverify.py \
  tests/unit_tests/robots/libero/test_v5_subtask_runtime_binding.py \
  tests/unit_tests/robots/libero/test_v5_subtask_observe_retreat.py \
  tests/unit_tests/robots/libero/test_v5_microwave_capture.py -q
```

87 passed。涵盖正例on/in、悬空/目标外/抖动、两帧中任何一个未松夹或未撤离、
cached/旧帧/同帧/错误capture step、私有标签不影响判定、截断稳定保持、未张夹
不probe、6中性controls、默认off、stop后没有下一块，以及通过后没有额外松夹/
位移/旧post-hoc测量。GPU精度、召回和物理成功率仍待smoke实测。
