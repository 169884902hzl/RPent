# Codex3：3722 实际提交

预回执commit80558a5已推送并追加远端COORDINATION，全部8片20局CPU路径/官方init存在性预检通过后提交3722。

实际命令：`SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime536_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/preparation sbatch --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime536_20261006/scripts/run_v5_runtime536_smoke20.sbatch`。

输出：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job3722/part0..7`，每片1卡，array0-7%8，无依赖/节点绑定；仅冒烟，不授予冻结/训练资格。SOURCE commit eb48c11。权重SHA b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb。原版10局+开发10局，期间继续CPU准备技能和采集估算。
