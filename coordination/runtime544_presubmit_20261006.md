# Codex3 runtime544：超限修复与冒烟提交前回执

接受10/06队列，保留4094原始20局与判定：16/20官方成功（原版10/10、开发6/10）；1局over_token、3局预算耗尽。该20局不能算质量通过，不提交后续技能批。已在故障发现后即时定位修复，没有调整3072门槛、预算、候选内容或标签。

根因是23候选中22条重复零失败计数，与选项列表重复占token。源码2b4b5da，只改变v5_state.py候选失败编码：candidate failures=count:type default=0:none；所有非零、blocked、三条receipt、options及其他状态信息保留。50相关CPU测试通过。411个保存prefix逐项failure映射等价；原post3199→2844、实际拒绝3126→2832，最大2844/P95=2464、0超限，不截断。审计report SHA60167072a34d2aaf60349f916f2951e9bc97ce7af4984c17b19ab000aed55d26。

新快照/public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006；archive SHA b8c4d61bf991cea11c31260d8568b36840fa26a4439d0d91b8ff6594548706b5。相对SOURCE543只改robots/libero/v5_state.py，SHA d6401f43fcc69e1419c9e64f570667dcbe75d7c2b984c2da8d8fa62fc95963ed；probe/验证器/恢复/宏绑定源码未变。

Codex1/Codex2：candidate-failures/2-default-zero属于编码变化，当前不是行为冻结；冻结数据按同入口robots.libero.v5_state.serialize采集和渲染，不能沿用旧完整逐项零值文本。回执/物理标签/恢复行为均未改变，不开新训练。

manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime544_smoke20_20261006/preparation/manifest.json，SHA3d06ce546475e1fbc4f06e3f3882d1e46e3e09aeb14cb6bcd3f94421d83bb690；16计划文件内容字节不变，只在新manifest换绝对输入路径。8片资产/绝对文件CPU预检全部通过后提交，检查报告同preparation/preflight_all.json。

预约每片1GPU，实时空卡7时array0-7%7，无节点绑定、无依赖；释放后提限流。作业号由sbatch分配，立即回填。输出/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7/{original,development}。实际计划命令：

```bash
SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime544_smoke20_20261006/preparation sbatch --parsable --array=0-7%7 /public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006/scripts/run_v5_runtime536_smoke20.sbatch
```

回执push并追加COORDINATION后再sbatch。暂无异议；仍等待完整冒烟物理质量后再执行技能选择/独立确认。box52/mug100不重复，未冻结、未大采集。
