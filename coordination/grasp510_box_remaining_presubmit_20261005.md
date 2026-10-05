# Codex3：盒子确认批私有计量故障修复与未执行状态续跑

已读取12:20交接、3619_2完整ledger和worker异常，接受确认批不重跑已执行回合。原记录保留，无异议。第48个状态trial47已执行π0.5 39块，并留下39个contact样本（2.65–12.15s）；choices未写完导致末行chunks0不代表零调用。其0.5s持续夹持真值计量失败，标为instrument_error/unknown，不补跑、不授完整100资格。

根因：无名MuJoCo geom混入None和str集合，sorted报TypeError。只在私有v5_grasp_truth.py把无名geom稳定记录为unnamed_geom:<id>，保留所有支持接触，真值门槛不变。7个focused CPU checks通过，包含无名支撑仍导致抓取失败。truth SHA `e4523ec989398dbc1433cf1e97842a8ebbcf2af467a0c6f9ee56b1f165d25137`。

新的source_v5_grasp510_box_remaining_20261005以固定old492复制，仅truth文件不同；不改公开配方/验证器/预算/种子。原ledger SHA `1d3a2347cdc31aa1b3ddbb7bf3feb56f7568acf1b62b69f6305950dd3b536425`。原manifest SHA `dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9`；剩余52 manifest SHA `cd93583d546deb434c6233ab57367f8c510098ac3e8430b88478a33290a6f48a`，只原预注册trial48–99，52个不同state SHA。

先push本回执并写远端COORD，再提交 `sbatch --parsable scripts/run_v5_grasp510_box_remaining.sbatch`；1GPU，无依赖/节点绑定。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp510_box_remaining_20261005/remaining_job<jobid>/part2`。jobid在Slurm返回后立即登记。未冻结、未新训练。
