# Codex3 stove556 公共图像裁剪SAM复查预回执

接受用户10/06全部条款，无异议。4210完整10/10、80双视角capture；主control0/80、腕4/80，directed lever/reference/angle0/80，未达测量前提。公共图像显示细部在炉体粗SAM框之外；先固定50%上下文ROI，保留原两query（stove knob/stove switch handle）和0.2阈值，比较full/crop。12原版保存视角×2profile×2query=48 SAM调用；不启动仿真、不打开私有标签，不冒充新的物理成功或端点确认。

SOURCE555 b07c707，producer e7fcbaf；manifest SHA 122de1d0048033c2334044f849e61738384f0c98970e801cfd80be74aa226069，三producer逐SHA固定。/tmp同入口CPU预检通过12/12原XYZ映射，preflight SHA b42f3d5d6eeb0ae38b48ee3cdeca90749844786409380ce223c31452b828cb52。crop mask还原原pixel后用原world cloud，内外参坐标合同不变。

1GPU、无依赖/节点绑定，与4235并行；作业号推送后由Slurm分配立即登记。输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove556_crop_SAM_original_20261006/crop_job<JOB>。实际拟命令：

```bash
env STOVE_CROP_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006/offline_crop_sam_manifest.json STOVE_CROP_MANIFEST_SHA=122de1d0048033c2334044f849e61738384f0c98970e801cfd80be74aa226069 STOVE_CROP_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove556_crop_SAM_original_20261006 sbatch --parsable --export=ALL /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006/run_offline_crop_sam.sbatch
```

关闭端点仍保持unmeasured，不开100格nearzero；查询结果有新证据后再修公共几何。
