# 10/24 06:40 PT 接续：宽容准备、绑定、私有规则和新训练布局

当前目录 /home/agilex/cobot_magic/rpent_libero_eval，分支harness-v5，起点0f4d11c8。
用户本轮：宽容准备进入oracle菜单+四类40状态各3重测，D2 oracle+A40；修三局绑定并复测；补两局storage规则；同生成器新约60train状态各whole-pi3+登记分叉；模型A schema8服务就绪后40D2+原版6。
不跑v-next-c、不训练。node02，nice500，C3最多3GPU，C2+C3<=80CPU/600GB。其他项目及旧held不动。仅全部自己任务清空、交付闭合才结束。

ROOT=/public/home/sunyihan/rpent_libero_eval，RUN=ROOT/results/bounded_skills/option_expansion_20261025。
SSH gpu5880-ts。
共享COORDINATION.md约6.9GB，只tail/flock append。C1/C2通知用ROOT/coordination/owner_alerts。
不使用子代理；未重复读memory。

## CPU生成与采集

12131 CPU数组60状态已全生成：RUN/layout60_CPU/states/case000-059。
登记RUN/preparation/layout60_registration.json。原生成器8a0f380a字节未改，20原版train父任务各3个新布局，种子11024000-11024059，上一批11020600-619不重叠，D2种子40不重叠。
每个状态有独立SHA、原生谓词可满足见证、无初始穿插和指令身份校验。CPU摘要RUN/preparation/CPU_layout60_valid.json。
生成器helper ROOT/prepare_asset_layouts_CPU_frozen_20261022.py，仅外部worker按每job旧distractors字段调用，既有generator文件不动。

采集60初态公开请求/完整checkpoint：source_own_layout_labels_c7520ae1_20261022（与旧65采集源一致）。
旧12199 capture启动失败，因为max_points1的纯快照采集故意0control，而旧startup硬要1control。日志保留，不是物理失败。
外部启动器ROOT/run_layout60_capture_only_20261025.py只移除不适用的startup，formal worker与模拟源码不变。12201跑RUN/collect60_r2，N8；60的kind=layout_collect，prefix_decisions1/max_points1。
完成后用已有prepare_own_layout_measured_CPU_20261022.py从point注册，每状态self2+in_place/initial_pose/full_task各3，共11；全句3次就在其中。后续源/标签保持准确绑定；最终交Codex2，PRO/D2/确认集不得训练。

## 模型A

C2新服务12193：/public/home/sunyihan/rd_instruction_20260923/c2_a_schema8_diag_20261024_0640/C3_SERVICE_HANDOFF_12193.json。
endpoint node02:18065/v1/bounded-choice；adapter5825fe0f4a29a268483413e6af07fb67be542df6b9477b5e79156749eb4efa26。
只支持K1，旧模型A合法softmax argmax，不是C，无新failure penalty。schema8/legal6，模型视图省略A/B，但source合法集和成功即停读完整A，false常数不影响候选。
12195已跑40D2+原版6，源3605901c（与基线相同），A-only，40decision/10000controls，human false，HTTP每步选择，不调oracle。
外部入口ROOT/run_model_A_feedback_20261025.py；本地已保存同名coordination/scripts。
RUN/model_A；RUN/preparation/model_A.json/sbatch。有效K全部1；原版6仍沿用相同3初态各两条，registered_baseline_k留旧1/4，不声称K4服务运行。
评测闭合后通知C2停服务，不自行取消12193（用户以前只授权取消11721，不沿用）。

## 宽容菜单与四类重测

实现工作区 /tmp/rd_option_expansion_20261025，从合格tree736631d06d6dd332144f447b18dde27a4fecde87隔离展开，避免本地未提交guided-SAM cache和HEAD另有代码污染。
/tmp/freeze_option10.py冻结修改（独立git index），/tmp/install_option10_remote.py部署新目录时用硬链接，再先unlink改变文件后解压，绝不原地修改旧快照。

新schema10：call_vla新增明确preparation=measured_anchor_permissive，同时保留screened measured_anchor；新接触技能可从任何测得把手/物体直接选compound准备。
新bounded_contact_setup.py用同一选中anchor的公开move_to/descend终点+bounded_permissive.move（200steps，2cm/0.10rad限幅，无扫掠/跟踪否决），再公开闭合；随后adaptive增量仍保留原4mm筛查、力和速度。无接触plan可公开surface拟合，否则明确失败。
实体不按私有任务筛选。模型8菜单保持冻结。

