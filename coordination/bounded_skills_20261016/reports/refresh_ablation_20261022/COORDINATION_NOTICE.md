[Codex3 | 2026-10-22 | 严格 N1 完整 30 对闭合]

精确执行树9d00ee63ab2196b95f8374e8245d9dea2ed8782b，归档SHA256
4623439f8b3415ab09148fbb798f5c86250a4008183111b262664f564a664c5b。
job11229三片均COMPLETED0:0。旧栈25/30，新栈24/30，改善1、退步2；
30个完整积分/控制器/RNG初态SHA均相同，24/25两个VLA试点不进分母。
达到用户≥24/30开发指标，不代表精度等价或任何确认批改判。
逐状态/四段时延原件：
/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/refresh_ablation/N1_30/partial29_verified/
该目录实际包含完整30对；本地报告为reports/refresh_ablation_20261022/。
循环中位104.276→30.152秒，整局333.929→123.833秒；四段每决策中位
18.866/63.403/14.717/4.327→3.857/12.197/2.638/2.589秒。
决策段含oracle后继legal标注14.548→2.619秒，不是模型推理时间。
退步object_swap_t0_s40、object_task_t0_s40的后续探针仍与本分母隔离。

接续90个原版train已登记状态：self每状态2次、initial_pose每状态3次。
执行/碰撞/oracle/chunk代码与达标N1相同；只叠加登记的重复采样、原生终态
完整恢复、未绑定VLA回退和诊断存盘字段，单独快照登记后做启动检查。
尚未交付新90状态标签，不把旧self1当成self2，也不重复append旧记录。
F4未执行检查为null及未执行lift保持夹持均保留，未据此声称held=True。
确认池永久排除，PRO/D2只用于评测；没有训练任何模型。

D2三项结论、245条归因和22条逐局表：
coordination/bounded_skills_20261016/reports/attached_05143337_20261022/D2_THREE_ISSUES.md。
170条绑定缺失的回退和终态native缓冲修复有CPU证据；新D2三档仍在90重测之后。
