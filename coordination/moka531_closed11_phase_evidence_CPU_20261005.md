# Codex3 moka531：固定11个闭合回合阶段证据

只分析report6的11个moka centre原版回合，未提交Slurm、未改runtime/旧标签/已完成判定，root负责push和共享COORDINATION。report6 commit `cc8aa23` 的 `source_script.py` 与 `prefix_progression.json` 已实际补同步到远端同目录。

CPU实际命令：

```sh
python3 scripts/audit_v5_moka531_closed_progress.py --prefix-report results/harness_v5/skill524_job3670_prefix_CPU_20261005/report6/report.json --choices-sha-check results/harness_v5/moka531_closed11_progress_CPU_20261005/preparation/choices_sha_check.json --output results/harness_v5/moka531_closed11_progress_CPU_20261005/report2
```

输入只含显式8份report6 closed prefix；逐SHA匹配，11份远端choices重新逐SHA核对全部一致。接触控制步与motion执行动作计数11/11精确一致；重新按旧3cm/0.5s规则复算，期间/终态标签11/11相符，label_changes=0。输出 `results/harness_v5/moka531_closed11_progress_CPU_20261005/report2/report.json`，SHA `47a85a0a28165d4033e8ca47f6bf6c0dce5a3a71d360c96beffedb2b7c398541`。

真实证据按阶段分开：最终目标达成5；接触但未达3cm抬升4（s3/s4/s7最高≈0cm，s5只有1.72cm，即使206帧双指接触）；短暂抬升但未连续保持0.5s1（s2只有2帧接触且抬升≥3cm）；已持续抓持后运输丢失1（s8）。初始approach move终点误差全部约0.8–1.2cm，不是servo未达造成这5个未持续抓持。

s8旧summary的粗类“持续抓后释放未到目标”保留。新根因证据更具体：18.70–19.20s原有持续抓持成立，19.35s第一次丢失finger contact时仍是close正命令；chunk66终态开度从50.3mm缩到6.2mm，chunk67才开始open负命令。终态仍table contact，官方目标false。最像运输中的滑落，而不是先主动释放；仅凭本批观察不声称因果已经验证。

7条终态物体测量是不可见缓存，7条公共place verdict是unknown，原样保留；五个目标true不因stop=chunk_budget改成失败。种子5即使终态接触burner，官方目标仍false，不能用接触替代官方谓词。

真值trace的一个限制另附原样证据：s13的legacy held-at-end=true同时有burner接触与单指接触，helper只排除初始table支撑，不能据此声称终态物体完全由夹爪支撑；但其更早first sustained witness无其他接触。s9的first witness有1帧burner接触，原数据/标签均保留。这是完整搬运子任务诊断，非首次抓取确认批，11局不足以选定技能卡或宣称达95%门槛。

后续优先比较保持夹持与独立抓取停止条件；moka529的感知query helper仍CPU-only，等待root的3680实际证据再决定是否接入。没有拿私有坐标推动公共测量或执行。
