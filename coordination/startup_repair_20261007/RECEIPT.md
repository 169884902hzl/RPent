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
| 4411 | r4摩卡壶单局预检 | 待实际物理证据，不能称通过 |
| 4412 | r4专家单局预检 | 待实际物理证据，不能称通过 |
| 4413 | r4 A3单局预检 | 待实际物理证据，不能称通过 |

r4保持SOURCE571行为，只修启动记账与摩卡公共目标绑定；新增时序模型在独立源码中开发。原4408测量的第二个stove bbox距公开EEF最近XY距离1.166m；wrapper以1.0m操作区过滤，保留全部公开测量/拒绝原因。过滤后仍须唯一，两个近stove或缺测均不执行；不从私有目标挑选。

r4远端源码：

`/public/home/sunyihan/rpent_libero_eval/source_v5_moka_startup_r4_20261007`

608显式源码文件；archive SHA256 `1f6bbf9f7b659ad7a4d89cc741604c8d52aa127723e49b74034bed751e2c0026`。

摩卡manifest：`results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/repair_r4/moka_visited10.json`，SHA256 `fe9cd53bc9e83d1405033e4bdbdfdd7689a6be5047b8a3fd5907354c5df1b458`。

专家/A3索引：`results/harness_v5/interim574_20261007/preparation/repair_r4/manifest.json`，SHA256 `a52d93d1d08d550988cd35fb80abe53fccedee416b9d6ffea2ae5b6d7b0c9c83`。

4379同类结束记账故障已止损：运行分片在当前回合完成后自然退出，part7保持hold，A3旧4390保持hold。153局均有物理轨迹，原startup_error ledger保留，不能当正式专家分数；13773 VLA块、83443脚本运动步是原记录的诊断合计。公开末状态133、私有末状态127只作诊断，曾成功后退回的六局另列于显式终态报告。

时序验证器先接入“测到终点立即停技能”，不是只做事后标签。默认关闭，缺测/模式或特征编码不匹配返回unknown；现有训练只支持turn_off。CPU578首轮使用5个原版选择状态，3训练/2验证，815注册行、483/322可测标签；验证AUROC0.9758，但阈值0.5下TP0/FP0/FN154/TN168，尚不合格。继续baseline-relative特征修复，不能调验证阈值宣称通过。确认状态不进训练，已知1315哈希排除清单完整性仍标pending。

微波炉方案见 `coordination/microwave_door_plane_offline_replay_20261007.md`。已有4340十个点云SHA/拟合重放10/10一致；9个实际请求仍缺测，不改判。撤臂后双视角多帧分别拟合固定框架与活动门平面，比较夹角/位置并要求稳定；遮挡、缺平面、多mask或冲突继续unmeasured。实现预计0.5–1天，离线/窄验证2–4小时；物理选择/确认批另需GPU。
