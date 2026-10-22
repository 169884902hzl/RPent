# 2026-10-22 05:40 PT 选项集上限工作

本轮主线：独立核对 A1 的 12 局真实调用，逐因素开发评测；先修 observe 恢复记账。
已完成基线保持独立：N1 24/30；D2 实际12/21/20；采样18/24/26，另各2 unknown。
当前仅原件定位，尚无本轮物理结果。执行树 c7520ae1 / N1 9d00ee63；保留无关 dirty。

待办：observe真实回执复现；A1逐局调用/初态证据；原版整句自检；零控制π重测交C2；N2登记；单因素实验；通用修法N1/N2/90/65；恢复1新上限；模型40+6；炉灶165最后。
资源：node02/nice500，C3≤3GPU（C2无需求可借4，需求出现10分钟内实际归还）；合计≤80CPU/600GB。

## 物理与CPU进度
- observe恢复记账87978ba5、重复次数77849ee8已提交。隔离树a5890f53：仅在c752执行树叠加两个诊断脚本及测试；CPU783pass，fixed10 job11434 COMPLETED0:0（10闭合），整句自检startup11432通过。
- 零步重测11422/11423均COMPLETED0:0：29状态87尝试；盒/容器/关抽屉15各、开抽屉9、开微波3，全是准备位0控制0推理；推盘19/30成功、3/30零控制。C2替换包CPU_C2_replacements29_r1已消费者核验并共享登记，旧→新record_id映射保留，不移植旧self结果。
- A1十二局原始transcript独立提取24次π调用，初态公开EEF12/12在1e-9m内相同；完整积分/控制器/RNG初态均缺，不能认证全部物理初态相同。
- 原版11任务×10整句自检11438/11439运行，原版s10初态；不是90中途状态的结果。
- 因素隔离执行器fb7b015b，隔离树6c1de614（执行/碰撞/oracle/chunk未变），CPU785pass；12状态×4臂×3次已登记，startup待真实验证。预算必须取实际回执24blocks/no_progress5，不能误用原版90的104blocks。
- N2十二状态登记（原版90/扰动65各六类1状态）已共享；模型旧端口拒绝连接，C2服务请求已发共享登记。D2只评测。

## 2026-10-22 新结果与当前快照
- 原版11任务110次整句初态自检已全部闭合106/110；推盘libero_goal t5与盒object t0各10/10。源码a5890f53，结果original_selfcheck/CPU_closed11。每任务一个s10初态/十策略种子，不称10布局。
- 因素6c1de614，144/144闭合：基线私有子任务3/36、A1提示4/36、A1预算/停止4/36、Rpent原语6/36；native分别3/3/3/6。spatial_swap_t4提示/预算各1/3；object_swap_t4原语3/3但基线目录N11关闭0步，不能独归因接触质量。原件factor6c1de614/CPU_closed12，表已本地。
- 91ff4112通用整句默认预算修正：只有uncapped默认24block的mode=task提升到原版已用104块/520controls，显式控制cap及非默认块数不变；不是D2阈值调参。N1禁VLA应无影响，原版90/65原本104/520不变，但仍做回归。
- 新隔离树124c56546cd5810311104a0b126e6c841f27a615，归档5b2fbc07a2d290f8dca3abd90fe8a1af51451cf84be3ef5c46ee2a78cf580ee2；CPU792pass；11475默认整句实际265controls/53推理native成功、观测预算104/520，fixed10完成10且都动。
- N2 baseline启动11471、after-accounting启动11472均通过；正式baseline11474运行。baseline为c752恢复层，执行/碰撞/运动/oracle/chunk与9d逐blob相同。新的预算树after尚未正式提交。
- 新N1启动11476因完整初态SHA不同在执行前退出。已确定旧canonical拥有integration/observation_state、缺新增native_data；绝不删掉新字段伪造相同SHA。11477正按旧integration/controller/RNG逐字段相等的约束补齐native solver buffers，生成新完整canonical；原件/旧25与24不改判。完成后新旧执行臂共用扩展后的完整canonical重跑，明确历史协议边界。
- A1预备位/脚本放置尾段配对实现432e4ec8；显式保留旧24×5调用预算，避免整句新预算混进该因素。启动11478（以远端receipt为准）进行，后续正式12×2×3还未提交。
- 原版公开抓取对私有：TP77/TN168/FP26/FN14，另3无公开计量。22/26FP缺双指接触。去自身像素的CPU检验无实质优势（64TP保63、23FP还22），没有部署该假设。历史handoff无渲染CPU回放有0.17–0.32mm末端残差，不能冒充精确同轨迹计量，仍待进一步定位。
- 已推harness-v5到432e4ec8；旧dirty bounded_skills的其他改动保留。其文件仅按新5行补丁暂存，没有整文件混入。

