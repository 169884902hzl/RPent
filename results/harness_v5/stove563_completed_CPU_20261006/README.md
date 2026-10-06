# stove563：4263 完成证据与 4210 私有评分配对

4263 是完成的开发 smoke，20 个新 RPC 无执行错误，但没有检测到任何
SAM 实例或有效控制几何。控制部件裁剪没有改善覆盖。全部 endpoint 仍是
`unmeasured`；本包不能准入开关验证器或用于训练。

| 来源 / profile | 实际 RPC | 有掩码的查询 | 有有效几何的查询 | 有效几何视角 |
|---|---:|---:|---:|---:|
| 4240 full | 24 | 1 | 1 | 1/12 |
| 4240 body context50 | 24 | 1 | 1 | 1/12 |
| 4263 control context25 | 20 | 0 | 0 | 0/12 |

4263 保留 12 个原视角。10 个视角各运行原来的两个 query，其余两个视角
没有独立公开控制框，保存 4 条 `missing_control_bbox` query 行。24 条 ledger
无错误；只读复用了 4240 的 48 条 baseline，没有重跑或改写它们。
在共同的 10 个可裁剪视角上，三种 profile 的掩码查询数也是 1/20、1/20、0/20。

作业身份：`4263 / COMPLETED / 0:0 / node01 / 25 秒`。GPU manifest SHA256：
`bdbfc3d9eab3b8240a6514013832b06b6231a1d88957c5d9cd04dd45308b3dbb`。
原始 summary SHA256：
`c8265185f409b1f9a09e18f3359ee1814234763303f6602de8d15ec64c025e16`。
原始 ledger SHA256：
`45e15a7d974ade6c918692feefa91bbcc3a849fc563f1c6b684cc92f717f531f`。
`job4263/` 保存全部显式输出：summary、queries、SAM/Slurm 日志、实际
preflight、sacct、10 个裁剪 RGB/映射和全部 12 个视角 summary。
4263 没有掩码或点云输出，因为没有返回实例。

## 4210：真实关节与公开几何逐时刻配对

80 份标签来自原版 Goal7 init0–9 的四个显式 `partN/episodes.jsonl` phase refs。
逐份核对保存的 SHA 和 source_step。它们有 30 个 `(on=false, off=false)`、
50 个 `(on=true, off=false)`，**没有 true_off**。10 个 `off/post_recovery`
全部仍是 true_on；不能把阶段名 `off` 当作真正关闭。

| 捕获 | 真实 q(rad) | true_on / true_off | 公开主视角角度 | 公开腕部角度 | 炉体红像素比例 |
|---|---:|---|---:|---:|---:|
| init0 on/before | 0 | false / false | 178.371° | 缺测 | 0 |
| init0 on/post | 1.915748 | true / false | −72.970° | 缺测 | 7.946% |
| init0 off/before | 1.915748 | true / false | −72.970° | 缺测 | 7.946% |
| init0 off/post | 1.486332 | true / false | −96.326° | −96.862° | 7.904% |
| init5 on/post | 2.088634 | true / false | −64.100° | 缺测 | 7.950% |
| init5 off/post | 1.977905 | true / false | 缺测 | −68.503° | 7.953% |

init0 on/post 与 off/before 的关节、RGB 和公开角度相同，是重复时刻。
两次同主视角角度变化与关节变化之差是 −1.106°、+1.248°；仅提供公开
角度随关节变化的初步证据。init5 的可测角来自不同相机，不能当作同视角
重复验证。关闭后仍红是关闭动作没有实现 true_off，未证明火焰 RGB 静态。
当前样本缺少 true_off 校准数据，**两条变化不能直接准入 endpoint**。

`labels80_scoring_table.json/.csv` 保存 80 行、原始标签 path/SHA、source_step、
私有 q 和谓词；`matched6captures.json/.csv` 保存六次捕获逐视角配对及
两次变化。私有真值只在评分表出现，不进入公共几何生成器、运行时或训练。
未读取 PRO、人工文本、sealed 文件或额外私有标签，未启动仿真。

## 固定 50 捕获的公开 CPU 扩展

每个 init0–9 固定取 on/before、on/pre、on/post、off/pre、off/post，合计
50 捕获、100 视角。选择规则不依赖私有成功；排除与已取时刻重复的
initial 与 off/before。`public50_capture_manifest.json` 保存显式 public packet refs。
生成器只读这些公开 RGB-D 和原 SAM 炉体 mask，未新发 SAM 查询。

算法复用 stove559 的 RGB max 40/64/80、组件相邻距离、圈拟合、上层 patch
和独立炉体边判据；RANSAC 圈拟合与炉体边函数从 SHA 固定的旧源码提取，
不执行旧程序 main，不改旧证据。10 个与 stove559 重叠的视角角度逐值复现通过。

RGBmax64：98/100 有当前炉体，53/100 有唯一暗色组件，31/100 有唯一支持
底座，24/100 有唯一有向柄，21/100 有候选相对炉体边角。后验评分分组中，
neutral 可测角 6/20 视角，true_on 15/80；true_off 仍为 0。这是候选几何覆盖，
不是语义召回、准确率或资格成绩。

40/64/80 均只有一个支持底座的 21 个视角，圈中心随阈值的变化中位
0.557 mm、P95 7.61 mm、最大 12.41 mm。条件 bootstrap 只表示选定拟合内部
的噪声，不覆盖阈值/模型选择偏差；多组件帧的跨组件距离不是同一物体的
不确定度。详见 `public50_geometry.json` 和 `public50_summary.json`。

## 产物与复现

- `summary.json`：4263 / 4240 比较与 4210 标签结论。
- `input_manifest.json`：完成证据读取的 231 个显式文件及逐文件 SHA。
- `public50_geometry_input_manifest.json`：公开扩展读取的逐文件 SHA。
- `public50_summary.json`：阶段/相机/后验私有评分分组、旧结果复现和不确定度。
- `public50_scoring_table.csv`：100 行公开测量与既有私有标签的评分配对。
- `manifest.json`：本包所有交付文件的 SHA；不保存原始 world maps。

远端目录：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove563_completed_CPU_20261006/`。
解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。
实际 CPU 入口如下（均不提交 Slurm 或启动 GPU/仿真）：

```bash
python collect_completed_evidence.py --root /public/home/sunyihan/rpent_libero_eval --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove563_completed_CPU_20261006
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python measure_public50_geometry.py --root /public/home/sunyihan/rpent_libero_eval --packet /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove563_completed_CPU_20261006
python summarize_public50_geometry.py
```

本包为窄范围 CPU 证据，不修改 shared runtime、已有作业或 COORDINATION，不 push。
