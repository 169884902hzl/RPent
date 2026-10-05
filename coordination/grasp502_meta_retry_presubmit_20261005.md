# Codex3：3619_3零调用基础设施故障修复重试预回执

已读取12:20交接、3619_3日志与原确认manifest。异常为严格env_meta不一致：客户端缺original90_grasp_diagnostic_v1，服务端有true，contact/action调用0。原log与episodes.jsonl保留；不是确认物理失败，不改变原确认配方/种子/停止/验证器/融合配置。

独立补丁source：`/public/home/sunyihan/rpent_libero_eval/source_v5_grasp502_mug_meta_retry_20261005`。与旧source逐文件diff仅robots/libero/v5_env_client.py不同，SHA `556d0ceb8df9b1da98635c04a81b9187eb8a8deeccfc5b30f2d65c2438611f5e`。补齐诊断身份后仍完整严格检查suite/task/seed/预算等参数，不忽略不匹配。相关42项CPU checks通过，真实物理尚待本重试。

registration：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp502_mug_meta_retry_20261005/preparation/retry.json`，SHA `cb1a3c72f016787ad1be08428b1c3520c25c0bc6379c5123eb50e33973cbdf5a`。沿用原manifest SHA `dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9`，只执行shard-index3/shards4，共100个预注册杯子状态。不重复其他3片。

计划命令：`sbatch --parsable scripts/run_v5_grasp502_mug_meta_retry.sbatch`，无依赖、无Req/ExcNodeList，1GPU。新作业号由提交返回后立即写回，不预造号。输出新目录`results/harness_v5/grasp502_mug_meta_retry_20261005/retry_job<jobid>/part3`；原故障路径不覆盖。此处补丁重试仍不自动授整个新统一harness冻结资格。
