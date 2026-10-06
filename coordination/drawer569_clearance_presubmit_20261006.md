# Codex3 drawer569 清障与分阶段诊断开发预回执

接受用户10/06条款，无异议。当前4311仍运行，三卡已释放；8片每片1GPU，提交时限流按实时空卡数，后续空卡即提升，不绑节点、不设依赖，不取消旧作业。计划job号由Slurm回传后补写。

20个与4295相同的原版已访问选择状态（open10/close10），不是独立确认。保持原版prompt/reset/setup/max160完整5controls、depth-v5、signed公共stop-v6阈值不变。新增真实40步release、实际开度≥.075m后沿公共测得front_axis水平清障8cm，再可恢复退避；WaypointNotReached不能抹掉已完成接触。新frontmost-v7保持off：额外宽度门产生新null，尚未纳入物理判定。私有标签每实际块、公共停点、release/clearance/retreat后只评分，不控制；评分故障回合后记infra/unknown，已执行物理不重跑。

SOURCE /public/home/sunyihan/rpent_libero_eval/source_v5_drawer569_20261006；commit 85052d594cf87e0db2e355b405034d758fdcf684；code-only archive SHA256 d09d09923a3b91491c0b18127fbb597411a5786550de8fabb970267bb466b1c2。manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer569_clearance_CPU_20261006/preparation/drawer569_same20_clearance.json；SHA256 9c22dd922751f7117f2a2fab766a1156215d613ad373bf1ed0f605f6a6cc2aa5。真实/tmp launcher8片CPU预检全部0，源码/资产/状态SHA逐引用验证；launcher SHA256 55e3f0fd538f805d500271e9d2a5d5a0716886d95718543d37274b899e1285cc。182相关CPU检查通过，另先前212通过。输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer569_clearance_CPU_20261006/physical_same20/job<JOB>/part0..7。

实际运行命令（并发值按即时空卡数）：

```bash
env DRAWER565_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer569_20261006 DRAWER565_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer569_clearance_CPU_20261006/preparation/drawer569_same20_clearance.json DRAWER565_MANIFEST_SHA=9c22dd922751f7117f2a2fab766a1156215d613ad373bf1ed0f605f6a6cc2aa5 DRAWER565_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer569_clearance_CPU_20261006/physical_same20 sbatch --parsable --job-name=libero-drawer569-clearance --array=0-7%<FREE> /public/home/sunyihan/rpent_libero_eval/source_v5_drawer569_20261006/scripts/run_v5_drawer565_depth_smoke.sbatch
```

报告按20注册分母保留真值、公共TP/FP/FN/TN/null、actualcontrols、公共stop到恢复各阶段真值、真实开度、waypoint与基础设施失败。π0.5 RNG未锁，跨轮差异不作纯因果。不授确认/冻结，0新训练行。
