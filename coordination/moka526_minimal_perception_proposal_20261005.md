# Codex3 child：摩卡壶感知最小修复建议（未实现）

依据仅为 3662 显式原版 public RGB-D / mask / 测量证据及已登记源码。3678、3680 本次查询仍 Pending，没有实际结果，不以排队状态推断成败。不修改 root 的 runtime、probe、place 或旧标签。

第一项只修查询不对称，放在 `moka_query_ladder_v1` 开关后，默认关闭；先看独立 3680 的 8 图 / 24 请求实际结果再决定采用。主相机当前在 raw reply 空时才试 `silver octagonal coffee maker` .35 / `coffee pot` .25，副相机只试 `silver moka coffee pot` .35。raw reply 非空但有限深度、类别排除或现有几何检查拒绝时，当前不会继续回退。

可审查的最小接口：把当前两处 moka SAM 请求/有效点提取收进一个**仅 moka** helper，原类别归一化和其它任务不变。两视角统一以下固定梯度：主名称 .5 → octagonal .35 → coffee pot .25；8 图诊断没有原 secondary .35 首名称，不能称其精确重现旧腕部配置。不要看 private contact/solved 来选 query 或 mask。

```python
def moka_candidates(image_encoded, world, *, excluded_same_frame_pan_mask, record):
    ladder = (("silver moka coffee pot", .5),
              ("silver octagonal coffee maker", .35),
              ("coffee pot", .25))
    for query, minimum_score in ladder:
        reply = sam_rpc.call("sam3.segment_all", kwargs={
            "image_base64": image_encoded, "text_prompt": query,
            "min_score": minimum_score,
        })
        accepted = []
        for item in reply.get("instances", []):
            mask = Sam3Client._decode_result(item).mask
            # Exact view's already associated pan mask; never pick a mask by
            # private position or silently infer class from an artifact name.
            if excluded_same_frame_pan_mask is not None:
                mask = mask & ~excluded_same_frame_pan_mask
            points = measured_points(world, mask)
            if len(points) < 10:
                record(query, item, mask, "finite_depth_points_lt_10")
                continue
            lower, upper = np.quantile(points, (.02, .98), axis=0)
            extent = upper - lower
            # Existing secondary low-confidence geometry rule, same thresholds.
            if item["score"] < .5 and (extent.max() > .45 or extent.min() <= 0):
                record(query, item, mask, "low_score_extent_invalid")
                continue
            accepted.append((points, item["score"], mask))
            record(query, item, mask, "geometry_candidate")
        if accepted:
            return accepted  # Existing neutral-ID association/fusion still follows.
    return []              # No current target evidence: keep nullable verifier.
```

这是建议的控制流，不是已经加载的代码。primary 原先低置信度 extent 规则依赖 `instruction_queries_v1`，secondary 一直采用该规则；统一后 primary 也采用相同规则，是需要原版对照验证的行为差异，不能藏成无影响重构。instance deduplication、同帧 pan 排除、类别绑定与融合应复用现有代码。fallback 要在这些可复算拒绝之后决定，不能仅在 raw reply 为空时决定。

最小 trace 存为已有状态 step 下的独立 artifact，不增 serializer131 的行或字段。每次请求存：camera/source_step、RGB/world SHA、query/min_score、raw mask SHA/score、排除前后有效点数、几何 bounds、拒因，以及关联后的中性 ID。特别区分 `raw_empty` / `score_filtered_by_service`（若服务确实返回此信息）/ `depth_invalid` / `pan_exclusion` / `geometry_rejected` / `unassociated`。旧 SAM log 没有这些信息，不能补写成当时真实执行记录。

第二项是 FOV，独立开关/对照，不和 query 改动一起归因：

1. `v6_som.project_bounds` 已处理相机 K 的高分辨率缩放、cam2world 逆变换及 near-plane clipping，可复用来记录**当时已有 public measurement** 是否投影出界；不能把 cached bounds 当当前实体测量，也不能拿 private pot 坐标造追踪 ROI。返回 mask 触到图像边缘，只说明该视角可能裁切，不证明抓住或没抓住。
2. 3662 step68/69 腕部壶身在图像下沿之外；query 无法生成画面外的有效深度。若物体与腕部相机刚性共同运动，整腕 yaw 不改变二者相对位姿，不能预期仅 yaw 就让壶身回到视野。应单独测试已有主相机 `clear_view` / 变姿态后的可见性，并保持当前夹爪命令；没有当前目标测量仍 null。增加视角动作时重新记录动作和 physics-time，不能继续称“没有新动作”的同步计量。
3. 原 `verify_grasp_measurement()` 对 independent verifier 提前 return，导致旧 `grasp_occlusion_scan_v1` 分支完全绕过；旧分支还限制 opening≤.07，排除 ≥.0773 的 wide 帧。若 3680 证实回退仍不能解决，应在独立 verifier 返回 unknown 后，依据公开缺测量 / `opening_may_hold()` 条件做一次受控感知恢复，然后重新运行原独立验证器。不能由 private truth 触发、不把 wide opening 本身当成功；老扫描 8/10→8/10 的证据继续保留，不能自动纳入冻结版。

第三项是测量证据：应在既有 capture 保存 camera sim_time 或 capture-id 与对应 raw robot snapshot，禁止额外 capture / 动作混入原同步 bracket。现有 257 帧机器人 pose 一致只支持对齐，独立 pixel-capture sim_time 仍缺，限制不变。

下一步顺序：3680 小样本检查 raw mask/score 与拒因 → 固定 query 梯度/过滤规则 → 原版 pilot32 的未筛选状态验证召回和真实 false/null 分布 → 单独 FOV 恢复对照。pilot 仍不是独立确认；minimum_points_per_finger 不从这两张 wide-positive 画面拟合，不降 95/90/95 门槛。3678 只检查 category runtime/恢复/持续 truth，其 mask 缺口不影响 3680，不改作业。
