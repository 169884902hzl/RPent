# Codex3 skill574 10/07 接管与微波炉预回执

已读取用户10/07 04:26新提示、4335恢复记录、SOURCE571微波炉交接，接受全部条款，无异议。4335全5片COMPLETED0:0，node01已恢复，实时8GPU空闲；补全5局而不重跑。临时基础设施每15分钟复查，恢复即继续，超过2h仍不能恢复才带证据交回。提交后每10min查sacct，开发失败直接修复继续；不nodebind、不重提旧链、不释放旧held。

用户批准摩卡壶按vla_subtask完整原版子句单独作为转移技能，确认与选择不重合≥100，门槛放到位≥90%、验证一致≥95%；拆分抓取60/100保留，剩五类抓取总体另算。开合采用多帧RGBD+本体感知训练小验证器，privatejoint仅标签，确认states永不进训练；不继续单标量调阈值。interim A3-N80和专家200可并行，不作冻结；before预测和sim-truth配对交Codex2。

先提交原版微波炉10选择开发回合，5分片每片1GPU，限流8（最大仅5实际任务），无node/dependency绑定。计划job由Slurm分配立即回填。所有状态/setup/失败保留，不授确认/冻结。

# 微波炉 SOURCE571 公共父实体原10选择批 CPU-ready

尚未提交GPU，root先COORD登记/push再提交。原4178注册open5/close5、同5个唯一raw状态、完整setup和原subtask_prompt/ordering全部保留；无结果筛选，不授确认或冻结资格。

原reject：registered_drawer_instruction不接受microwave类别，因此没有drawer式公共coarse登记；4178主要被contact_probe_controls的measured_fixture_handle预接近拒绝（8 current_handle＋1 wrist_handle），另1个重复父实例。current articulate自身不要求把手；已有双视角measure_fixture_endpoint(parent, microwave door) before/after＋严格门plane判据。

本法联合改变：SOURCE549→SOURCE571；current160＋contact_approach=none；owned monkeypatch只允许唯一当前source_step、visible、name=microwave、无part_of的父实体。完全不调用policy.bind/private object_symbol，不造door、handle或坐标。setup和first公共open/close the microwave句作用域单独登记并恢复；同预算160×完整5controls。公共门plane测不到仍null，strict阈值/私有评分规则保持。原两视角RGB/世界点云/相机外参文件的before/after路径及SHA记录在public_microwave_adapter字段，额外capture/action为0。

CPU：12个单测通过（空/旧/缓存/重复/door-only、模式/文本矛盾、私有bind trap、drawer委派不变）；compile、bash-n、diff通过。24个源码文件实际SHA与固定commit一致，code-only archive已核。真正/tmp launcher cwd=/tmp、CUDA_VISIBLE_DEVICES=""的5片preflight returncode全部0，每片2个原状态SHA已核，0物理运行。

固定身份：
- source `/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006`；commit `5da67d19fe8dde8564e06c39266bb1fedc330d2a`
- source archive SHA `41afc849c146eae7db2220960d2057da95c03fba23465b15fa61d0caa7bed718`
- manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json`；SHA `f9a8b3532b169c0cf93e3d78445e11e96c8beeb343ec36b76ad96c491b9a2296`
- adapter `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/packet/probe_v5_microwave_public571.py`；SHA `fb648b99d3fb3304619fc805a656e77ed3a4912d740b1787626f53c8dc05e599`
- actual launcher `/tmp/run_v5_microwave_public571_original10_20261006.sbatch`；SHA `ec3fc05c4d0c31b4b3090043efaebe2360fba94f2bf3bc2f6af56794bd61cd6f`
- preflight `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/launcher_preflight.json`；SHA `62e7fda52a29a57b8aa5f1fbe795e714f4ebfb15c090e252ad0422998b875a6c`
- output `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/physical_original10/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}`

计划命令（当前root通知6空卡，5片上限5；root提交前再次实查基础设施状态）：

```bash
sbatch --parsable --array=0-4%5 --export=ALL,MICRO571_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006,MICRO571_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json,MICRO571_MANIFEST_SHA=f9a8b3532b169c0cf93e3d78445e11e96c8beeb343ec36b76ad96c491b9a2296,MICRO571_ADAPTER=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/packet/probe_v5_microwave_public571.py,MICRO571_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/physical_original10,MICRO571_PREFLIGHT_ONLY=0 /tmp/run_v5_microwave_public571_original10_20261006.sbatch
```

实际runner：`ROOT/.venv/bin/python -u ADAPTER --manifest MANIFEST --shard-index SLURM_ARRAY_TASK_ID --shards 5 --output OUTPUT`，PYTHONPATH与cwd固定SOURCE571。无ReqNodeList/ExcNodeList/依赖。所有物理失败保留；基础设施错误独立ledger与原probe契约不变。真实GPU运行后要核每例完整请求/实际5控制步、不以已有完成计新完成；注册10、接触真实执行、before/after私有端点、公共测量/null、实体唯一性和两视角覆盖一并报告。
