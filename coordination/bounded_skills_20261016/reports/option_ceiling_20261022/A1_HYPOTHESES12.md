原版整句自检为106/110，推盘子和盒子各10/10，说明这两类原版初态能够完成。
A1的12局仅有公开初态摘要；EEF均在1e-9 m内相同，完整积分、控制器和RNG初态不能认证相同。
单独换A1提示或其预算/停止规则，旧树的11个有效配对状态各只多出1次子任务成功；三个策略种子的证据范围有限。
平底锅的旧单因素行误配到炉灶调用，已保留并排除其因果解释；纠正后较长预算臂原生整局2/3，A1八块预算与原语均0/3。
子任务抓取失败和整局完成分别保存；六条已核实漏计保留原分数，新源码单列原生完成。新整局采样上限另见本轮最终报告。

下表记录A1实际工具参数和实测动作块。原件没有逐控制步ledger，每次π调用的精确控制步数缺测；不把块数乘5当实测步数。

| 局 | π调用数 | 实测块数 | 同子任务π重试 | 完整初态 |
|---|---:|---|---|---|
| libero_spatial_swap_t4_s40 | 1 | 8 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_spatial_task_t0_s40 | 2 | 9,8 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_spatial_task_t4_s40 | 2 | 8,4 | pick重试1次 | 缺全状态 |
| libero_object_swap_t3_s40 | 2 | 8,8 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_object_task_t3_s40 | 1 | 16 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_goal_task_t0_s40 | 1 | 19 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_10_swap_t0_s40 | 2 | 14,14 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_10_swap_t2_s40 | 6 | 24,16,24,20,25,22 | moka重试2次；stove重试2次 | 缺全状态 |
| libero_goal_swap_t4_s40 | 1 | 7 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_object_swap_t4_s40 | 1 | 20 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_goal_task_t2_s40 | 1 | 16 | 0；不同子任务调用分开计 | 缺全状态 |
| libero_10_task_t2_s40 | 4 | 20,8,10,8 | pan pick重试1次 | 缺全状态 |

共24次π调用、336个实测动作块。重试按同一目标子任务的再次调用计，所有提示及工具回执保留在原始提取文件中。

| 局 / 子任务 | 基线 子任务/整局 | A1提示 | A1预算/停止 | RPen原语 | 源码树 |
|---|---:|---:|---:|---:|---|
| libero_spatial_swap_t4_s40 / g0:pick | 0/3；0/3 | 1/3；0/3 | 1/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_spatial_task_t0_s40 / g0:pick | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_spatial_task_t4_s40 / g0:pick | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_object_swap_t3_s40 / g0:pick | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_object_task_t3_s40 / g0:pick | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_goal_task_t0_s40 / g0:open | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_10_swap_t0_s40 / g0:pick | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_10_swap_t2_s40 / g1:pick | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_goal_swap_t4_s40 / g0:on | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 6c1de614 |
| libero_object_swap_t4_s40 / g0:in | 0/3；0/3 | 0/3；0/3 | 0/3；0/3 | 3/3；3/3 | 6c1de614 |
| libero_goal_task_t2_s40 / g0:on | 3/3；3/3 | 3/3；3/3 | 3/3；3/3 | 3/3；3/3 | 6c1de614 |
| libero_10_task_t2_s40 / g1:pick | 0/3；2/3 | 0/3；2/3 | 0/3；0/3 | 0/3；0/3 | f6987f0d；纠正pan对应；基线使用新默认预算 |

每行三次均从同一保存的完整初态、使用配对策略种子开始。旧树其余11行和纠正后的pan行分别报告，不把它们包装成同一预算下的统一总平均。原语臂与预算/停止臂比较；on/in子任务中A1可能实际使用脚本放置，不能把其邻近pick工具当成完整放置配方。

| 局 | H1 提示 / H2预算证据 | H3 准备移动或脚本尾段（子任务；原生整局） | H4 | H5 |
|---|---|---|---|---|
| libero_spatial_swap_t4_s40 | 提示 1/3，预算 1/3；基线 0/3 | 0/3；0/3 → 0/3；0/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_spatial_task_t0_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 2/3；0/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_spatial_task_t4_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 0/3；0/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_object_swap_t3_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 3/3；0/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_object_task_t3_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 1/3；3/3 | 缺全状态，未排除 | 出现抓取False但native整局True，分开记账 |
| libero_goal_task_t0_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 0/3；0/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_10_swap_t0_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 0/3；0/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_10_swap_t2_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 0/3；0/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_goal_swap_t4_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 3/3；3/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_object_swap_t4_s40 | 提示 0/3，预算 0/3；基线 0/3 | 0/3；0/3 → 3/3；3/3 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_goal_task_t2_s40 | 提示 3/3，预算 3/3；基线 3/3 | 不适用：A1无单独脚本放置尾段 | 缺全状态，未排除 | 未证实私有子任务判据错误；回放差异另表 |
| libero_10_task_t2_s40 | 新长预算native2/3；A1提示2/3；A1短预算与原语0/3 | 0/3；0/3 → 0/3；1/3 | 缺全状态，未排除 | 出现抓取False但native整局True，分开记账 |

A1测得的绝对笛卡尔命令仅用于评测干预，未进入运行时技能或训练。准备动作整组改变属于H3干预；后续子任务还存在A1任务顺序差异，不能由这组结果单独解释所有优势。

