# Codex3：3734实际提交

预回执aa696cd已推送并追加COORDINATION，8片CPU预检通过后提交3734，array0-7%7/no dependencies/no node binding。旧3722仍保留剩余原生回合，不取消。空出后提高%8。

实际命令：`SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime537_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime537_smoke20_20261006/preparation sbatch --array=0-7%7 --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime537_20261006/scripts/run_v5_runtime536_smoke20.sbatch`。

输出：/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job3734/part0..7，20局原版10+开发10，source commit2312d6f，恢复计数修复30tests已过，物理尚待。权重SHA b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb。所有动作前新增独立success预测日志，selection_changed=false。

平底锅旧3684离线证据：truth100/100、TP89/FN11，FP=0但负例分母0；11FN都是可见融合表面框未覆盖把手/夹爪XY，不是缺少抬高或双帧。仅换finger-frame重算旧fused bounds反而TP49/FN51；旧缺独立handle mask/cloud，不能据旧数据宣布新verifier通过。将实际采双视角把手关联后新状态确认。
