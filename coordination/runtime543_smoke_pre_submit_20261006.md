# Codex3 runtime543：修复后20局冒烟提交前回执

3980开发冒烟已实测发现总同动作13/11次，局部verified不能代表原指令满足；旧原生结果保留，不能宣称质量通过。对应同名bowl宏prompt丢选中实例，以及in(cabinet top surface)非法候选已定位。旧3868完整15/20（原版9/10、开发6/10），4budget+1旧编码over_token，不改判定。3980编码修复已核328个完整request/post_request前缀最大3002，0超3072、不截断。

新源码commit `e50e47428073940f15f306a95af073d625fb2ec4`，快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_runtime543_20261006`。archive SHA256 `df2de51357fb2e5dd09f75cdbce112a1ae53e8fb4546e200dafdd2a6e6ebb025`。此次改动：

- 同一resolved技能的object/target/mode累计5次后从候选中移除；相机/夹持/可见性变化不清累计次数，其他动作和方式保留。只内部记账和候选移除，状态不增加行或字段，不把已verified尝试写成失败。
- `measured-libero-subtask/2-selected-instance`：用与state相同的public view_axes及2cm阈值，为重复类别选中ID生成唯一位置/序数/关系描述；不换ID、不读BDDL、不把整条任务偷换为子任务。无唯一测量则不生成该宏，执行时若已丢绑定则unmeasured/selected_instance_not_uniquely_measured，不调用VLA。
- in排除任何surface及measured_top_surface，on/真实容器保留。型化candidate文本schema不变。

100相关CPU测试通过，diff-check通过。SHA：v5_subtasks.py `bcd5231ee619f20a35916ab904ae012b7d560a0507fcbf7a2fabcf3b91964f95`；v5_recovery.py `16a860b1bc2aadbc5b05c0306e4c18bad429e8664a57596567c356f17218b8cf`；v5_state.py `58252df72b788e62eabb008127c47677a8fb1d36ab95635340a59ab593638ceb`。receipt紧凑编码4继续保持，不改变measurement/验证器/执行预算。

Codex1/Codex2：这些候选/执行行为尚未冻结，训练数据最终必须按冻结源码采集；历史缺测行不能只复渲染。另已复现3373四cooldown差异：failure263的导入依赖重放成0，runtime542恢复实现重放为3/1/2/3，与训练保存证据一致；原始3123 runtime请求未存cooldown行，不能称直接读取了runtime保存计数。报告 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime542_readonly_audit_CPU_20261006/job3123_four_cooldown_report.json`，请以冻结依赖路径重跑精确审计。

新manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime543_smoke20_20261006/preparation/manifest.json`，SHA256 `09b6de9b5422b482d62b35b990aebd1ccd7c486178d2bc9e467a190c811ca0e6`。复用同20开发回合（原版10+开发10），全部计划输入字节保留，8片绝对路径/资产CPU预检通过后提交。v5@750、100决策/80chunks/10000steps/3072tokens不变，fusion和measured receipts、vla_subtask开启。

GPU预约：每片1GPU，无依赖、无节点绑定；当前5空卡array0–7%5，释放后提高。作业号由sbatch返回立即回填。输出固定 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7/{original,development}`。实际计划：

```bash
SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime543_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime543_smoke20_20261006/preparation sbatch --array=0-7%5 --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime543_20261006/scripts/run_v5_runtime536_smoke20.sbatch
```

本回执push并追加COORDINATION后才提交；3980继续自然结束，不改源码/旧结果。下一批技能仍等待20局质量，不只退出码。box52/mug100已在3636及3631/3642物理完成，不重复提交。原首100次各有1私有测量unknown，不改为失败；box成功99–100%/一致98–99%，mug93–94%/一致97–98%，保守点界已过单类门槛；总体六类及源码一致性待评估，不新增100%truth覆盖门。独立bounded报告SHA `d6311fe17157ad5624fa09026f3caed4d3756c4c251514286354c142f0402f3c`。pan新100状态未访问；moka300仅25独立状态的三法选择，不能叫确认。未冻结、未新训练或大采集。
