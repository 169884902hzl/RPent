# Codex3 多帧选择补采与 interim 提交前回执

4340全部五片COMPLETED 0:0：原版微波炉注册4/10，Wilson95%16.8%–68.7%；open1/5、close3/5。9/10实际first执行，1局父实体绑定缺失；9执行公共门验证全部unmeasured，无execution_error。14真实VLA调用/2240完整块/11200controls。120个公共RGB-D/cloud文件SHA全匹配。正式report `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_monitor_CPU_20261007/job4340/report.json` SHA `79e27763d767472c942108bbf3b9bda861cc701b53fae1f35e26f19470aa8b10`，逐次记录与显式manifest同目录，commit18160e8。未达门槛，不以COMPLETED替代确认。

现场4346是Codex2 v6作业，4GPU占用，剩4GPU。登记本轮预约：Codex3使用剩余4卡，技能577优先（5片1GPU），interim低优先级nice10000（每组8片1GPU）；无节点绑定/依赖，限流4，以后按实时空卡调整。技能批准备好后可在interim回合边界让步，不停同回合物理。

## 多帧公开输入补采577（选择开发，不是确认）

固定4335已访问5原版状态，不挑成绩。补动作前3帧、松手后3帧、撤离后3帧公开RGB-D＋本体；后两段按0.3s间隔。私有真值只后置评分，不作停止条件。source577 commit `2914f3bf3980f395e0d281b85cc1498611d86e4a`，archive SHA `c8fdda53afe6873d6b9c5f29e0f543c4c9bc3d11911fb36057e7f5afa857b247`，packet SHA `fb133e41a88931a99750ff87c7d22e77ba11df08788966389b49c3c493ab33d4`，sampling manifest SHA `c10129d51d27c70acc8a83fff1f62237ca240c5e41cf6088b2edf9584300dc4f`，launcher SHA `7932f3b3614a848ba489d1734de6547d9b0e2788c33ef1e9881da02b40202a1e`；真实/tmp五片CPU预检全0，3隔离/推理parity测试通过。

同4335开发CPU多帧模型已实际训练：3/2 rawstate split，val320帧 precision73.91%、recall62.96%、accuracy90%、AUROC0.922。分母只有2验证状态，未授运行时stop或确认资格。确认states显式排除。

拟提交：

```bash
sbatch --parsable --array=0-4%4 --export=ALL,TEMPORAL577_PACKET=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_temporal_CPU_20261007,TEMPORAL577_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_temporal_CPU_20261007/sampling_manifest.json,TEMPORAL577_MANIFEST_SHA=c10129d51d27c70acc8a83fff1f62237ca240c5e41cf6088b2edf9584300dc4f,TEMPORAL577_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_stove_multiframe_original_20261007 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_temporal_CPU_20261007/run_sampling.sbatch
```

## Interim574：A3-N80与专家200

SOURCE571固定commit `5da67d19fe8dde8564e06c39266bb1fedc330d2a`、archive SHA `41afc849c146eae7db2220960d2057da95c03fba23465b15fa61d0caa7bed718`。显式合并place-v9、五类抓取/独立测量/PAN、dual fusion、失败屏蔽/坚持重试配置；drawer单帧stop_v6关闭，因为同公开值对应相反真值，未用未准入的CPU时序模型。无memory。100decisions/160chunks/10000controls/3072token，源与完整预算逐项写在manifest，属于未冻结联合开发配置，不称全部技能已验证。

模型是同一v5@750，checkpoint SHA `b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb`，每片实际service health核验；A3仅PRO开发旧40＋新41原80，expert只原版40×init0–4共200。官方物理成功作主指标；correct_finish次要。与用户指定46/80、177/200逐局配对。

所有16片已用真实launcher在/tmp、CUDA空集做CPU预检，returncode全0，路径全绝对/逐SHA、原资产trials全通过。CPU预检发现ROOT没有configs、code-only快照没有batch入口；已改用显式注册原manifest和独立逐SHA批量入口，未浪费GPU失败。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/{A3-N,expert}/job<id>/part0..7/probe`。

拟提交两次（COHORT分别A3-N、expert）：

```bash
env INTERIM574_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006 INTERIM574_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/preparation INTERIM574_COHORT=A3-N sbatch --parsable --array=0-7%4 /public/home/sunyihan/rpent_libero_eval/scripts/run_v5_interim574.sbatch
env INTERIM574_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006 INTERIM574_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/preparation INTERIM574_COHORT=expert sbatch --parsable --array=0-7%4 /public/home/sunyihan/rpent_libero_eval/scripts/run_v5_interim574.sbatch
```

提交后立即回填实际job，持续10min检查失败/日志。MAX CPU独立审计进行中，GPU暂不提交，最多2卡且技能优先。摩卡壶76个未重合官方状态/缺24已交用户选择，独立工作照常进行。
