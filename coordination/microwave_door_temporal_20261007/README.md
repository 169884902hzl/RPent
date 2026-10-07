# 微波炉多帧门平面原型（2026-10-07）

已实现 `robots/libero/v5_microwave_door_temporal.py`，入口
`measure_microwave_door_temporal(before_frames, after_frames, mode)`。
该模块只处理调用者显式提供的公开测量，不访问仿真、关节、BDDL、文件目录或 SAM。
原型没有接入运行时，默认不允许终点停止；没有新增物理资格结果。

## 输入与测量

动作前、动作后各至少两帧。各阶段末帧与首帧间隔至少 0.3 秒，时间与
`source_step` 严格递增。所有帧必须来自同一 `world` 坐标系，单位为米，
明确标记 `source=perception`、`arm_withdrawn=true`、`occluded=false`。
时间戳取采集时间，不取离线读取时间。机械臂遮挡时不填虚假的撤臂标记。

每帧的固定 `frame` 和活动 `moving` 平面复用现有 `vertical_face` 字段：
`centre`、`normal_xy`、`residual_p90_m`、`points`。也可提供当前显式
`points_world` 点云数组，由同一个 fitter 重新拟合。每个平面保留
`source_cameras`（`agentview` / `wrist`）、可用的 `path` / `sha256` / `mask_id`。

绑定必须唯一：`mask_count=1`，或现有
`measurement_counts.{frame,moving}.accepted_faces=1`。两区域的实测
`frame_moving_mask_overlap` 不超过 0.05；相同 mask、云 SHA 或云路径不能
同时充当固定面和活动门。输入缺失、源相机缺失、私有 source、过期平面、
多 mask、遮挡和拟合拒绝均返回 `unmeasured`，端点为 null。

输出保存各帧门相对固定面的法向夹角、中心偏移和法向间距，以及前后变化。
固定面法向变化不超过 10°、沿法向漂移不超过 1 cm；每阶段门相对角范围
不超过 3°、相对中心两两距离不超过 1 cm。法向符号翻转不算转门。
暂用已有开发角度判据（开 ≥30°、关 ≤15°），要求动作后所有帧都通过；
这些阈值尚未在新确认批上定资格。稳定但不在端点返回 measured/false，
缺证据返回 unmeasured/null。已经处于端点可报告端点，但不会宣称发生了
所请求的方向变化。

## 终点停止接线

`stop_admitted` 仅在公共稳定端点为真且 `endpoint_stop_enabled=true` 时为
true。开关默认关闭；开发试验可以显式开启，失败后修复重跑。当前原型
尚未取得物理资格。确认批和最终评测的配置与资格要求由既有协议管理，
测量代码不另加资格门槛。

运行时接线仍需在动作块之间获得无遮挡的多帧测量，并在允许停止时立刻
不再下发下一块。必须确保关门/关火到达终点后不会继续执行导致回退。
当前原型只提供测量与 admission 接口，没有修改 executor、launcher、
renderer 或技能停止行为。撤臂采集会改变控制时序，须单独做窄物理检查。

## 验证与现有记录

窄测试命令：

```bash
python -m pytest tests/unit_tests/robots/libero/test_v5_microwave_door_temporal.py -q
```

结果：25 passed。覆盖开/关、已经到端点、未到端点、默认停用和开发显式开启、
原始点云拟合、法向符号翻转、门回弹、参考面漂移、重复/过近帧、掩码歧义、
遮挡、过期测量、损坏字段，以及私有标签不能改变公共判定。

显式检查 `job4340/report.json` 的全部 10 条注册记录；每阶段只有一帧，
因此新时序入口全部保留为 unmeasured（0/10 measured），没有重判旧成绩。
逐条平面可用性与输入 SHA 见 `legacy4340_audit.json`（保留初版生成时的源码 SHA）。这与此前 10 个
点云的拟合重放 10/10 一致不矛盾：拟合可复现不能补出多帧或独立参考面。

源码 SHA256：

```text
12f217dc8f6690f7f3a76ea58bfaf79dfacaf4447fbd25cfc390f27667b231ee
```

窄测试 SHA256：

```text
b66a7c35cee02823a3ee37072032f3f37cba8b02745bc65b3adbaaab68f4821e
```

## 缺口与工作量

原型的纯几何部分已完成。公开多帧采集、独立固定框架/活动门提取和
executor 停止接线预计仍需 0.5–1 天；离线重放与小量物理 smoke 约 2–4 小时。
选择/确认批另需 GPU 时间。固定框架、当前门平面和无遮挡多帧未测到之前，
不调阈值补 verdict，不把私有关节真值填进运行时。确认状态不得用于
验证器训练或阈值选择。
