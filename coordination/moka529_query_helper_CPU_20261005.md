# Codex3 moka529 可审查查询helper

Owned `robots/libero/v5_moka_queries.py` 和 `tests/unit_tests/robots/libero/test_v5_moka_queries.py`，依据 `coordination/moka526_minimal_perception_proposal_20261005.md` 实现。没有改root runtime/probe501/v5_pan_surface、renderer、旧源码快照、作业或原标签。root负责以后opt-in接入、push和共享COORD。此时仅CPU代码；3680与后续原版物理结果仍决定是否采用。

接口：`collect_moka_instances(rpc, image_encoded, world, *, excluded_pan_mask=None, record=None)` 返回 `instances`、`query_trace`、`query_count`。实例为原raw item的浅拷贝，保留原始mask payload/score等，新增 `geometry_query` 字符串和 `moka_query={query, minimum_score, query_index}` provenance；不生成中性ID或改融合规则。

梯度固定：`silver moka coffee pot` .5 → `silver octagonal coffee maker` .35 → `coffee pot` .25，两视角调用同一helper。退出依据是除同帧pan mask后至少10个有限非零世界点，及现有低分(<.5)extent规则：02/98分位extent最大值>.45m或最小值≤0则拒绝。raw reply非空但无可用几何时继续梯度，不加新的阈值、形状先验或class oracle。返回的是未改mask的raw实例，root旧主/副路径仍要用相同pan mask排除；helper中的几何检查不会覆盖SAM mask。

`record(event)` 的event类型：`query_started`（每次RPC之前，便于失败时仍正确计calls）、`instance`、`query_finished`。instance事件提供原raw item、`raw_mask`副本、`mask_after_pan_exclusion`副本、排除前后有限点数、移除pan像素数、测量lower/upper和拒因。query_finished含query/min_score、raw数量、accepted数量、rejection_counts和outcome。root可在callback闭包追加camera/source_step、RGB/world文件SHA及mask落盘路径；这些只进artifact，不进131状态行。成功返回时 `query_count=len(query_trace)`；用query_started计calls时不要再次累加返回count。

fresh mask与world尺寸不匹配明确抛 `ValueError`，先callback记 `mask_world_shape_mismatch`；excluded pan与world尺寸不匹配在RPC前明确抛错。缺mask、有限深度不足、pan排除和低分几何拒绝分开记录。RPC/decode错误不改成普通未检测到，也不拿private坐标/contact/solved选择query或mask。

实际验证：`python3 -m pytest -q tests/unit_tests/robots/libero/test_v5_moka_queries.py`，10项通过（0.28s）；compile、F821/F823检查通过。覆盖非空无深度仍fallback、pan排除仍fallback、低分范围/零厚度拒绝、原mask不修改、全部候选保留给原关联、缺mask/零深度区别于raw_empty、shape error、三次空请求计数，以及callback mask副本不影响raw返回。未调用真实SAM、未声称召回改善或物理成功。

helper SHA256 `34ab29423fcdb82dbe468861051a820c90b5276f9530946e74e5b72e6d2a4319`。CPU真实结果和边界如上，无新Slurm作业。
