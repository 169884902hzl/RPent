# current fragment 修复的运行范围

当前 `0eff8550d2c9cb73f778423d5945c1562c62898d` 中，current cabinet/drawer duplicate alias 的窄修只在公开诊断 probe 开启。4536 的独立柜顶绑定与800个目标 controls，证明这个开发干预在该状态有效；它不证明默认 harness 已修复，也不授予确认资格。

诊断调用链为 `probe_place_trace.py` → `original_placement_trace()` → 临时包装 `MeasuredScene.refresh()` → 同帧独立 `drawer` SAM 查询 → `canonical_fixture_scene(..., allow_drawer_fragment_alias=True)` → 写回 `scene.entities` → 原有 probe `bind_action()` → `OraclePolicy.bind()` → 执行目标动作。开发 wrapper 还在已有 carry segment 后额外采集、查询物体。它不改变 robot controls，但可以改变测量、绑定和回执，因此不是旧轨迹的精确重放。

默认运行链仍是 `V5Executor._refresh()` → `MeasuredScene.refresh(names)`；refresh 本身没有调用 `canonical_fixture_scene`，也没有该窄修的开关。原版专家 `OraclePolicy.bind()` 按原 scene 的实体做唯一绑定，没有预先 canonicalize。拆分 place 直接使用已选定的实体 ID，也没有调用该窄修。

`v5_subtasks.measured_instance_description()` 已调用 `canonical_fixture_scene(scene, max(source_step))`，但没有传 `allow_drawer_fragment_alias=True`。因此默认候选的唯一描述检查只应用默认 False 的旧 thin horizontal surface alias 清理，仍保留 current cabinet fragment 歧义。把 helper 参数默认为 True，也不能替代独立 current drawer 测量；默认查询集不一定包含 drawer。

运行时接线已实现为 `fixture_fragment_alias_v1`，CLI 为 `--fixture-fragment-alias-v1`，默认 False。查询 cabinet 时，同一次 capture 加独立 drawer 查询；场景测量和部件生成结束后、渲染/候选/专家绑定之前，共用 `MeasuredScene.canonicalize_fixture_fragments()`。该方法不偷换已选 ID，不新增状态字段。公开 alias 历史记录同帧测量、已有 mask 引用和 mask overlap，属于诊断元数据。未匹配、stale drawer、多 parent 的歧义仍保留。

23项窄CPU测试通过，包含4533实际公开frame的绑定从None变成已有measured top e104，保留实体的数值与ID不变；无独立current drawer或parent不唯一时不删除fragment。`probe_place_runtime_identity.py`使用`original_placement_trace(observe_runtime_only=True)`采证；observer不额外capture、query或再次canonicalize，不增加robot controls。测试也确认observer的这一性质。实际物理单局尚未完成，因此仍不声明默认技能修复或资格通过。

本轮仅核对源码调用链、生成提交映射并准备CPU产物审计；没有新增GPU作业、修改冻结快照或旧判定。