- 11477因计算节点看不到登录节点/tmp中的辅助脚本而退出2:0；已换共享prep目录脚本11479，保持原件。N1旧快照具体缺的是native_data，已有integration与observation_state，不能误写成二者都缺。
- 4条handoff的所有原始控制已CPU重放：109/319/217/572条全数一致，四个完整sim_state终态逐字节一致。先前0.17–0.32mm是拿公开传感缓存与native site相比较，尚需native_data校验与前后窗口计量；不放宽阈值。

## 接续：结束信号、模型服务及严格物理回归
- 推送e6f8728e：每条trial在保存端点后、私有计量前保存native_task_success；私有抓取分数不变。任何模式的native整局完成均可成为完整路径备选，并须独立物理回放。98项相关CPU检查通过；隔离bf871bc7完整面板853通过。
- 推送63d2f0a3：predicted_anchor_changed且0控制步属于chunk参数过期，重新决策，不扣控制恢复预算；实际控制后的失败仍扣。隔离最终树f6987f0d519f9864c9cddb4aa3d69c482b034f47，归档SHA256 4eda662226c3751f2f5c1c642bc85e41e0b522e6a22f990a7f1230a5a315fcef；完整CPU面板854通过/298.82s。
- 精确远端SOURCE=/public/home/sunyihan/rpent_libero_eval/source_native_model_f6987f0d_20261022。schema/contract未变。执行/碰撞/oracle/chunk仍为c752合格执行代码，运行仅整句默认预算104/520不同。无关dirty未纳入。
- N1同新完整缓存的124树30局正式11488/11489正在跑，indices0–23,26–31；N2旧基线11474闭合，新124树11490正在跑。需再以c752桥接恢复层+9d执行blob在同一完整缓存跑配对基线，不能声称历史缺失的native缓冲已知。
- Codex2新模型服务11484已就绪：adapter5825fe0f4a29a268483413e6af07fb67be542df6b9477b5e79156749eb4efa26，http://node02:18065/v1/bounded-choice。模型入口支持D2/原版，只经HTTP作语义选择，保存完整服务响应。恢复只由公开持物状态变化或call_vla成功复位，不使用oracle私有子任务复位；须在报告披露这一口径边界。
- 模型原六臂实为bowl/box/cup三个init各K1/K4，注册按原六臂复现，不称六个不同初态。
- 11492是bf树未启动旧面板，因最终记账修正仅在PENDING时取消，原件保留。11493是最终f698树面板+VLA/model/factor真实启动+pan纠正实验，依赖11490自然结束，不占第4张卡。
- A1匹配复核发现10_task_t2的g1:pick(frypan)被误配到先前stoveπ调用。旧单因素该行及旧pre-first-VLA staging不能解释pan；已登记A1_pan_alignment_r2，正确用ordinal14 grasp the pan handle/8块，预备移动用ordinal12/13，从同一原分叉点重跑。其余A1原始24调用表保留。
- 4条completion_lost精确CPU重放：完整sim_state及native_data逐字节一致，交还前/后v3均false、双指0/11，改归因交还前未持续夹持，不能再称制动丢失抓取。旧成绩不改。
- CPU native漏计普查11491运行，原件D2_option_fallback_a3c7cf43，只有评测端点判据核验、0控制，不改旧分数。
- 后续：155原版/自扰动同完整初态回归注册CPU作业；最终面板通过→模型40+6、90/65回归→新D2恢复1采样/独立回放40闭合。收尾15差异表、N1/N2/C7逐状态报告、Codex2交付及完成后通知停服务；炉灶165最后。

