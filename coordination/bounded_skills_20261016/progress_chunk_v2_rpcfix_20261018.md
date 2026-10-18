Codex1/Codex2：v2 chunk 启动错误已定位并修复。本轮只开发与仿真，不训练。

8284_24 在 71 秒后 exit 1，尚未产生物理请求。原错误：`TypeError: Pickling an AuthenticationString object is disallowed for security reasons`。调用链为 `probe_bounded_feasibility:episode -> BoundedOracle.choose -> copy.deepcopy(self.binding)`；绑定器持有真实 RPC，深拷贝进入 RPC 进程对象。原日志与 startup_error 完整保留在 `/public/home/sunyihan/rpent_libero_eval/results/slurm-8284_24.log`、`results/bounded_skills/feasibility_20261017/job8284_24/episodes.jsonl`，没有把它计作技能失败。

修复：绑定字典和 peer 集合独立复制，RPC 对象保持原身份。oracle 主前缀和可接受集合枚举两处均已修正。新增带真实 `multiprocessing.process.AuthenticationString` 的 CPU 回归，核对 K4、原绑定不被改写及 peer 集合隔离。chunk 测试 7 passed；Ruff 致命错误检查、diff check 通过。

源码：harness-v5 `b1a6fd1e4dd038856d5628bbb41b36d5450e3ae3`，已推送 user-fork/harness-v5。新快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v2_rpcfix_20261018_b1a6fd1`。归档 SHA256 `b6cc9f068709afc45b2436fbc17759c485238d04d8b581509315b797ea81c4a5`。

schema 仍为 bounded-skills/2，SHA256 `2af1ac62f759f540c5d96a0f1c6328982f414c0c2b560e80ea98a430a2ef601c`，规格 SHA256 `90633f58a6fa6f57c07485e5e4a11d08c4bb40e9a0b6d6b1b282e1ca326d6c5f`。入口 `robots.libero.bounded_skills:MeasuredSkillAdapter.request/prefix_context/execute`；仿真入口 `scripts.probe_bounded_feasibility:episode`；解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

220 个原版状态重新通过 CPU 预检，case、BDDL、state SHA、预算、永久排除登记未变。新 manifest：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/preparation/original20_manifest_chunk_v2_rpcfix_20261018.json`，SHA256 `e8d39ddaf55423b22d5c18c70a1fd3e2489eea5f342a3a121fda9ffa3f746cc2`。

同快照、同 launcher 新启动 `8288_24` 已提交，依赖正在运行的 8173_33 自然结束。正式数组尚未提交，必须先有 first_physical_request、正常启动退出。启动通过后优先使用三个通道做新/旧截断配对，旧版普通 pending 顺延，运行任务不取消，held 不动。只 node02、Nice500，本项目合计 ≤3，Codex2 8280 使用第4卡。

已补 CPU 汇总：`scripts/summarize_chunk_v2_pairs_20261018.py`（本目录下），按完整同状态双 arm 配对；报告动作实执行数直方图、每技能带后缀尝试的中断率与原因、分层成功率/Wilson、墙钟和步数超限。未闭合的 arm 不冒充配对结果。

平滑指标覆盖检查：新增 `scripts/audit_smooth_joins_20261018.py`，把名义 spline、制动参考重置、相邻运动参考重置分开。已有两局旧版记录（8173_32、8192_109）19 段运动、14 个同测量端点的运动衔接，其平移参考加速度跳变最大 0.0851207468299001 m/s²；旧记录未存名义 extrema，且这两局没有制动，不能据此声称全链 C2/jerk 达标。v2 名义指标本身也不覆盖所有制动/跨技能衔接；待 v2 物理记录后继续核对。未调速度、加速度、jerk、力或预算。

Codex2 接口核对：MODEL_IO_SPEC 已写入 v2，消费者能加载唯一 schema 和私有 oracle_labels；已查看的 6 行格式报告仍绑定旧 v1，不能当作 v2 实际消费证据。另发现当前 `serialization.validate_request` 限 26 个选项，而旧 LIBERO 真实请求有 22–82 个候选（8173_32: 11 次决策；8192_109: 10 次决策）。请在模型接入前协调公开候选容量，不能按 oracle 答案删候选。新 v2 请求出来后会交精确分母与真实消费检查；本轮不直接改 Codex2 仓库。

确认状态永久排除训练；历史旧规则、启动失败、开发失败均保留。当前仍在 oracle 上限阶段，尚未启动后续对照、K1/K4 平滑配对或分叉。
