# 4128 SOURCE544 完整选择批

1200/1200 完成，8片×150，全部 Slurm COMPLETED 0:0；最后结束 2026-10-06 13:47:09 UTC。执行/开发异常 0。

真实首次接触 786 次，全部 before=false；新增端点 619，保留 0。注册 1200 次 nominal reset，共 450 个不同原始状态。无 first 接触的 414 条绑定/setup 失败保留在全部注册分母中。

| 类型/方法 | 新增/真实接触 | Wilson 95% | TP/FP/FN/TN | unmeasured（真/假） | 全 known 一致率 | 请求/实际控制步 | 短块 case |
|---|---:|---|---|---:|---:|---:|---:|
| drawer_close/current160 | 89/100 | 81.4%–93.7% | 51/1/0/0 | 38/10 | 51/100 (51.0%) | 80000/42700 | 70 |
| drawer_close/vla_subtask160 | 66/100 | 56.3%–74.5% | 0/0/0/0 | 66/34 | 0/100 (0.0%) | 80000/49030 | 55 |
| drawer_open/current160 | 82/100 | 73.3%–88.3% | 0/0/0/0 | 82/18 | 0/100 (0.0%) | 80000/42824 | 69 |
| drawer_open/vla_subtask160 | 0/0 | 未执行 | 0/0/0/0 | 0/0 | 无分母 | 0/0 | 0 |
| microwave_close/current160 | 42/43 | 87.9%–99.6% | 0/0/0/0 | 42/1 | 0/43 (0.0%) | 34400/13870 | 42 |
| microwave_close/vla_subtask160 | 43/43 | 91.8%–100.0% | 0/0/0/0 | 43/0 | 0/43 (0.0%) | 34400/14057 | 43 |
| microwave_open/current160 | 0/0 | 未执行 | 0/0/0/0 | 0/0 | 无分母 | 0/0 | 0 |
| microwave_open/vla_subtask160 | 0/0 | 未执行 | 0/0/0/0 | 0/0 | 无分母 | 0/0 | 0 |
| stove_turn_off/current160 | 46/100 | 36.6%–55.7% | 0/0/0/0 | 46/54 | 0/100 (0.0%) | 80000/29859 | 93 |
| stove_turn_off/vla_subtask160 | 52/100 | 42.3%–61.5% | 49/7/0/38 | 3/3 | 87/100 (87.0%) | 80000/27703 | 99 |
| stove_turn_on/current160 | 99/100 | 94.6%–99.8% | 0/0/0/0 | 99/1 | 0/100 (0.0%) | 80000/40999 | 69 |
| stove_turn_on/vla_subtask160 | 100/100 | 96.3%–100.0% | 99/0/0/0 | 1/0 | 99/100 (99.0%) | 80000/40407 | 70 |

公开验证：TP199、FP8、FN0、TN38；541次unmeasured（420真/121假）。全 known 分母一致 237/786=30.15%；只在 measured 分母的一致 237/245=96.73%，precision199/207=96.14%，measured recall199/199=100%。后两项不能隐藏unmeasured或替代总体一致门槛。

旧短块的公平性限制：请求628800控制步，实际301449；610个case出现executed<requested。motion记录的terminated flag为false，因此实际短块与native latch分列。两arm的实际预算和提示词暴露并不相同；不能从本选择批授予确认资格或冻结行业标准。first前native latch共100（stove_off setup）；原版native成功不代替当前注册端点。

根因：绑定缺失414；已执行但当前端点未到167。新增端点619。不更改旧标签、旧回执或失败。

新出现的stove_on current唯一失败为libero_90 task44 seed23；实际完整执行800步，无native latch，端点false，保留为contact_budget_exhausted_without_endpoint。

产物与SHA：
- manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/preparation/fixtures.json；59cc228e9aa4aa49349009c639f3312e6044a60201f8834b0f223b62ddace387
- source /public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006；commit 2b4b5da
- report.json：cdb013ac1d9e70236db1836b1a39f9b12c453b5e9448cc45c85dda3c0f76c668
- registered_prompt_native_1200_v3.json：8b9d52bfde0555d0af83135942b4090234db0485e709c9e96e1966f732445302
- complete_evidence.json：5df3d029063ceabaa510956c9c1a768852ae14eeaf8695ca9cadd59941897b43
- report.json 内含每个固定ledger显式路径与SHA；副本与原始结果都保留。