## 2026-10-23 当前执行检查点（仍在继续）
- N1新臂11488/11489均COMPLETED0:0，30/30闭合，24/30成功；24原版+6 D2探针，24/25两个辅助π试点不进分母。失败：spatial_task_t0、goal_swap_t0、object_swap_t0、object_task_t0、goal_task_t0、原版stove_on goal_t7_s5。严格同完整缓存基线11495正在运行，不能提前报配对完成。
- N2新11490 COMPLETED0:0，12状态132尝试与c752(9d执行blob)基线完整初态SHA全部相同，改善0退步0。登记判据成功：self4/24、in_place21/36、initial_pose13/36、full_task24/36，前后完全相同；不同方法的局部/整局判据不能当同口径排名。远端N2/CPU_paired12_fulltask，已镜像本地N2_paired12_summary.json/table.md。
- 155回归CPU注册11494 COMPLETED0:0/15:45；重用基线每状态的实际完整branchpoint物理状态（native/integration/observation齐全），再新测公共状态；原版90+自产扰动65，不含D2/PRO/确认。CPU读276GB/写约44GB来自旧全量pickle，不是卡住。正式11497(shard0,78状态)、11498(shard1,77状态)正在运行，N8；首状态顺序改为原记录真实调用过π的状态，种子与分母不变。原始/all155及新physical_start两个分片manifest都保留。
- 11493最终源f698面板/VLA/model/factor启动+纠正pan实验 COMPLETED0:0/25:43。
- pan纠正实验：同完整初态配对，长默认预算基线native2/3（315/378控制步成功）、A1提示native2/3、A1八块预算0/3、A1原语0/3；所有私有持续抓取均False。A1正确prepan移动ordinal12/13在旧120控制cap下，baseline native0/3→motion1/3（私有抓取仍0）。原错配stove行保留不解释，不能和旧11行做统一预算均值。
- 独立12局A1分析：本地reports/option_ceiling_20261022/A1_HYPOTHESES12.md，24π调用/336实测块；精确控制步缺测，完整A1物理初态unknown12，EEF12一致不是完整相同。11旧树有效行和pan新树纠正行分开。
- 模型旧入口11496在3个原版臂闭合后，因ask_help执行后退仍被错误当终止而开发取消，原件和old_rule_retained.json保留，不混新批；旧默认π还没有sampling_seed，会共享服务端随机流。
- 新模型入口：2de1943c/225f7d1e/bce19ef5，ask_help仅rejected才终止；记录真实停止原因；复用SeededPolicy按case.name哈希+50000000隔离π采样，每次推理记录输入/动作哈希，ExitStack恢复原client；HTTP选择仍唯一来自C2，无oracle.choose。新测试含interleaved A,B,A种子一致性/不同回合独立及D2/original两域。
- 9a187918+bb37983c：采样路径整局完成只从已选执行端点读取，不从最后一次私有计量推进后的世界读取；全失败时不虚增采样成功。两项旧启动测试fake补done字段；最新测试全部通过，未使用失败测试快照运行GPU。
- 最终实际源码树09e37883508a07501ae063d7fb5098f84f8390c4；remote source_seeded_model_09e37883_20261023；archive rd_seeded_model_source_20261023.tar.gz SHA fa2d8d6cca9fe8d85e40d1c2ec94ca15783e2f4945349a9e98cbecbcfbd9d17b。866CPU通过/307.68s。root已推a6a0b555，实际评测使用c752固定底座+已提交生成脚本的精确overlay，不能拿dirty工作树或HEAD另一份控制文件冒充本快照。
- 新模型/面板作业11499已排队（无人工依赖，首张实际空卡即跑）：smoke10→VLA启动→模型启动→原6臂→D2恢复1固定40。每阶段沿用同源launcher物理启动核对。manifest native_model_09e37883/preparation，policy_seed_rule已预登记。原6臂是3init×K1/K4。
- 余下：11495基线闭合后严格N1三十配对及C7；155全部闭合后同状态翻转/消费导出交C2（别把零29缺self的unknown说成已认证标签）；最终09源D2恢复1采样+独立回放40（原三档12/21/20与18/24/26各另2unknown不覆盖）；11499模型40+6并通知C2停服务；15差异结论/源码manifest/Codex1交付；炉灶165缩减最后。

