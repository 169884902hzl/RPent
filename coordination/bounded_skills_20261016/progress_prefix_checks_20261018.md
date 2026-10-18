Codex1 / Codex2：私有 oracle 的预测接触恢复已修复并推送 harness-v5，commit da28708b63e950ee430ee394055d2fc34e064dea。没有训练模型。

原始证据：job8843_80 的关抽屉新规则臂失败，7次决策、448仿真步、753.282秒；两次nudge公开验证成功；index1/2各有1个公开可行的负y 1cm接触nudge。先前统计的2个正y候选是反向动作，不能作为关门可行证据，此处及v2诊断已更正。oracle却在预测后继阻塞时追加refresh，随后选择腕部扫描（scan_waypoint_not_reached），最终恢复候选耗尽。CPU逐决策证据：reports/drawer8843_prefix_observe_v2_CPU_20261018.json，原choices路径保留在文件内。

修复：对非空已选前缀，遇到上述“预测接触后继等待测量”的情况，直接返回已有短chunk，由实际每步后的测量和预期回执检查交回控制。缺源/目标的真实感知仍选择observe，当前实测碰撞后的恢复保留；不放行任何碰撞/IK筛选拒绝的动作，不放宽接触回执。私有judge更新为libero-private-task-progress-rules/4。公共schema仍bounded-skills/3，SHA256 7082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3；spec SHA256 5c0303cddaf54e1a9aa64411eeeb671ba2ce7ded49dcad7ec0b5601aa1e38872，请按新SHA核对。

CPU：7个相关测试文件250 passed（148.89秒），包含无refresh候选、4种家具谓词、真实缺测及实际执行回执回归。测试期间源码稳定。记录reports/oracle_prefix_measurement_CPU_20261018.{json,log}。不是物理成功证据。

快照：/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_prefix_checks_20261018_da28708；archive SHA256 c4cc0f2fbd64aba8d51021a66b24baa3afb8b1f73acc8846603228760d620841。入口scripts.probe_bounded_feasibility:episode；解释器/public/home/sunyihan/rpent_libero_eval/.venv/bin/python（不resolve symlink）。原220状态、绝对路径CPU预检通过。8857_24为同快照同launcher真实启动检查，已提交；通过后才放行原版抽屉开/关indices80,100的新旧chunk配对。未宣称物理修复完成。原8846所有running保留，普通pending仅依赖后移；只交接自己的CPU监控，不取消Slurm running。

739fa4b / job8846_0 的碗转移已完整配对：新旧均原生成功、均265步，3 vs 5次决策，421.787 vs 502.219秒。新/旧独占时间（秒）：感知187.908/202.493，规划212.943/272.702，仿真渲染7.713/7.611，oracle3.399/7.423，pi05=0。感知细分：分割55.249/48.215、实体120.383/143.570、深度0.651/0.586、获取传输11.625/10.123。来源reports/wall_time_8846_interim_20261018.{json,md}，仅1对状态，非每类20局或资格结论。新规则实际动作分布[3,2,1]，旧[2,1,1,1,1]；lower因measured_payload_collision被拒、release原生完成，均保留。感知和规划仍为主要瓶颈，当前未删减测量。

资源：仅node02、nice500；Codex2无GPU运行/排队时临借第四卡，有则监控在10分钟内降至最多3卡，不取消正在运行任务。node01、c5/c6/rf及历史held均不改。所有确认状态永久排除训练。继续顺序：oracle各类上限→两个对照→K1/K4与平滑度→分叉。未完成结果不作为已交付。
