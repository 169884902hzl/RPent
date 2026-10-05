# Codex3 私有抓取真值 v2

只修改owned `robots/libero/v5_grasp_truth.py` 与对应focused tests；未改runtime公共判定、probe hook、旧snapshot/manifest/标签/确认批，未提交作业、未push，root负责新manifest启用和共享COORDINATION。

新私有contact sample字段：`all_non_gripper_contact_geoms`；`gripper_geometry={version,source,complete,component_count,geoms}`。固定版本 `gripper_geometry/1`，来源 `component.contact_geoms+component.important_geoms`，掌面/手部碰撞几何属于夹爪，机器人其他链节或炉面等不属于夹爪。任一component缺完整contact_geoms时complete=false、all_non字段=null，不补成空列表。installed robosuite的base.py属性已实时核对：contact_geoms返回正确前缀命名的完整碰撞几何；PandaGripper的important_geoms只含指/指垫，掌面由contact_geoms补足。

新API：

```python
from robots.libero.v5_grasp_truth import sustained_grasp_v2, grasp_trace_summary_v2
hold = sustained_grasp_v2(samples, reference, duration_s=.5)
phase = grasp_trace_summary_v2(reference, samples, duration_s=.5)
```

新rule为 `all_current_non_gripper_contacts/2`：连续至少0.5秒、物体最低碰撞面相对落定参考抬升至少3cm、存在手指接触、全部当前接触都没有非夹爪几何。目的地炉面接触即使不在初始table集合中，也拒绝“完全由夹爪支撑”。首窗与终窗共用 `_v2_sample_check`，不能只更改终窗。首窗known通过后，后续放置/松手不抹掉期间真抓，但后续环境支撑拒绝终态真抓。

新诊断输出使用 `success=True/False/None`、`status=passed/failed/unknown`、`support_rule`、`unknown_sample_indices`；各check保留全部当前非夹爪几何与是否受支撑。trace报告 `unknown_contact_samples`。缺新版字段、非固定source/version或完整几何缺失均为unknown，不从旧other_contact_geoms反推新版真值；不跨unknown段拼接true窗口。已验证的一段完整known窗口可以独立证明期间抓持；不足0.5秒且紧接unknown的终窗仍unknown。

CPU实际运行：`python3 -m pytest -q tests/unit_tests/robots/libero/test_v5_grasp_truth.py`，21项通过。覆盖s13式burner支撑（legacy true / v2 false）、合法finger+palm/hand接触（v2 true）、完整component几何缺失（unknown）、旧样本缺字段（unknown）、期间抓成后放到炉面（during true / end false）、接触中断/unknown不拼窗。只用fake metrology CPU测试，未声称新物理成绩或验证器一致率达标。

独立AST检查 `object_lower_extent`、`sustained_grasp`、`measure_hold` 三个旧函数与修改前HEAD完全一致；contact_sample原finger/dual/other/contacts字段与语义保留，只附新增私有字段。源码SHA `5dc88383bcd5bc2bbab47256f1b0722e42cd54636dabd2ac27306b1af90cd541`。旧3550/3670及确认批不重判；新物理采样必须用新source+manifest登记rule。
