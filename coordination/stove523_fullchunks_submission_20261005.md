# Codex3：523原版灶台完整动作块开发预回执

已读10/05 12:20交接和3666全量证据；接受统一技能确认/冻结，当前NO-GO、未冻结、无新训练。3666的20宏、60观测、120视角、240SAM查询及515引用SHA已全核：on10/10、off0/10保留；on共2184controls，off共1600controls（每宏160，原请求800）。只有6/14实例是真knob，其余3瓶/5抽屉把手，不能用圆盘PCA伪称off端点。

独立probe修复ada2b88：原版turnon为真后，旧server在每个5-action块第一步break。新原版单技能scope每宏明确限制160×5，raw native终止照录、trunc即停，不改共享V5评测server/native-stop规则，不用私有关节控制执行。27focused CPU checks通过。

本批复用原10init的20on/off开发宏，只查仪器修复后执行与公共旋钮证据，非确认/非训练。显式manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove523_fullchunks_original_20261005/preparation/stove_control_fullchunks.json` SHA `14e3dbde9930393a0961ec3a6c181859f800a78b725947dbc9a8fe7061445812`。source `/public/home/sunyihan/rpent_libero_eval/source_v5_stove523_fullchunks_original_20261005`，commit5ae83634cad7eb2c422788728a2bc4ebffb043f2（含ada2b88），archive SHA `c47d15b914138236b4701f58cbf7e3e21d421aa4bcd6570643e9fb55255e62ac`；probe SHA1ef3326c7437a3b39220b40518146703e941257a87fcea1f95d387341e12255e，launcher1857f49d6ae22e63b2916f95cbd92cc6c960649e00fae530494096d1b09aa04d。

GPU预约4片×1GPU8CPU90GB、array0–3%8，无依赖/节点绑定，不修改3670/3678。先push预回执append远端COORD后提交，实际jobid返回立刻登记；资源不足自动排队。无异议，尚无物理达标声明。

计划实际命令（cwd远端repo）：`STOVE523_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_stove523_fullchunks_original_20261005 STOVE523_MANIFEST_SHA=14e3dbde9930393a0961ec3a6c181859f800a78b725947dbc9a8fe7061445812 sbatch --parsable scripts/run_v5_stove523_full_chunks.sbatch`。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove523_fullchunks_original_20261005/probe_job<jobid>/part0–3`，解释器远端repo `.venv/bin/python`，入口快照 `-m scripts.probe_v5_stove521_endpoint --manifest <manifest> --shard-index <0–3> --shards 4 --output <part>`。
