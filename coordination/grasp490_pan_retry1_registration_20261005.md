# Codex3：3612启动失败修复与同规格新目录复跑登记

3612_0–3全部FAILED1:0，summary completed=0，未开始物理抓取，不计0/400模型成绩。根因已用原source import复现：ModuleNotFoundError: typed_choice_eval；归档只放harness/robots/rpent/scripts，漏根目录模块。随后private_grasp_diagnostic写未创建目录掩盖原异常。已补 typed_choice_eval.py、shared_v5r_schema.py进新快照，probe显式保存/打印首次原异常，旧source/日志/作业不改。

拟提交新数组一次：`sbatch --parsable runtime_launchers/run_v5_grasp490_pan_retry1.sbatch`，编号待Slurm返回。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp490_pan_retry1_20261005/full_job<array_id>/part0–3/`。4条件×100与3612相同；array0–3%2/每片1GPU/8CPU/90GB/4h/nice1000，不设节点绑定或依赖。无规格/预算/判据变更，无异议。

source `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp490_pan_retry1_20261005/` commit caf33ff；archiveSHA `42b879bcc4bb48cf548fba0473125c57fb80f206db005e7e4fd981b561c2dc3a`；manifestSHA `7f53e64c71ab6c74309424e6ec2a819c57495417c1c9c92bd1b861dac63eee1c`；launcherSHA `223ba3f96f9cae9b93882e8032d50653d3c7bc38232e80e310df6330aa297a92`。
入口 scripts/probe_v5_grasp449_20261005.py::main，解释器 /public/home/sunyihan/rpent_libero_eval/.venv/bin/python。回执先推送、远端append确认及真实runner依赖import后，再sbatch一次。复跑物理0/400尚未开始，不当完成。GPU预约最多2卡，仍留足共享训练资源。

实际提交3616：sbatch --parsable runtime_launchers/run_v5_grasp490_pan_retry1.sbatch。输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp490_pan_retry1_20261005/full_job3616/part0–3/；400次，一次提交，无依赖，最多2卡。已先push cf4c5b6，再核远端pre append和runner实际依赖import通过，然后提交。3612失败日志保留，不计模型成绩。
