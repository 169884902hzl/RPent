# place4311 独立原版单局 CPU 就绪包

源码 commit：`9b6e9b79a80da246d123b7dacaed6e2d2153d4df`（钩子初始提交 `d39dce8`）。

源码快照：`/public/home/sunyihan/rpent_libero_eval/source_v5_place4311_public_trace_r1_20261008`。
解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`（Python 3.10.19）。
入口：`coordination/drawer_public_identity_hold_CPU_20261008/probe_place_trace.py`；上下文 `robots.libero.v5_place_public_trace.original_placement_trace()` 调用原 `scripts.probe_v5_skill501_original.main()`。

源码 archive：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation/source_code.tar`；SHA `0e78ef37fa150d2d762316752cea0cb06cc9e1039fb6da58c77cff5eb09b38c3`。462 个显式文件来自上述固定提交，不读取 artifacts 目录生成源码。

8 个单局请求、6 个 distinct 原版初始状态，全部沿用已访问 selection 的 setup、deterministic reset、原版 subtask 和 160-block 预算。case0 对应第三个绑定失败；case1–7 对应原 7 个 footprint FN 请求。禁止作为确认/训练或修改原 4311 分数。

manifest index：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation/registered/manifest_index.json`；SHA `fccbff2d796e1b8fb2903bd349c7578fb3f709453f68321fb3ea0858d3d79fca`。
永久开发状态排除索引：同目录 `permanent_training_exclusion_registry.json`；SHA `15b51be0c34c211ca17af2bbd3d501a50cbd0e668db23336605bb51d75f752c6`（8 请求条目，6 distinct 状态，不宣称全项目排除清单齐全）。

CPU：25 个相关 tests 通过；launcher `bash -n` 通过。同一 launcher 的 `PLACE_TRACE_PREFLIGHT_ONLY=1` 从 `/tmp` 运行，8/8 manifest + 官方状态 SHA 校验通过。报告：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation/preflight_r1/report.json`；SHA `0f955f62f23e9ba56e1244106d92fb75a65dee2a8fbc1465a83d8c431eb3f6d9`。

新增证据：actual SAM masks refs；per-camera segmented clouds；fused cloud；EEF XYZ/body quaternion；held offset；双相机当前 RGB-D 与 source_step；既有 carry move_to 前后公开测量。公开 JSON 不读物体仿真坐标，私有 truth 仍由原 worker 仅作标签。

额外 drawer query 与 carry 后 capture 可以改变后续测量/绑定/回执。这是开发观察干预，非旧轨迹精确重放；没有新增 robot controls、修改 held offset 或放宽阈值，状态/候选的字段格式未扩展。将实际证据保存为 State 注册的 session-level `place_trace_index.jsonl`，分析仅读此显式索引。

优先单局 manifest：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation/registered/case0_vla_subtask160_t25_s2.json`；SHA `11161664c58f354bcc4106cb746956d1fd141d17b601c185d7ce7c869fc3afcd`。

仅由 root 完成 COORDINATION 预回执、预约与提交。准备好的实际提交命令：

```bash
env PLACE_TRACE_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_place4311_public_trace_r1_20261008 PLACE_TRACE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation/registered/case0_vla_subtask160_t25_s2.json PLACE_TRACE_MANIFEST_SHA=11161664c58f354bcc4106cb746956d1fd141d17b601c185d7ce7c869fc3afcd PLACE_TRACE_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case0 sbatch --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_place4311_public_trace_r1_20261008/coordination/drawer_public_identity_hold_CPU_20261008/run_place_trace.sbatch
```

CPU 命令使用同一环境，加 `PLACE_TRACE_PREFLIGHT_ONLY=1` 并把 `sbatch --parsable` 换为 `bash`。本子任务新 GPU job 数为 0；真实执行和证据质量尚未验证。
