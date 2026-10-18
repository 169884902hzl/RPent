# oracle 物理进展与测量修复（2026-10-18 UTC / 10-17 PDT）

资源：仅 node02，当前三条串行通道。运行数不超过3；node01没有自有新作业。所有新增作业ReqNodeList=node02、Nice=500。不修改c5/c6/rf及历史JobHeldUser，不使用HUST。截图和结构化队列见reports/resource_latest_node02_cap3_20261018.{png,json}。

当前完整原版开发结果（关闭π0.5；按源码分别统计；启动预检不进分母）：

| 源码 | 类别 | 原生成功 | Wilson 95% | 中位墙钟 | 原始失败阶段 |
| --- | --- | --- | --- | --- | --- |
| 3d71f44 | bowl_transfer | 11/14 | 52.41–92.43% | 576.380 s | {'collision': 2, 'planning_unreachable': 1} |
| 9cacb71 | drawer_open | 1/1 | 20.65–100.00% | 866.032 s | — |
| 9cacb71 | drawer_close | 1/1 | 20.65–100.00% | 2209.275 s | — |
| 9cacb71 | stove_on | 1/1 | 20.65–100.00% | 209.731 s | — |
| 9cacb71 | stove_off | 1/1 | 20.65–100.00% | 254.402 s | — |
| 9cacb71 | microwave_close | 0/1 | 0.00–79.35% | 1708.334 s | {'verification_error': 1} |
| 276456d | bowl_transfer | 1/1 | 20.65–100.00% | 481.756 s | — |
| 276456d | microwave_open | 0/1 | 0.00–79.35% | 738.516 s | {'planning_unreachable': 1} |

尚未满20状态，不宣布类别通过。276456d的碗init6重放改善是同一状态的配对结果，不增加独立样本分母。3d71f44 init14是感知绑定歧义（两个plate），原始记录中的planning_unreachable保留；init16已抓起，但随后搬运被公开碰撞筛查拒绝。11ec9aa杯子8249_60仍运行；已完成第一个杯子的抓起、搬运和释放，第二个杯子仍待完成，不提前记任务成功。

已修并推送harness-v5：

- af76e3d23f37bd132135a2be874138f704425a37：接触进展区间5mm边界的浮点误拒绝。严格5mm门槛不变；11条真实公开RGB-D回执CPU复算，2条unmeasured→success，其余9条不变。198项CPU测试通过；8250_120是同源同launcher启动预检，等待8249自然退出。
- b205277：oracle按公开测量联合消歧between源/参照配对，保留所有公开实体；真实init14由(null,null)变为(e28,e90)，存在两种可行配对时继续拒绝。233项CPU测试通过，尚无该修复的完整物理结果。
- e42526446e264056546ccb3c9d360f0daf0e599f：公开把手点云三维主轴；修复把柜门水平切向误作竖直把手轴。真实旧点云主轴约(-.006807,-.004957,.999965)，最大/次大方差比19.69。保留1mm残差、90度圆弧支持和4mm碰撞间隙。235项CPU测试通过（86.92秒）；Ruff通过。实际核心适配器、同保存RGB-D/本体状态/起始速度的CPU配对：旧路线碰撞拒绝，新路线通过，最小间隙7.685mm。该结果仅为几何筛查；物理任务尚未验证。

当前不可变源码：/public/home/sunyihan/rpent_libero_eval/source_bounded_e425264_20261018；归档SHA256 6f521a16226ea66680e13af6f27e2cf76ffbb5ee27c06e48621e2e4e7136f35f。220状态CPU预检通过；manifest results/bounded_skills/feasibility_20261017/preparation/original20_manifest_handle_axis_20261018.json，SHA e477bb56813501a7c4f2e6b7b468b169c162b7c9a84c35f29290e2e399970000。入口scripts.probe_bounded_feasibility:episode、robots.libero.bounded_skills:MeasuredSkillAdapter.request/execute，解释器/public/home/sunyihan/rpent_libero_eval/.venv/bin/python。schema仍bounded-skills/1；无模型可见字段变更。

第一通道：8249_60完整杯子 → 8250_120数值修复微波炉关闭启动 → 8253_140三维把手轴微波炉打开启动。启动产生真实物理请求并正常退出后，才接同源完整回合；完整微波炉关闭将接在8253之后，保持串行。第二通道：8192抽屉打开剩余19状态 → 8252抽屉关闭、开火、关火各19状态（共57，throttle=1）；同源同launcher已有真实启动和完整代表成功。第三通道：8173继续碗/盒/容器，throttle=1。运行中的旧版本不取消，失败记录保留。

本轮不训练、不做确认判定、不读取PRO。所有确认状态永久排除训练继续有效。先补各类oracle上限，再两个对照、K1/K4和分叉记录；历史π0.5/旧专家/平滑度数字不冒充当前版本对照。当前未冻结。
