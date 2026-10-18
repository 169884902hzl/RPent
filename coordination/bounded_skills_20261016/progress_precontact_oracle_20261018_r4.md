# Codex3 接触前实例身份修复与原版 oracle 进度

时间：2026-10-17T23:02:19.075069-07:00

原版开发仿真；oracle 禁用 π0.5；不训练。不同源码分开；重复状态只作配对，不加成独立确认样本。

|源码|类别|原生成功|Wilson 95%|中位墙钟秒|
|---|---|---:|---:|---:|
|3d71f44|bowl_transfer|14/17|58.97–93.81%|581.6|
|3d71f44|box_transfer|7/10|39.68–89.22%|347.8|
|9cacb71|drawer_open|7/7|64.57–100.00%|882.5|
|e6b0b47|bowl_transfer|1/2|9.45–90.55%|868.8|

## a4d51ef 与启动/完整任务边界

commit `a4d51efe34843fc822f7576fd5bb58ca97535355` 已推送 harness-v5。快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_a4d51ef_20261018`；归档 SHA256 `4a44429cea9dd36cc9ff08cad9cf62914fcdaeecb421eba68dbf9315a39d3054`。manifest `results/bounded_skills/feasibility_20261017/preparation/original20_manifest_precontact_20261018.json`，SHA256 `ba4207e7e45c92612389a6f5bddfbd2fe45c4529fdbed6fd8e907119ba9a9c1b`。入口 `scripts.probe_bounded_feasibility:episode`；解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。220 状态 CPU 预检通过，相关 CPU 测试 232 passed。

精确接触前实例像素只提供身份参考；当前 RGB-D 必须有至少40个1mm内共享点，且恢复像素通过连续表面/圆柱截面和测量范围约束。verified held 后不使用静止参考，release清除。兼容 adapter 默认关，bounded probe 默认开。碰撞间隙4mm、执行力和预算不变。

8270_24 同快照/同launcher真实物理启动 COMPLETED 0:0，状态为 startup_physical，绝不计入完整任务分母。完整 8272_[24,25%1] 已提交第三通道，依赖当时运行的8173子任务；后续8173待运行子任务依赖8272。完整结果待出。

盒子 init4：公开RGB-D CPU重放恢复8/8自身漏边，完整lift路线从拒绝变为通过；这是路线筛查证据，尚不是完整任务成功。init5仍有1个自身漏边未恢复，新旧筛查均拒绝，保留缺口。见 `reports/box8173_24_runtime_precontact_CPU_20261018.json` 和 `reports/box8173_25_runtime_precontact_CPU_20261018.json`。私有射线只用于诊断，不用于控制或训练。

## 已完成配对与下一处阻塞

8262_14（e6b0b47）碗init14原生成功：8决策、619步、750.8秒；对旧8173_14为改善。8262_16同源碗init16失败：11决策、563步、986.8秒，collision；第二次抓取已lift成功，后续carry被单个目标自身像素阻挡。私有射线归因仅用于定位，公开身份恢复仍在CPU诊断中，不按私有标签删碰撞点。

## 资源与后续顺序

已刷新 squeue，node02本项目3个运行、node01本轮0个；所有活跃数组ReqNodeList=node02、Nice=500，各通道%1。截图 `reports/resource_latest_node02_cap3_20261018.png`。未动c5/c6/rf和历史JobHeldUser。

继续原版oracle各类20；低上限类别先修技能/测量，再两个对照、K1/K4、最后分叉。全部确认状态永久排除训练；不读PRO，不训练。
