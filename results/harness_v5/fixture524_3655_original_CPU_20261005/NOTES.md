# 3655 原版家具探针：准备污染与独立测量

12 请求全部保留。显式 manifest、3 个 ledger、每个 states.json 引用共核 449 个文件；producer、choices、已签点云引用的 SHA 无差异。未读取 PRO 文件，0 新训练行，未授予确认资格。

|首次动作的真实转移|请求数|
|---|---:|
|新达成 requested 端点|5|
|已有满足保持|2|
|未达 requested 端点|3|
|已有满足被破坏|2|

公共回执 true 3、false 1、unknown 8。已有满足保持不算新完成。report.json SHA256 `fd5839c23af6fb6d74c27f3d9d58e687a200abff719e1fbf88c1411d9e656c4a`。

已定位的原因：

- Long3 bottom drawer 初始已 open；两条 close 请求此前仍用 open setup，setup 把 qpos -0.146 拉回 -0.005/-0.015，open true→false。之后 current close 未达、macro close 达成。应删除这一不必要准备，旧判定保留。
- Long9 microwave 初始已 open；open 两臂 800 controls 后却变成 close，open true→false。两个 close 请求的 open setup 同样把初始打开的门关上，因此测试 close 的 true→true 只是保持，不能计新关闭。
- 当前 generic fixture_parts 把 nonplanar 整机 shell 59,695 点冒充 measured microwave door；独立 vertical_face/measured_microwave_door 均拒绝整机云。去掉该兜底，真正门必须来自独立 SAM door mask 和门面测量，缺测仍 unknown。
- 初始公共 RGB-D 的相邻 panel proposal 存在，但只可给 SAM 点提示，不可视为门/端点证据。没有放宽 frame 几何阈值，也没有用私有 qpos 供运行时补齐。

新的 fixture526 开发对照使用 Goal0/Long3/Long9 init0–2，4 类 × 3 init × 2 arm = 24 请求。close 不做 open setup；microwave open 先做真实 close setup，实际 setup 失败单列并保留。每个边界读取 requested/opposite 两个谓词，仅作标签，不跳过、不路由、不控制重试。

独立诊断服务固定 setup/first <=160×5 controls，保留每步 raw native term，不因原任务成功截断反向技能的每个 chunk；外部 truncation 立即停。shared facade、harness runtime 和正式评测规则不改。每请求都记录真实 controls 与 phase scope。已启用现有独立 door/endpoint geometry 通路。

20 focused CPU tests、Python compile、bash syntax及24请求 manifest validator通过。尚未运行新的物理对照，不以CPU通过冒充技能成绩。确认池须另行预登记并排除按 state SHA 计的全部选择批访问，不能把 catalog 元数据读取当已执行。

实际审计命令（5880）：

```bash
cd /public/home/sunyihan/rpent_libero_eval
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_stove521_control_measurement_20261005 .venv/bin/python scripts/audit_v5_fixture517_3655.py --manifest results/harness_v5/skill517_fixture_measurement_smoke_20261005/preparation/fixtures_smoke.json --job-root results/harness_v5/skill517_fixture_measurement_smoke_20261005/smoke_job3655 --output results/harness_v5/fixture524_3655_original_CPU_20261005/audit
```
