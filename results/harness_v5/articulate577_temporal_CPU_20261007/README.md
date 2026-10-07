# 公开RGB-D/本体时序验证器

已实际完成CPU训练，非scalar-only。双视角8×8 RGB/depth/可测mask，动作前帧+最近3帧，末端/夹爪变化；私有joint只在独立标签文件。800样本按rawstate分train3/val2：480/320行；1315显式确认state排除，重合0。

MLP32训练37epoch，最佳7，patience30早停。验证AUROC 0.9220、precision 0.7391、recall 0.6296、Brier 0.0810。只两验证状态，尚未达验证器门槛；不准入stop。未调scalar阈值。缺测标unknown，不补false。

owned补采样入口已实现：before_off、after_release、after_retreat每相位3帧；后两相位以6个零位移保持controls隔开（0.3s），每状态新增24controls，总120。前三阶段的原始标签不改，另存序列最后帧的后置私有标签；没有用标签控制采样。此为新增开发条件，不冒充原literal冻结结果。

源码commit2914f3b。两端3tests全部通过（含推理数值parity）；5片实际/tmp launcher预检全过，不启动GPU。源snapshot和runtime共享文件均未修改。

提交命令（root登记后提交）：

```bash
sbatch --parsable --array=0-4%5 --export=ALL,TEMPORAL577_PACKET=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_temporal_CPU_20261007,TEMPORAL577_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_temporal_CPU_20261007/sampling_manifest.json,TEMPORAL577_MANIFEST_SHA=c10129d51d27c70acc8a83fff1f62237ca240c5e41cf6088b2edf9584300dc4f,TEMPORAL577_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_stove_multiframe_original_20261007 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_temporal_CPU_20261007/run_sampling.sbatch
```

输出与SHA完整列在handoff/packet_manifest。
