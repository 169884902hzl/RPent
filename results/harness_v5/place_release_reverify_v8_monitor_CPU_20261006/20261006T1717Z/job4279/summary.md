# job4279 / 放置 v8 完整选择批回执

40/40 注册案例已记录，8 片全部 COMPLETED 0:0。保留原始结果，未改变旧 4219/4262 判定。本报告是原版任务选择批，不授确认或冻结资格。

全 40 注册分母：22 次真实执行、18 次未执行；新增完成 16/40（40.0%，Wilson 26.3–55.4%），已有完成保留 5/40。终态物理真 21/40（52.5%，Wilson 37.5–67.1%），其中 5 个本来就已满足，不能称为新增完成。setup v2 真 19/40（47.5%，Wilson 32.9–62.5%），假 21/40；旧版 setup 真 21，其中 2 个被全接触支撑规则 v2 判为假。

条件分母“真实持续持物 setup、动作前未完成、动作实际执行”为 13/13 首次新增完成（100%，Wilson 77.2–100.0%）。13 只用于技能条件分析，不能代替 40 注册分母或先筛状态授门槛。

| 方法 | setup v2 真/注册 | 真实执行 | 条件分母首次新增完成 | Wilson 95% | TP / FP / FN / TN / null |
|---|---:|---:|---:|---|---|
| place_in/current160 | 4/10 | 6 | 3/3 | 43.9–100.0% | 6 / 0 / 0 / 0 / 0 |
| place_on/current160 | 4/10 | 4 | 2/2 | 34.2–100.0% | 3 / 0 / 0 / 1 / 0 |
| place_in/vla_subtask160 | 5/10 | 7 | 3/3 | 43.9–100.0% | 2 / 0 / 0 / 0 / 5 |
| place_on/vla_subtask160 | 6/10 | 5 | 5/5 | 56.6–100.0% | 3 / 0 / 2 / 0 / 0 |

strict6 验证：TP14、FP0、FN2、TN1、null5。可测精确率 14/14（100%，Wilson 78.5–100.0%），可测召回 14/16（87.5%，Wilson 64.0–96.5%）；已执行且真值已知的总体一致 15/22（68.2%，Wilson 47.3–83.6%），其中 null 保持“未证实”。公共两帧覆盖 17/22（77.3%）。样本及覆盖不足以满足行业准入。

2 个 FN 分别为 footprint 不足、真实末端闭夹；5 个 null 全部属于 in/VLA，first 和 second 都是 invisible 的同 source_step 缓存。动作后端点 private 真，但无两帧公共测量，不能改成成功。5 例末端 EEF 仍在抽屉附近；同姿态 v7 重测未解决视线/缓存问题，下一步需要真实移出遮挡再观测，并保持缺测为 null。

实际 v8 开夹重验触发 1 次：`place548_place_on_libero_90_t10_s4_r0_place_vla_subtask160`。真实 release 20 控制步，开度从 0.0653m 到 0.0786m；新传感器开度 0.0785784423m，两帧 fresh，公共 false→true，最终 private 真。同次 VLA 的传感器逐块与真实 motion trace 完全一致。没有 release 前即时 private truth，故不将这个公共变化称为已证明的物理改善。

基础设施失败 0，execution_error 0，短 VLA 块 0。setup VLA 15775/15775、first VLA 10130/10130 控制步均完整；first non-VLA 846 步。全 40 案例实际只有 20 个唯一原始状态，条件间复用同 state SHA，不是 40 个独立状态。

## setup 与绑定缺口

40 个 setup 全部仍是通用 direct：base SHA 3805be2a884256b8ce8e76c5c5d1507ce38bff8fcbeb8394d37cb87af83a547e 与 arm overrides 均未启用 `grasp_category_profiles_v1`，不是已选定的类别技能卡。实际 receipt 的 approach standoff 为 15cm，允许残差 8cm；旧公开抓取验证仍沿用注册 base。

全 setup 公私混淆 TP18、FP10、FN1、TN11，公开报成功 28/40、实际持续持物 19/40。12 个公开 setup 失败：11 chunk_budget、1 waypoint_not_reached；端点分类为无 finger_contact 10、有接触但未持续离开支撑 1、真持物漏判 1。漏判例 t25/s3/VLA：开度 .0043m、测量升高 18.95cm，private 11/11 finger_contact 且 0/11 非夹爪支撑。setup 策略与验证器是最大缺口，独立确认必须用已确认类别方式及现行公共抓取验证器；不能把通用 direct 的缺口隐藏在放置条件分母中。

18 个未执行：公开 setup 失败 12；动作前公共目标缺失/歧义 3；所选实例非唯一 2；支持面非唯一 1。2 个实例绑定拒绝都因另一个同名 drawer 是不可见 cache；3 个目标绑定和 1 个支持面绑定涉及 cabinet / top surface 多实例。原始 peer 测量与 private setup 真值逐例保存在 diagnosis，不能用 private symbol 选择公开实体或忽略歧义。

4262 仍保留原 40：真 setup 条件新增完成 14/20、TP9/FP0/FN6/TN7/null5；4279 为 13/13、TP14/FP0/FN2/TN1/null5。注册状态相同，setup/控制轨迹却未锁定策略 RNG，所以这两轮差异不能归因给 v8。

## 证据与下一步

完整审计含 40 条互斥分类、22 条公共几何、原 4262 逐例标签和 9 个 explicit ledger 引用。所有 captured ledger 双端 SHA 一致，未扫描 artifacts。

独立确认草案：至少 100 个未用于选择的原版新状态原样尝试，不预筛持物真、可绑定或成功。确认保留 setup/绑定/缺测失败，同时报告全注册分母及真持物条件分母；on/in 分层；使用已确认类别 setup、原 strict6 和 v8。先修公共绑定与缺测并做 CPU 回归，再由父代理登记/提交。此处未生成 GPU 作业、物理试验或训练行。

| 文件 | SHA256 |
|---|---|
| report.json | `e2d0702d952b19b186300a856a2b018089310852cbe79d321c2585f382e8f2c8` |
| strict_setup_release_and_verifier_audit.json | `e6f510366b147631132bf1b97581f8a6b8a4307c2c6a3758a7fb4ef1cb04ef85` |
| setup_and_missing_frame_diagnosis.json | `46666be81fdb11ea6176203f7b763bb986c5acd79716449a1ecaf372a97366a7` |
| manifest | `d58698cef76bbbad9189238adf025a4e75c797b00bc511af06d7388db5c01a24` |
| source archive | `712e72d29c2adc4a6d73ed3ce152f60393a3975da96d9190bc35de9ce9de91d8` |

源码 snapshot：`/public/home/sunyihan/rpent_libero_eval/source_v5_place_release_reverify_v8_20261006`；commit `67a4d4bc67af5db89e31dd1f631c88a8eab6397b`。完整产物：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_release_reverify_v8_monitor_CPU_20261006/20261006T1717Z/job4279`。