首版20df91b2 CPU1fail347pass，原因菜单只给有plan实体导致可见无拟合把手无选项。修后34eff6d725ae0a90dff64b377b9ddc2c8411321a，CPU12196 348pass。
12197 source_option10_34eff6d7_20261025 跑RUN/skills_permissive，40train状态各3。每个common_checkpoint直接从旧skills_r2引用，完整初态严格相同。
最新预览前五个关抽屉状态全3/3，不能作最终数字。源码控制端只用公开几何，私有接触度量只评判。
旧对照RUN(success_feedback)/CPU_skills_r2_closed：关抽屉6/30、开微波炉0/30、关微波炉0/27+3unknown、推盘子0/30。

## 绑定和规则根因

初始原件来自旧success_feedback_20261024/preparation/oracle_A_r1.json，case007 object_task_t3、case043 spatial_task_t0、case044 spatial_task_t4。
公开初帧框图在RUN/CPU_binding/case007.png/case043.png/case044.png，本地/tmp/rd_binding_images。
- t0两个碗早已独立(e118、e75)，未合并；指令not between被旧bind当positive between，错选e118。新否定关系CPU真实坐标测试选e75。
- object_t3实际一瓶ketchup e75和一瓶BBQ e113都被SAM叫ketchup，导致None。短GPU12198复用固定28类公开词表做裁图，e75 ketchup .875 vsBBQ .229；e113 BBQ .953 vsketchup .633。无私有类别/物体坐标。
- t4初始源e75正确（柜顶碗），但有假plate e32（炉灶片）和真plate e5；对e32所有类别分数<现有.35门槛（plate .0076，max黑书.230），应保留ID/点云但改unclassified object。真plate .9375；两个碗各.9805，保留独立。

新bounded_instance_crops.reclassify_duplicate_instances对重复类每个实例裁图，用既有v5_runtime的28类词表做分数argmax；门槛复用现有SAM .35；未决叫unclassified object，ID和障碍点云都保留。
词表从segmentation_prompt原dict提升为PUBLIC_SEGMENTATION_PROMPTS，内容字节语义未增特例。使用原mask证据+SHA及公开RGB-D，不按任务名写类规则。
同类物体描述优先唯一实测支撑面（如bowl on cabinet top surface），再保留左右序；schema10关系增above/below（原有left_of/on/in保持）。pi0图像水平镜像的轴约定原来有证据，未改。
CPU重放脚本ROOT/replay_binding_public_inputs_20261025.py（正在session25127），用12198冻结裁图得分重放三个旧公开输入，写RUN/CPU_binding/replayed_public_inputs.json；不要把CPU当物理。

两局规则缺口不是语法谓词未知，是同一drawer in+close缺“先开→插入→最后关”。新私有bounded_storage_progress.ordered_status通用重排并在测得原生close=True且未in时插入open前置；不进入公开adapter。
split_subtasks新版4不再宣称unsupported；BoundedOracle和success_loop私有选择都使用相同顺序。只用于上限测量，无D2阈值调优。

当前完整修复冻结8eb2b31e436eba87e1dba18e9c2d53e5b00f532c：ROOT/source_option10_8eb2b31e_20261025。
CPU12200已349pass/197.86s，1已有pytest timeout warning。除前版348外再加支撑面描述测试。
12202 D2 oracle+A 40局，RUN/oracle_A_option10；依赖CPU12200+四类12197，复用其卡不超3。
该40内包含用户3绑定复测和2规则复测。same full initial refs、policy seeds、config与28/40旧oracle相同；新schema10菜单和私有规则全登记，旧结果不改。

## 待继续

1. 查询当前12195/12197/12201/12202；修程序错不编物理标签；不要结束仍有本轮作业的回合。
2. 检查session25127 CPU真实输入绑定重放；如果失败定位具体边界。
3. 60点捕获完成后立即注册+提交同源分叉，至少full_task3/state；按原11分支格式全部测，可随物理卡释放分成2-3GPU，C3最多3。
4. 模型A闭合→CPU逐局表/ Wilson/40Aflag口径→通知C2停服务，绝不改其作业。
5. 四类闭合聚合与旧逐次同初态比较；D2新40闭合与28基线及方法并集40行表。
6. 新执行栈已加schema10，需继承旧N1/N2回归要求的相关证据，不借用旧源测试。不要未经证据改力/速度/碰撞阈值。
7. 同步schema10 SHA/contract SHA及新params给C1/C2共享登记，模型A仍schema8。不用v-next-c。
8. 集成本轮自己的补丁回harness-v5：只合入隔离目录相对736的差异（主HEAD部分实现不同，需3way按文件合并）；保留主目录旧dirty，不整文件覆盖bounded_skills中的guided-SAM cache。逐文件add、push已获授权，不merge/force。
9. 完成报告先<=5句结论、证据，未训练，数据隔离明确。


