# Codex3：四类独立确认批预提交登记

已读取用户11:30要求、3550全1800试次、C轨迹600条、grasp487独立池。接受：探索只用于选配方；95/90/95资格仅按独立确认，不后验换失败状态、不用探索分数补资格。无异议。

已选定bottle=C、bowl=C、box=B、mug=B，原提示与停止/验证器全部固定为3550这四类所选配置；碗/瓶C未发现抓后释放证据，已有RPent下降→抬升public stop保留。pan/moka方法仍在修，预留确认状态不消费。暂不宣称六类通过。

拟提交新数组一次，编号待Slurm返回：`sbatch --parsable --dependency=afterany:3616 runtime_launchers/run_v5_grasp492_first4_confirmation.sbatch`。依赖仅用于保证最多2卡并行资源；四类确认结果不依赖pan探索成绩。4片×100新官方初始状态、array0–3%2/每片1GPU/8CPU/90GB/4h/nice1000，无节点绑定，不释放或绕过旧链。
输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp492_first4_confirmation_20261005/full_job<array_id>/part0–3/`。

独立性：每类100不同raw-state SHA，与3550全部435独立状态tuple与raw-SHA零重合。init10–39。bottle/bowl/box来自原版40，mug明确使用原版LIBERO-90官方任务，记为确认分布扩展，不冒充40任务未用init。六类完整池有34个跨类共享场景，类内无重复，后续报告披露。

90入口只在单技能诊断开关 original90_grasp_diagnostic_v1=True 时开启：provideroracle/standard/max_decisions1/指定抓取类别/无collection/无done_gated/无反事实目标。默认ORIGINAL_SUITES仍40，不扩大训练oracle边界。确认时核每个init文件、BDDL文件及选中state的SHA；真值只进诊断标签、不进入状态或控制。未读取PRO/人工/密封文本；这些确认记录不入训练。

source `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp492_first4_confirmation_20261005/`，commit63e345e；archiveSHA `e371b6f865fccf332f8897c66aa0dd568b3c1a1997f264002fe86a0675468827`。
manifestSHA `dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9`；poolSHA `89ea5ea7ee50e1cf7dc9eeafcdb925b299cc6cab541090e2b174bbad98fd8f64`；launcherSHA `81114e7258ab96c3523919e2fbb3c9fe4e2205a527be013de518f8c601dcfb96`。
入口 scripts/probe_v5_grasp449_20261005.py::main；解释器 /public/home/sunyihan/rpent_libero_eval/.venv/bin/python。原版90入口/抓取/采集68 focused tests通过；主代理补确认state核验后48 focused tests通过；真实90物理启动未运行，由本独立确认保留其启动证据，基础设施错误不算模型成绩。

回执先push、远端append核对成功，再一次sbatch。未完成：400确认试次、pan/moka各100确认、95/90/95判定、A3/A4复测、行为冻结。
