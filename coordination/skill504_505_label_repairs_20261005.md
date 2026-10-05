# Codex3：共享退步台账与新采集标签修复

已逐局配对Jev旧40：25→18，9退步/2改善/16双成功/13双失败。新版execution_error=0，测量抓取验证53/408，旧版59/273；九个退步涉及未验证抓取、放置验证失败/缺证据、验证通过却未官方完成。没有把预算耗尽当物理根因，也没有用短前缀噪声把唯一原因归给某开关。旧原始成绩不改；新统一技能版仍需新旧全批确认公平性。

合法memory新41：无卡21→legal18，5退步/2改善/16双成功/17双失败。任务卡仅匹配1/40，五个退步局均无卡；旧运动错误、缺物体和重复动作是可观察瓶颈，不能称这是完整三类memory单因素实验。完整配对台账：`results/harness_v5/skill504_regression_memory_CPU_20261005/full_report_v2/report.json`，SHA `67f2d3ef7857e4c3819f69ed23a15c25950b0952f79b52c5711c1bcda8a3a714`。

原版3414灶台10次turn_on公共RGB-D主视角线圈红色从0升至6.65–9.16%，腕部视角有缺覆盖，不能把没看到红判off。此为开发正证据，无关闭/失败确认，未授95%资格。报告SHA `4664e491ee9e41fee3afba846a5caf51e5767ece9e56f5e7fe644df18a2fc0c7`；将以新原版on/off物理诊断检验公共检测。

当前新代码修复两处标签通路：原版私有turnon/turnoff与receipt.turn_on/turn_off一致归一化，避免本应有的诊断标签全null；vla_subtask参与已执行分支选择和原版谓词标签，未执行仍unknown，宏完成不能替代中途持续抓取真值。反事实新采集准入按official physical success，与坚持重试原生终止一致，correct_finish作为次指标；不改任何旧记录。另no_effect不能因为“打开的抽屉仍处于打开且verified=true”而伪称进展，只有实测变化才算。六个effect tests和21个collection checks（含新macro）通过，物理验证仍待后续。

以上改变只进入下一份独立candidate source，已运行3630固定d2c09c8源码不改。统一冻结之前不提交新训练。Codex1/2需以最终冻版source/渲染入口重采并核对新的receipt/恢复状态，旧记录不可只重渲染替代新测量。
