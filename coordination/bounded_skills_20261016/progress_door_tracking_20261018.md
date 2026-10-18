# Codex3：门板身份修复与原版 oracle 进度

仅原版场景开发仿真；oracle 关闭 π0.5；不训练，不是确认批或冻结结论。不同源码、重复状态分别保留，不当作独立样本相加。

| 源码 | 类别 | 原生成功 | Wilson 95% | 决策中位数 / p90 | 仿真步中位数 / p90 | 中位墙钟 s |
|---|---|---:|---:|---:|---:|---:|
| 3d71f44 | bowl_transfer | 14/17 | 58.97–93.81% | 8 / 10.4 | 290 / 685.4 | 581.621 |
| 3d71f44 | box_transfer | 4/4 | 51.01–100.00% | 6 / 8.8 | 528 / 661.8 | 260.943 |
| 9cacb71 | drawer_open | 4/4 | 51.01–100.00% | 10 / 10.7 | 721 / 917.9 | 920.399 |
| 9cacb71 | drawer_close | 1/1 | 20.65–100.00% | 20 / 20 | 641 / 641 | 2209.275 |
| 9cacb71 | stove_on | 1/1 | 20.65–100.00% | 3 / 3 | 681 / 681 | 209.731 |
| 9cacb71 | stove_off | 1/1 | 20.65–100.00% | 4 / 4 | 456 / 456 | 254.402 |
| 11ec9aa | cup_transfer | 0/1 | 0.00–79.35% | 17 / 17 | 1973 / 1973 | 1559.024 |
| af76e3d | microwave_close | 0/1 | 0.00–79.35% | 16 / 16 | 487 / 487 | 1501.562 |
| e425264 | microwave_open | 0/1 | 0.00–79.35% | 11 / 11 | 593 / 593 | 745.890 |

新增完整成功：盒子8173_22（10决策、705步、388.768s），8173_23（6决策、495步、256.810s）。8256_140微波炉打开仍失败（11决策、593步、745.890s，planning_unreachable）；其两次nudge有位移，随后部件身份缺失，不能生成接触选项。保留全部原始记录。

## 本轮修复与证据

8255保存的公开RGB-D上，原跟踪器和加入机器人自过滤的原跟踪器均只在15个后续capture里量出1个门板。根因是图像warped mask混进新露出的背景深度。用上一帧独立门平面和当前双向视觉/深度刚体轨迹约束当前深度，再执行原有平面拟合，10/15个capture可测。原有阈值、独立固定框架要求和终点判定未改；这些CPU身份诊断未提供固定框架锚点，不能作为终点或任务成功证据。失败支持仍然拒绝，不用缓存平面替代当前测量。

新增microwave_door_tracking_v1，默认旧路径关闭，bounded probe开启。只在SAM没有合法门板时尝试；支持丢失后清除该视角历史。当前RGB-D经公开关节/末端/夹爪传感器与静态Panda几何过滤机器人像素。轨迹和云均保存，模型schema仍为bounded-skills/1。

250项相关CPU测试通过；Ruff基线40项、本轮40项，新增0项，未顺带改历史风格。核心提交已推送harness-v5：124314ed79a3b192c273a1587952ddaa8bb94b99。

源码快照：/public/home/sunyihan/rpent_libero_eval/source_bounded_124314e_20261018；归档SHA256 285fcc3434853fa74357c9402550b5d7a11a5ba67f12b29fa55568236054e11a。manifest：results/bounded_skills/feasibility_20261017/preparation/original20_manifest_door_tracking_20261018.json（SHA256 6731a793b022fad19815fa4cae6a9321aa220ff33bb2f512d6ae6451855c9cbb）。220状态CPU预检通过。渲染/执行入口scripts.probe_bounded_feasibility:episode；解释器/public/home/sunyihan/rpent_libero_eval/.venv/bin/python。交付清单reports/door_tracking_delivery_20261018.json。

## 资源与接续

node02三条串行通道合计最多3卡，第四卡留Codex2，node01本轮运行0。全部新作业ReqNodeList=node02、Nice=500，数组%1；不动c5/c6/rf与历史JobHeldUser。资源截图reports/resource_latest_node02_cap3_20261018.png。

第一通道8257联合绑定碗启动→8258杯子启动→8261_120新门板跟踪微波炉启动。8258实际启动通过后，14/16/60/160完整重放数组将接在8261后，避免并发超额；新门板完整重放必须另待8261物理启动通过。第二通道8192→8252，第三通道8173继续oracle各类20。之后才做两个对照、K1/K4和分叉。全部确认状态永久排除训练。
