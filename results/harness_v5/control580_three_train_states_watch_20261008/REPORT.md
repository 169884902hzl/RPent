# control580 r2：三个原版训练状态的真实采集与可测性

4467_0（seed0）、4474_1（seed1）、4474_2（seed2）均 `COMPLETED 0:0`。每状态开火 160 块 / 800 controls，关火 160 块 / 800 controls；合计 4800 contact controls。480 条 off 逐块记录序号完整，每条实际执行 5 controls，公开 source_step 严格递增。最终 collector boundary 为 completed、stop_admitted=false、model_or_skill_success=null；这是采集链通过，不是关火技能达标。

| 原版状态 | 关火 true 的块末端 | 首块 / 末块的私有转轴角 | 三个时序阶段的关火正标签 |
| --- | ---: | --- | ---: |
| goal task7 init0 | 0/160 | 2.093687 / 2.093517 | 0/9 |
| goal task7 init1 | 0/160 | 2.094875 / 2.094871 | 0/9 |
| goal task7 init2 | 0/160 | 2.097135 / 2.097111 | 0/9 |

所有 480 个块末端 turn_on=true；三个状态的转轴跨度分别只有 0.000170、0.000004、0.000024。没有观测到任何块末端“已关上、后来又退回”。标签每 5 controls 保存一次，未保存逐 control 的 turn_off 真值，因此不能将此结果冒报为 0/2400 个逐 control 正例。关节和谓词仅用于后置诊断，不进入公开输入或控制决策。

18 个固定阶段标签和 27 个多帧序列标签均无 turn_off 正类。本批单独不能计算关火分类器 AUROC，也不能校准两类的停止门。末态关火为 0/3；Wilson 95% CI 为 [0, 0.562]，只描述这三个训练状态，不是独立确认批。

before_off、after_release、after_retreat 各保存三个公开帧，共 27 帧 / 54 个相机视图。每个阶段只有首帧重新执行 SAM 几何查询，共 18 个查询结果；其它 36 个 raw RGB-D 视图有意不重复查询，保留原图、点云和缓存几何引用，不能把它们算成 36 次检测失败。

- 18 个实际 control feature 查询结果中，16 个 `no_valid_current_control`。
- 另外 2 个能测到 control_pose，但 pivot、tip 或 front_edge 缺失；有向转轴角 0/18 可测。
- 所有 18 个 feature endpoint_state 为 unmeasured。仅有无方向的表面轴线不能判开关。

因此应分别处理“动作没有关火”和“公开控制几何缺测”。原始双视角 RGB-D 与本体变化已经实采，可继续用于时序验证器开发；此次不放宽公开阈值、不把缺测改为通过。

完整逐块端点、逐帧公共绑定、原始输入路径与 SHA 在 report.json。读取仅由 manifest、三个 ledger 及其中的文件引用定位；off 私有标签的固定同目录 `labels.json` 写法来自已固定的 r2 producer 第 108 行，未枚举产物目录。已登记确认排除的 overlap 为 0，但 confirmation_registry_complete=false；不能把它说成完整排除审计通过。首轮只看 27 帧的记录保留在 phase_frame_initial_report.json。
