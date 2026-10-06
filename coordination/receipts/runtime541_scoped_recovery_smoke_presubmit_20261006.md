# Codex3：runtime541 局部恢复门物理验证预回执

3734全部结束：官方成功15/20（原版9/10、开发6/10）、4预算耗尽、1over_token，0execution_error，失败原样保存。3780继续原生运行，不修改其snapshot。源码537的恢复门与2312d6f一致，没有blocked membership/过滤bug；根因是无关实体的感知重测跳变释放失败动作。goal_swap的step34无关实体变化3–36cm释放4个失败grasp/restage，step42无关边界变化36.7cm再次释放4个。

已修复：按失败动作自身object/target/所属测量部件的变化解锁，内部保存失败动作after参考，避免该动作自己的失败位移在下一次reperceive又解锁；控制恢复动作仍按全局场景门。execution_error失败类型明确保留。无新状态行/字段，恢复数值语义变化已在此通知Codex1/Codex2。90 focused tests通过。历史transition replay显示重点step34释放4→0，step42释放4→仅reperceive，拒绝旧轨迹10个失败grasp；这是CPU证据，尚非新物理结果。

源码commit241776a；snapshot /public/home/sunyihan/rpent_libero_eval/source_v5_runtime541_20261006；source archive SHA91f1e2ab9b810e6c6b12b7372ea2bd72d0b4c4e8bd03fbea28e79bfea4f2368a，本地/远端一致。3072硬上限和紧凑等价回执保持。全部8片CPU资产/路径预检通过。

仍为同一20局（原版10+开发10），只将受影响的原版spatial t2 init0与开发goal_swap t0 init41排到part0首局，先检查修复，同时完成全20局质量冒烟；不另重复提交两个相同物理suffix。manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime541_smoke20_20261006/preparation/manifest.json SHA92e7ab9b60d474234dd32e9bf728b0be5cfed75702724e728f2ece98cf62f317。v5@750权重和已登记预算不变，不授予冻结或训练资格。

GPU预约：当前两个其他owner服务各1GPU、3780尚4片运行，共6卡；本数组0-7%2，先使用2空卡，不绑定节点/无依赖。资源释放后按实时空卡提高并发，不动其他owner。Slurm分配job号后立即回填；输出固定 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7。

实际计划命令：SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime541_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime541_smoke20_20261006/preparation sbatch --array=0-7%2 --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime541_20261006/scripts/run_v5_runtime536_smoke20.sbatch。

新冒烟真正质量通过后才能进入开合/放置/抓取技能批次。原先指向3722或3780的外层待执行条件由本次最终实际smoke质量依赖替代，旧manifest字节不改。技能manifest和确认状态CPU排重结果继续保留。
