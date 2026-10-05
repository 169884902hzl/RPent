# Codex3 独立开发模块回执：公共双帧抓取验证器候选（509）

已完成 `robots/libero/v5_grasp_measurement.py` 与14项单元验证，不改主代理拥有的runtime/harness/渲染器，不改任何运行快照、Slurm、原始标签或确认批门槛。本模块尚无物理准入，不宣称95%；正式资格仍须独立原版确认。

依据固定3620前30：12个FN缺至少一帧当前可见测量，2个FN开度超过固定7cm而根本未测。reset s25主视角检测被失败腕fallback替换成cached；因此支持保留独立视角。宽开度的2条没有新鲜post尺寸/图像，不足以校准，不能仅放宽上限。本模块把不足的证据保留为None/unmeasured。

API：

```python
evaluate_grasp_frame(before, views, opening, eef_xyz, *, previous_step,
                     opening_calibration=None, finger_frame=None,
                     measured_points_by_view=None, support_top_z_m=None,
                     require_support_clearance=False, minimum_lift_m=.03)
evaluate_grasp_pair(first, second, interval_s, *, minimum_interval_s=.3)
```

`views={"agentview": Entity或entity_record, "wrist": ...}` 必须由采集器分别保存。Entity本身是公共RGB-D测量合同；record的src必须为perception类且非cached，并有新增source_step。主视角当前有效、腕视角缺测时保留主视角；两个当前视角结论冲突记None，不后验挑乐观的。不同物体ID/name不能验证选中物体。每视角返回freshness、下沿lift、近夹指、开度和原支撑clearance条件及所有输入证据。

`opening_calibration` 的keys为 `closed_empty_max_m`, `open_empty_min_m`, `max_sensor_opening_m`, `tolerance_m`, `minimum_points_per_finger`, `provenance`；调用方必须用原版空夹爪开/闭测量标定，不存在生产默认值。没有校准输出None。接近空张开区间的宽开度必须提供当前匹配object_id的SAM点云，两侧夹指接触区域均有足够测量点才可通过，不能只看开度。测试里的校准仅是synthetic fixture，严禁拿去运行。

`finger_frame`：`origin_world`, `rotation_world_from_fingers`（3×3 proper旋转）, `closing_axis`（0/1/2）, `depth_half_m`, `height_half_m`, `provenance`；来自本体姿态和刚性夹爪几何标定。`measured_points_by_view` 每相机一个 `{xyz_world, src:"perception", source_step, object_id}`；真值坐标不能传入。没有finger frame的普通开度暂显式返回旧world-axis体积证据；宽开度不能据它通过。

对平底锅，调用方启用 `require_support_clearance=True` 并传测量的原支撑顶面 `support_top_z_m`；缺支撑测量为None，不把centre抬升替代底沿离支撑。两帧聚合要求≥0.3秒、不同source_step、同一物体，unknown保留；输出 `qualified_on_independent_original_confirmation=False`。

实际测试 `.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_grasp_measurement.py -q`：14 passed。覆盖缺测腕帧不能覆盖主帧、不改输入、cache/stale/sim_truth拒绝、缺校准、宽开度两侧点证据/错误物体/旧帧、旋转、支撑下沿、视角冲突和双帧间隔。当前运行时未集成，未跑物理验证。

module SHA256 `a5f29741c53ad5efeb7f140fdb3c19dd9cce1397a3068997d78d80fb2d86c58a`；tests SHA256 `f4f049eaf5f07cd262bde771f3d5eb2af64b491443a680e61933dbbbf2023e13`。子代理只scoped commit，不push、不sbatch；主代理接runtime。


## 公共输入取得路径：只读核对与3个原版CPU例证

`MeasuredScene.measurement_clouds[eid]` 在dual_view=True时已经融合，不是独立per-view raw。独立raw可以在 `MeasuredScene.refresh()` 中融合前保存当前camera points，或启用 `record_sam_masks_v6` 后从 `scene.perception_evidence[eid]["sam_mask_files"][camera]` 读取该实体当前mask，再配 `toolkit._state.load(f"{camera}_world_high.npz", step=mask_source_step)` 用 `v5_perception_geometry.measured_points(world,mask)` 重建。`EnvState.load`支持显式step；下一次refresh可能把entity/cloud/evidence覆盖，调用方须先保存不可变副本。旧3620的3个检查case没有保存SAM masks，不能把融合cloud伪称raw，不在本任务重新跑SAM。

原支撑顶面使用 `measured_work_surface(pregrasp_world, [pregrasp Entity])` 的 `height_m`，不是 `scene.support_z`（它只是其他对象可见lower的中位数）。在固定prefix中的命名case s25(reset)、s14(overhead)、s10(handle) 上仅用原RGB-D与公开pregrasp Entity跑CPU，分别得到 `.90076171875`、`.90125`、`.90076171875`m的连接平面，约56–57万深度点。0物理查询、0模型调用，未读取私有真值作为输入。证据 `results/harness_v5/moka508_fixed30_diagnosis_20261005/public_measurement_interfaces.json`，SHA256 `5ffefbd6cdf0043683982b3997560c1d338c033d75d459f6b81a1e5053ff3405`。首次在remote旧root直接import失败，改为已知完整source492工作目录后同样3个CPU请求成功；没有修改旧source。

本体姿态必须核对frame：远端robosuite `robots/robot.py` SHA256 `dcb317e6d6b9eba54469f38d1c26ba44bafb1beb0dd4612ebc026ad0b25efda6` 的eef_pos取grip_site，eef_quat取arm body，eef_quat_site才取site旋转。不得直接混用eef_pos与body quat构造finger frame。

本机与远端 `models/assets/grippers/panda_gripper.xml` SHA256相同 `066fd7ae45afb11e1844869360e587646e9768210ba5389aa3cd35292cde29c1`。公开刚体链显示grip_site局部z=.097；pad中心z=.0524+.056-.015=.0934，site→pad中心offset约[0,0,-.0036]m。finger局部绕z90°使slide y映射到site x，closing_axis为site x。pad半深/高约8mm，inner pad gap与joint opening差约1mm。这是固定机器人几何，不是物体真值；但官方诊断允许whole finger mesh接触，未经原版验证不能用pad-only体积或这些初值宣称95%。
