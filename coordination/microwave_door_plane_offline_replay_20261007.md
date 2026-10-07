# 微波炉门平面离线重放与窄验证（2026-10-07）

## 已落地

入口保持现有公共几何合同：`MeasuredScene._measure_microwave_door` 读取已保存 RGB-D/SAM 点云，`measured_microwave_door` 调用 `vertical_face`，端点判定仍由 `measured_fixture_endpoint` 使用固定 frame 与 moving door 的法向夹角。没有修改阈值、公共 verdict、训练排除规则或确认分母。

新增离线脚本：

`scripts/replay_v5_microwave_door_planes_20261007.py`

脚本只读取报告中已经记录的 frame/moving `*.npz` 引用，逐文件校验 SHA，重跑当前 `vertical_face`，并在同一 before/after 阶段同时有两张平面时重算法向夹角。它不会调用 SAM、仿真、机器人动作、目标谓词或私有状态；缺失文件、SHA 不一致和拟合拒绝均保留为证据。

## 4340 离线结果

输入：`results/harness_v5/microwave571_monitor_CPU_20261007/job4340/report.json`。

输出：`results/harness_v5/microwave571_monitor_CPU_20261007/job4340/door_plane_offline_replay.json`

- 10 个注册请求全部保留；其中 1 个 public-parent binding missing，9 个实际 first 请求均保留为 `unmeasured`，没有把 null 改成 false。
- 报告中引用的 10 个点云全部加载，SHA 全部一致。
- 当前 `vertical_face` 重放接受 10/10，点数、中心、法向和 p90 残差与原记录逐项一致 10/10。
- 只有两个阶段同时有固定 frame 和 moving door：close s0 before 夹角 87.85°、open s1 after 夹角 89.84°。其余阶段因缺静态 frame、缺 moving plane、moving 多 mask 或点云非平面而保持 unknown。
- 该结果仅验证拟合和证据链可重放，不能把 4340 变成确认批，也不重判公共门端点成功率。

SHA：

```text
script  d2bfdd9b7b762c53196367a84cd28176c467418e9962f811120f45c0a684a72c
output  1c90bd87b5e31e30b7df0ef232200abb6f987242764a164d61bea166a31022ac
```

远端 GPU 节点上复现命令（不启动物理执行）：

```bash
scp scripts/replay_v5_microwave_door_planes_20261007.py \
  gpu5880-ts:/tmp/replay_v5_microwave_door_planes_20261007.py
ssh gpu5880-ts 'PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006:/public/home/sunyihan/rpent_libero_eval \
  /public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /tmp/replay_v5_microwave_door_planes_20261007.py \
  --report /public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_monitor_CPU_20261007/job4340/report.json \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_monitor_CPU_20261007/job4340/door_plane_offline_replay.json'
```

若报告和点云在同一挂载路径，直接使用：

```bash
python scripts/replay_v5_microwave_door_planes_20261007.py \
  --report results/harness_v5/microwave571_monitor_CPU_20261007/job4340/report.json \
  --output results/harness_v5/microwave571_monitor_CPU_20261007/job4340/door_plane_offline_replay.json
```

## 进入确认批前的窄方案与工作量

1. 先用离线脚本对新一批已保存 RGB-D/SAM 点云做同一重放；只接受逐文件 SHA、独立 frame/moving provenance 和现有拟合结果一致的证据。缺失或歧义继续记 unknown。
2. 若窄验证通过，再用现有 `microwave_door_cloud_v6`、`door_point_recall_v7`、`door_plane_consensus_v1` 入口做极小物理 smoke，保留每个 first attempt；不通过就修复点云入口，不放宽公共阈值。
3. 确认批仍按现有 `measured_fixture_endpoint/2-dev` 公共判据，逐试次记录 frame/moving 两张平面、源相机、source step、法向夹角和 null 原因；不得从私有开关或原生 endpoint 标签补公共 verdict。

预计工作量：几何入口接线约 0.5–1 天；离线/窄 smoke 约 2–4 小时；确认批在窄验证通过并获准后再安排。当前没有提交大批 GPU，也没有改变评测标准。

