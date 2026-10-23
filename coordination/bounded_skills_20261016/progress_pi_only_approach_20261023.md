# 10/22 20:30 PT 接续

- 用户范围：纯π整句评测、约30个准备路径否决诊断、无人求助公开字段；v-next-b和新的DAgger清单等Claude登记，不启旧服务、不训练。
- 实现仓库 harness-v5；保留既有无关dirty。当前生产诊断源为冻结 Git tree `2db200134ea6689e36a66e8aee6f45daa8270b4e`，不是commit。
- 纯π46臂11610–11613均COMPLETED 0:0。D2 18/40 [30.7%,60.2%]，首试16、重试补2；原版6/6，对应3初态的K1/K4标签。38局初态SHA与24/40回放匹配、2局旧对照SHA缺失。
- 远端原件：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/pi_only_and_approach_20261023/CPU_pi_only46`；本地镜像 reports/pi_only_and_approach_20261023。
- 路径诊断：105个零步单事件手扫掠否决，35个不同状态；类别轮转抽30个（碗3/盒5/容器5/杯1/关抽屉5/开抽屉4/开微波炉6/盘1）。直线无否决与高位路径保留原筛查，同完整状态、同公开端点。只在开发入口禁用否决，私有接触只作评分。
- 11620–11622缺SAM3_CHECKPOINT_PATH，启动即退，无物理结果；日志保留。启动配置补齐后11623–11625重提，输出approach_shard{0,1,2}_r2。Codex2有11615单卡，当前只占3卡。
- `human_available`根字段默认false，无人不生成ask_help，legal/5排除（含停滞时），schema6/7均附加可选布尔；历史缺字段视为不可用，旧结果不重跑。41项聚焦CPU测试通过；大CPU面板在本地.venv重跑，先导入env_server保正确MuJoCo导入顺序。
- 待做：路径真实接触/到达统计决定是否部署通用路径；若部署按用户做N2/155/旧方法/N1回归和D2恢复1。提交仅本轮hunk，bounded_skills已有无关SAM缓存改动不得暂存。

## 闭合更新

- 11623–11625全部COMPLETED 0:0，30对初态/端点全部相同。直线新增接触11/30，超过1mm的2/30、无超过5mm；6到位（5无新增接触），其余不能按误杀计。高位29扫掠+1IK全0步，不部署，不启动条件性N2/155/D2重复批。
- 人类能力修改`ff352fc4`已推送harness-v5；向Codex2发了字段与两份schema/contract SHA通知。生产路径源码未改，无关SAM缓存hunk保留dirty。
- 大CPU面板832过、1旧期待失败；该测试按有人/无人分支更新，58项相关面板全部通过。诊断和纯π聚焦41过。
- 报告见reports/pi_only_and_approach_20261023/STATUS.md。当前等待Claude登记v-next-b和DAgger清单；本轮自有队列已清空。
