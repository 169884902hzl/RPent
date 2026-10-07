# 4550：高频观测仍丢失关门末段身份，不能用于公开控停

4550 已真实执行并 COMPLETED 0:0（node01，Slurm墙钟9分44秒，回合578.625秒）。
单局原版 LIBERO-90 task33/init0，仍是已访问的开发状态，非确认、非训练。
没有增加动作或改变提示词、40块预算、每块5步、验证阈值与恢复配置；
200个实际VLA control后分别保存主视角和腕部视角1024 RGB-D、当前标定和本体感知。
公开记录先写，仿真标签后读并另存；私有标签没有控制执行。

## 启动和输入

- 相同快照/launcher的CPU前检 exit0，647源码文件和1/1状态哈希核对完成。
- 实际启动证据：`startup4550_observed.json`，当时105个连续control、0捕获错误。
- 完整采集200个唯一control，两个相机各200组RGB-D，捕获错误0。
- 捕获调用墙钟合计220.345秒，中位1.107秒；这些保存耗时不代表部署时的每步推理时间。
- 所有40个五步边界，RGB像素和世界深度与本局运行时原帧逐值一致。
  因此只有这些边界可以复用该时刻的独立SAM候选。没有跨缺测帧补身份。

## 先公开分析，再私有配对

从开局独立SAM门面候选初始化，以双向RGB光流、当前3D刚性对应和当前深度拟合延续身份。
跨相机只允许实际当前3D点在腕部深度中获得支持，不能复制主视角plane或以机壳替代门。
原门面宽度5cm、刚性/平面8mm、支持比例0.55等检查全部保持。

| 公开观测量 | 实际控制帧分母 | 支持数 |
|---|---:|---:|
| 主视角门面候选 | 200 | 177 |
| 腕部门面候选 | 200 | 50 |
| 至少一个相机支持 | 200 | 177 |
| 本帧重新获得SAM门面候选 | 200 | 35 |
| 无本帧SAM、由时序/跨视角获得支持 | 200 | 142 |

另外2帧是开局观测，不计入200个control分母。帧是相关观测，不是200次独立技能试次。
上述“支持”仅说明公开对应与平面检查通过，不是门实例真值的资格证明。

control170、174、175、176的门面角分别为60.57°、42.98°、38.30°、33.34°。
control177只有10条双向/深度对应、5条刚性支持（比例0.5），按原判据拒绝。
177–199连续23帧两个视角均丢身份；control200重新获得SAM候选，但输出75.89°。
本局运行时始终0个终点候选、0次撤离确认、0次temporal stop。

公开分析和summary完成后，才按`capture_id`与`actual_control_index`配对独立私有标签。
200/200一一配对、私有缺测0：control184首次官方close=true，184–200共17步始终为真，
没有成功后再次退回。其中16帧公开门面缺测；control200的75.89°与关门真值矛盾，
该SAM候选也不能称为正确门面重获。这个差异是身份/测量问题，不能靠放宽关闭阈值解决。

原始最终回执在40块用完后，执行release/restore_view，再由旧的动作后验证路径输出
`articulate_verified=true`。必须保留这个原始结果：它和动作中公开时序控停是两条路径，
不能把此后的verified记为temporal stop成功。

与4529属于同初始状态、同配置的独立开发回合，并非冻结动作前缀的重放。
两局的物理控制轨迹可能不同，不能将跨局差异直接计作高频跟踪的因果收益。
4529失败记录保留。当前运行时默认配置未改变，也不接入这个尚未达标的诊断跟踪器。

## 后续方法和工作量

本配置下，高频0.05秒仍未恢复关门末段身份，单纯增加采样频率尚不能解决本次缺测。
不再重复文本/点查询微调，也不降低原判据。下一方法是用户已允许的公开多帧+本体小验证器：
输入动作前后两视角RGB-D序列、公开相机标定和机器人状态/末端位移；仿真关节只作为训练标签。
门实例ROI由公开测得的家电区域约束；缺测和遮挡作为输入，不用假门面填补。
输出关闭/打开端点与缺测概率，开发阈值在独立原版验证状态上选定，运行时再确认稳定端点后停止。

数据合同和CPU特征/训练骨架预计1–2小时；采集与确认不能给出未经物理运行支持的成功率保证。
按本局40块高分辨率采集实测约9.6分钟/状态，200个新状态约32 GPU小时，
需先根据显式预约与状态库存分训练/验证/确认，确认状态永远不进验证器训练。
本次task33/init0继续`train_allowed=false`，不能改作训练数据。
这是排程估算，不是已经提交的作业或门槛通过结果。

## 运行身份与复现

- SOURCE：`/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_dense_public_20261008`
- overlay commit：`568afa3aa610b742670f5742939a3c9aa20a6701`
- Python：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`
- plan：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_identity_tracking_CPU_20261008/r1/close_dense40.json`
  SHA256 `f8eea2ed143bc3e3476a1bffe57f9a15fc261350de0ca15cced26e11748cbf0e`
- source identity SHA256 `d6d57671c987418be2165c39d60f5dfbaa07bd434dc574fd38c1d2ab89f5421d`
- launcher：`SOURCE/coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch`
  SHA256 `8cba334fa65b15d906b8c5cda055c5599804602d127131fd7e33c0935ad0d2bf`
- 原始输出：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_dense_public_original_20261008/close40`
- 公开ledger：`OUTPUT/dense_public/public_captures.jsonl`
- 私有标签：`OUTPUT/dense_public/private_labels.jsonl`
- 日志：`/public/home/sunyihan/rpent_libero_eval/results/slurm-4550.log`

输入/输出引用与SHA256见本目录`manifest.json`，没有目录扫描。
公开链：`dense4550_completed.public.json` → `dense4550_public_manifest.json` →
`dense4550_dual_identity.json` → `dense4550_public_summary.json`。
事后私有链：上述公开summary + `dense4550_completed.json.gz` → `dense4550_private_pairing.json`。
完整逐次记录均保留，训练行0，确认资格未通过。

首次CPU分析因BLAS线程过度并行停止，仅重启同一离线分析，物理回合未重跑。
成功运行使用`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`与`cv2.setNumThreads(1)`。
公开跟踪 helper SHA256 `f7321473fd3b351d0969b3d8694cb70a3a090119cc55dfeb53505dd89518b5be`，
通过显式importlib加载；运行目录是冻结SOURCE，避免ROOT旧包遮蔽。
统计脚本：`summarize_dense_public.py`和`pair_dense_private.py`，均已在本批输入上实际运行exit0。
