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