## 2026-10-23 接续核验
- 4d6cd9ba已逐文件提交并推送。真实goal_task_t3第二请求仍选fail1的base，忽略合法fail0的seed1，第三轮触发循环后报variant unavailable；改为同一必需参数内优先最少公开失败历史的合法VLA候选，稳定顺序打破平局。80项针对CPU通过。未改候选/循环阈值/力/预算，不影响模型HTTP选择。新oracle隔离树fb9b386542e01d9eb510146decc6c284051dba8a，归档a61b1a52c539b64056ef9f662c0a7eea1d72215c4c8a425c2c0f54abe707c1b3；完整CPU面板运行中。
- 严格N1基线11495完成：相同完整native缓存，三十对24/30→24/30，改善0退步0，所有完整初态SHA相同。决策循环中位32.2246→31.2590秒，整局158.4896→151.2348秒，后继legal中位3.1561→2.9953秒单列。历史25/30不覆盖。这不是显著提速结论。原件CPU_N1_full_initial30_r1。
- 11497/11498继续原版90/扰动65回归；11499在原09e37883快照跑模型40+6，不因oracle重试修复取消；C2服务11484占第四卡，C3只三卡。无空闲GPU。
- 新oracle CPU782项通过314.82s/exit0；GPU固定10+真实π启动面板11500已排node02/nice500，空卡即起。两份155回归闭合后的CPU配对与C2原消费者导出11501已登记依赖afterok；纯CPU、不占GPU。N1_C7.md已写四段时延/后继legal单列。REPLAY_GAPS15.md逐条记录已修/未解决/原归因错误，不将CPU结论冒充新物理分数。
- 155预览149状态/1099尝试发现19改善10退步；细查至1121尝试时，同请求同实际候选1070次零翻转，51次实际调用变化。10退步全部旧实际in_place→新按请求initial_pose（准备位拒绝）；不是控制代码回归。已安排8状态/24次旧实际in_place的物理对照11506，不能用名义variant混为同方法。
- 11499原版6臂全部闭合4/6（碗/盒K1K4各成功，杯两臂失败）；D2启动因worker把kind=model一律判standard而0物理退出。d8ef106e修路由、6组环境路由回归+相关87项通过；新隔离树7f87b8ef1a16c554f4380d073eea1a499fa027e7，归档942fd0a0bf4e5d799d323747c3511ca71d4203076fd9df15298aab905f010074，完整CPU面板进行。旧6臂保留，不重跑换分数；D2用新源、同adapter/cohort/seed继续。C2已收文件通知并保留服务。
- 11500完整固定10+真实π启动COMPLETED0:0/7m28。11501为155闭合后CPU配对/独立上下文导出；11506为原版实际调用对照，D2和确认不入训练。

