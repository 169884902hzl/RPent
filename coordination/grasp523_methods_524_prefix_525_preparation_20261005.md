# Codex3 原版抓取方法证据、3670中间快照与runtime烟测准备

独立 CPU 汇总已运行，未提交 Slurm、未修改 runtime、未读取 PRO、sealed 或人工文本。主代理负责 push、远端 COORDINATION 和最终源码快照/提交。

- `grasp523_method_evidence_CPU_20261005/report/report.json`：3550/3616/3620/3658共2504个闭合case与choices SHA全部一致；SHA `d944d5bc595b09004bbc1831ed55edd8a188fa41411f34b991d30a1a73379384`。四份显式manifest不足以证明pan/moka已经试完5种独立首次抓取方法；160/320不多算，pan别名不多算，moka3550 B/BA是相同物理条件，完整子任务smoke不并入首次抓取确认。平底锅最好83/100与84/100，摩卡壶selected-reset63/100；handle缺测未执行另列。旧私有标签、unknown和误判都保留。
- 同目录 `first4_runtime_integration_plan.json` SHA `9cbd5009e352b37f3b245458169d01dae596f53653f27e7f3a8ef1112e1d24b7`：源 `source_v5_grasp492_first4_confirmation_20261005/scripts/probe_v5_grasp449_20261005.py` SHA `20c05a0174054abbdcb0f2974449a31fe131159c41e59b363a974166f760cd36`。C的`probe_contact_prompt`为`pick up the {measured_category} first, then {instruction}`；B为`pick up the {measured_category}`。原确认均RPent `pi0_pick(...,max_chunks=160)`后`rpent_pick_then_measure`旧测量验证，不能声称后来的独立双视角验证或C真实回初始pose已经被原确认验证。
- `skill524_job3670_prefix_CPU_20261005/report1/report.json` SHA `21111430cb6a066477dd5c5d147c4c2fc478cca46ce84b5589980d438b615914`：8条显式part ledger冻结闭合prefix，25/400、choices SHA25全部一致。pan centre16中持续抓住16、最终目标14；handle9中持续抓住8、最终目标5。公共place TP0/TN6/FP0/FN19/unknown0；Moka尚无闭合局。末尾release不抹掉期间成功。TP/TN是最终放置验证，不冒充抓取验证。50原版scene每臂重复2次，非确认批；不可变prefix留在远端同report1目录。

`grasp525_first4_runtime_smoke_20261005/preparation/smoke.json` 已在远端生成，SHA `2b1097366c0097a71ceead869cc45c4927a524760036560ec1f88132e31ce451`。原版40固定类别任务：bottle Object2/3；bowl Spatial0/1；box Object1/6；mug Long4/6（porcelain mug）。每类两个初始、一个真实公共退臂后+10cm X偏移恢复，共12请求、8个唯一原版状态；恢复与第一初始配对，无成绩选择。`executor=current`、160chunks、`grasp_category_profiles_v1=true`，独立双视角验证+calibration513明确为新验证干预，`private_frame_sync=true`仅取既有测量作只读同步标签。私有真值只在公共receipt固定后记录，不覆盖held/receipt、不控制执行；计量异常保留unknown。

Owned入口 `scripts/probe_v5_skill501_original.py` 新增standalone kind=grasp与regrasp_restage路径；恢复setup只用公共retreat和当前EEF测量偏移，未用private restore/attach。准备入口 `scripts/prepare_v5_grasp525_first4_runtime_smoke.py`，运行器 `scripts/run_v5_grasp525_runtime_smoke.sbatch`，4片%8、每片1GPU8CPU90GB、无节点绑定或依赖。最终snapshot注册后由主代理执行：`GRASP525_SOURCE=<source> GRASP525_MANIFEST_SHA=2b1097366c0097a71ceead869cc45c4927a524760036560ec1f88132e31ce451 sbatch --parsable scripts/run_v5_grasp525_runtime_smoke.sbatch`。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp525_first4_runtime_smoke_20261005/probe_job<job>/part0–3`。

53项focused CPU tests通过；compile、F821/F823、bash语法和scoped diff检查通过。未声称GPU烟测通过、未授资格、未冻结，95/90/95门槛不变。已有报告、原任务结果和计量unknown均不重跑、不覆盖。
