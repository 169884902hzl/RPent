# Codex3 3670 prefix6 与后续摩卡壶诊断

Owned report6与本回执。root负责push和共享COORDINATION，未提交Slurm、未动runtime/旧任务/标签。

3670 report6实际CPU运行：183/400闭合、choices SHA183一致，报告SHA `e68c05c992ad4c493473fa585eae58a3e14a799f59e03fd3c50ce5eb7bc85667`。八份不可变prefix逐SHA且追加report5；旧162条记录全字段未改，新增21条，源SHA相同，label_changes=0。

moka centre独立rep0 11局：期间持续抓6/11（Wilson95%28.01–78.73）、最终目标5/11（21.27–71.99）、终态仍夹1/11；公共place TP2/TN2/unknown7，私有unknown0。失败类别：未持续抓5、持续抓后释放未达目标1；所有stop=chunk_budget，不抹掉5个已经达成的目标。moka handle尚未闭合，不记失败。

pan centre名义96/100抓、91/100最终目标，rep0独立47/50、44/50；pan handle名义50/72、42/72，rep0独立31/50（48.15–74.14）、27/50（40.40–67.03）。名义重复仅描述、不据探索判资格；unknown单列。所有rep0状态SHA去重计数另附prefix_progression.json。

已有moka529 helper commit `2becf9b` 的CPU-only副本已实际同步：`/public/home/sunyihan/rpent_libero_eval/source_moka529_queries_CPU_20261005`，archive SHA `a2650c9193758da2d78044bcb3825bb3b4a847256dbc15c38306e60eec80516f`、helper SHA `34ab29423fcdb82dbe468861051a820c90b5276f9530946e74e5b72e6d2a4319`。没有接入runtime/提交physical smoke。10项CPU测试通过；capture身份措辞纠正见独立pan527_capture_identity_clarification，旧报告保留。

后续只分析这个闭合prefix内的原版moka公共轨迹与私有阶段标签，分未抓稳/抓后释放未到目标，找共性；不单纯轮询、不重跑已有局、不拿私有坐标驱动公共感知。
