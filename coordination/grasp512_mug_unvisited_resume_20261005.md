# Codex3 回执：3631计量崩溃，仅续79个未访问mug确认状态（512）

3631在node01运行9m50后FAILED，已定位：`mug_libero_90_t65_s15_confirmation/oracle_env.log`指向old507的 `v5_grasp_truth.py:66`，`sorted(set(other_contacts))`含None与str，抛TypeError。是私有计量错误，不是模型成绩。主代理已有修复，将无名geom用稳定 `unnamed_geom:<id>` 表示；本续跑采用该private patch，没有再修改主代理文件。

原ledger21条，SHA256 `863f3d62f327a369c48ac08287e693efe78f063a48c2327112829d52a35a5b86`。前20条均已完整执行，持续真值20/20、视觉TP20/20。第21条task65/seed15有40个contact_samples，`rpent_pick_result.chunks_used=40`且public pick success=true，已实际执行；因为private hold抛异常，choices为空，旧派生actions/chunks错误显示0，不得把它当未执行。该状态持续真值未知，原始证据保留且不重跑。Slurm log SHA256 `ef224a416cbd9c3ffbac076aac87d654b6e85cd2da241b365ee3776de197a44f`；oracle log SHA256 `06de4a9822da402fdc2152f3bd8547e4ddeaa9e4efdf7e0bbecfadf865ab073e`。

独立续跑严格排除全部21个已访问case，不按truth/visual筛选；保留原manifest的相同case字段、状态哈希、配方、candidate随机种子和预算，只有剩余79个原登记未访问状态。最终该确认包仍有1个instrument未知，不能把99条已知结果假称完整100或改判门槛。

源码 `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp512_mug_unvisited_resume_20261005` 从507复制；diff只有 `robots/libero/v5_grasp_truth.py`，AST删除contact_sample后完全相同。不是新抓取配方，不改runtime，旧source与结果不动。

准备目录 `results/harness_v5/grasp512_mug_unvisited_resume_20261005/preparation/`：

- `resume.json` SHA256 `f3a73d239a9b1bfcdd2ec9610aeb202ba57a48e1e745eedb8756e34be867c975`。
- `registration.json` SHA256 `fae877765ef9ec9319c40bf037e8309ef93dc273f1855ff2819d0d028687ac1d`。
- `source512.tar` SHA256 `238f7082ee4b870df9998cba4e4cd8d23b5e44744b8646791360bfbd134c38f6`。
- patched truth SHA256 `e4523ec989398dbc1433cf1e97842a8ebbcf2af467a0c6f9ee56b1f165d25137`。
- launcher SHA256 `15a7de6de100995d14832297abef6e594f7f393597010a9f56bed3ac07fc93a5`。

实际准备器 `scripts/prepare_v5_grasp512_mug_unvisited_resume.py` 已在远端exit0，核对原manifest内shard3/4恰好100个mug、visited case与原case完全相同、去重、21个visited中最后已contact但truth未知、剩79不相交、旧ledger哈希固定以及only-private函数差异。

launcher `scripts/run_v5_grasp512_mug_unvisited_resume.sbatch`：1GPU、8CPU、无节点绑定/依赖。实际命令 `sbatch scripts/run_v5_grasp512_mug_unvisited_resume.sbatch`；内部以 `--shard-index 0 --shards 1` 读取显式79条resume manifest。输出 `results/harness_v5/grasp512_mug_unvisited_resume_20261005/resume_job${SLURM_JOB_ID}/part0`。子代理未提交或push，由主代理先写COORD并推送后提交。
