# Codex3 skill544：实际2030试次作业回执

4103完整20质量通过（15/20官方成功，5预算；478全部完整请求≤3072，max2539）。预回执37efcf5与质量回执ed22569均push并追加COORDINATION后，已依次实际提交下述5个GPU数组。每片1GPU、无绑定/无依赖，共享全部8张当前空卡。

SOURCE544源码2b4b5daab664a5d49e17cebcc070e1de0fb3ca3b，archive SHA b8c4d61bf991cea11c31260d8568b36840fa26a4439d0d91b8ff6594548706b5；技能46片launcher CPU已全通过。第三开合smoke为选择，1200与400和moka300都为选择；pan100为独立确认，失败不补分。Box/mug不重复。

|组|作业号|计划试次|输出|
|---|---:|---:|---|
|thirdsmoke30|4117|30|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/fixture540_measured_handle_selection/source544_smoke30/job4117/part<N>`|
|pan100|4123|100|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/pan_runtime544_confirmation/job4123/part<N>`|
|moka300|4126|300|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/moka_runtime544_selection/job4126/part<N>`|
|place400|4127|400|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/source544_place400/job4127/part<N>`|
|fixtures1200|4128|1200|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/source544_fixtures1200/job4128/part<N>`|

## 实际命令（环境参数与SHA完整保留）

### thirdsmoke30 job4117

```bash
env SKILL535_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006 SKILL535_PROBE_SHA=c9077711da8f5d69841f8774f50fabbfe5ea1b2d7088273aba85785919ee10f9 SKILL535_ARTICULATE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/fixture540_measured_handle_selection/preparation_smoke30/fixtures_measured_handle_selection.json SKILL535_ARTICULATE_MANIFEST_SHA=ae6feb7ab1933698fdb8e1fc5a53b949c1bc64a7d026e4fc23542cc6c16010b3 SKILL535_ARTICULATE_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/fixture540_measured_handle_selection/source544_smoke30 SKILL535_SHARDS=6 SKILL535_PREFLIGHT_ONLY=0 sbatch --parsable --array=0-5%6 /public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006/scripts/run_v5_skill535_articulate_confirmation.sbatch
```

### pan100 job4123

```bash
env GRASP_REPAIR_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006 GRASP_REPAIR_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/preparation/pan_wrist_new_states.json GRASP_REPAIR_MANIFEST_SHA=d5091b678e980f73e37157a769c9f85f9846c3cd91dfd93dac26553567e6fb58 GRASP_REPAIR_PROBE_SHA=f6d082336fac5d2c2e1fe1a9823b9427106ecb36aae3f8ce912056bed67f09e8 GRASP_REPAIR_SHARDS=8 GRASP_REPAIR_PREFLIGHT_ONLY=0 GRASP_REPAIR_OUTPUT_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/pan_runtime544_confirmation sbatch --parsable --array=0-7%8 /public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006/scripts/run_v5_grasp_repair_20261006.sbatch
```

### moka300 job4126

```bash
env GRASP_REPAIR_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006 GRASP_REPAIR_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/preparation/moka_methods_selection.json GRASP_REPAIR_MANIFEST_SHA=5f9044d6236128de6900b7b8ed15c0e792db615e117a6affe6be6dfc96061daa GRASP_REPAIR_PROBE_SHA=f6d082336fac5d2c2e1fe1a9823b9427106ecb36aae3f8ce912056bed67f09e8 GRASP_REPAIR_SHARDS=8 GRASP_REPAIR_PREFLIGHT_ONLY=0 GRASP_REPAIR_OUTPUT_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_next_methods_20261006/moka_runtime544_selection sbatch --parsable --array=0-7%8 /public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006/scripts/run_v5_grasp_repair_20261006.sbatch
```

### place400 job4127

```bash
env SKILL535_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006 SKILL535_PROBE_SHA=c9077711da8f5d69841f8774f50fabbfe5ea1b2d7088273aba85785919ee10f9 SKILL535_PLACE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/preparation/place.json SKILL535_PLACE_MANIFEST_SHA=23e97aeda7ae28c44ba15c74c10d4c80e92f12fd8de49e17b17c37fdb00abe93 SKILL535_PLACE_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/source544_place400 SKILL535_SHARDS=8 SKILL535_PREFLIGHT_ONLY=0 sbatch --parsable --array=0-7%8 /public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006/scripts/run_v5_skill535_place_confirmation.sbatch
```

### fixtures1200 job4128

```bash
env SKILL535_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006 SKILL535_PROBE_SHA=c9077711da8f5d69841f8774f50fabbfe5ea1b2d7088273aba85785919ee10f9 SKILL535_ARTICULATE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/preparation/fixtures.json SKILL535_ARTICULATE_MANIFEST_SHA=59cc228e9aa4aa49349009c639f3312e6044a60201f8834b0f223b62ddace387 SKILL535_ARTICULATE_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/source544_fixtures1200 SKILL535_SHARDS=8 SKILL535_PREFLIGHT_ONLY=0 sbatch --parsable --array=0-7%8 /public/home/sunyihan/rpent_libero_eval/source_v5_runtime544_20261006/scripts/run_v5_skill535_articulate_confirmation.sbatch
```

每次sbatch返回后已立即追加作业号/完整命令/输出/规模到远端COORDINATION。当前只完成启动提交，物理逐次结果持续监控；不以COMPLETED代替技能通过。每约10分钟查sacct/squeue，故障立即定位；SOURCE快照不改，修复用新快照和独立输出保留旧attempt。技能全部过门后才集成/冻结/大采集。

