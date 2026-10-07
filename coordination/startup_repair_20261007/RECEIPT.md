# Codex3 启动修复与终点验证（2026-10-07）

4369/4378 已完成原始日志核对。4369 的 delayed import 报错为：

```text
ModuleNotFoundError("No module named 'typed_choice_eval'")
```

4378 的结束记账报错为：

```text
FileNotFoundError(2, 'No such file or directory')
```

SOURCE571 的结束记账代码从快照根目录读 typed_choice_eval.py，但实际 supplement 在 manifest preparation 目录。该异常覆盖已发生的物理结果。4378_3（libero_90/task19/init3）已执行320块、1600 controls；期间174 controls曾达原生成功，末态done=false。保留这条首次物理失败，剩余分片排除它。4369只有0–3 FAILED，5–7 CANCELLED，4无sacct记录；4378八片FAILED，不能把所有旧尝试都说成零物理。

修复包含：显式依赖、实际import路径/SHA、完整traceback、同快照同launcher单局真实预检、正式数组匹配启动合同并剔除已执行状态，以及 startup_error 非零。39项相邻启动/基础设施回归和最新29项绑定/时序合同检查通过。

真实开发预检记录全部保留：

| 作业 | 结果 | 物理证据 |
| --- | --- | --- |
| 4399 | 排队时取消，0秒 | 无；远端wrapper版本不匹配 |
| 4406 | FAILED 1:0，64秒 | 无；harness/执行器时序参数版本不匹配 |
| 4408 | FAILED 1:0，71秒 | 无；启动与记账正常，但两个stove导致公共绑定歧义 |
| 4409 | COMPLETED 0:0，97秒 | 专家11VLA块+106放置运动步；SOURCE571行为的启动修复版 |
| 4410 | FAILED 1:0，3秒 | 无；错误纳入identity的可写pyc变化 |
| 4411 | FAILED 1:0，14分59秒 | NFS阻塞导致SAM启动300秒超时；0物理 |
| 4412 | COMPLETED 0:0，真实预检通过 | 抓取11块+放置115步 |
| 4413 | COMPLETED 0:0，真实预检通过 | 抓取11块+放置125步 |

r4保持SOURCE571行为，只修启动记账与摩卡公共目标绑定；新增时序模型在独立源码中开发。原4408测量的第二个stove bbox距公开EEF最近XY距离1.166m；wrapper以1.0m操作区过滤，保留全部公开测量/拒绝原因。过滤后仍须唯一，两个近stove或缺测均不执行；不从私有目标挑选。

r4远端源码：

`/public/home/sunyihan/rpent_libero_eval/source_v5_moka_startup_r4_20261007`

608显式源码文件；archive SHA256 `1f6bbf9f7b659ad7a4d89cc741604c8d52aa127723e49b74034bed751e2c0026`。

摩卡manifest：`results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/repair_r4/moka_visited10.json`，SHA256 `fe9cd53bc9e83d1405033e4bdbdfdd7689a6be5047b8a3fd5907354c5df1b458`。

专家/A3索引：`results/harness_v5/interim574_20261007/preparation/repair_r4/manifest.json`，SHA256 `a52d93d1d08d550988cd35fb80abe53fccedee416b9d6ffea2ae5b6d7b0c9c83`。

4379同类结束记账故障已止损：运行分片在当前回合完成后自然退出，part7保持hold，A3旧4390保持hold。153局均有物理轨迹，原startup_error ledger保留，不能当正式专家分数；13773 VLA块、83443脚本运动步是原记录的诊断合计。公开末状态133、私有末状态127只作诊断，曾成功后退回的六局另列于显式终态报告。

时序验证器先接入“测到终点立即停技能”，不是只做事后标签。默认关闭，缺测/模式或特征编码不匹配返回unknown；现有训练只支持turn_off。CPU578首轮使用5个原版选择状态，3训练/2验证，815注册行、483/322可测标签；验证AUROC0.9758，但阈值0.5下TP0/FP0/FN154/TN168，尚不合格。继续baseline-relative特征修复，不能调验证阈值宣称通过。确认状态不进训练，已知1315哈希排除清单完整性仍标pending。

