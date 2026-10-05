# Codex3 child：缺失目标点诊断与 strict6 误拒

接受 parent 的只读计量任务；不修改 runtime、probe501、place 模块或历史判定，不提交 Slurm、不推送。不是唯一编辑者，owned 新文件仅 `prepare_v5_grasp524_public_queries.py`、`probe_v5_grasp524_saved_queries.py`、`audit_v5_place525_closed_mismatch.py` 和本回执。全部输入来自显式原版 manifest/ledger/state 声明，无 PRO、人工或密封文本。

3662 中 moka centre 的 114 sample：主视角 step0–19 有目标点，step20–113 全缺；腕部只有 step85 有目标点，其余 113 帧缺。两种 moka 方式合并共 137 sample / 274 个视角，主视角缺 98、腕部缺 136。不是单纯缺少开度点数校准。

已查看保存的双视角公有图像及显式 SAM 掩码：

- step20 主视角的摩卡壶仍可见，但被夹爪部分遮挡；上一帧 step19 有壶 mask，到 step20 消失。
- step0 腕部中壶身基本完整可见，但没有壶 mask，说明不能全部归因于遮挡。
- step68/69 的主视角仅保存平底锅 mask；腕部壶身在画面底部之外，仅壶盖边缘可见。step85 腕部目标回到视野中，得到壶 mask。
- 冻结 303a6b3 的 MeasuredScene 里 instruction_queries_v1 / wrist_recall_v1 默认 false，实际 base/override 没有覆盖。主视角有 `silver moka coffee pot` .5、`silver octagonal coffee maker` .35、`coffee pot` .25 的空回复回退；副视角只有首个措辞 .35，没有同义词回退。
- `shared_sam3.log` 只保存加载/服务启动，没有逐 query 回复或 mask 拒绝原因。因此现有证据不能进一步断言究竟是 raw empty、低置信度、几何过滤还是类别排除，不能补造记录。

图像证据：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp524_missing_points_CPU_20261005/visual1/public_masks_montage.png`
SHA `09669778ed8d8b18685da411bcaaac7b1758e976b50cc407798d09d8b616be4d`。所画绿色包含该帧**全部已存 mask**，不是把每个 mask 都认成摩卡壶；输入与 SHA 在 `visual1/sources.json`。

按 parent 最终收窄，最小预登记是 moka centre source_step 0、20、68、69 × 两视角，8 图、24 请求。三个 query 在两视角一致应用，全部措辞/阈值在结果之前写入 manifest：`silver moka coffee pot` .5、`silver octagonal coffee maker` .35、`coffee pot` .25。该矩阵不是精确复现原来副视角首个 query 的 .35 阈值，不能混作旧运行；只用于比较现有梯度的召回。私有标签不进入 SAM 请求，也不得用于选择运行时查询或接受 mask。

最终 manifest：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp524_missing_points_CPU_20261005/preparation_min8/queries.json`
SHA `b932876ebced88c224c5772c44b0e7a03b2fc7b31435025b1c2444e1d38eb977`。RGB、world、camera metadata 的逐文件 SHA 均已登记。较早 `preparation`（137 sample）及 `preparation_smoke4`（5-query 草案）保留为未执行 CPU 产物，不用于本次 GPU 请求。

独立薄 runner 复用现有 V5Sam3Facade / Sam3Client。严格核 RGB/world SHA，保存每个原始实例的 score、mask 文件/原始数组 SHA、finite depth、测量 bounds 和副视角低分 extent 拒绝原因；不发仿真请求。没有原始 query-to-class 关联时，不猜测 pan 排除 mask，不声称完整复现多查询去重/绑定；返回 mask 不等于验证目标。控制台只打印短统计，完整记录到 report.json。脚本已做 CPU 编译，**未加载 SAM、未完成 GPU 诊断、未提交新作业**。

parent 可以在预约资源后使用以下命令；输出目录必须新建：

```bash
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_grasp520_synced_measurements_20261005 \
  /public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /public/home/sunyihan/rpent_libero_eval/scripts/probe_v5_grasp524_saved_queries.py \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp524_missing_points_CPU_20261005/preparation_min8/queries.json \
  --manifest-sha256 b932876ebced88c224c5772c44b0e7a03b2fc7b31435025b1c2444e1d38eb977 \
  --checkpoint /public/home/sunyihan/rpent_libero_eval/assets/sam3/sam3.pt \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp524_missing_points_CPU_20261005/query_job<JOB_ID>
```

源码 SHA：prepare `7e5851e3154b90f322a74442758075b715763caa93c3fe5a765a8d5170ba9da0`；thin runner `f93cc4a81f95bc9e16832f4cd7463bda979f1030c7a242c1b118268e1e4af8bc`。下一步最小运行时修复候选：记录 query/image SHA、raw mask score/SHA 与每个拒绝原因；先用原版 saved-image 对照确认同义词对部分遮挡确有帮助，再按同一固定梯度给两视角确定性回退。腕部 FOV 缺失应另行登记感知扫描姿态诊断，不能把被裁掉的对象或私有位置当当前测量。缺证据继续 null。独立 capture sim_time 尚未保存的限制不变。

3670 放置误拒已抽取三条原版闭合记录，使用它实际冻结的 303a6b3 / strict_place6 源码纯 CPU 重算。所选为显式 part 顺序中前 3 条 private satisfied=true / public false，仅做根因诊断，不是新成绩。

| pan centre init | 基础放置 | 整 bbox 支撑比例（两帧相同） | lower 对目标顶面距离 | strict6 |
| --- | --- | ---: | ---: | --- |
| 4 | true | 54.65% | 3.125 mm | false |
| 8 | true | 71.80% | 2.441 mm | false |
| 12 | true | 59.67% | 2.441 mm | false |

三条两帧稳定、中心在目标 xy 内、松手、撤离、高度和 1 cm 接触带均通过；唯一失败是整物体 xy bbox 要求 90% 覆盖。锅体+柄的完整 bbox 不等于支撑接触 footprint，优先调查这一几何表示。**没有放宽统一 90% 门槛，也没有把旧 false 改 true。** root 已把公开锅体/柄几何可识别性分给 summary owner；我没有重复拟合或造锅尺寸。

报告：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place525_strict6_mismatch_CPU_20261005/report1/report.json`
SHA `3b2712cba44d5d5aecd2f3516061f4b84b08aeb3b424c3d486c31933cae00595`。报告包含每条 closed choices SHA、所读 ledger 前缀 SHA/字节数、原版私有谓词诊断、完整公有前后实体/回执/严格放置测量，以及逐条件复算。verifier 源 SHA `753b8604c0955eeb1e5e4fa21e0c1747fdc390509a9bdac54f2dad5058e36e6f`。

CPU 审计器 SHA `82d40be177dfd353b903244511c9bac0eecb0d9fb35ac89d9a1f400bf8307eb3`；实际已用上述 frozen source、该 verifier SHA、显式 `exploration_job3670/part0–7/episodes.jsonl` 和 output `place525_strict6_mismatch_CPU_20261005/report1` 运行退出 0。无新动作、无重放、无训练行、未通过 95% 门槛、未冻结行为。
