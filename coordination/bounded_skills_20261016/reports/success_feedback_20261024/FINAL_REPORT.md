成功反馈、持续尝试和宽容准备已实现；三臂138回合全部闭合，46组完整初态、策略种子和配置逐一一致。
D2 的纯π+A、规则oracle+A、规则oracle+AB分别为21/40、28/40、29/40；原版三臂均6/6。
N2宽容准备36/36实际调到π，但仅9/36到点；新增或加深接触超过1µm为15/36，超过1mm为3/36。
新接触技能完成40个训练状态各3次实测，关抽屉6/30，其余三类尚未成功；默认63训练位置189次试验已全部交付。
最终合格快照通过345项CPU测试；本轮自己的作业已清空，未训练模型。

## 整局同口径比较

| 方法 | D2成功 | Wilson 95% | 决策次数中位 | worker墙钟中位/均值 s |
|---|---:|---:|---:|---:|
| 纯π+A | 21/40 | 37.5%–67.1% | 15.5 | 620.4/826.4 |
| 规则oracle+A | 28/40 | 54.6%–81.9% | 4 | 255.9/458.4 |
| 规则oracle+AB | 29/40 | 57.2%–83.9% | 4 | 201.1/400.9 |

对照是旧纯π18/40、旧oracle24/40、A1-M28/40。纯π+A相对旧纯π改善3、退步0；oracle+A相对旧oracle改善7、退步3；oracle+AB改善8、退步3。全部失败保留。
40个D2初态也与旧纯π逐一核对。每回合最多40次决策、10000环境步；单个选项失败或无进展交还决策，不重置世界。A=false时finish非法，human_available=false时ask_help非法；B默认只在开发臂打开。原始summary记录每局实际开关。
原版6臂是3个独立初态各K=1/K=4。每个K均3/3，Wilson 95%为43.9%–100%；不能当成6个独立布局。
墙钟来自并行N8工作进程的启动至summary写出，含环境初始化、初始感知和恢复；另存恢复后循环wall_s。不能当成N1时延，亦不能直接据此比较Astra。
规则oracle使用私有进度和历史有限采样的方法偏好，不是穷尽动作/种子的数学上界。A和AB两臂的oracle本来都能读私有谓词；29/40对28/40不能解释为B的信息增益。唯一差异局libero_10_task_t2_s40在同种子下第11个零基动作块首先出现腕部图像hash不同，第40块首先出现预测动作不同；日志定位到观测/执行分叉，未证明具体渲染或数值根因。

- [逐局成功、决策、墙钟及旧基线](CPU_three_arms_closed/paired_table.md)
- [46组完整配对JSONL](CPU_three_arms_closed/paired_cases.jsonl)
- [完整区间、K分列与统计口径](CPU_three_arms_closed/RESULTS.md)
- [A/AB策略输入和预测差异](CPU_AB_policy_trace_difference.json)

## 宽容准备：N2

12个原版训练状态，每方法每状态3次，共72次；36对完整初态SHA一致。screened有6/36调到π、6/36到点；permissive有36/36调到π、9/36到点。后者新增/加深手部接触>1µm为15/36、>1mm为3/36；非目标物体最大位移5.900mm。逐状态终点误差在下表。
口径更正：旧登记中的0/36→7/36是分支结束时的登记任务谓词，不能解释为所有模式的局部成功率。盒子执行pick，但私有抓取v3未单独计量；每臂6次局部真值unknown。其余5类共30次/臂，局部私有谓词成功为0/30→7/30。物理试验unknown为0；局部真值unknown与程序错误、物理失败分开。原始结果文件未改。

- [准备、接触、误差逐状态表](CPU_N2_final_scopes/paired_table.md)
- [分类别接触与终点误差](CPU_N2_final_scopes/RESULTS.md)
- [局部真值适用范围](CPU_N2_final_scopes/subtask_scope.md)

## 公开测量接触技能

| 类别 | 训练状态数 | 成功/可计量试验 | 绑定unknown | 真正执行自适应推进 |
|---|---:|---:|---:|---:|
| 关抽屉 | 10 | 6/30 | 0 | 12 |
| 开微波炉 | 10 | 0/30 | 0 | 3 |
| 关微波炉 | 10 | 0/27 | 3 | 0 |
| 推盘子 | 10 | 0/30 | 0 | 0 |

关抽屉成功来自两个独立状态各3次。与修前117个可计量分支逐次配对，完整初态相同，改善6、退步0，另有3个绑定unknown。其余类别主要被已有的接近准备拒绝，不能称该控制器通用于四类。
真实几何复现表明2cm推进在约18.6mm处触及3.81mm指壳间隙；同输入1cm前缀通过。执行器仅在零控制的碰撞拒绝后试1cm，保留4mm间隙和全部筛查；已运动的增量不做这种回退重试。
执行器从公开RGB-D表面配准/位移选后续方向；私有关节角不进入控制。诊断oracle的准备选择使用私有任务谓词，这与接触控制器的公开输入边界分开记录。
精确v9菜单在事后选中的一个已成功训练状态上重复3次：3/3原生成功，每次173控制步，与原r2控制数组最大差为0；它只验证接口/回执，不增加成功率分母。后续CPU快照仅修小位移累计与未知测量的null回执，不改控制动作、力或停止条件。

