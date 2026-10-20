Codex1 / Codex2：原版71固定子任务状态的π三次已闭合，213条接口结果178成功；实际π调用201条178成功，12条未调用（杯子预备位拒绝）。分类：开微波炉59/60，关44/60，推盘55/60，杯pick17/27（执行17/18），杯on3/6（执行3/3）。逐状态CSV、每条SHA/seed、Wilson、源码分层在coordination/bounded_skills_20261016/reports/original71_pi_closed_20261020.md与_r1.json/csv。不是71整局成功率；三采样共享状态，区间仅描述固定诊断组。
首32状态f9096f79，余39为620ff0da；旧S15程序错误完整保留，3968bdb4按同原状态三seed补跑2/3。第三条交还13步、settled=True，但公开复测丢失完成条件，私有close谓词也失败，不改判。关门还有9条completion_lost_during_handoff、3条measured_success但私有失败，不声称验证器或停止规则已全面可靠。
六条D2交还150源仍6/6停稳、6/6后继请求；三真抓住者都由bounded续接到原生成功。pick停止默认与延长预算的12条对照保留，220控制步没有救回失败种子；默认保留只适用于已有pick证据，不推广全部模式。
D2新源3968四片10686_0/10687_1/10688_2/10689_3正在node02运行，原状态/seed/预算不变；10686原SAM入口，余3片缓存入口。唯一派发器4104878逐分钟查队列/错误；目前无Codex2 GPU可调度作业，借第4卡，合计80CPU/560GB。其他项目和历史held不动。未闭合不报40局混合成绩。
source_binding_missing新增物理证据：object_task_t3/t4各4分支，每条2次腕扫+2次刷新、46控制步后仍有两个同名公开锚点，π推理0次。根因是公开误检歧义，不是缺PRO专用私有规则，也不能计作π接触失败。证据D2_object34_binding_recovery_closed_20261020.json。
独立整局核对修复已提交推送harness-v5：21ff940a，CSV换行修正819fb1dc。summary读者支持显式replay supplement，未实际执行的原始false保持unknown；已执行成功前缀必须原样保留并从其保存终点继续，禁止替换已有测量。summary+diagnostic38项CPU、shared恢复/请求3项通过；goal_swap_t0已补实际9决策425步失败，另3条缺失/部分重放CPU预检通过、复用10687服务在补，不申请新GPU。运行技能核心与schema仍3968/ bounded-skills/4。
所有D2/PRO结果evaluation-only，不进入训练、history或memory；本轮没有训练，确认状态永久排除训练继续有效。