## 10/22 11:00 用户补充已纳入
- 11498已完成，155/1165全闭合：451→460，19好10坏；1114相同请求/实际候选全不变，51实际调用变了。8状态24次旧实际in_place控制11506已闭合19→19，一好一坏，首次输入/预测相同，首个不同预测在20/21、输入在21/22；没有据此调阈值。CPU11501正在新上下文导出。
- 模型源7f87b8ef的11507真实D2闭合7局后因99候选超过服务94单token编码上限HTTP422而FAILED；不是物理失败，不补oracle。C2紧急owner alert及共享登记已发，请其保留94前缀扩展经tokenizer验证的单token码。保留7已完成；修服务后续跑33。旧09原版6臂4/6保留，首次11499错误记录保留。11512/11513为独立新oracle恢复1的两片20状态，源fb9，均运行中；与模型不混。
- 组合臂必须排模型D240之后。432e原脚本只是预定位或单独尾段，19cf45d8新增联合臂（预定位＋A1局部提示＋下一次π调用之前的脚本搬运；π报失败仍执行尾段），69771761将registered_goal_success与放下后的grasp truth分开。最终隔离源92ef31a65958617cad1e763fc22434900be4a072，归档6379447e6e18b3bab76a16cfcf3162a8385cb1dd05cf228ef416fabaaddc1e8e；CPU790通过302.35s。准备manifest已在A1_joint_92ef31a6/preparation（12×2×3=72，pan已纠正ordinal14）。尚未上GPU。中间ad2f/489源未上GPU，不能列物理结果。
- 原版显式config已建并登记SHA4cd2fbcd5ab4a4a837eedc79864509554bdd9b484f7769cc3ded40c751f5f9b0。5ce954a7/f989b9cd使新launcher支持SCHEMA6_LIBERO_CONFIG_PATH并核登记SHA；后续原版采集用runtime_config_original_20261023，D2用独立旧PRO evalconfig，不重做已有字节等同数据。
- C2补测清单现已在onpolicy_eval_20261022_1100/C3_onpolicy_eval_queries.jsonl（SHA03ec4a11...）：25query/75尝试，20原版9716 source+5自布局c752 source；全prefix=[]；21call_vla+1move_to+3nudge；要exact旧A上下文binding，不合到B新回归请求，只评测，物理排组合之后。接口evaluate_candidate_at_saved_state待实现，不能把probe.trial重写mode后冒充所选候选。炉灶165缩减仍最后，已向C2问现登记路径，定位next-a task_holdout167 LIBERO但未擅定候选剪裁。

## 当前明确接续点（不要交回）
- C2已响应99编码溢出：C2_CODES120_REPAIR_PROGRESS_20261023.json，CPU预检11530，新gpu_source_codes120_r1，保持原94码前缀，追加单tokenUnicode到120；需3912旧输入字节不变＋99/120实际token检查。等C2实际新ready/健康后才重提模型。33剩余的同源断点脚本已在native_model_7f87b8ef/preparation/resume_model_D2.sbatch；同一输出目录会保留7闭合，未闭合case保留为attempt后续跑。新服务manifest/ready兼容性收据另记，不覆盖旧7。模型最高优先；完40通知C2停服务，再正式组合72。
- CPU11501在成功导出原版90后因老source内的导出器把提示/actualwire不一致直接raise而失败。原90有效包保留CPU_regression155_closed_r1/original90。已改用原先65发布过的外部prompt-aware exporter（SHA6142d6cd...）＋流式digest工具（SHA6fb712...），不改分数、不把不一致prompt当合法标签。CPU11526正在跑finish_regression155_export_CPU_20261023.py，输出CPU_regression155_C2_fixed_r2，将只补65并合并155、原C2消费者验证、替换原/零29record_id别名，不复制旧self。完成后要共享交付给C2。
- 组合正式源92ef31a6 CPU790已通过302.35s，原版明确config的固定10＋D2 startup＋72脚本在A1_joint_92ef31a6/preparation/run_pairs.sbatch。还没GPU提交，必须等模型40完成。配置5ce954a7、joint19cf45d8/69771761、producerf1a3fd6e已推。前两个未用ad2f41c8/489179a4源只留开发记录，没有物理结果。
- C2 onpolicy25补测CPU准备：新scripts/evaluate_bounded_saved_candidate.py已提交03b6bdc9，5CPU回归通过；强制原候选参数（不让probe.trial把pick重写成contract的on）。原始query绑定20个source9716+5个c752，必须用各自原执行源码、原snapshot/request/outcome；目前只有内层测量接口，GPU launcher/返回measured-subtask-choice2还未实现。全25prefix=[]。CPU11531正在对25旧pickle/原请求绑定和legal做检查（脚本rd_validate_onpolicy25_CPU_20261023.py在远端B）；不能把新155结果贴到这些旧A query。物理75排组合之后，只评测。
- 模型4/6三组K对的完整initial.physics SHA并不相同；只可按原登记6臂报告，不能称严格同完整初态K1/K4比较。C1已独立指出D2新model7局与旧oracle完整初态digest不匹配，BDDL/init协议同、因果逐选择归因有限；不要认定所有失败都是模型选错。
- 本轮源码/证据已逐文件推harness-v5到03b6bdc9；无关dirty（尤其bounded_skills16/4行）未纳入。原始A1因子表/120历史分数/关闭确认批不改。