每个实际π调用的原始提示和参数：

| 局 / ordinal | 工具 | 参数 | 实测块数 |
|---|---|---|---:|
| libero_spatial_swap_t4_s40 / 19 | pi0_pick | `{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 30, "prompt": "Pick the akita black bowl in the top layer of the wooden cabinet and place it on the plate"}` | 8 |
| libero_spatial_task_t0_s40 / 17 | pi0_pick | `{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 10, "prompt": "grasp the upper right black bowl by the rim"}` | 9 |
| libero_spatial_task_t0_s40 / 24 | pi0_doubled | `{"max_chunks": 15, "prompt": "seat the black bowl on the plate"}` | 8 |
| libero_spatial_task_t4_s40 / 19 | pi0_pick | `{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 30, "prompt": "Pick the akita black bowl on the top of the wooden cabinet and place it on the plate"}` | 8 |
| libero_spatial_task_t4_s40 / 28 | pi0_pick | `{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 12, "prompt": "pick up the black bowl"}` | 4 |
| libero_object_swap_t3_s40 / 18 | pi0_pick | `{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 12, "prompt": "pick up the brown BBQ sauce bottle with red cap"}` | 8 |
| libero_object_swap_t3_s40 / 21 | pi0_doubled | `{"max_chunks": 14, "prompt": "put the bbq sauce into the basket"}` | 8 |
| libero_object_task_t3_s40 / 11 | pi0_pick | `{"prompt": "pick up the ketchup", "max_chunks": 20, "lift_thresh": 0.08, "gripper_closed_thresh": 0.06}` | 16 |
| libero_goal_task_t0_s40 / 11 | pi0_doubled | `{"prompt": "pull the lowest gray drawer handle outward", "max_chunks": 35}` | 19 |
| libero_10_swap_t0_s40 / 11 | pi0_pick | `{"prompt": "pick up the tomato sauce can", "max_chunks": 14, "gripper_closed_thresh": 0.04}` | 14 |
| libero_10_swap_t0_s40 / 19 | pi0_pick | `{"max_chunks": 14, "prompt": "pick up the alphabet soup can", "gripper_closed_thresh": 0.04}` | 14 |
| libero_10_swap_t2_s40 / 24 | pi0_pick | `{"prompt": "pick up the moka pot", "max_chunks": 24, "lift_thresh": 0.05, "gripper_closed_thresh": 0.06}` | 24 |
| libero_10_swap_t2_s40 / 26 | pi0_pick | `{"prompt": "grasp the moka pot", "max_chunks": 16, "lift_thresh": 0.05, "gripper_closed_thresh": 0.06, "descent_thresh": 0.08}` | 16 |
| libero_10_swap_t2_s40 / 36 | pi0_pick | `{"prompt": "pick up the moka pot", "max_chunks": 24, "lift_thresh": 0.05, "gripper_closed_thresh": 0.06}` | 24 |
| libero_10_swap_t2_s40 / 43 | pi0_doubled | `{"max_chunks": 20, "prompt": "turn on the stove"}` | 20 |
| libero_10_swap_t2_s40 / 45 | pi0_doubled | `{"max_chunks": 25, "prompt": "turn the stove knob to turn on the stove"}` | 25 |
| libero_10_swap_t2_s40 / 47 | pi0_pick | `{"prompt": "turn on the stove", "max_chunks": 25, "lift_thresh": 999, "gripper_closed_thresh": 0}` | 22 |
| libero_goal_swap_t4_s40 / 11 | pi0_pick | `{"prompt": "pick up the patterned bowl", "max_chunks": 12, "lift_thresh": 0.05, "gripper_closed_thresh": 0.06}` | 7 |
| libero_object_swap_t4_s40 / 12 | pi0_pick | `{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 20, "prompt": "pick up the ketchup"}` | 20 |
| libero_goal_task_t2_s40 / 16 | pi0_pick | `{"prompt": "put the wine bottle in the bowl", "max_chunks": 24, "lift_thresh": 0.05, "gripper_closed_thresh": 0.06}` | 16 |
| libero_10_task_t2_s40 / 11 | pi0_pick | `{"gripper_closed_thresh": 0, "lift_thresh": 999, "max_chunks": 20, "prompt": "turn on the stove"}` | 20 |
| libero_10_task_t2_s40 / 14 | pi0_pick | `{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 8, "prompt": "grasp the pan handle"}` | 8 |
| libero_10_task_t2_s40 / 26 | pi0_doubled | `{"max_chunks": 10, "prompt": "push the pan onto the burner"}` | 10 |
| libero_10_task_t2_s40 / 29 | pi0_pick | `{"gripper_closed_thresh": 0.06, "lift_thresh": 0.05, "max_chunks": 8, "prompt": "grasp the pan handle"}` | 8 |

原件与独立核验入口：

- [A1实际物理调用和原件引用](A1_12_physical_calls.json)
- [原12状态单因素记录](factors12_summary.json)
- [纠正pan单因素](A1_pan_factor_corrected.json)
- [纠正pan准备动作](A1_pan_staging_corrected.json)
- [CPU原生端点漏计普查](native_endpoint_audit_summary.json)
- Codex1独立报告：/public/home/sunyihan/rd_instruction_20260923/codex1_USER1022_0540/A1_ATTRIBUTION12.md；保留其独立结论，未改写。
