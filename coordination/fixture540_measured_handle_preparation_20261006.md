# fixture540：测量把手第三法与 place400 准备回执

本轮只做 CPU 准备和显式文件预检，没有提交 Slurm，没有物理回合，没有新增训练行。未改旧 3686/3687、旧 manifest 或失败日志。本次四份 manifest 都是选择批；只有未来与选择批不重合的独立确认批才能判技能准入。

## 产物与预检

远端根目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/`。本地按同相对路径同步关键 JSON。

|产物|cases|manifest SHA256|CPU核验文件/初态|
|---|---:|---|---:|
|skill540_articulate_place_selection/preparation/fixtures.json|1200|59cc228e9aa4aa49349009c639f3312e6044a60201f8834b0f223b62ddace387|2426 / 1200|
|skill540_articulate_place_selection/preparation/place.json|400|23e97aeda7ae28c44ba15c74c10d4c80e92f12fd8de49e17b17c37fdb00abe93|826 / 400|
|fixture540_measured_handle_selection/preparation_smoke30/fixtures_measured_handle_selection.json|30|ae6feb7ab1933698fdb8e1fc5a53b949c1bc64a7d026e4fc23542cc6c16010b3|87 / 30|
|fixture540_measured_handle_selection/preparation_selection600/fixtures_measured_handle_selection.json|600|9557d0dbef347e43b33dc38aa3f8c921a5910dda02b028e81eeeeaed39fa6e06|1227 / 600|

预检报告：

- parent fixtures：`skill540_articulate_place_selection/preparation/cpu_preflight_state.json`，SHA `8491bedcb253d78d2b4cc4734bbcbb63b2ea4ee44b10929cf81e63e226189832`。
- place：`skill540_articulate_place_selection/preparation/place_codex3_cpu_preflight_state.json`，SHA `12dfdf8e73e5e8cffb06d15c371c6b512c8f1e44f48314925de2b13022b7181a`。
- smoke30：`fixture540_measured_handle_selection/preparation_smoke30/codex3_cpu_preflight_state.json`，SHA `d33586d755c10b4233b53a73a8908771e542c402c820a51a828a77d7a3416828`。
- selection600：`fixture540_measured_handle_selection/preparation_selection600/codex3_cpu_preflight_state.json`，SHA `12c2d43a90a8e114cc204a5cc0ec16a559d97c197f19c976c90f3dad1a8ae006`。

全部从 `/tmp` 执行，`explicit_files_only=true`、`explicit_cases_only=true`。helper 只查 manifest 中显式资产、tokenizer、预留 manifest/ledger；`--states` 对每 case 核验官方原版初态字节 SHA，不启动物理仿真。后三份 raw stdout/stderr、argv/cwd/env 位于对应报告同目录、同 stem 后缀 `_stdout.log` / `_stderr.log` / `_command.json`。

实际 CPU 命令（对上述四个 manifest 分别执行）：

```bash
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime537_20261006 \
LIBERO_TYPE=standard \
LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config \
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /public/home/sunyihan/rpent_libero_eval/runtime_launchers/v5_probe_preflight.py \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/fixture540_measured_handle_selection/preparation_smoke30/fixtures_measured_handle_selection.json \
  --states
