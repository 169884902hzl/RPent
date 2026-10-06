# Codex3：3868 实际提交

预回执ede5de9已推送并追加COORDINATION后提交3868。新20局：原版10+开发10，两个恢复缺陷回合优先；SOURCE commit241776a，archive91f1e2ab9b810e6c6b12b7372ea2bd72d0b4c4e8bd03fbea28e79bfea4f2368a；全部8片CPU预检通过；v5@750权重b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb。

实际命令：`SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime541_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime541_smoke20_20261006/preparation sbatch --array=0-7%2 --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime541_20261006/scripts/run_v5_runtime536_smoke20.sbatch`。

输出：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job3868/part0..7`。当前%2填2空卡，释放后提升，无依赖/节点绑定。3780继续原生运行；不宣称3868通过或冻结。所有技能选择/确认实际执行依赖3868完整质量结果，旧待提交manifest的旧smoke字段不改字节，本外层明确替代。
