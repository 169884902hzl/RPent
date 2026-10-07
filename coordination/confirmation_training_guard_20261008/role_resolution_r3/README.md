# 确认登记角色核对 r3

本轮只读哈希固定的登记计划、池、提交命令与 COORDINATION 中具名登记行；不读任何成绩、episode outcome、PRO、密封集或人工指令。0 GPU。只写本目录，不改历史 r1/r2 或 root 守卫源码。

## 结论

1. **旧 skill535 开合 1200 条、放置 400 条就是选择批。** 用户 2026-10-06 第 3 项已明确指定；后续 `skill540_articulate_place_selection` 两份 manifest 的 `cohort=selection`，与旧 535 的 `(suite,task,seed,state_sha256)` 集合逐项相同。450 + 200 = 650 个身份全部解决角色歧义，不需要再请用户或 Codex1 批准。r3 元数据明确 `role_gap_status=resolved`、`temporary_role_hold_effective=false`、`unresolved_role_identities=[]`。旧文件名或旧 confirmation 声明不能继续形成这项 hold。
2. **650 个选择身份与 r2 的 665 个真实确认身份交集为 0。** 取消角色歧义不会误释放这 665 个确认态。独立的开发/诊断/密封范围排除与技能准入条件保持各自原义；本核对不授予训练或技能资格。
3. **本轮没有识别出实际漏登记的官方确认计划。** 六份来源的身份并集与 r2 完全一致；495/497 的具名池与提交命令也没有额外身份。pan559/4246 使用 pan556 的相同 manifest SHA，不是另一份漏登记计划。
4. **全历史清单仍未证全。** r2 producer 的 `coverage_complete=false` 是保守写死的标志，并非已检测出某一漏项的计数。六份计划与 495/497 出处不足以证明全历史穷尽；因此 r3 保留全历史 coverage 尚未证明，不声称存在未发现的确认态，不要求新的角色审批。

## 真实确认来源的覆盖

| 登记 | 登记行数 | 该计划唯一身份 | 相对 r2 遗漏 |
|---|---:|---:|---:|
| grasp492 first4 full | 400 | 400 | 0 |
| grasp512 mug resume | 79 | 79 | 0 |
| grasp510 box remaining52 | 52 | 52 | 0 |
| grasp535 frypan full | 100 | 100 | 0 |
| grasp535 moka_pot full | 100 | 100 | 0 |
| pan556 coupled_lift100（pan559/4246 实际使用） | 100 | 99 | 0 |

合计 831 行，去重并集 665 个身份。495/497 引用的 grasp487 六类候选池有 600 个身份，全部在 r2 内；完整池不因名字自动新增重复登记。

`skill544_confirmation_pools/pool_only_v2/report.json` 已核对 `cohort=candidate_pool`、`pool_only=true`、`not_reserved=true`，不是漏登记确认批。摩卡壶 layout580100–580199 采用独立布局永久排除合同，不能用未扰动的官方 base tuple 代替布局身份；本轮不推定它漏登，也不改变 root 的布局守卫。

## 产物与来源

- 正式报告：`final/report.json`，SHA256 `3171ca113fa1e4ea8aae25f7f633a2b44a9126ff106b595a6a12c926181aacec`。
- 已解决的 650 身份元数据：`final/resolved_selection_role_registry.json`；逐身份明确选择角色与无效的旧临时角色 hold。
- 具名登记行快照：`coord_registration_metadata.json`，SHA256 `b48a688642b682271ebac99cb821a234a1a0450779ea71de9806c790c0ca0f40`。COORD 源路径、读取时 SHA 与行号都在文件内。包括旧 535 命令、后续 540 选择批命令、pan559→pan556 的提交命令及 layout 独立合同。
- r2 registry SHA256 `49273ed0e83a0183393f8771c77131ecf01c4478227878950c637443db035cdf`，保持原样。
- r2 producer SHA256 `d8a87e5c6956de0c319f095fa17316fbf39f60fafb90405d5717018ea7f9d465`；写死 coverage 标志的源码行已记录在正式报告。
- 495/497 provenance SHA256 `8e44862ff451c7d0fb67dcdca64c034c1840f4f33d5095d0f7741a26d30a7968`；它引用的 command/pool 和六份来源路径、SHA 均随报告记录。

远端正式入口：

`/public/home/sunyihan/rpent_libero_eval/coordination/confirmation_training_guard_20261008/role_resolution_r3/final/report.json`

## 恢复命令

本脚本只读登记 metadata，不启动环境或模型。输出目录须新建，避免覆盖已有收据：

```bash
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /public/home/sunyihan/rpent_libero_eval/coordination/confirmation_training_guard_20261008/role_resolution_r3/analyze_role_resolution.py \
  --output /public/home/sunyihan/rpent_libero_eval/coordination/confirmation_training_guard_20261008/role_resolution_r3/recheck_new
```

既有 `analysis/report.json` 是说明补齐前的中间收据，保留不覆盖；交付以 `final/` 为准。root 负责 commit、COORDINATION 与后续 producer/consumer 接入，子代理未暂存或提交。
