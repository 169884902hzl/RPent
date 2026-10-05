# Codex3 child：3678 类别运行时 smoke 的独立审计入口

新增 `scripts/audit_v5_grasp528_runtime_smoke.py`，不修改 runtime/probe 或旧审计522。仅按 manifest、显式 ledger、case output_dir 和 states.json 的声明读取；闭合 choices 的 SHA 与逐行内容都核对。范围为实际 B/C 类别提示词与160块预算、公共恢复路径、已存同步metadata/point SHA、公共回执与其后0.5秒的私有持续抓取真值复算。unknown、FP、FN分开计数，不把后来的持续抓取真值回填为单帧标签。

3678 未打开 SAM mask 记录，缺mask是证据限制，不能算执行失败，也不宣称具备522的mask重建证据。12例只是运行时集成smoke，不是每类≥100新状态的独立确认批。确认门槛未改，未产生训练行。

静态语法编译通过。真实运行审计尚未做：最近实时查询3678四片仍为Pending(Resources)，3680为Pending(Priority)。无提交、取消或修改作业。

待每个分片的显式 `episodes.jsonl` 出现后，可从 `.venv/bin/python scripts/audit_v5_grasp528_runtime_smoke.py` 运行，传入已登记manifest SHA `2b1097366c0097a71ceead869cc45c4927a524760036560ec1f88132e31ce451`、实际闭合ledger和源码根目录 `source_v5_grasp525_category_runtime_20261005`。必须以实际报告交付，不把本静态准备写成审计通过。
