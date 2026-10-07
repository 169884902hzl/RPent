MAX 摸底 160 对已抽定，未运行物理评测。抽样前先在权威 COORDINATION 登记 seed `20261007`、算法与 Lite 源 SHA；没有读取策略成绩。

上游 `a1e3cef258b3e00487db5282aef4e36010aaf401` 的 Lite 800 对源 SHA 为 `0f2b7fc879e91f1ab85156f005adbb708c68966c631603f179f8153f4f2e22f7`。8 类事件各抽 20 对，按原 Lite 70/30 比例每类 Plus14、PRO6，总计112/48。事件排序后，依次处理 Plus/PRO；每池按 case_id 排序，使用同一个 `random.Random(20261007).sample`。所有 case 字段原样保留，不根据结果替换。

登记文件 SHA `ef69e42df227d88eece6353b3b6cc5f6b747e228b97f3185e097f659e2c674dd`；采样器 SHA `156d49c9b321073e88de9fc957a8a18083a470d3fcef154e5b3f2bdf1ba5acdf`。选定清单 SHA：

- selected160.json：`ff8ecaca1bcc0514f86a3604e8a952de9d275dfd938c6f3d1b478ba30037d495`
- plus.json：`ec4eb39e14d0efd9523c9d1e76f24e828f641b98fc285aa38b38d782dd7acfc4`
- pro.json：`1da24a6bbcb0beb6964be53428ff0d3e4a75de2ae7f3b14987e5cf15d2703cae`
- metadata manifest：`f1dde2aae6edae1ff80dd34a3f7ac60302da8c790c22649e3a42d999d42a21cc`

上游 `libero_max.manifest.load_manifest` 已验证完整160及两个112/48分片。原始用例文件只保存在隔离评测产物，不提交到训练代码仓库；提交包含抽样代码、登记和不含任务文本的 case-ID 索引。MAX 用例、文本、事件参数一律不进训练、手册和 memory。

尚未接入 MAX worker/传感器受扰路径、Plus/PRO 独立固定版本环境、逐控制步共同动作前缀、公开缓存恢复或开局相机标定对照。所选 manifest 保留上游 protocol 的 query_interval；真正运行时须为各策略登记实际原生查询频率，不能把上游 X-VLA 的30步当成π0.5的5步。此检查只验证采样和schema，不证明环境或评测可运行。

后续两组使用相同160对：π0.5 单独、当前 harness+v5@750；camera_shift 20对另跑外参开局标定冻结配置。最多2GPU、技能门槛优先。没有提交 MAX GPU 作业；640+40 个回合的 GPU 时间须由真实配对冒烟估计。
