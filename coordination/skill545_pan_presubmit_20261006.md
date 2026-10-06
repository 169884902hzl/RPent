# Codex3 calibration545 启动修复与 pan100 提交前回执

已读取10/06 00:52指令、SOURCE544、4123/4126全部16片账本及4117。接受全部技能门槛、独立确认、失败保留、3072硬限、双视角/公开测量、禁PRO训练/禁人工密封文本与满空卡无绑定条款，无异议。

4123八片仅8次TypeError启动尝试，0 servo/VLA/contact，因此仍是100个未首次物理访问状态，修复后按同一manifest补首次物理执行；旧日志不改。4126有8次物理尝试，禁止覆盖重执行，不在此作业中。4117完成30次但0接触VLA，正在修公开把手测量，不提交600。4127放置400正在8卡运行；4128开合1200排队，没有重复提交。

根因 harness_v5_eval.py 将嵌入校准dict当Path；修为支持已加载dict和CLI文件，保留校准身份；所有preflight使用同一个真实消费函数、比对pinned calibration和gripper XML。11 CPU回归通过，pan完整8片launcher CPU预检（每片SOURCE545）通过后提交。SOURCE545仅harness加载与CPU preflight变动，技能物理阈值/回执不变。

源码commit：14cb1f9f144cb5627e03b29789373ff83589332f；快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_runtime545_20261006`；archive SHA256 `523f28bff6b220ebd62bce11594f8bc2d58de42e58c586390dc10611bc4b7e27`。

计划pan100确认，job号由sbatch分配后立即回填；无依赖、无节点绑定、每片1GPU，8片/限流8（现8GPU用于place，按调度空出即用）。输出：/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/pan_runtime545_confirmation/job<sbatch_id>。

实际拟提交命令：
```bash
env GRASP_REPAIR_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime545_20261006 GRASP_REPAIR_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/preparation/pan_wrist_new_states.json GRASP_REPAIR_MANIFEST_SHA=d5091b678e980f73e37157a769c9f85f9846c3cd91dfd93dac26553567e6fb58 GRASP_REPAIR_PROBE_SHA=f6d082336fac5d2c2e1fe1a9823b9427106ecb36aae3f8ce912056bed67f09e8 GRASP_REPAIR_SHARDS=8 GRASP_REPAIR_PREFLIGHT_ONLY=0 GRASP_REPAIR_OUTPUT_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/pan_runtime545_confirmation sbatch --parsable --array=0-7%8 /public/home/sunyihan/rpent_libero_eval/source_v5_runtime545_20261006/scripts/run_v5_grasp_repair_20261006.sbatch
```

新批门槛不变：真值抬离并持续夹持；类>=90%，总体>=95%，public verifier一致>=95%，Wilson描述性报告。不把零执行启动异常计成抓取0%，不把选择批当确认批。