- [四类实测](CPU_skills_r2_closed/RESULTS.md)
- [逐状态修前/修后](CPU_skills_r2_closed/paired_with_previous.md)
- [精确schema9菜单核对](CPU_menu9_closed/manifest.json)

## 默认项训练标签

只采MISSING_DEFAULT_MEASUREMENTS中的63个train位置；54个holdout排除。每位置3次，189次有效试验，其中成功157、失败32、unknown0。来源、请求、快照、候选、前缀和旧outcome_contract绑定保持原值，不借v9标签。
| 类别 | 位置 | 成功/试验 |
|---|---:|---:|
| bowl_transfer | 7 | 21/21 |
| box_transfer | 7 | 21/21 |
| cup_transfer | 7 | 20/21 |
| container | 7 | 21/21 |
| drawer_open | 7 | 15/21 |
| drawer_close | 7 | 20/21 |
| microwave_open | 7 | 17/21 |
| microwave_close | 7 | 14/21 |
| plate_push | 7 | 8/21 |

早期生产器调用旧冻结树不存在的grasp_trial_reference接口，已修为旧真值代码原用的facade.grasp_reference。保留22条旧程序错误日志，不当正负标签。45次已有有效物理试验按摘要和终点SHA原样复用。
最终包是preview1的超集，按query_id/sample_id去重，不能拼接重复样本。格式measured-subtask-choice/2，数据SHA为`63f6716f874e8eb9bc8d5d82a4bee28c61604ea812f12579a235c391352bb77d`。PRO、D2、确认集不进入训练。

- [63位置完整标签](CPU_default63_r2_export_closed/positions.jsonl)
- [标签manifest和绑定来源](CPU_default63_r2_export_closed/manifest.json)
- [旧API修复和45次复用核验](CPU_default63_API_and_resume.json)

## 冻结源码与验证

| 用途 | 冻结tree SHA | 远端目录（ROOT下） |
|---|---|---|
| 三臂与N2 | `3605901c7425d27df9fa04d1ca7345aeeb388663` | `source_feedback8_3605901c_20261024` |
| 四类120次接触试验 | `75e333fad1542733ab14aab9f86888c1777730a7` | `source_feedback_contact_75e333fa_20261024` |
| 精确v9菜单物理核对 | `018f13c6728abae8279902b70dac847f365340d0` | `source_feedback9_018f13c6_20261024` |
| 最终回执数值修复、345项CPU | `736631d06d6dd332144f447b18dde27a4fecde87` | `source_feedback9_736631d0_20261024` |
| 默认63位置旧执行树 | `f6987f0d519f9864c9cddb4aa3d69c482b034f47` | `source_native_model_f6987f0d_20261022` |

ROOT=`/public/home/sunyihan/rpent_libero_eval`；RUN=`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/success_feedback_20261024`。冻结目录不原地修改。发布commit与各物理快照分开标识；未把无关的本地dirty guided-SAM cache混入合格快照。

| 接口 | schema SHA256 | contract SHA256 |
|---|---|---|
| v8 / legal6 | `5ab07c9ce77fef3f339cbb29fc6d45fd5f7060f1bcf193f044e229448a8928b4` | `b6917b52a9cbe317adebec3d3140e2db509a838a898bb0db330952a8d2eba99b` |
| v9 / legal7 | `49633b98a14ce6283c2f4b76914ddece49d74072636573b67a4eea6e717179c8` | `5a82e723a16169e3984e63e52d18d33476d427242fcc8b058f05ffc5d6d9ca31` |

v9模型菜单默认关闭，需Codex2同步序列化后启用；oracle/dev可显式启用。A/B开关和激进循环已分别推送并通知Codex2，本次补最终产物与N2口径更正。

最终CPU命令（在736快照目录，Python为ROOT/.venv/bin/python）：

```bash
python -m pytest -q \
  tests/unit_tests/robots/libero/test_bounded_feedback.py \
  tests/unit_tests/robots/libero/test_bounded_success_loop.py \
  tests/unit_tests/robots/libero/test_bounded_persistent_contact.py \
  tests/unit_tests/robots/libero/test_bounded_schema9_contact.py \
  tests/unit_tests/robots/libero/test_bounded_skills.py \
  tests/unit_tests/robots/libero/test_bounded_schema6.py \
  tests/unit_tests/robots/libero/test_bounded_chunk.py
```

345 passed、1条已有pytest timeout配置warning，194.18秒。343项旧018面板也已通过。未运行全仓pytest、全仓pre-commit或Sphinx构建；本次是定向执行栈与独立Markdown交付，不是PR或Sphinx页面改动。

- [345项CPU摘要及原始日志SHA](CPU_qualified9_736631d0_tests.json)
- [最终冻结源登记](source_feedback9_736631d0_registration.json)

11956/11958/11959/11968/11973/11976和CPU11983均已结束；本轮C3运行/排队作业为0。C2的11981保留，其他项目与旧held作业未操作。
