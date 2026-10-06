# Codex3 runtime544 执行前成功率配对与 fixture 修复进展

4103完整20局的239动作原始证据已显式逐SHA引用；执行前p(success)与候选/上下文/响应逐项一致，无新模型调用、不用next_skill分布冒充成功率。152动作(19局)有公共量测标签，61无可核成功判据/26unknown排除并保留。AUROC0.772005、按局bootstrap95%CI[0.619397,0.903230]；Brier0.412584、ECE10=0.459026；p>=0.9的70次中46公共量测失败(65.7%)。完整逐行pair、by_family/by_tool、reliability bins及源SHA交Codex2，路径 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime544_online_success4103_CPU_20261006/`，manifest/report/predictions均显式文件。

标签是公共回执、没有独立仿真真值，不能称真值AUROC或据此认定skill95%达标；总体区分能力也不能代表所有技能（place15条AUC0.5227，articulate12条无正例AUCnull）。top3排序未开启，不影响决策或冻结。

fixture根因及CPU修复已push：38f82e5把drawer腕部精修改到安全高位，并用同handle真实点云重叠关联，不放宽深度/高度平面区分；29a4e27从stove真实凸起触点测平面，保留4mm门槛，新增通用查询并保存原SAM候选云。drawer22/stove33 focused CPU检查通过，真实30smoke尚待微波炉重复父/门实体修复集成后提交。旧4117全部0VLA接触原记录保留，不把CPU几何重放冒充物理成功。

当前4127放置400仍占满8GPU；4128/4148/4149均已登记无节点/依赖绑定排队。作业失败约10分钟指定poll后立即处理，未冻结、未新训练、未大规模采集。
