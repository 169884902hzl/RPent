# 4550 单局：每个实际控制步的双视角公开证据

主代理已登记GPU预约并提交 `4550`，没有节点或依赖绑定。
4550现已COMPLETED 0:0（node01、Elapsed 00:09:44）；200个真实control、400组双视角RGB-D、
捕获错误0，40/40运行时边界逐值相同。公开跟踪在177–199连续23帧双视角都丢身份。
原始启动实证见 `startup4550_observed.json`（当时105control）；完整结果见 `REPORT4550.md`。
公开temporal stop仍0，不能用于冻结资格。不动4346训练。

- Python：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`
- SOURCE：`/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_dense_public_20261008`
- commit：`568afa3aa610b742670f5742939a3c9aa20a6701`
- source identity：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_identity_tracking_CPU_20261008/r1/source_identity.json`
  SHA256 `d6d57671c987418be2165c39d60f5dfbaa07bd434dc574fd38c1d2ab89f5421d`
- PLAN：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_identity_tracking_CPU_20261008/r1/close_dense40.json`
  SHA256 `f8eea2ed143bc3e3476a1bffe57f9a15fc261350de0ca15cced26e11748cbf0e`
- launcher：`SOURCE/coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch`
  SHA256 `8cba334fa65b15d906b8c5cda055c5599804602d127131fd7e33c0935ad0d2bf`
- OUTPUT：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_dense_public_original_20261008/close40`

同launcher CPU前检实际exit0，显式状态hash 1/1、647源码文件；snapshot真实import/constructor exit0。
保留source4529的动作块、提示、预算、验证器和恢复逻辑，新增动作0，默认运行时不改。
公开文件：`OUTPUT/dense_public/public_captures.jsonl`，每次实际control后的
双视角1024 RGB-D/标定/本体感知引用。标签文件：`OUTPUT/dense_public/private_labels.jsonl`。
每一行用server PID与actual_control_index配对，标签读取发生在公开记录写入之后。
所有访问 `train_allowed=false`，不是确认批，不拿此状态训练验证器。

计划为200个原始controls、400组视角图像；若原公开stop提前触发，按真实执行量报告，不能补凑。
读结果用本目录 `collect_dense.py --job 4550 --output 新文件.json.gz`，只能按显式ledger读。
监测首个实际control证据，再检查公开时序身份链，私有结果只用于事后误判分析。
有缺测保持unknown，不从机壳正面补门身份，不用真实关节控停。

工作量实测：Slurm墙钟9分44秒、回合578.625秒，捕获调用合计220.345秒。
0.05秒仍不能保持关门末段身份；下一方法需原版非确认状态的公开多帧+本体验证器数据。
本单局只回答公开可观测性，不代表门槛已达标；所有访问继续排除训练。
