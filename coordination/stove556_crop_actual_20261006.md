# Codex3 stove556 已提交4240

预回执a8d66b5先推送并写COORDINATION；1GPU，无依赖/节点绑定。12原版保存视角、48同query/阈值full/crop查询，不启动仿真、不读私有标签。SOURCE555 b07c707，producer e7fcbaf，manifest SHA 122de1d0048033c2334044f849e61738384f0c98970e801cfd80be74aa226069。输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove556_crop_SAM_original_20261006/crop_job4240。

实际命令：

```bash
env STOVE_CROP_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006/offline_crop_sam_manifest.json STOVE_CROP_MANIFEST_SHA=122de1d0048033c2334044f849e61738384f0c98970e801cfd80be74aa226069 STOVE_CROP_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove556_crop_SAM_original_20261006 sbatch --parsable --export=ALL /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006/run_offline_crop_sam.sbatch
```

只修测量召回的开发诊断，不把火焰熄灭当官方off端点。确认及原始成绩不改。