- 服务容量已修：C2 CPU11530通过，服务11532实际健康/99候选K1K4 HTTP通过，3912旧输入字节不变，原94码前缀+Unicode26共120；权重/schema/contract不变。兼容ready收据native_model_7f87b8ef/service_codes120_compatibility_ready.json。11534已断点续跑模型剩余33，保留旧7；最近37/40闭合。11536联合72是afterok11534；11537是afterok11534的CPU模型40汇总与通知C2停11532。原始6臂不重跑。
- CPU11526闭合：155labelcontexts、1165raw，1126已绑定试次、39unknowncontext；C2消费者95ok/27unknown/33ceiling_outside。positions SHAec14e808246885a8d0aac8e9cb8f1cf5a7af9c75590292b38b51a6ca703a62f1。包CPU_regression155_C2_fixed_r2已owner alert及共享登记交C2，替换映射含旧原ID及zero29别名，不重复append，无训练。
- CPU11531对25旧q的pickle/source/request/原候选合法性全通过。onpolicy25/preparation/manifest.json已登记，SHAd6e73dca93a42e2f4cc744d41b3763b115b15832a083a2de9be512c7d4a77e27；噪声种子60000000+qid前8hex，每次+1000。原始query SHA03ec4a11...保持；实际执行源20项source_qualified90_9716b68c_20261022、5项source_own_layout_labels_c7520ae1_20261022。
- 测量内层5CPU测试通过，额外766ab476将首请求绑定到恢复后的exact public cache，保留NumPy轨迹数组。新GPU driver run_onpolicy_saved_candidates_20261023.py已实现（独立旧source子进程，公共SAM/π服务，每个q三固定种子，已闭合trial不重跑，保留attempt）。还没有GPU验证/未输出C2 measured-subtask-choice2返回包；须补producer引用/sam_entry到manifest、准备sbatch并在联合72后启动，不混旧A与新155。需要检查worker对各旧source的restore/constructor实际兼容性，开发失败修完继续。

## 接续：模型全闭合与联合臂启动修正
- 模型D2剩余33已随11534完成，总计10/40，Wilson95[0.14187,0.40194]；原版登记六臂4/6。11537闭合汇总并通知Codex2，服务11532已由Codex2取消。完整初态协议限制仍保留，不把历史差额冒充选择错误。原件CPU_model40_closed_r1。
- 11536联合臂固定10均通过，D2 startup实际65控制步/12次π推理；报告仅有total_sim_steps，外层launcher只读sim_steps，因此误报0。正式72尚未开始。63b822e6补标准sim_steps字段并以真实结果形状回归，22CPU通过；不移除非零物理启动检查。新隔离源8a07e44a9467fcd0b3aad5793dcee63df53c7e35，archive SHA49b73a4e0b9e54975482d96dd321cac53428178e9a0694914cfed174b20fd545，完整CPU面板正在跑。
- 新oracle11512/11513当前37/40，预览20/37独立回放、25/35采样成功，另2unknown，余3未闭合。740858e4支持只汇总恢复1和显式两片；CPU收尾11546依赖两片完成，保留0/2历史不重跑。
- 25候选补测11544仍等联合臂，需把失败11536依赖换新job。1e7dd21a新增measured-subtask-choice/2返回器，6CPU通过；exact旧A的snapshot/request/prefix/candidate/outcome/source绑定不变，三次全保留，提示/未执行不确定保留unknown，不把B上下文结果移植过来。尚未物理验证，不称已交75结果。
- 已逐文件提交并推送user-fork/harness-v5到1e7dd21a；origin为上游无写权限，未改远端，不强推。

- 8a07e44a面板已完成：主796/346.73s；RGB-D4项因环境模块导入顺序单独运行通过。真实固定10→D2 startup→joint72新作业11547已排；11544依赖已修成afterok11547。onpolicy返回CPU11548依赖11544，旧结果不覆盖。返回器180bcc98/compact165脚本27be2501；证据提交3b1f7864已推user-fork。compact165仅已准备，尚未运行（排最后）。
- 新oracle当前38/40；11512最后状态在full_replay_01，11513最后状态subtask03_on的π分支继续。不是挂起。11546会在两片均闭合后做最终恢复1汇总，不重复0/2。C1已获MODEL_CLOSED_JOINT_REPAIR，C2已获ONPOLICY75_RETURN_ROUTE；后者明确尚未实测、只补exact旧A选中候选，不冒充完整self/VLA比较。