微波炉方案见 `coordination/microwave_door_plane_offline_replay_20261007.md`。已有4340十个点云SHA/拟合重放10/10一致；9个实际请求仍缺测，不改判。撤臂后双视角多帧分别拟合固定框架与活动门平面，比较夹角/位置并要求稳定；遮挡、缺平面、多mask或冲突继续unmeasured。实现预计0.5–1天，离线/窄验证2–4小时；物理选择/确认批另需GPU。

## 续接修复

4416已实际进入技能，原生结果记official_success=true；随后`harness_v5_eval.py:829`和probe第658行写JSON报`TypeError: Object of type bool_ is not JSON serializable`，退出1:0。既有物理记录保留，不把它计作干净启动通过。7aa7a08只在日志写入边界把NumPy标量/数组转换成JSON值；15项窄检查通过，状态文本与技能规则未改。

r5源码`/public/home/sunyihan/rpent_libero_eval/source_v5_moka_startup_r5_20261007`，608显式文件，archive SHA256 `0690bc1ffd338f699e05d43070fcf929d6508e006684e32b6e95737e6264b882`。manifest SHA256 `5b5ad0b80c4502b753e11c1222a105d4d60e76905e4188826ef53b8fb4d5c48f`。同一launcher真实预检4425 **COMPLETED 0:0**，320块、1600 requested/executed controls，1447个control时刻原生成功，末态成功。公开`place_verified=null`（缺新鲜两帧），不算技能达标；这是访问过init0上的开发修复重放，不算独立确认。contract SHA256 `a0de75b7c9b5941308b09499d937ef75c8c1b744cdca797cff3e902d0e0989ba`。

修复后的interim专家4417和A3 4418已提交；各自先通过真实预检4412/4413。4417若为技能预检让卡，仅在当前回合结束后自然退出，完整回合保留；后续需按显式episode身份续跑。所有旧startup_error与旧物理153局继续保留。

微波炉原型已提交7514b32，后续开发停止开关修正为bcf210f，见`coordination/microwave_door_temporal_20261007/README.md`；25窄测试通过。公开采集与运行时停止接线进行中，预计0.5–1天，加2–4小时窄物理验证；没有资格结果。

时序CPU578与579均不能启用stop。578的train-only阈值在验证rawstate首次停止1/2正确；579改用固定世界XY网格，帧AUROC0.9933，但首次停止0/2正确（1早停、1漏停）。保留逐帧/逐状态失败，不能按帧级一致率放行。默认关闭，后续需要更多公开无遮挡/腕部视角变化和接触运动证据。

## 4430 后续开发修复

4430保留逐片记录。part1/init2没有物理控制：同一灶台的e11（融合双视角）与e47（agentview单视角）bbox几乎相同，但中心偏约4cm，旧按中心去重未合并。末段日志又报原文：

```text
TypeError: sequence item 0: expected str instance, dict found
```

位置为r5 launcher第202行`join(missing_controls)`，不是依赖导入问题。a1b99dc仅以当前公开bbox的3D IoU≥0.8、每边差≤2cm合并重复目标；原始实体和拒绝原因保留，仍不从私有目标选择。不同近灶台继续歧义。修正错误提示读case.name；startup/零物理仍非零退出。25项窄检查通过。

r6保持r5技能行为，不混入新时序或微波炉接口。源码`/public/home/sunyihan/rpent_libero_eval/source_v5_moka_startup_r6_20261007`，608显式文件，archive SHA256 `0844ca8b47db469dd6ffcecdad962f5e3e2f0b15c5dc9d76650ae019273c348d`；manifest SHA256 `2fdc12748f9374f3148e4a4cb2f6145caf3de20dc1f91085449314df9f7d04de`。同一launcher绝对路径/哈希/状态CPU预检已通过，真实init2预检作业4440已提交，物理结果待核对；init2在4430中未执行物理。

专家4417新增错误同属被屏蔽的ask_help仍被oracle硬造：object t7/s3、t8/s0报候选index ValueError；object t9/s1、long t2/s1报StopIteration。602be11修复所有fallback只从当前候选取动作，47项窄检查通过；无合法动作明确记no_legal_candidate。当前4417仅在回合边界让出，已有物理与错误全部保留，余量按显式episode身份续跑。