```

## 方法和边界

第三法 `measured_fixture_handle160`：抽屉开/关、微波炉开/关、灶台开/关各5个 smoke、各100个 selection，沿用固定 parent 的前 N 个 current160 状态；新增独立 arm，parent 原两臂不变。当前 `executor=current`、`max_chunks=160`、`contact_approach=measured_fixture_handle`、`contact_standoff_m=0.15`、原版已注册子任务提示、双视角融合开启。只按当前 RGB-D 测量把手/旋钮与正面方向，安全接近、腕部精修后接触执行。缺少唯一可测把手/旋钮时记录 unmeasured，不用仿真几何补齐。

requested joint endpoint 只作私有单技能标签。before/after、already-satisfied、新达终点分别报告；full task solved() 只作上下文，不能替代单技能成功。第三法 runtime 已通过定向 CPU 接口测试，物理成功率尚未验证。

实际原版资产 root 是 `.venv/lib/python3.10/site-packages/liberopro/liberopro/{bddl_files,init_files}`。第一次准备把 expected root 设成 `site-packages/libero` 导致 CPU 失败；已纠正并重跑通过，原失败 command/log 保留在 parent 上级目录。这不是模型成绩。

## launcher 与源码 SHA

- `scripts/prepare_v5_skill535_articulate_place_confirmation.py`：`c3d206563ac6d1d865667475746649931d579fe44c19d1f458192aa277986d17`。
- `scripts/prepare_v5_fixture540_handle_selection.py`：`d3948e9c0491849a3d27c7134456969874b4e0319ff6026cba1256dd3426ec35`。
- `scripts/v5_probe_preflight.py`：`0dbd2334ae6cf849329cdb8dcd3d4c63be762d2754985a58c1b1fb20d4140dcd`。
- `scripts/run_v5_skill535_articulate_confirmation.sbatch`：`2a84b98336f428345fab6086f5eb4f58f103067f152b36011cc470627c32c0a5`。
- `scripts/run_v5_skill535_place_confirmation.sbatch`：`5f0a8b6ad184ade7f38d565bdafeea63d2d36896c125ecfc80914dee1b88022f`。
- `tests/unit_tests/robots/libero/test_v5_skill535_paths.py`：`f6552516423f71ecea8431895dcc2f16559c585dca4e2bfbb8ce36ae004e4701`。

launcher默认 `--array=0-7%8`，1GPU/片，无节点绑定/依赖；并发由主代理按实时空卡登记。尽管历史脚本名含 confirmation，内部强制 cohort=selection 且 qualification_authorized=false，不准将结果当确认资格。两launcher支持 `SKILL535_PREFLIGHT_ONLY=1`，先从绝对路径预检再 cd 到源码 snapshot。

主代理登记的新 snapshot 为 `/public/home/sunyihan/rpent_libero_eval/source_v5_runtime538_20261006`，源码 commit `b5ab18a`（`15a01bb` 加主冒烟 preflight 输出目录修复），包含最新 measured-handle/stove/fixture、helper、grasp/token 修复。登记时本地 probe SHA 为 `c9077711da8f5d69841f8774f50fabbfe5ea1b2d7088273aba85785919ee10f9`；解包后再次对字节核实。snapshot 已解包就绪，archive SHA 为 `e5961ddb4d38295b0de90e7c30cea2e148cae5edb7c7b30d5f313f3fe894c535`。本轮已按真实 launcher 完成全部30片 CPU 预检，结果在下方。旧 source_v5_runtime537 没有 helper，不能直接作 GPU launcher 的源码目录。主代理确认 snapshot ready、通过 launcher CPU 预检与主冒烟3780真实质量检查后才提交后续GPU选择批（不仅检查Slurm退出状态）。作业号由实际 sbatch 返回，不预填。

smoke30（主代理执行；先在 COORDINATION 登记）：

```bash
export SKILL535_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime538_20261006
export SKILL535_PROBE_SHA=c9077711da8f5d69841f8774f50fabbfe5ea1b2d7088273aba85785919ee10f9
export SKILL535_ARTICULATE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/fixture540_measured_handle_selection/preparation_smoke30/fixtures_measured_handle_selection.json
export SKILL535_ARTICULATE_MANIFEST_SHA=ae6feb7ab1933698fdb8e1fc5a53b949c1bc64a7d026e4fc23542cc6c16010b3
export SKILL535_ARTICULATE_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/fixture540_measured_handle_selection/smoke30
export SKILL535_SHARDS=6
SKILL535_PREFLIGHT_ONLY=1 bash "$SKILL535_SOURCE/scripts/run_v5_skill535_articulate_confirmation.sbatch"
sbatch --parsable --array=0-5%6 "$SKILL535_SOURCE/scripts/run_v5_skill535_articulate_confirmation.sbatch"
```

place400（同一个源码身份）：

```bash
export SKILL535_SHARDS=8
export SKILL535_PLACE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/preparation/place.json
export SKILL535_PLACE_MANIFEST_SHA=23e97aeda7ae28c44ba15c74c10d4c80e92f12fd8de49e17b17c37fdb00abe93
export SKILL535_PLACE_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/place400
SKILL535_PREFLIGHT_ONLY=1 bash "$SKILL535_SOURCE/scripts/run_v5_skill535_place_confirmation.sbatch"
sbatch --parsable "$SKILL535_SOURCE/scripts/run_v5_skill535_place_confirmation.sbatch"
```

第三法smoke30按主代理要求覆盖6片（每类5个），array `0-5%6`、`SKILL535_SHARDS=6`。place400/parent fixtures1200/第三法600各8片。新 snapshot 与所有manifest预检通过、真实20请求冒烟通过之后才提交；receipt 写明即将提交输出目录与无依赖，不声称作业已提交。

如主代理决定提交第三法600，另用 selection600 manifest、对应 SHA、`SKILL535_SHARDS=8`、独立输出 `.../fixture540_measured_handle_selection/selection600`；不得覆盖 smoke30，也不能把 smoke 失败删去。

## 已做检查和交付

路径定向测试5 passed；Python compile、bash -n、git diff --check通过；synthetic跨cwd helper核8引用通过。真实远端全量preflight见上表。冻结后容量估算另见 `coordination/collection540_capacity_estimate_20261006.md`（CPU，不授权训练采集）。本回执由主代理纳入 commit/COORDINATION，不由子代理提交。

## b5ab18a 真实 launcher 全分片补验（完成）

从 `/tmp` 以 snapshot 中的原始 bash launcher、`SKILL535_PREFLIGHT_ONLY=1` 运行；第三smoke30用6片，fixtures1200/place400/第三600各8片。30/30片退出0，按stride覆盖全部30/1200/400/600 case；各片分别核87/2426/826/1227个显式引用文件。probe、helper、两launcher在新snapshot里的实际SHA与本回执登记一致。

报告远端：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/launcher_preflight_b5ab18a_20261006/report.json`。本地已按字节镜像；SHA `04e0b53b9459d4a824c41d28604b44210d225257464c8afb65d25e12ae96bb20`。报告列出全部30片；同目录各group/partN的`.command.json`、`.stdout.log`、`.stderr.log`、`.summary.json`保留实际命令、环境、耗时和结果。不覆盖任何manifest或先前preflight报告。

仅CPU预检：0物理调用、0训练行、0作业提交。初态SHA全量核验仍由本回执第一节的`--states`报告提供，本次launcher预检不会重复物理执行。后续第三法/放置等GPU选择批仍须等待主冒烟3780实际质量通过，不仅凭COMPLETED。