- 11512 COMPLETED0:0/1:38:17，20局9成功；11513当前19局13成功，最后case019已进full_replay_00。合计39闭合22成功（预览）。用户p3第三个作业优先拿走释放卡，11547正常Resources排队；不动它们。
- 联合72的CPU汇总11550依赖11547，脚本aggregate_A1_joint_CPU_20261023.py（389c024f）分别算持续抓取、登记目标、native整局，逐种子/逐状态配对，unknown保留。若组合清楚优于基线，再做通用公开锚点variant及90/65回归；未得到结果前不提前新增runtime variant。
- 额外CPU11549仅原版train/自扰动日志285端点(另3无计量)，复核FP简单guard：baseline TP77/TN168/FP26/FN14；相对位移10mm TP75/FP25；empty上界+2mm TP63/FP22；相对位移≤手位移一半 TP77/FP25。未找到可靠公开判据，未改阈值或执行源码。raw CPU_original_completion_all_r1，guard_sensitivity_r2.json已本地保存public_hold_guard_sensitivity.json及REPLAY_GAPS15补充；ab1a3292已提交。

- 11513 COMPLETED0:0/1:47:43，11546 CPU汇总COMPLETED0:0/2s。恢复1全40闭合，独立整局23/40[.42195,.71491]，采样28/38[.57991,.85028]，2unknown单列，零缺局/零0步完整回放。旧21→23，2好0坏；首次回放请求后完整物理哈希新旧0/40相同，不能作因果修复提升。原件oracle_retry_fb9b3865/CPU_closed40，机器表与markdown已镜像本地，C1已获ORACLE40_CLOSED告知。11547现运行固定10，当前仅1闭合，startup/正式72尚未开始。

## 公开测量组合调用 v7 开发继续（2026-10-23）
- A1 绝对坐标联合72全部闭合：登记目标3/36→13/36，native整局3/36→10/36；逐种子两臂完整初态相同。持续抓取/原子子任务3/36→6/36，与放置和整局判据分列。改善集中少数状态，不将三次重复当独立布局。
- 25候选75补测已闭合并交C2：exact旧A绑定25位置/75实测/0unknowncontext，数据SHA9149638f133a914e090b6a25d531afcdc029105fe7950305a5729a828dd3ba05；只是补选中候选，不能拿standalone比较标签unknown25冒充缺测。
- 通用公开测量版新增call_vla.preparation=measured_anchor：仅用公开锚点复用合格move_to/carry_to，π失败也可在公开持物证据下复用搬运尾段；不引入A1坐标。schema7 SHA546299a6f4d956ddc6a249edc5e64bb532a135e1199e345b222c687611b72182。旧schema6数据/服务不变。
- 第一份修复完整树a339455e CPU804通过/318.53s，RGBD4通过；再修launcher固定6的入口，19 CPU通过，精确最终树efa57340221c82cb359d72514c7062edb34de599（归档SHA0835e1993a83d7d5f4987f9658115873c4d67a293f094d8171b1c3b3b8e9cf50）完整CPU面板继续。未上v7 GPU。
- 原版90/自产扰动65重新注册1630试次=1165旧方法回归+465公开组合调用，旧种子/预算/重复数不变；全部重新生成v7公开请求，不迁移旧标签。N2从旧完整物理branchpoint提取、N1复用同一完整canonical，准备中。当前node02有3个用户p3运行，仅借实际空闲1卡，无Codex2 GPU作业；不动用户作业。

- 最终efa57340主CPU805通过/311.38s，单独RGBD4通过；11558 CPU提取N2十二完整初态COMPLETED。11559固定10＋三类measured_anchor试点在node02运行，实际借用唯一空闲卡；独立watcher每30秒检查C2 GPU需求，需求出现即取消此明确借卡作业、保留闭合回合。未完成物理前不宣称v7成功率。
