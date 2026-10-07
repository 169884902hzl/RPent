# 显式注册的确认状态身份：覆盖不完整

只按6份固定路径、SHA及明确 confirmation cohort 的注册plan提取，没有读取运行成绩选择状态、没有扫 artifacts 目录。主registry共有831个注册case rows、665个distinct episode/state SHA。重复状态保持全部registration refs；未执行但已正式注册的确认状态同样永久训练排除。

远端目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation/confirmation_registry_r1/`。

- `official_confirmation_exclusions.json`：schema `libero_official_confirmation_exclusions/1`，SHA `7c4aaf7a8e3d916b9552bf7fa86189a5aa8034c106e24fb749c215c4d89a908d`。665条records均有episode、state_sha256、permanent_training_exclusion=true和registration_refs；training_allowed=false、coverage_complete=false。
- `ambiguous_training_hold_identities.json`：schema `libero_ambiguous_registration_training_hold/1`，SHA `9072494f5a6b79b1a562826fb41664e9f9bd309e3ad6b916177424346d59c85b`。两个旧skill535 fixtures/place清单1200/400 requests，共650distinct identities。用户10/06称其选择批，与旧manifest的confirmation字符串冲突。它们不进主确认registry、不标永久确认排除；future training_allowed=false，待Codex1按协议元数据、不看成绩澄清。
- `report.json`：SHA `c0937e9a324b8a0535924b84f7bab444ab969768a2185313cfde14c5cb67db8d`。每份source的路径、SHA、cohort、rows/distinct及gap逐项记录。

主registry六来源：grasp492 first4(400)、grasp512 resume(79)、grasp510 remaining box(52)、grasp535 frypan(100)、grasp535 moka(100)、pan559 registered resets(100 rows/99 distinct)。源plan SHA逐项在report和producer中写死。父registry消费端由root实现；本子任务不修改共享 `v5_confirmation_exclusions.py`。

已验证本地产物hash与远端相同、schema、唯一身份数、所有permanent字段与refs、临时hold650且permanent=false。没有读取confirmation物理结果或改变旧判定。

缺口：此pass未定位grasp495/497等全部历史确认注册；不能声称全历史覆盖。skill544 pool_only/not_reserved不加入，layout union100的base tuple不自动列为确认；place4311的6个已访问诊断状态另有独立永久开发排除清单，不改称确认。

实际CPU命令：

```bash
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation/prepare_known_confirmation_exclusions.py \
 --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation/confirmation_registry_r1
```
