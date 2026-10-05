# 原版独立确认池（CPU登记）

已选六类各100个官方原版状态；未执行物理试次，未授予资格。
与3550全部435个唯一场景的tuple及原始state SHA均零重合。init仅10–39。
平底锅、摩卡壶与杯类明确扩展到原版LIBERO-90；不能声称这三类来自原版40任务未用状态。

|类别|确认候选数|显式任务池可用数|唯一state|非原目标抓取探针|
|---|---:|---:|---:|---:|
|bowl|100|100|100|0|
|bottle|100|100|100|0|
|box|100|162|100|0|
|frypan|100|180|100|0|
|moka_pot|100|120|100|75|
|mug|100|120|100|0|

运行资产与3550一致：标准benchmark的Python命名空间为libero.libero，原版目录由runtime_config指向liberopro安装下的原版套件。
未读取任何PRO套件文本；文件读取只来自显式任务映射。

独立确认前须先固定技能卡方式、提示词与验证器。当前只是准备可用状态清单，不能后验选成功样本。
候选是否在当前视角唯一可见尚待物理启动核对；该缺测必须保留为未验证/基础设施记录，不能静默替换。

candidate_pool.json SHA256: 89ea5ea7ee50e1cf7dc9eeafcdb925b299cc6cab541090e2b174bbad98fd8f64
original_task_sources.json SHA256: ff179ce2be81e0414b9fd68a5872b105b58b5879be4abf56749fc8a02df3b9a8

原版平底锅实际指令叫法统一为 `frying pan`，六份原版BDDL逐字证据见 pan_noun_phrase_evidence.json；可用抓取短提示 `pick up the frying pan`。
原版40任务内平底锅唯一场景的50个init已被3550用尽；这里使用原版LIBERO-90官方init，不生成、不冒称新的40任务官方init。
pi0_pick 入口 robots/libero/tools.py::LiberoPrimitives.pi0_pick；每块实际5个7D动作，160块上限=800步，原生终止/公开下降再抬升stop可提前停止。
实际CPU命令及一次非生产目录上游自动初始化的副作用见 preparation_run.json；未改生产配置或共享服务。

运行限制：现有 v5_oracle_server.py 的 ORIGINAL_SUITES 和 CLI 只接原版40任务，LIBERO-90候选不能直接交给旧3550探针。需另加只用于单技能原版90诊断的显式开关/独立服务入口，保持训练采集的40任务边界。此项尚未修改或运行。
不同类别之间有34个共享初始场景（主要pan/moka配对），合计566个独立原始state；每类内部仍为100唯一state，且全部与3550零重合。统计时应披露跨类共享场景。