## 已刷新到最终 b96 快照

- 最终物理源码 b96cf55ffb6a446a08cae5809f0f42ba88e67221，CPU面板351通过（195.92s）。
- 旧8eb开发批12202保留11闭合局及未完成日志，因storage-open/observe私有oracle修复已取消，不混最终分母；旧待运行12233/12234也取消。
- 最终D2为12255，N1/N2旧方法回归12256/12257依次运行。
- 模型A12195全46闭合：D2 11/40（Wilson95%16.1–42.8%），原版6/6；所有46完整初态、种子、配置与基线匹配。已通知C2停止12193，不能自行取消。
- 四类120次闭合：关抽屉15/30（旧6/30）、开微波炉0/30、关微波炉0/27另3绑定unknown、推盘子0/30。117可测配对改善15、退步6。推盘子>1mm接触15/30、非目标最大位移0.03975457785m。
- 新60布局已全生成并捕获；标签12218/12219/12220按self2+三种pi各3，共660计划分支。12218已闭合20状态，后两批继续。
- 当前主树集成保留已有selected-grasp与未提交guided-mask cache，新增菜单只在相应schema/flag启用。主树发布commit不冒充物理b96快照。

## 用户10/24 08:05 + 08:25：当前闭合后立即执行

1. A先闭合模型46（已完成并在共享登记明确12195已结束）、新oracle+A40、60布局660实测并交C2。
2. B按任务分级：训练扰动65+60，每类5独立布局×1，oracle+A/model+A；PRO40任务×dev种子40–44，每任务5，另外纯pi+A只跑5级。5>=4升10，10>=9升20，20>=19毕业；失败回修复队列，修后重起5级。维护TASK_BOARD.md/task_board.jsonl，每级更新共享登记路径+SHA。
3. C0最高优先：模型A713move中675planning_unreachable，查粗筛null/起点/重复障碍；通用提前完整筛最可能项或公开失败历史；train5验证后模型A重测D2。
4. C1开/关微波炉、推盘子：按真实回执诊断，用训练布局修（铰链弧线/远侧边缘接触等），每修在开发该类5次>=4才采用，再测PRO对应类别。不为PRO任务/物名写特例。
5. D共享栈变动后已毕业类各5抽查；N1每日30至少一次（当前12256已排）。E找最大2–3时延热点，不改行为，N1验证不降。
6. C2新服务替换模型线从5级重测；DAgger2训练清单每项1次。最终200实例(种子0–4)仅CPU构建/hash，绝不跑策略。
7. 两面板协议统一40决策/10000环境控制/7200秒；pi全句和子任务104块/520控制；无跨局记忆、不重置世界，仅基础设施故障补跑。PRO开发只能40–44，最终0–4不可开发。


## 15:45 UTC 刷新

- 发布dd8031a3已推送user-fork/harness-v5，19个文件逐个暂存；guided-mask dirty cache保持未提交。集成CPU面板355pass，新增schema6历史菜单测试7pass。
- C0只读真实回执审计已完：713move，675planning_unreachable，其中643零步（sweep522/IK121），32已控制；618失败项已显示正recent_failures，216次完全相同动作起点连续重复。原件RUN/CPU_C0_model_A。没有证据将其统称IK起点错。
- 新60第一包20状态已交C2：RUN/CPU_layout60_batch00/manifest.json，SHA e918f46e6d23f0a2672b233a34579a2dfd21790a7b8617d077d267fe17a0296a；消费者coverage_issues=[]。
- 第二批12219全20闭合，CPU导出12281已运行；第三批12220继续，CPU导出12282依赖它。全60聚合CPU依赖12281/12282。
- 12193已自行退出，未由C3取消。当前C3仍<=3GPU。schema10模型面板接口需求及C0审计已通知C1/C2。
