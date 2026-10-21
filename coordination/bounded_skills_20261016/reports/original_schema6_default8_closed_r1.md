# 原版 schema6 默认 call_vla：9 状态开发批闭合

8 个位置有完整分叉，共 24 次 π0.5 和 8 次自有技能；容器在前置阶段失败，未到达分叉点，保持 unknown。
8 个位置均通过 Codex2 当前标签构建器，coverage_issues 为空；没有训练模型。
每类只有 1 个原版训练身份状态，区间描述该状态的种子试次，不是类别总体可靠性。
当前目录的默认 call_vla 已产生实测标签；新 B2 变体仍关闭且保持 unknown。
数据源为 645c4d22；新的持物验证方向修复 e4bac511 另行重放，不改写本批。

| 类别 | 自有技能 | π0.5 | π0.5 Wilson 95% |
|---|---:|---:|---|
| bowl_transfer | 1/1 | 3/3 | 43.9%–100.0% |
| drawer_open | 0/1 | 3/3 | 43.9%–100.0% |
| microwave_close | 0/1 | 3/3 | 43.9%–100.0% |
| microwave_open | 0/1 | 3/3 | 43.9%–100.0% |
| plate_push | 0/1 | 3/3 | 43.9%–100.0% |
| box_transfer | 0/1 | 1/3 | 6.1%–79.2% |
| cup_transfer | 0/1 | 2/3 | 20.8%–93.9% |
| drawer_close | 0/1 | 3/3 | 43.9%–100.0% |

所有试次使用同位置、同成功合同，独立策略种子固定登记。标签按私有 v3/原任务谓词给出；实际提示词与推理 wire 哈希一致。执行成本剔除事后私有计量，并保留原始耗时。持出集和确认排除沿用冻结身份；没有把其他来源状态补入训练。炉子开/关在源220中全部是 task_holdout，本开发标签批没有取用。

公开回执对私有结果：TP19、TN2、FP1、FN2，一致21/24。盒子1次误报的11帧私有窗口均缺双指接触；杯子2次漏报来自向上1cm测量路线被拒，无法产生新的随动证据。均保留，未放宽真值。

完整交付清单：[DELIVERY](original_schema6_default8_delivery_r1.json)；逐类指标和区间：[metrics](original_schema6_default8_metrics_r1.json)。
远端数据：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/original_schema6_labels_20261021/645c4d22/CPU_closed_r1/positions.jsonl`。
数据 SHA256：`dbb1ccd3d5a8d5260e6625e46fb25b027cfe1f33b2fc1064b482c73117ddc4c4`。
同目录包含 manifest、C2_intake_validation、metrics 和 DELIVERY；manifest 关联全部9个注册状态，逐位置证据关联全部控制、私有真值和完整共同状态。

最终包替代 preview 的版本；相同 record_id 不重复拼接。初态身份链接只用于切分，不认证旧请求/前缀兼容。新捕获没有规则 annotation 的位置明确保持 source_rule_result=unknown，没有复制 M7 规则集合。
