# 放置公开身份与执行证据交接 r1

本交接补充旧 CPU handoff，保留其内容及所有原判定。4555 已实际走过显式开启 `fixture_fragment_alias_v1` 的运行时场景路径；此开关全局默认仍为 false，strict6 阈值未改。相关结果是复用原版开发状态的诊断证据，不能授予独立确认批的技能或验证器资格。

## 4555：场景 owner 的实际运行路径

源码 commit：`a5e7aeae9829a6626be138f5695a8e91b33b5044`。
不可变源码：`/public/home/sunyihan/rpent_libero_eval/source_v5_place_runtime_identity_r1_20261008`。
archive SHA256：`395859fe3394f3984c348980fe77597a8ce0a84deb672ec92ef169b01adc3df6`。
解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。
入口：`coordination/drawer_public_identity_hold_CPU_20261008/probe_place_runtime_identity.py`，经 `original_placement_trace(observe_runtime_only=True)` 调原版 probe；观察器不额外 capture、query、cleanup 或发 controls。

父代理提交的作业 4555 为 `COMPLETED 0:0`，输出：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_runtime_identity_dev_20261008/case0/job4555`。
目标动作 `vla_subtask(e15,e12,on)`，160 个完整的 5 步动作块，共 800 个实际环境 controls；motion trace 与 snapshot counter 差值均为 800。私有完成标签 false→true，公开 strict6=true，基础设施失败=false，墙钟 127.344314 秒。

目标动作前可见 cabinet 唯一为 e12、已测 cabinet top 唯一为 e104。16 个公开 frame 全部确认 `runtime_identity_path_only=true`、`extra_capture_query_intervention=false`；475 个显式源码文件逐项 SHA 核对通过。这是运行时接线的物理验证，不是仅靠离线别名清理证明。

执行审计：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_runtime_identity_r1/actual_job4555_execution_audit.json`。
SHA256：`d03f41865f042607aa6832b2923e99e1f79982aedb78587850de35ca6fa2e6ac`。
实际提交回执 SHA256：`e2173913d192c0414fd87032888927f155630d4c58f8d143e6a3768ab8fc2182`。

## 七个 r2 单局：执行与原验证器复算

4541–4547 均完成并实际执行目标，私有 before=false→after=true，基础设施失败 0。总物理完成为 7/7，Wilson95 区间 [0.645669565, 1]；公开回执 true=2、false=4、null=1。184 个公开 frame、2031 个公开文件引用已逐项核 SHA；没有私有物体几何参与公开复算。

| 作业 | 条件 | 实际目标 controls | 公开验证 | 私有完成 |
|---|---|---:|---|---|
|4541|vla_subtask160|800|true|true|
|4542|vla_subtask160|880（800 VLA + 80 retreat）|null|true|
|4543|current160|178|false|true|
|4544|vla_subtask160|800|true|true|
|4545|current160|190|false|true|
|4546|current160|182|false|true|
|4547|current160|189|false|true|

current 臂原 motion_evidence 漏记 gripper controls，只记 143/156/148/155；此表依据两个 snapshot 的 `counters._elapsed_steps[0]` 差值补齐账目，原记录不覆盖。snapshot counter 只用于步数记账，不读取真值几何。

4542 两帧物体均 invisible，缺新鲜双帧证据，null 复算一致。观察 retreat 执行 80 controls 仍距目标 0.2452m，回执为 `observation_retreat_not_reached`。drawer 测量从水平底部抽屉变为柜体前面，保留该测量异常和 null，不改判。

4543/4545/4546/4547 的唯一失败 gate 均是 measured bbox footprint 未达原登记 0.90，覆盖率依次为 0.7627965/0.7447336/0.7268232/0.6741294；其他基础视觉 gate 与 ≤1cm 支撑间隙通过。四局 carry held-offset 的最大公开 XY 差为 0.009223/0.009581/0.011489/0.009573m，末次 carry 到落定公开 XY 位移为 0.099239/0.077630/0.086578/0.079660m。现有证据不能区分真实滑移与测量变化；不能把根因写成巨大 carry-offset 漂移。

复算使用原 `strict_place_verified_v6`，阈值、公开回执和私有标签均未更改。本批只有正例，不能据此放宽阈值或声称 precision 达标。

根因报告：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/remaining7_launcher_preflight/public_verifier_root_causes_v1.json`。
SHA256：`730961c10f4cefec7d715ef32fe8cc24ddfa37628b8694b058e069ce0eb84f18`。
完整 controls 审计 SHA256：`b473c612a82738473066d67add910106068a61c18b00aa242a4026dc8c0c0ca6`。

## 边界与交付

完整显式路径与 SHA 见同目录 `PLACE_EXECUTION_ARTIFACTS_r1_20261008.json`。旧七局 source commit 为 `0eff8550d2c9cb73f778423d5945c1562c62898d`，与 4555 的运行时修复源码分开记录；二者的观察方式不合并。子代理没有新增 GPU 作业，没有训练行；所有已访问状态仍不入训练。确认排除表的 coverage_complete 不在此交接中改变。
