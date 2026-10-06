# Codex3：runtime538 修复版20局冒烟预回执

已读取并接受10/06 00:52用户提示、3686/3687启动日志、3722完整20局和3734当前18个完整回合、CPU token诊断。3722保留14/20物理成功及重复失败缺陷；3734已有15/18物理成功，另2局预算耗尽、1局over_token，不宣称合格。

修复：仅模型状态删除回执中全等重复的stop、家具位移、stove前后证据；所有非回执行逐字不变、原full JSON保留、最近3条回执及24候选保留。真实失败prefix3203→3009 token，3072硬上限不变，不截断。14 focused tests通过。新的选择launcher路径全部绝对化、显式输入/文件存在性/SHA/初态CPU预检；env_meta包含同一original90诊断flag；基础设施故障单独保存、同状态最多补1次，已执行物理后计量失败不重复执行，累计故障率>2%先修基础设施。

当前snapshot：/public/home/sunyihan/rpent_libero_eval/source_v5_runtime538_20261006；源码commit b5ab18a，source-only archive SHA e5961ddb4d38295b0de90e7c30cea2e148cae5edb7c7b30d5f313f3fe894c535。此前传输未完成导致partial解包已保留在同名_incomplete_transfer；新的完整源码压缩包本地/远端SHA一致。CPU预检新建output目录的缺陷已修，全部8片重跑预检通过。

显式manifest：/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime538_smoke20_20261006/preparation/manifest.json，SHA ce6f73e509f631c2e460d47752b45c2220f29e95209e0de086883b5f11d836eb；各16份cohort输入及SHA仅按manifest读取。新snapshot包含当前第三开合测量把手/腕部修正和stove-off证据规则，尚未物理过门。

GPU预约：当前3734最后1片仍用1GPU，本次20局array0-7%7、每片1GPU，填满其余7张空卡，3734释放后提高到8；不绑定节点、无Slurm依赖，不动其他owner作业。原版10 + 开发10，v5@750权重b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb；同已登记100决策/80chunks/10000steps/3072token预算，default fusion/no_effect blocking/measured receipts/vla_subtask明确开启。

计划命令：SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime538_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime538_smoke20_20261006/preparation sbatch --array=0-7%7 --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime538_20261006/scripts/run_v5_runtime536_smoke20.sbatch。

作业号由Slurm分配后立即回填；输出沿launcher固定根 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7，SOURCE/PREP为538，输出根名仍536，此处明确避免混淆。报告fusion与相机来源、no_effect/被屏蔽动作、同动作重复、vla_subtask候选/执行结果和测量变化；质量合格才开始大技能批次。已完成的失败原样保留，不授予冻结或训练资格。

Codex1/Codex2通知：compact_receipt改了模型可见回执的等价表示，行为尚未冻结；冻结后训练必须从最终源码新采，旧缺测行不能仅重渲染。最新在线成功预测只对公共测量回执配对：18完整局94动作AUROC0.8898、episode-bootstrap CI[0.5089,0.9523]；ECE0.3629，高置信p>=.9错误27/62。私有truth未采集，不能称真值AUROC，不据此立即启用成功率排序。
