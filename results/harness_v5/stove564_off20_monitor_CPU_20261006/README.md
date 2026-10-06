# 4303 原版 stove off20 完整开发汇总

8 个分片全部 COMPLETED 0:0；20/20 cell完整有效，基础设施失败0。原版Goal7 init0–4 × 4方法，只有5个不同的初始状态，非20个独立样本、非确认批。

已核6400/6400 contact chunks、32000/32000 controls、6440/6440独立私有评分行、100/100双视角capture；源码、资产、公开/私有capture引用SHA全部一致。私有q/谓词不驱动执行、停止、绑定或endpoint阈值。on setup成功20/20，失败分母0/20，保留所有cell。

| 方法 | 曾到off | contact终点 | release/retreat后 | 最终Wilson95% |
|---|---:|---:|---:|---|
| literal_off | 5/5 | 2/5 | 0/5 | 0–43.45% |
| paraphrase_off | 0/5 | 0/5 | 0/5 | 0–43.45% |
| complete_knob_off | 0/5 | 0/5 | 0/5 | 0–43.45% |
| measured_complete_knob_off | 0/5 | 0/5 | 0/5 | 0–43.45% |

互斥物理失败分类：15次固定contact从未满足off；3次contact中曾成功后失去；2次contact终点成功、联合恢复后失去。所有方法最终配对结果均失败，不能称改写改善。

literal init0：q在contact末为−0.005365，联合恢复后+0.058643；init2：−0.006110→+0.005253。这两个恢复后on/off谓词都false，不能说它们重新开到了on。已有逐step motion_trace只存机器人关节，没有灶台q，无法进一步区分release与retreat各自的贡献。

公开精修5/5 unmeasured：每局双视角×3查询全部0实例，实际没有执行精修waypoint。这一组没有估计“成功测量并精修”后的效果。dual_view_fusion_v1实际配置为true；公开控制capture仍按视角分开、control_views_fused=false；继承runner未保存shell fusion历史，不虚构其来源分布。

每cell中位墙钟123.46秒。原始文件保留在远端：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off20_original_20261006/probe_job4303/part0` 至 `part7`，具体20个case路径及SHA见 final_complete_v1/input_manifest.json。

正式汇总：final_complete_v1/summary.json；逐局表：per_cell.csv；互斥分类与证据界限：failure_classification.json；逐块q/谓词：private_chunk_curves.jsonl；100个capture评分：capture_scoring_table.jsonl。只用manifest显式引用，没有glob/scandir，没有读取PRO/人工/sealed。

下一步证据支持：隔离固定接触持续导致的回转与联合恢复；继续使用公开感知确定动作，私有评分仅在执行后记录。不能以私有成功停止、放宽官方谓词、拟合endpoint门槛，或把当前方法当作已达标。
