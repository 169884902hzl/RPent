# pan527 稳定帧身份补充说明（旧报告保留）

此前报告将sample6/7点云逐字节相同与“不能作为两份稳定证据”连得过强。更准确的限制是缺少独立pixel-capture的时间/身份记录，不能由相同SHA推断复用了旧capture，也不新增“云必须字节不同”的稳定判据。静止物体与float16量化完全可以使两次真实capture的图/云相同。

已核显式原版证据：`pan527_observed_support_feasibility_CPU_20261005/input/states.json` SHA `85f5a7ed6b320ef114af1dcc7ff4b2e2c2b1a07a5cc56aa5f58f5bbb2cf5096d`。step_idx6/7分别记录`v5_measurement`，分别有自己的agentview/wrist图、depth/world、private_frame_sync_0006/0007和各自SAM artifact名；source_step不同。机器人pose相同、elapsed_s=0，不足以确认或否认新图采集。

choices SHA `6638dfd82ba1323402c6fffafb6584eb28f65d9c361dc2372cc51692e49f543d` 的公共验证记录明确first.source_step=6、second=7、interval_s=3.5337954279966652、target.source_step=0（静止目标缓存）。因此保存的验证时间间隔已经大于0.3s；这份interval并不等同于单独保存的两帧pixel acquisition timestamps。`grasp522.../report2/frames.jsonl` 对sample6/7的agentview/wrist capture_sim_time都null；已有private bracket时间相同，仅用于诊断，不能当pixel-capture时间。没有把同云或同机器人状态当成失败或证明复用。

target raw云只有sample0和6，7无当前target云，是当前mask/footprint配准诊断的缺口。静止目标按既定规则使用预抓缓存仍允许；本补充不新增“每个post帧必须当前target云”的运行时判据。

判据仍是已有要求：真实独立capture且间隔≥0.3s，不要求像素或点云变化。新probe可补capture-id/时间，以区分实际采集与artifact别名。旧report1/2及SHA、原始记录、标签和runtime判断全部保留；这里只修正证据措辞。
