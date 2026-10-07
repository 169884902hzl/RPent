# Codex3 启动修复后继续执行

4355八片和4356前四片退出0但episode都是startup_error，原因是SOURCE571精简快照未含运行时延迟导入typed_choice_eval；没有进入单局初始化/物理，不能报模型0分。原记录保留。发现后已hold未启动4356分片，补用固定5da67d19版本的typed_choice_eval，独立文件SHA登记到interim manifest.runtime_supplement，SOURCE571本体不改。真实/tmp launcher新增运行时所有前置imports后再次通过首片，资产已全16片核过。随后恢复4356未运行的part4–7；part0–3另建修复attempt，完整200以首次有效物理记录合并。A3先提交修复part0（10局），确认实际物理请求后立即补part1–7，不等待整片结束。

实际待执行：

```bash
scontrol release 4356
env INTERIM574_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006 INTERIM574_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/preparation INTERIM574_COHORT=A3-N sbatch --parsable --array=0%1 /public/home/sunyihan/rpent_libero_eval/scripts/run_v5_interim574.sbatch
```

摩卡壶4357仍全部held、0物理：确认发现SOURCE571原生成功会截块，client.complete_skill不能改变server chunk语义。owned server已改用SOURCE571既有complete_probe_chunk，完整5control且不改私有goal标签或SOURCE。新manifest SHA `1ada085776124842f00ce86d2bf4788a4c2cd9f639e467dcd235523894af4773`，8片真实CPU预检再次全0，准备commitcb375dc。4357在Slurm spool固定的旧export SHA不能匹配新manifest，取消这一零执行开发计划后用新SHA提交，不保留一个必定拒绝的旧计划。旧SHA/旧代码在f7519a4及前预回执保留。

```bash
scancel 4357
sbatch --parsable --array=0-7%4 --export=ALL,MOKA_TRANSFER_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006,MOKA_TRANSFER_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/moka_original_public_placement_visited10.json,MOKA_TRANSFER_MANIFEST_SHA=1ada085776124842f00ce86d2bf4788a4c2cd9f639e467dcd235523894af4773 /public/home/sunyihan/rpent_libero_eval/scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch
```

4349补多帧全部五片COMPLETED0:0，逐次物理/时序输入汇总中。当前4346用4卡，剩4卡空闲；技能nice1000高于interim nice10000，不绑定节点，不绕依赖，不触旧held链。

成功率真值的新采集已实现原版专用passive sidecar：选动作和执行前预测照原接口，后台按每个实际control采真实接触/支撑证据，并在动作后评分唯一原版谓词；仿真量只写private_action_labels.jsonl，不返回动作选择/状态/回执，不额外执行物理control。三项隔离/歧义/错误部件测试通过，真实CPU imports/asset预检首片通过；20原版开发局全4任务族，未知绑定/无定义动作保留但从AUROC分母排除。尚无新真值物理结果，不把旧0.772冒称新真值AUROC。
