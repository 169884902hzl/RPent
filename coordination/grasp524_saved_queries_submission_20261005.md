# Codex3：524同帧双视角SAM查询开发预回执

已读取10/05 12:20感知/融合/抓取计量条款，接受且无异议。当前NO-GO、未冻结、无新训练。3662证明moka主视角step20仍可见但未测，腕视角有查询回退不对称及FOV裁切；历史没有逐query原始mask，不能猜SAM为空或几何拒绝。

本批仅8张已保存原版RGB-D图（step0/20/68/69×agentview/wrist）×3条预登记query，共24请求：silver moka coffee pot .5、silver octagonal coffee maker .35、coffee pot .25。两视角同一梯度；图像/世界点/相机metadata SHA显式登记。只重测SAM、纯CPU复刻可复算几何拒因，无场景/机器人重放，无私有truth请求，不改旧判定、不入训练。

manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp524_missing_points_CPU_20261005/preparation_min8/queries.json` SHAb932876ebced88c224c5772c44b0e7a03b2fc7b31435025b1c2444e1d38eb977。source `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp524_saved_queries_20261005` commit1638f93e05900242acc7d833cf1464171d861fb3，tar SHA6cde380609107883fc2f26e91059ce46de4c0b89f69dd72025af2f39b4314176；runner SHA f93cc4a81f95bc9e16832f4cd7463bda979f1030c7a242c1b118268e1e4af8bc、launcher36a3b1cace7fa02fbf83b61fc61066f41524a10c294aa78570841f374af113fb。

GPU预约1GPU8CPU90GB/2h，无依赖/节点绑定，使用空卡、现有3670/3678/3679不改。先push并append远端COORD、同步独立源核SHA后提交，真实jobid返回即登记。计划实际命令（cwd远端repo）：`GRASP524_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_grasp524_saved_queries_20261005 sbatch --parsable scripts/run_v5_grasp524_saved_queries.sbatch`。

输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp524_missing_points_CPU_20261005/query_job<jobid>`。解释器远端repo `.venv/bin/python`；checkpoint `assets/sam3/sam3.pt`；入口快照 `-m scripts.probe_v5_grasp524_saved_queries --manifest <queries.json> --manifest-sha256 b932... --checkpoint <sam3.pt> --output <dir>`。CPU编译/bash syntax已通过，真实SAM尚未运行。保留所有无mask及几何拒绝，不凭阈值参数宣称感知达标。
